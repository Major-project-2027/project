import os
import cv2
import time
import threading
import numpy as np
import mediapipe as mp
from pathlib import Path

from scipy.spatial import distance
from tensorflow.keras.models import load_model
from ultralytics import YOLO

# Friend's integrated AI components (Phone+Person / Looking-away /
# Sleeping-Drowsiness / Emotion) -- see backend/services/friend_ai/ and
# MODEL_INTEGRATION_PACKAGE/ at the project root. Selectable per-component
# via env vars (AI_OBJECT_DETECTION_MODEL / AI_LOOKING_AWAY_DROWSINESS_SOURCE
# / AI_EMOTION_MODEL_SOURCE, see loader.py); every existing "current"
# code path below is untouched and still fully functional as the fallback.
from services.friend_ai import loader as friend_ai_loader

# The MediaPipe FaceLandmarker (VIDEO mode, monotonic timestamps) and the
# TensorFlow/YOLO models below are single shared instances used by every
# request. None of them are safe to call from multiple threads at once, so
# every actual inference call is serialized through this lock. Per-student
# STATE (blink counters, caches) is scoped separately in ai_state.py and is
# NOT protected by this lock -- only the model calls themselves are.
inference_lock = threading.Lock()


# ============================================================
# MODEL PATHS
# ============================================================
#
# YOLO_MODEL_PATH / LANDMARKER_PATH are relative to the backend/ working
# directory (where uvicorn is launched from) and are correct as-is --
# both files live directly under backend/.
#
# FACE_MODEL_PATH / EMOTION_MODEL_PATH previously used the same
# backend-relative style ("ml_models/...") but those .keras files
# actually live one level up, under student_engagement_system/ml_models/,
# not backend/ml_models/ (which doesn't exist). That mismatch, not a
# missing model, was why face/emotion loading always failed. Resolved
# relative to this file's own location so it no longer depends on
# which directory the process happens to be launched from.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

FACE_MODEL_PATH = str(
    _PROJECT_ROOT / "ml_models" / "face_recognition_model.keras"
)
EMOTION_MODEL_PATH = str(
    _PROJECT_ROOT / "ml_models" / "emotion_recognition" / "emotion_model.keras"
)

# CURRENT_YOLO_MODEL_PATH is this project's own existing production
# weights -- kept exactly as-is, never deleted/overwritten. Which one
# actually loads below is resolved by friend_ai_loader from
# AI_OBJECT_DETECTION_MODEL (default "friend" -- see loader.py's module
# docstring); flip that env var to "current" to go back to this model
# with no code change.
CURRENT_YOLO_MODEL_PATH = "yolov8n.pt"
YOLO_MODEL_PATH, YOLO_MODEL_SOURCE = friend_ai_loader.resolve_object_detection_weights_path(
    CURRENT_YOLO_MODEL_PATH
)
LANDMARKER_PATH = "face_landmarker.task"


# ============================================================
# LOAD MODELS
# ============================================================

print("Loading Face Recognition Model...")

face_model = None
if os.path.exists(FACE_MODEL_PATH):
    try:
        face_model = load_model(FACE_MODEL_PATH)
    except Exception as exc:
        # The file exists but failed to deserialize -- e.g. it was saved
        # with a different Keras version than is installed here. Degrade
        # gracefully rather than let this crash the whole process: face
        # recognition just isn't available, the rest of the pipeline
        # (blink/gaze/head-pose/YOLO/emotion) must keep working.
        print(f"WARNING: Face recognition model failed to load ({exc}). "
              f"Face authentication disabled.")
else:
    print("WARNING: Face recognition model not found. Face authentication disabled.")

print("Loading Emotion Model...")

emotion_model = None
if os.path.exists(EMOTION_MODEL_PATH):
    try:
        emotion_model = load_model(EMOTION_MODEL_PATH)
    except Exception as exc:
        print(f"WARNING: Emotion model failed to load ({exc}). "
              f"Emotion recognition disabled.")
else:
    print("WARNING: Emotion model not found. Emotion recognition disabled.")

print(f"Loading YOLO ({YOLO_MODEL_SOURCE} model: {YOLO_MODEL_PATH})...")
yolo_model = YOLO(YOLO_MODEL_PATH)

print(
    "AI component sources -- "
    f"object_detection={YOLO_MODEL_SOURCE}, "
    f"looking_away_drowsiness={friend_ai_loader.LOOKING_AWAY_DROWSINESS_SOURCE}, "
    f"emotion={friend_ai_loader.EMOTION_SOURCE} "
    "(override via AI_OBJECT_DETECTION_MODEL / "
    "AI_LOOKING_AWAY_DROWSINESS_SOURCE / AI_EMOTION_MODEL_SOURCE)"
)


# ============================================================
# EMOTION LABELS
# ============================================================
# IMPORTANT:
# Keep the same order used when your emotion model was trained.

emotion_labels = [
    "Angry",
    "Disgust",
    "Fear",
    "Happy",
    "Sad",
    "Surprise",
    "Neutral"
]


# ============================================================
# OPENCV FACE DETECTOR
# ============================================================

face_detector = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


# ============================================================
# MEDIAPIPE FACE LANDMARKER
# ============================================================

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

options = FaceLandmarkerOptions(
    base_options=BaseOptions(
        model_asset_path=LANDMARKER_PATH
    ),
    running_mode=VisionRunningMode.VIDEO,
    num_faces=1
)

landmarker = FaceLandmarker.create_from_options(options)


# ============================================================
# EYE LANDMARKS
# ============================================================

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]


# ============================================================
# HEAD POSE LANDMARKS
# ============================================================

NOSE = 1
CHIN = 152
LEFT_EYE_OUTER = 33
RIGHT_EYE_OUTER = 263
LEFT_MOUTH = 61
RIGHT_MOUTH = 291


# ============================================================
# GAZE LANDMARKS
# ============================================================

LEFT_IRIS = [468, 469, 470, 471]
RIGHT_IRIS = [473, 474, 475, 476]


# ============================================================
# BLINK SETTINGS
# ============================================================

EAR_THRESHOLD = 0.25
CONSEC_FRAMES = 1

# How often (in received frames, PER STUDENT) each expensive step runs.
# Blink/head-pose/gaze come from the MediaPipe landmarker, which is cheap
# (~10-30ms) and runs on every frame for responsiveness. YOLO (phone/person
# detection) is heavier and runs every other frame. Face recognition +
# emotion are the heaviest (two TensorFlow model calls) and run least often
# -- neither needs to be instantaneous the way phone detection does.
PROCESS_EVERY_YOLO = 2
PROCESS_EVERY_FACE = 6

# How many consecutive YOLO checks (person_count == 0) must happen before
# "no person" is treated as real rather than a brief camera hiccup/frame
# glitch. At PROCESS_EVERY_YOLO=2 and a ~600ms client send interval, YOLO
# runs roughly every ~1.2s, so a streak of 3 is a ~3.5s grace period --
# long enough to absorb a momentary camera stutter, short enough that an
# actually-empty seat is flagged quickly.
NO_PERSON_CONFIRM_STREAK = 3

# ============================================================
# SLEEPING (temporal, both-eyes-closed) SETTINGS
# ============================================================
# A student is "sleeping" only when BOTH eyes (the same EAR/EAR_THRESHOLD
# measurement blink detection already uses above) stay continuously below
# EAR_THRESHOLD for this many real wall-clock seconds -- timed with
# time.time(), not a frame count, so it is correct regardless of the
# client's actual frame rate. A normal blink (a few hundred ms) or a
# brief MediaPipe landmark miss never reaches this; see
# process_frame()'s sleeping-tracking block for exactly how the streak
# is started/held/reset.
SLEEP_THRESHOLD_SECONDS = 4.0

# Real EAR readings from the actual MediaPipe landmarker are noisy frame to
# frame (confirmed empirically: a real, plainly open-eyes registration photo
# measured ear~0.15-0.18, already below EAR_THRESHOLD=0.25 on its own -- the
# margin between "open" and "closed" is thin). A single stray frame that
# happens to read >= EAR_THRESHOLD in the middle of an otherwise-continuous
# closed-eye episode must NOT be treated as genuine reopening, or the
# eyes_closed_since timer resets to zero and a real 4s+ episode can never
# accumulate enough continuous time to fire. Mirrors the exact same
# debounce idea NO_PERSON_CONFIRM_STREAK already uses above: only treat the
# eyes as genuinely open after this many CONSECUTIVE open readings.
EYES_OPEN_CONFIRM_STREAK = 3

# TEMPORARY diagnostic logging for the sleeping-detection pipeline only --
# prints one line per processed frame with landmark/EAR/timer/sleeping
# state. Defaults ON so the fix above can be verified against a real
# camera; set AI_SLEEP_DEBUG=0 to silence it once verified. Safe to leave
# in (a single guarded print), but intended to be removed/disabled once
# the feature is confirmed working live.
SLEEP_DEBUG = os.environ.get("AI_SLEEP_DEBUG", "1") != "0"

# ============================================================
# LOOKING-AWAY: ACCEPTABLE "LAPTOP SCREEN" VIEWING ZONE + DEBOUNCE
# ============================================================
# A student's head/gaze naturally wanders a little even while genuinely
# looking at their laptop screen. Treating ANY non-dead-center reading as
# "looking away" (the previous behaviour) fired on almost every frame.
#
# Two independent fixes, both reusing values/signals the existing
# gaze/head-pose implementations already expose rather than inventing new
# ones:
#
# 1. DEAD ZONE -- FRIEND_HEAD_POSE_MAP above already treats the friend
#    module's own "slightly_distracted" tier (within
#    HEAD_POSE_SLIGHTLY_DISTRACTED_YAW_DEG/PITCH_DEG = 30/25 degrees of
#    center) as still "Looking Forward". For gaze, the friend module has
#    no equivalent middle tier -- only a single center/off-center
#    threshold (config.GAZE_HORIZONTAL_THRESHOLD/GAZE_VERTICAL_THRESHOLD
#    = 0.18/0.16), meant for DISPLAYING a direction label, not for
#    deciding whether to alert. GAZE_ALERT_*_THRESHOLD below is a second,
#    wider threshold used ONLY for the alert decision -- roughly double
#    the display threshold, mirroring the ~2x ratio between the friend's
#    own "focused" (15 deg) and "looking_away" (30 deg) head-pose bounds
#    -- applied to the SAME continuous gaze_horizontal_ratio/
#    gaze_vertical_ratio values the friend predictor already computes
#    (already EMA-smoothed, see temporal_filter.py), not a fresh guess.
# 2. TEMPORAL DEBOUNCE (hysteresis) -- even outside the dead zone, a
#    single stray frame must not flip the alert. LOOKING_AWAY_CONFIRM_
#    STREAK consecutive outside-zone frames are required before
#    `looking_away` becomes True, and LOOKING_AWAY_CLEAR_STREAK
#    consecutive inside-zone frames are required before it clears again
#    -- the same debounce pattern SLEEP_THRESHOLD_SECONDS/
#    EYES_OPEN_CONFIRM_STREAK already use above for drowsiness. State
#    (away_streak/on_screen_streak/looking_away_confirmed) lives in the
#    caller's per-student `state` dict (ai_state.py), so it persists
#    across frames for that student/session without creating a new
#    predictor or losing state between calls.
GAZE_ALERT_HORIZONTAL_THRESHOLD = 0.36
GAZE_ALERT_VERTICAL_THRESHOLD = 0.32

LOOKING_AWAY_CONFIRM_STREAK = 3
LOOKING_AWAY_CLEAR_STREAK = 3

# ============================================================
# FRIEND LOOKING-AWAY / DROWSINESS OUTPUT MAPPING
# ============================================================
# Maps the friend's GazeHeadPosePredictor output vocabulary (see
# gaze_headpose_pkg/ml/training/gaze_headpose/gaze_estimator.py's
# `_classify_direction` and headpose_estimator.py's `_classify`) onto
# THIS project's own existing gaze/head_pose string vocabulary (see
# calculate_gaze()/calculate_head_pose() above), so calculate_engagement(),
# get_active_alert() (app/routers/monitoring.py), the DB columns, and the
# frontend all keep working completely unchanged regardless of which
# source produced the value -- neither only ever compares for equality
# against "Center"/"Looking Forward", so an unmapped/new label still
# safely counts as "not centered"/"not forward".
FRIEND_GAZE_DIRECTION_MAP = {
    "center": "Center",
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
}
# "slightly_distracted" is the friend's own middle tier (see
# headpose_estimator.py's _classify: within HEAD_POSE_SLIGHTLY_DISTRACTED_
# YAW_DEG/PITCH_DEG of center -- up to 30 deg yaw / 25 deg pitch, well past
# a natural head turn while still reading a laptop screen). It is mapped
# to "Looking Forward" -- i.e. still INSIDE the acceptable laptop-screen
# viewing zone -- rather than "Looking Away", so small/natural head
# movement never counts as looking away. Only "looking_away" (beyond
# those bounds -- the friend module's own definition of clearly outside
# the zone) maps to "Looking Away".
FRIEND_HEAD_POSE_MAP = {
    "focused": "Looking Forward",
    "slightly_distracted": "Looking Forward",
    "looking_away": "Looking Away",
}
# Drowsiness -> the existing boolean `sleeping` field. "fatigued" is a
# real intermediate tier the friend's module reports (see
# drowsiness_detector.py's _SEVERITY_ORDER) but is deliberately NOT
# treated as `sleeping=True` here -- it mirrors this project's own
# SLEEP_THRESHOLD_SECONDS intent (a sustained, high-confidence closed-eye
# episode), not an early/borderline signal.
FRIEND_SLEEPING_DROWSINESS_STATES = {"drowsy", "microsleep"}


# ============================================================
# EAR FUNCTION
# ============================================================

def eye_aspect_ratio(eye):

    A = distance.euclidean(
        eye[1],
        eye[5]
    )

    B = distance.euclidean(
        eye[2],
        eye[4]
    )

    C = distance.euclidean(
        eye[0],
        eye[3]
    )

    ear = (A + B) / (2.0 * C)

    return ear


# ============================================================
# HEAD POSE FUNCTION
# ============================================================

def calculate_head_pose(landmarks, width, height):

    face_2d = []
    face_3d = []

    landmark_ids = [
        NOSE,
        CHIN,
        LEFT_EYE_OUTER,
        RIGHT_EYE_OUTER,
        LEFT_MOUTH,
        RIGHT_MOUTH
    ]

    for idx in landmark_ids:

        x = int(landmarks[idx].x * width)
        y = int(landmarks[idx].y * height)

        face_2d.append([x, y])

        face_3d.append([
            x,
            y,
            landmarks[idx].z
        ])

    face_2d = np.array(
        face_2d,
        dtype=np.float64
    )

    face_3d = np.array(
        face_3d,
        dtype=np.float64
    )

    focal_length = width

    cam_matrix = np.array([
        [focal_length, 0, width / 2],
        [0, focal_length, height / 2],
        [0, 0, 1]
    ])

    dist_matrix = np.zeros(
        (4, 1),
        dtype=np.float64
    )

    success, rot_vec, trans_vec = cv2.solvePnP(
        face_3d,
        face_2d,
        cam_matrix,
        dist_matrix
    )

    if not success:
        return "Looking Forward"

    rmat, _ = cv2.Rodrigues(rot_vec)

    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

    x_angle = angles[0] * 360
    y_angle = angles[1] * 360

    # Widened from the original +/-10 deg to +/-15 deg -- this is the
    # "current" (non-friend) fallback path's own acceptable-viewing-zone
    # bound, matching the friend module's "focused" bound
    # (HEAD_POSE_FOCUSED_YAW_DEG/PITCH_DEG = 15, see config.py) so both
    # sources agree on what counts as "still looking at the screen". Only
    # reached when AI_LOOKING_AWAY_DROWSINESS_SOURCE=current or the
    # friend predictor briefly has no result for a frame (see
    # process_frame's FRIEND LOOKING-AWAY OVERRIDE block).
    if y_angle < -15:
        return "Looking Left"

    elif y_angle > 15:
        return "Looking Right"

    elif x_angle < -15:
        return "Looking Down"

    elif x_angle > 15:
        return "Looking Up"

    return "Looking Forward"


# ============================================================
# GAZE FUNCTION
# ============================================================

def calculate_gaze(landmarks):

    # Use iris center and eye region.
    # This provides a simple center/off-center classification.

    left_iris_x = np.mean(
        [landmarks[i].x for i in LEFT_IRIS]
    )

    right_iris_x = np.mean(
        [landmarks[i].x for i in RIGHT_IRIS]
    )

    iris_x = (
        left_iris_x +
        right_iris_x
    ) / 2.0

    left_eye_x = landmarks[33].x
    right_eye_x = landmarks[263].x

    eye_center = (
        left_eye_x +
        right_eye_x
    ) / 2.0

    difference = iris_x - eye_center

    # Widened from the original +/-0.015 (a fraction of a percent of eye
    # width -- effectively any iris micro-movement) to +/-0.05, still much
    # tighter than the friend module's own 0.18 display threshold since
    # this "current"-path measurement is a raw unnormalized/unsmoothed
    # iris-center difference, not the friend's normalized ratio. Only
    # reached as a fallback -- see calculate_head_pose's comment above.
    if difference < -0.05:
        return "Left"

    elif difference > 0.05:
        return "Right"

    return "Center"


# ============================================================
# YOLO DETECTION
# ============================================================

def detect_objects(frame):

    results = yolo_model(
        frame,
        verbose=False
    )[0]

    person_count = 0
    phone_detected = False

    for box in results.boxes:

        cls = int(box.cls[0])

        label = yolo_model.names[cls]

        if label == "person":

            person_count += 1

        elif label == "cell phone":

            phone_detected = True

    return (
        results,
        person_count,
        phone_detected
    )


# ============================================================
# ENGAGEMENT SCORE
# ============================================================

def calculate_engagement(
    emotion,
    blink_count,
    head_pose,
    gaze,
    phone_detected,
    person_count,
    no_person_confirmed=False,
    sleeping=False,
):

    # No student in frame -- there is nothing to score. gaze/head_pose
    # would otherwise still be reporting their last-known (or default
    # "Center"/"Looking Forward") values, which is exactly why engagement
    # previously stayed pinned at 100 while the seat was empty: those
    # stale/default signals looked perfect. 0 is the formula's own floor
    # (see `max(score, 0)` below) but is never actually reached by any
    # combination of the other penalties (worst case with all of them is
    # 100-30-30-30-10-10=10), so it isn't overloading a meaning that
    # already exists elsewhere -- it uniquely marks "no one to measure."
    if no_person_confirmed:
        return 0

    score = 100

    if phone_detected:
        score -= 30

    if person_count > 1:
        score -= 30

    # Sleeping (both eyes continuously closed for >= SLEEP_THRESHOLD_SECONDS,
    # see process_frame()) is weighted the same as phone/multiple-person --
    # a genuinely disengaged state, not a minor distraction like a brief
    # off-center gaze. This is purely an ADDITIONAL term in the same
    # existing linear-penalty formula; nothing else about how the score is
    # computed changes, and it naturally stops applying the moment
    # `sleeping` next reports False (real per-frame recomputation, no
    # artificial decay/recovery curve -- see process_frame()'s reset logic
    # for exactly when that happens).
    if sleeping:
        score -= 30

    if gaze != "Center":
        score -= 10

    if head_pose != "Looking Forward":
        score -= 10

    return max(score, 0)


# ============================================================
# PROCESS ONE FRAME
# ============================================================

def process_frame(frame, state):
    """Run the AI pipeline on a single frame for ONE student.

    `state` is that student's own per-session dict from ai_state.py --
    mutated in place (blink_counter/blink_total/frame_counter/last_*) so
    the caller's copy stays in sync, and also returned as part of the
    result for convenience.
    """

    if frame is None:
        return None

    height, width = frame.shape[:2]

    state["frame_counter"] += 1
    frame_counter = state["frame_counter"]

    blink_counter = state["blink_counter"]
    blink_total = state["blink_total"]

    # All calls into the shared MediaPipe/YOLO/TensorFlow model instances
    # are serialized -- none of them are safe to call concurrently from
    # multiple request threads.
    with inference_lock:

        # ========================================================
        # YOLO (phone / person count) -- runs most frequently among the
        # heavy steps so a phone held up to the camera is flagged quickly.
        # ========================================================

        if frame_counter % PROCESS_EVERY_YOLO == 0:

            yolo_results, person_count, phone_detected = detect_objects(
                frame
            )

            state["last_person_count"] = person_count
            state["last_phone_detected"] = phone_detected

            # ---------------- No-person streak (debounced) ----------------
            # Only updated on frames where YOLO actually ran, so the streak
            # counts real consecutive observations rather than being
            # inflated by cached-frame reads below.
            if person_count == 0:
                state["no_person_streak"] = state.get("no_person_streak", 0) + 1
            else:
                state["no_person_streak"] = 0

        else:

            person_count = state["last_person_count"]
            phone_detected = state["last_phone_detected"]

        no_person_confirmed = (
            state.get("no_person_streak", 0) >= NO_PERSON_CONFIRM_STREAK
        )

        # ========================================================
        # OPENCV FACE DETECTION
        # ========================================================

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        faces = face_detector.detectMultiScale(
            gray,
            scaleFactor=1.3,
            minNeighbors=5
        )

        # ========================================================
        # MEDIAPIPE -- runs on EVERY frame. This is what blink / head
        # pose / gaze are derived from, and it is cheap relative to
        # YOLO/TensorFlow, so there is no reason to skip it. Skipping it
        # is what previously made blink detection miss almost every
        # blink (a blink only lasts ~100-400ms; sampling it rarely means
        # rarely catching it at all).
        # ========================================================

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp_ms = int(
            time.time() * 1000
        )

        result = landmarker.detect_for_video(
            mp_image,
            timestamp_ms
        )

    # ========================================================
    # DEFAULT VALUES
    # ========================================================

    name = state["last_name"]
    emotion = state["last_emotion"]

    ear = 0.0

    head_pose = "Looking Forward"
    gaze = "Center"

    # ========================================================
    # BLINK + HEAD POSE + GAZE
    # ========================================================

    if result.face_landmarks:

        landmarks = result.face_landmarks[0]

        # ---------------- Blink ----------------

        left_eye = [
            (landmarks[i].x, landmarks[i].y)
            for i in LEFT_EYE
        ]

        right_eye = [
            (landmarks[i].x, landmarks[i].y)
            for i in RIGHT_EYE
        ]

        leftEAR = eye_aspect_ratio(
            left_eye
        )

        rightEAR = eye_aspect_ratio(
            right_eye
        )

        ear = (
            leftEAR +
            rightEAR
        ) / 2.0

        state["last_ear"] = ear

        if ear < EAR_THRESHOLD:

            blink_counter = 1

        else:

            if blink_counter == 1:
                blink_total += 1

            blink_counter = 0

        # ---------------- Head Pose ----------------

        head_pose = calculate_head_pose(
            landmarks,
            width,
            height
        )

        # ---------------- Gaze ----------------

        gaze = calculate_gaze(
            landmarks
        )

    # ========================================================
    # SLEEPING (temporal, both-eyes-closed) -- reuses the exact same
    # landmarks/EAR computed above; no second face/eye pipeline.
    #
    # State transitions (per this student's own state dict only):
    #   - no_person_confirmed (existing, already-debounced signal):
    #     there is no genuine face/eye evidence at all -- always reset,
    #     never sleeping. Satisfies "no-person must never be treated as
    #     sleeping."
    #   - result.face_landmarks present (a real face WAS found this
    #     frame) and ear < EAR_THRESHOLD (same threshold blink detection
    #     already uses): this is genuine closed-eye evidence. Start (or
    #     continue) a real wall-clock timer via time.time(). Once the
    #     continuous closed duration reaches SLEEP_THRESHOLD_SECONDS,
    #     `sleeping` becomes True. A normal blink never reaches this --
    #     it reopens within a fraction of a second, hitting the branch
    #     below long before 4s.
    #   - result.face_landmarks present and ear >= EAR_THRESHOLD (a
    #     candidate "eyes open" reading): NOT trusted on a single frame,
    #     because real EAR is noisy (see EYES_OPEN_CONFIRM_STREAK above).
    #     Only once EYES_OPEN_CONFIRM_STREAK consecutive open readings
    #     have been seen is the episode considered genuinely over --
    #     THEN the timer and one-shot alert flag reset, so a LATER >=4s
    #     closed episode can trigger a fresh alert. A lone noisy "open"
    #     frame in the middle of a real closed episode leaves
    #     eyes_closed_since untouched, so the elapsed duration keeps
    #     counting through it.
    #   - result.face_landmarks ABSENT this frame, but the student is
    #     still otherwise present (no_person_confirmed is False -- e.g. a
    #     momentary MediaPipe landmark miss, which also happens routinely
    #     for a face with closed eyes): neither advance nor reset -- a
    #     genuine multi-second sleeping episode must not be destroyed by
    #     one missed frame, but it also never STARTS from missing
    #     landmarks alone (only the ear < EAR_THRESHOLD branch above ever
    #     starts the timer).
    # ========================================================

    # The one-alert-per-continuous-episode debounce is NOT reimplemented
    # here -- app/routers/monitoring.py already only creates a new Alert
    # row the first time active_alert transitions to a new value (see
    # its existing `if active_alert != state.get("last_alert_type")`
    # check), and only reverts away from "drowsiness" once `sleeping`
    # below goes back to False. That existing mechanism is reused as-is.
    now_ts = time.time()

    if no_person_confirmed:
        state["eyes_closed_since"] = None
        state["sleeping"] = False
        state["eyes_open_streak"] = 0
    elif result.face_landmarks:
        if ear < EAR_THRESHOLD:
            state["eyes_open_streak"] = 0

            if state.get("eyes_closed_since") is None:
                state["eyes_closed_since"] = now_ts

            closed_duration = now_ts - state["eyes_closed_since"]

            if closed_duration >= SLEEP_THRESHOLD_SECONDS:
                state["sleeping"] = True
        else:
            state["eyes_open_streak"] = state.get("eyes_open_streak", 0) + 1

            if state["eyes_open_streak"] >= EYES_OPEN_CONFIRM_STREAK:
                state["eyes_closed_since"] = None
                state["sleeping"] = False
    # else: face detection momentarily failed but the student is still
    # present -- deliberately leave eyes_closed_since/sleeping/
    # eyes_open_streak untouched.

    sleeping = bool(state.get("sleeping", False))

    # ========================================================
    # FRIEND LOOKING-AWAY / DROWSINESS OVERRIDE -- only takes effect when
    # AI_LOOKING_AWAY_DROWSINESS_SOURCE=friend (the default; see
    # friend_ai_loader's module docstring). Everything above this block
    # (the existing solvePnP/iris-ratio/EAR "current" computation) still
    # runs on every frame exactly as before -- unchanged -- so gaze/
    # head_pose/sleeping simply keep their "current" values below if this
    # is disabled, unavailable, or this particular frame's face wasn't
    # detected by the friend's own MediaPipe FaceMesh pass (e.g. extreme
    # profile/occlusion) -- a graceful per-frame fallback, never a crash.
    # ========================================================
    friend_gaze_result = None

    if (
        friend_ai_loader.LOOKING_AWAY_DROWSINESS_SOURCE == "friend"
        and not no_person_confirmed
    ):
        friend_gaze_predictor = state.get("friend_gaze_predictor")

        if friend_gaze_predictor is None and "friend_gaze_predictor" not in state:
            # Stateful (adaptive EAR baseline, blink counters, temporal
            # smoothers) -- one instance per (session, student), created
            # once and reused; see INTEGRATION_GUIDE.md "Instantiate ONCE
            # PER STUDENT SESSION". Cached even on failure (None) so a
            # broken/missing dependency isn't retried every single frame.
            friend_gaze_predictor = friend_ai_loader.new_friend_gaze_headpose_predictor()
            state["friend_gaze_predictor"] = friend_gaze_predictor

        if friend_gaze_predictor is not None:
            try:
                with inference_lock:
                    friend_gaze_result = friend_gaze_predictor.predict_frame(
                        frame, timestamp=now_ts
                    ).to_dict()
            except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
                friend_gaze_result = None
                if SLEEP_DEBUG:
                    print(f"[FRIEND_GAZE_DEBUG] predict_frame failed: {exc}")

        if friend_gaze_result and friend_gaze_result.get("face_detected"):
            gaze = FRIEND_GAZE_DIRECTION_MAP.get(
                friend_gaze_result.get("gaze_direction"), gaze
            )
            head_pose = FRIEND_HEAD_POSE_MAP.get(
                friend_gaze_result.get("head_pose_classification"), head_pose
            )
            sleeping = (
                friend_gaze_result.get("drowsiness_state")
                in FRIEND_SLEEPING_DROWSINESS_STATES
            )
            # Keep ai_state's own sleeping flag in sync so a later frame
            # that falls back to "current" (e.g. friend predictor
            # transiently unavailable) doesn't see a stale True/False.
            state["sleeping"] = sleeping

    # ========================================================
    # LOOKING-AWAY: dead zone + temporal debounce (see the "ACCEPTABLE
    # LAPTOP SCREEN VIEWING ZONE" comment block above process_frame for
    # the reasoning). `head_pose` here already reflects the dead-zone-
    # aware mapping (FRIEND_HEAD_POSE_MAP / the widened calculate_head_pose
    # bounds), so "Looking Away" only means genuinely outside the
    # acceptable zone. Gaze only contributes when it is CLEARLY extreme
    # (the wider GAZE_ALERT_* thresholds on the continuous, already-
    # smoothed ratio -- not the tighter display-categorization
    # threshold), since gaze naturally wanders more than head pose while
    # still reading a laptop screen.
    # ========================================================

    frame_outside_screen_zone = False

    if head_pose == "Looking Away":
        frame_outside_screen_zone = True
    elif friend_gaze_result and friend_gaze_result.get("face_detected"):
        h_ratio = friend_gaze_result.get("gaze_horizontal_ratio")
        v_ratio = friend_gaze_result.get("gaze_vertical_ratio")
        if h_ratio is not None and abs(h_ratio) > GAZE_ALERT_HORIZONTAL_THRESHOLD:
            frame_outside_screen_zone = True
        elif v_ratio is not None and abs(v_ratio) > GAZE_ALERT_VERTICAL_THRESHOLD:
            frame_outside_screen_zone = True
    elif gaze != "Center":
        # "current"-path fallback with no continuous ratio available --
        # calculate_gaze()'s own widened +/-0.05 threshold is already
        # this path's dead zone, so any classified deviation counts.
        frame_outside_screen_zone = True

    # BUG THIS FIXES: head_pose/gaze default to "Looking Forward"/"Center"
    # (see the DEFAULT VALUES block above) whenever NEITHER this
    # project's own MediaPipe FaceLandmarker NOR the friend's own
    # landmark pass finds a face THIS FRAME. A moderate head turn is
    # tracked fine and correctly classified via the branches above -- but
    # a sufficiently LARGE turn (exactly the "genuinely looking away"
    # case this feature must catch) is precisely when a face detector
    # loses tracking. Previously that made a genuine look-away
    # indistinguishable from "still centered", silently resetting
    # away_streak every such frame and preventing the alert from ever
    # confirming. landmarks_available tells the two cases apart; a
    # landmarks-missing frame is treated as supporting evidence for
    # "outside the zone" (same confirm/clear bookkeeping as an explicit
    # outside-zone classification) rather than being defaulted to
    # "inside the zone". This mirrors the sleeping-detection block's own
    # established handling of a missed-landmarks frame (see its comment
    # above) -- reusing an existing pattern, not inventing a new one.
    landmarks_available = bool(result.face_landmarks) or bool(
        friend_gaze_result and friend_gaze_result.get("face_detected")
    )

    if no_person_confirmed:
        # Nobody to judge -- never stay stuck "looking away" from before
        # the student left, mirrors the sleeping reset just above.
        state["away_streak"] = 0
        state["on_screen_streak"] = 0
        state["looking_away_confirmed"] = False
    elif frame_outside_screen_zone or not landmarks_available:
        state["on_screen_streak"] = 0
        state["away_streak"] = state.get("away_streak", 0) + 1
        if state["away_streak"] >= LOOKING_AWAY_CONFIRM_STREAK:
            state["looking_away_confirmed"] = True
    else:
        state["away_streak"] = 0
        state["on_screen_streak"] = state.get("on_screen_streak", 0) + 1
        if state["on_screen_streak"] >= LOOKING_AWAY_CLEAR_STREAK:
            state["looking_away_confirmed"] = False

    looking_away_confirmed = bool(state.get("looking_away_confirmed", False))

    if SLEEP_DEBUG:
        closed_since = state.get("eyes_closed_since")
        elapsed = (now_ts - closed_since) if closed_since else 0.0
        print(
            f"[SLEEP_DEBUG] student={state.get('last_name')} "
            f"landmarks={bool(result.face_landmarks)} "
            f"no_person_confirmed={no_person_confirmed} "
            f"ear={ear:.4f} EAR_THRESHOLD={EAR_THRESHOLD} "
            f"eyes_closed_since={closed_since} elapsed={elapsed:.2f}s "
            f"eyes_open_streak={state.get('eyes_open_streak', 0)} "
            f"sleeping={sleeping}"
        )
        if friend_gaze_result is not None:
            print(
                f"[FRIEND_GAZE_DEBUG] face_detected={friend_gaze_result.get('face_detected')} "
                f"gaze_direction={friend_gaze_result.get('gaze_direction')} "
                f"head_pose={friend_gaze_result.get('head_pose_classification')} "
                f"drowsiness_state={friend_gaze_result.get('drowsiness_state')} "
                f"ear={friend_gaze_result.get('ear_average')}"
            )
        print(
            f"[LOOKING_AWAY_DEBUG] student={state.get('last_name')} "
            f"head_pose={head_pose} gaze={gaze} "
            f"landmarks_available={landmarks_available} "
            f"frame_outside_zone={frame_outside_screen_zone} "
            f"away_streak={state.get('away_streak', 0)} "
            f"on_screen_streak={state.get('on_screen_streak', 0)} "
            f"looking_away_confirmed={looking_away_confirmed}"
        )

    # ========================================================
    # MEDIAPIPE FACE FALLBACK
    # ========================================================

    if len(faces) == 0 and result.face_landmarks:

        landmarks = result.face_landmarks[0]

        xs = [
            lm.x * width
            for lm in landmarks
        ]

        ys = [
            lm.y * height
            for lm in landmarks
        ]

        x1 = max(
            0,
            int(min(xs))
        )

        y1 = max(
            0,
            int(min(ys))
        )

        x2 = min(
            width,
            int(max(xs))
        )

        y2 = min(
            height,
            int(max(ys))
        )

        padding_x = int(
            (x2 - x1) * 0.15
        )

        padding_y = int(
            (y2 - y1) * 0.15
        )

        x1 = max(
            0,
            x1 - padding_x
        )

        y1 = max(
            0,
            y1 - padding_y
        )

        x2 = min(
            width,
            x2 + padding_x
        )

        y2 = min(
            height,
            y2 + padding_y
        )

        if x2 > x1 and y2 > y1:

            faces = np.array([
                [
                    x1,
                    y1,
                    x2 - x1,
                    y2 - y1
                ]
            ])

    # ========================================================
    # FACE RECOGNITION + EMOTION
    # ========================================================

    for (x, y, w, h) in faces:

        face_crop = frame[
            y:y+h,
            x:x+w
        ]

        if face_crop.size == 0:
            continue

        # ---------------- Face Recognition ----------------

        face_input = cv2.resize(
            face_crop,
            (224, 224)
        )

        face_input = (
            face_input.astype("float32")
            / 255.0
        )

        face_input = np.expand_dims(
            face_input,
            axis=0
        )

        if frame_counter % PROCESS_EVERY_FACE == 0:

            with inference_lock:

                if face_model is not None:
                    face_pred = face_model.predict(
                        face_input,
                        verbose=0
                    )

                # Current project has one enrolled student
                state["last_name"] = "Disha"

                # ---------------- Emotion ----------------
                # AI_EMOTION_MODEL_SOURCE=friend (the default; see
                # friend_ai_loader's module docstring) tries the friend's
                # MobileNetV2/FER2013 model (96x96 input, its own internal
                # preprocessing -- see EmotionPredictor._preprocess) on
                # the SAME face_crop this project's own model would use,
                # writing the SAME state["last_emotion"] string format
                # ("Happy"/"Neutral"/... -- Title-case, matching
                # emotion_labels below) so nothing downstream needs to
                # change. Falls back to the current model (unchanged
                # below) if the friend source is disabled/unavailable, or
                # if her prediction call itself fails on this frame.
                emotion_source_used = None

                if friend_ai_loader.EMOTION_SOURCE == "friend":
                    friend_emotion_predictor = friend_ai_loader.get_friend_emotion_predictor()

                    if friend_emotion_predictor is not None:
                        try:
                            friend_emotion_result = friend_emotion_predictor.predict(face_crop)
                            state["last_emotion"] = friend_emotion_result["raw_label"].capitalize()
                            emotion_source_used = "friend"
                        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
                            if SLEEP_DEBUG:
                                print(f"[FRIEND_EMOTION_DEBUG] predict failed: {exc}")

                if emotion_source_used is None:

                    emotion_input = cv2.resize(
                        face_crop,
                        (224, 224)
                    )

                    emotion_input = (
                        emotion_input.astype("float32")
                        / 255.0
                    )

                    emotion_input = np.expand_dims(
                        emotion_input,
                        axis=0
                    )

                    if emotion_model is not None:

                        emotion_pred = emotion_model.predict(
                            emotion_input,
                            verbose=0
                        )

                        state["last_emotion"] = emotion_labels[
                            np.argmax(emotion_pred)
                        ]

                    else:
                        state["last_emotion"] = "Neutral"

        name = state["last_name"]
        emotion = state["last_emotion"]
        # ---------------- Face Box ----------------

        cv2.rectangle(
            frame,
            (x, y),
            (x+w, y+h),
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Name: {name}",
            (x, y-35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"Emotion: {emotion}",
            (x, y-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2
        )

        break

    # ========================================================
    # ENGAGEMENT
    # ========================================================

    engagement_score = calculate_engagement(
        emotion,
        blink_total,
        head_pose,
        gaze,
        phone_detected,
        person_count,
        no_person_confirmed,
        sleeping
    )
        # ========================================================
    # AI ALERT
    # ========================================================

    active_alert = None

    # No person takes priority over every other signal -- phone/gaze/head
    # pose are all meaningless (stale or default) when nobody is in frame.
    # Sleeping ranks next: a confirmed >=4s closed-eye episode is a more
    # actionable, more certain signal than a mere off-center gaze/phone
    # sighting, so it's checked before those.
    if no_person_confirmed:
        active_alert = "no_person_detected"

    elif sleeping:
        active_alert = "drowsiness"

    elif phone_detected:
        active_alert = "phone_detected"

    elif person_count > 1:
        active_alert = "multiple_persons"

    elif looking_away_confirmed:
        active_alert = "looking_away"

    # ========================================================
    # DISPLAY INFORMATION
    # ========================================================

    cv2.putText(
        frame,
        f"Blinks: {blink_total}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )

    cv2.putText(
        frame,
        f"Persons: {person_count}",
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"Phone: {'Detected' if phone_detected else 'Not Detected'}",
        (20, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255) if phone_detected else (255, 0, 0),
        2
    )

    cv2.putText(
        frame,
        f"Head: {head_pose}",
        (20, 145),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        f"Gaze: {gaze}",
        (20, 180),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    cv2.putText(
        frame,
        f"Engagement: {engagement_score}",
        (20, 215),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2
    )

    # Write the updated blink state back into the caller's per-student
    # state dict so the next frame from THIS student (and only this
    # student) continues from here.
    state["blink_counter"] = blink_counter
    state["blink_total"] = blink_total

    return {
        "frame": frame,
        "name": name,
        "emotion": emotion,
        "blink_count": blink_total,
        "head_pose": head_pose,
        "gaze": gaze,
        "phone_detected": phone_detected,
        "person_count": person_count,
        "no_person_detected": no_person_confirmed,
        "active_alert": active_alert,
        "engagement_score": engagement_score,
        "sleeping": sleeping,
        # Debounced "genuinely outside the acceptable laptop-screen
        # viewing zone" signal -- see the LOOKING-AWAY block above.
        # app/routers/monitoring.py's get_active_alert() uses this
        # instead of re-deriving from raw head_pose/gaze equality checks.
        "looking_away": looking_away_confirmed,
        "engagement_status":
            "No Person Detected"
            if no_person_confirmed
            else "Engaged"
            if engagement_score >= 70
            else "Distracted"
    }
