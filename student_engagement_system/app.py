"""
Predictive Multimodal Student Engagement Monitoring System
============================================================

Real-time webcam application that fuses face recognition, emotion
recognition, blink detection, head pose estimation, gaze estimation, and
YOLO-based person/phone detection into a single engagement score.

This module ONLY orchestrates the existing utility modules in `utils/`.
No detection/recognition/scoring logic is re-implemented here except for:
    - Gaze DIRECTION classification (utils.gaze only exposes iris_center,
      it does not classify a direction), and
    - Face-prediction decoding (utils.face_utils.recognize_face returns the
      raw model output, not a resolved student name).

Run:
    python app.py
Quit:
    Press 'q' in the video window.
"""

import os

# Keep TensorFlow's console output quiet before it is imported.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import csv
import time
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import load_model

from utils.config import (
    EMOTION_LABELS,
    LEFT_EYE,
    RIGHT_EYE,
    LEFT_IRIS,
    RIGHT_IRIS,
    EAR_THRESHOLD,
    CONSEC_FRAMES,
)
from utils.blink import eye_aspect_ratio
from utils.gaze import iris_center
from utils.head_pose import estimate_head_pose
from utils.face_utils import get_face_roi, recognize_face, detect_emotion
from utils.yolo_utils import YOLODetector
from utils.engagement import calculate_engagement

tf.get_logger().setLevel("ERROR")


# =========================================================
# Paths / Constants
# =========================================================

FACE_MODEL_PATH = "ml_models/face_recognition_model.keras"
EMOTION_MODEL_PATH = "ml_models/emotion_recognition/emotion_model.keras"
FACE_LANDMARKER_PATH = "face_landmarker.task"

LOGS_DIR = "logs"
CSV_PATH = os.path.join(LOGS_DIR, "student_engagement.csv")
CSV_HEADER = [
    "Timestamp",
    "Name",
    "Emotion",
    "BlinkCount",
    "HeadPose",
    "Gaze",
    "PersonCount",
    "PhoneDetected",
    "EngagementScore",
    "Status",
]
LOG_INTERVAL_SECONDS = 1.0

# Only one student is currently enrolled in the face recognition model.
# To add more students, retrain/extend the model and append their names
# here in the same order as the model's output classes.
STUDENT_NAMES = ["Disha"]
FACE_RECOGNITION_CONFIDENCE_THRESHOLD = 0.60
EMOTION_CONFIDENCE_THRESHOLD = 0.0  # Always trust the top emotion class.

# Heuristic thresholds for classifying horizontal gaze direction from the
# normalized iris position within the eye's horizontal span.
GAZE_LEFT_THRESHOLD = 0.65
GAZE_RIGHT_THRESHOLD = 0.35

WINDOW_NAME = "Student Engagement Monitoring System"

COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_YELLOW = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)


# =========================================================
# Helper Functions (app-level only; no utility logic is duplicated)
# =========================================================

def decode_face_prediction(prediction):
    """Resolve the raw output of `recognize_face` into a student name.

    Args:
        prediction: Raw model output returned by `utils.face_utils.recognize_face`.

    Returns:
        (name, confidence)
    """
    prediction = np.asarray(prediction)

    if prediction.ndim > 1:
        prediction = prediction[0]

    if prediction.size == 0:
        return "Unknown", 0.0

    if prediction.size == 1:
        # Binary / single-logit output (e.g. sigmoid "is enrolled student").
        confidence = float(prediction[0])
        if confidence >= FACE_RECOGNITION_CONFIDENCE_THRESHOLD and STUDENT_NAMES:
            return STUDENT_NAMES[0], confidence
        return "Unknown", confidence

    class_idx = int(np.argmax(prediction))
    confidence = float(np.max(prediction))

    if confidence < FACE_RECOGNITION_CONFIDENCE_THRESHOLD:
        return "Unknown", confidence

    if class_idx >= len(STUDENT_NAMES):
        return "Unknown", confidence

    return STUDENT_NAMES[class_idx], confidence


def classify_gaze_direction(landmarks):
    """Classify horizontal gaze direction using iris_center() from utils.gaze.

    utils.gaze only provides the raw iris center coordinates, so the
    direction classification itself lives here in app.py.

    Args:
        landmarks: MediaPipe face landmark list for the detected face.

    Returns:
        One of "Left", "Right", "Center", or "Unknown".
    """
    try:
        left_iris_x, _ = iris_center(landmarks, LEFT_IRIS)
        right_iris_x, _ = iris_center(landmarks, RIGHT_IRIS)

        left_corner_a = landmarks[LEFT_EYE[0]].x
        left_corner_b = landmarks[LEFT_EYE[3]].x
        right_corner_a = landmarks[RIGHT_EYE[0]].x
        right_corner_b = landmarks[RIGHT_EYE[3]].x

        left_span = abs(left_corner_b - left_corner_a) + 1e-6
        right_span = abs(right_corner_b - right_corner_a) + 1e-6

        left_ratio = (left_iris_x - min(left_corner_a, left_corner_b)) / left_span
        right_ratio = (right_iris_x - min(right_corner_a, right_corner_b)) / right_span

        avg_ratio = (left_ratio + right_ratio) / 2.0

        if avg_ratio > GAZE_LEFT_THRESHOLD:
            return "Left"
        if avg_ratio < GAZE_RIGHT_THRESHOLD:
            return "Right"
        return "Center"

    except Exception:
        return "Unknown"


def compute_blink_state(landmarks, frame_width, frame_height,
                         blink_counter, blink_total):
    """Update blink counters for the current frame using eye_aspect_ratio().

    Args:
        landmarks: MediaPipe face landmark list.
        frame_width: Frame width in pixels.
        frame_height: Frame height in pixels.
        blink_counter: Consecutive-frames-below-threshold counter (state).
        blink_total: Total confirmed blink count so far (state).

    Returns:
        (avg_ear, updated_blink_counter, updated_blink_total)
    """
    left_eye_pts = [
        (landmarks[i].x * frame_width, landmarks[i].y * frame_height)
        for i in LEFT_EYE
    ]
    right_eye_pts = [
        (landmarks[i].x * frame_width, landmarks[i].y * frame_height)
        for i in RIGHT_EYE
    ]

    left_ear = eye_aspect_ratio(left_eye_pts)
    right_ear = eye_aspect_ratio(right_eye_pts)
    avg_ear = (left_ear + right_ear) / 2.0

    if avg_ear < EAR_THRESHOLD:
        if blink_counter == 0:
            blink_total += 1

        blink_counter = 1

    else:

        blink_counter = 0

    return avg_ear, blink_counter, blink_total


def ensure_csv_logger(csv_path):
    """Create the logs directory and CSV file (with header) if missing."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)


def log_engagement_row(csv_path, row):
    """Append a single engagement record to the CSV log."""
    try:
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
    except OSError as exc:
        print(f"[WARNING] Failed to write CSV log row: {exc}")


def draw_dashboard(frame, info, warnings):
    """Draw a semi-transparent dashboard panel with engagement info."""
    overlay = frame.copy()
    panel_w, panel_h = 340, 260
    cv2.rectangle(overlay, (10, 10), (10 + panel_w, 10 + panel_h), COLOR_BLACK, -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)

    lines = [
        f"Name: {info['name']}",
        f"Emotion: {info['emotion']}",
        f"Blink Count: {info['blink_count']}",
        f"Head Pose: {info['head_pose']}",
        f"Gaze: {info['gaze']}",
        f"Persons: {info['person_count']}",
        f"Phone: {'Yes' if info['phone_detected'] else 'No'}",
        f"Engagement: {info['score']}%",
        f"Status: {info['status']}",
        f"FPS: {info['fps']:.1f}",
    ]

    y = 35
    for line in lines:
        cv2.putText(frame, line, (22, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    COLOR_GREEN, 2, cv2.LINE_AA)
        y += 23

    warn_y = 10 + panel_h + 30
    for warning_text in warnings:
        cv2.putText(frame, warning_text, (22, warn_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, COLOR_RED, 2, cv2.LINE_AA)
        warn_y += 30

    return frame


def print_session_summary(csv_path):
    """Use pandas to summarize the logged session on shutdown."""
    try:
        if not os.path.exists(csv_path):
            return
        df = pd.read_csv(csv_path)
        if df.empty:
            return
        print("\n===== Session Summary =====")
        print(f"Total logged samples : {len(df)}")
        print(f"Average Engagement   : {df['EngagementScore'].mean():.2f}%")
        print(f"Most common status   : {df['Status'].mode().iloc[0]}")
        print("============================\n")
    except Exception as exc:
        print(f"[WARNING] Could not generate session summary: {exc}")


# =========================================================
# Load Models
# =========================================================

print("Loading TensorFlow models...")
try:
    face_model = load_model(FACE_MODEL_PATH)
    emotion_model = load_model(EMOTION_MODEL_PATH)
except Exception as exc:
    raise RuntimeError(f"Failed to load TensorFlow models: {exc}") from exc
print("TensorFlow Models Loaded")

print("Loading YOLO detector...")
try:
    yolo = YOLODetector()
except Exception as exc:
    raise RuntimeError(f"Failed to load YOLO model: {exc}") from exc
print("YOLO Loaded")

print("Loading MediaPipe Face Landmarker...")
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

try:
    landmarker_options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=FACE_LANDMARKER_PATH),
        running_mode=VisionRunningMode.VIDEO,
        num_faces=1,
    )
    landmarker = FaceLandmarker.create_from_options(landmarker_options)
except Exception as exc:
    raise RuntimeError(f"Failed to load MediaPipe Face Landmarker: {exc}") from exc
print("MediaPipe Ready")


# =========================================================
# Webcam
# =========================================================

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    landmarker.close()
    raise RuntimeError("Cannot open webcam")


# =========================================================
# CSV Logger
# =========================================================

ensure_csv_logger(CSV_PATH)
print("CSV Logger Ready")
print("Initialization Completed Successfully\n")


# =========================================================
# Main Loop
# =========================================================

blink_counter = 0
blink_total = 0

prev_time = time.time()
last_log_time = 0.0
last_timestamp_ms = -1
frame_count = 0
name = "Unknown"
emotion = "Unknown"
head_pose = "Unknown"
gaze = "Unknown"

try:
    annotated_frame = None
    person_count = 0
    phone_detected = False
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[ERROR] Failed to read frame from webcam. Stopping.")
            break

        frame_height, frame_width = frame.shape[:2]
        warnings = []

        # ---------------- YOLO Detection ----------------
        # Run YOLO only every 5 frames
        # Always start from the latest frame
        annotated_frame = frame.copy()

        # Run YOLO every 5 frames
        if frame_count % 5 == 0:
            try:
                yolo_frame, person_count, phone_detected = yolo.detect(frame)

                if yolo_frame is not None:
                    annotated_frame = yolo_frame

            except Exception as exc:
                print(f"[WARNING] YOLO detection failed: {exc}")

        # ---------------- MediaPipe Face Landmarker ----------------


        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            timestamp_ms = int(time.time() * 1000)
            if timestamp_ms <= last_timestamp_ms:
                timestamp_ms = last_timestamp_ms + 1
            last_timestamp_ms = timestamp_ms

            result = landmarker.detect_for_video(mp_image, timestamp_ms)
        except Exception as exc:
            print(f"[WARNING] MediaPipe detection failed: {exc}")
            result = None

        if result is not None and result.face_landmarks:
            landmarks = result.face_landmarks[0]

            try:
                face_roi, (xmin, ymin, xmax, ymax) = get_face_roi(frame, landmarks)
            except Exception as exc:
                print(f"[WARNING] Face ROI extraction failed: {exc}")
                face_roi, (xmin, ymin, xmax, ymax) = None, (0, 0, 0, 0)

            if face_roi is not None and face_roi.size > 0:
                try:
                    if frame_count % 20 == 0:
                        prediction = recognize_face(face_roi, face_model)
                        name, _ = decode_face_prediction(prediction)
                except Exception as exc:
                    print(f"[WARNING] Face recognition failed: {exc}")
                    name = "Unknown"

                try:
                    if frame_count % 10 == 0:
                        emotion, _ = detect_emotion(
                            face_roi,
                            emotion_model,
                            EMOTION_LABELS
                        )
                except Exception as exc:
                    print(f"[WARNING] Emotion detection failed: {exc}")
                    emotion = "Unknown"

                cv2.rectangle(annotated_frame, (xmin, ymin), (xmax, ymax),
                              COLOR_GREEN, 2)
                cv2.putText(annotated_frame, name, (xmin, max(ymin - 10, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GREEN, 2,
                            cv2.LINE_AA)
            else:
                warnings.append("Empty Face ROI")

            try:
                head_pose = estimate_head_pose(landmarks, frame_width, frame_height)
            except Exception as exc:
                print(f"[WARNING] Head pose estimation failed: {exc}")
                head_pose = "Unknown"

            gaze = classify_gaze_direction(landmarks)

            try:
                _, blink_counter, blink_total = compute_blink_state(
                    landmarks, frame_width, frame_height,
                    blink_counter, blink_total,
                )
            except Exception as exc:
                print(f"[WARNING] Blink detection failed: {exc}")

        else:
            warnings.append("No Face Detected")

        # ---------------- Person / Phone Warnings ----------------
        if person_count > 1:
            warnings.append("WARNING: Multiple Students Detected")

        if phone_detected:
            warnings.append("Mobile Phone Detected")

        # ---------------- Engagement Score ----------------
        score, status = calculate_engagement(
            emotion=emotion,
            head_pose=head_pose,
            blink_count=blink_total,
            phone_detected=phone_detected,
            person_count=person_count,
            gaze=gaze,
        )

        # ---------------- FPS ----------------
        current_time = time.time()
        fps = 1.0 / (current_time - prev_time) if current_time != prev_time else 0.0
        prev_time = current_time

        # ---------------- Dashboard ----------------
        dashboard_info = {
            "name": name,
            "emotion": emotion,
            "blink_count": blink_total,
            "head_pose": head_pose,
            "gaze": gaze,
            "person_count": person_count,
            "phone_detected": phone_detected,
            "score": score,
            "status": status,
            "fps": fps,
        }
        annotated_frame = draw_dashboard(annotated_frame, dashboard_info, warnings)
        frame_count += 1

        cv2.imshow(WINDOW_NAME, annotated_frame)

        # ---------------- CSV Logging (every 1 second) ----------------
        if current_time - last_log_time >= LOG_INTERVAL_SECONDS:
            log_engagement_row(CSV_PATH, [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                name,
                emotion,
                blink_total,
                head_pose,
                gaze,
                person_count,
                phone_detected,
                score,
                status,
            ])
            last_log_time = current_time

        # ---------------- Exit ----------------
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Quit signal received. Shutting down.")
            break

except KeyboardInterrupt:
    print("\nInterrupted by user.")

finally:
    cap.release()
    cv2.destroyAllWindows()
    try:
        landmarker.close()
    except Exception:
        pass
    print_session_summary(CSV_PATH)
    print("Shutdown complete. Webcam released and windows closed.")
