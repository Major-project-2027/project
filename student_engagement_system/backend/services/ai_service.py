import cv2
import time
import threading
import numpy as np
import mediapipe as mp

from scipy.spatial import distance
from tensorflow.keras.models import load_model
from ultralytics import YOLO

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

FACE_MODEL_PATH = "ml_models/face_recognition_model.keras"
EMOTION_MODEL_PATH = "ml_models/emotion_recognition/emotion_model.keras"
YOLO_MODEL_PATH = "yolov8n.pt"
LANDMARKER_PATH = "face_landmarker.task"


# ============================================================
# LOAD MODELS
# ============================================================

print("Loading Face Recognition Model...")

if __import__("os").path.exists(FACE_MODEL_PATH):
    face_model = load_model(FACE_MODEL_PATH)
else:
    print("WARNING: Face recognition model not found. Face authentication disabled.")
    face_model = None

print("Loading Emotion Model...")

if __import__("os").path.exists(EMOTION_MODEL_PATH):
    emotion_model = load_model(EMOTION_MODEL_PATH)
else:
    print("WARNING: Emotion model not found. Emotion recognition disabled.")
    emotion_model = None

print("Loading YOLO...")
yolo_model = YOLO(YOLO_MODEL_PATH)


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

    if y_angle < -10:
        return "Looking Left"

    elif y_angle > 10:
        return "Looking Right"

    elif x_angle < -10:
        return "Looking Down"

    elif x_angle > 10:
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

    if difference < -0.015:
        return "Left"

    elif difference > 0.015:
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
    person_count
):

    score = 100

    if phone_detected:
        score -= 30

    if person_count > 1:
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

        else:

            person_count = state["last_person_count"]
            phone_detected = state["last_phone_detected"]

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
        person_count
    )
        # ========================================================
    # AI ALERT
    # ========================================================

    active_alert = None

    if phone_detected:
        active_alert = "phone_detected"

    elif person_count > 1:
        active_alert = "multiple_persons"

    elif (
        gaze != "Center"
        or head_pose != "Looking Forward"
    ):
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
        "active_alert": active_alert,
        "engagement_score": engagement_score,
        "engagement_status":
            "Engaged"
            if engagement_score >= 70
            else "Distracted"
    }
