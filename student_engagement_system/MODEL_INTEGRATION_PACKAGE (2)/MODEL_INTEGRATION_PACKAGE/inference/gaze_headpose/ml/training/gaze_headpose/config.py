"""
config.py
---------
Centralized configuration for the Gaze & Head Pose Estimation module.

Purpose
-------
Single source of truth for every path, threshold, landmark index, and
dataset registry entry used by every other file in this module
(`landmark_detector.py`, `gaze_estimator.py`, `headpose_estimator.py`,
`blink_detector.py`, `drowsiness_detector.py`, `face_quality.py`,
`temporal_filter.py`, `trainer.py`, `predictor.py`, and all notebooks).

No file in this module hardcodes a path, threshold, or dataset location —
everything is read from here, matching the project's existing config
pattern (`backend/app/config.py`, `ml/training/emotion_model/config.py`).

Models used (per module spec, "Only use pretrained models"):
  1. MediaPipe FaceMesh (468 landmarks + iris refinement) — primary
  2. MediaPipe Iris (bundled into FaceMesh via `refine_landmarks=True`)
  3. OpenCV `solvePnP` — geometric head-pose recovery from landmarks

No custom landmark detector is trained anywhere in this module.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------
# Filesystem layout
# ----------------------------------------------------------------------
MODULE_DIR: Path = Path(__file__).resolve().parent                  # ml/training/gaze_headpose
PROJECT_ROOT: Path = MODULE_DIR.parents[2]                           # repo root

ARTIFACTS_DIR: Path = MODULE_DIR / "artifacts"
EVALUATION_DIR: Path = MODULE_DIR / "evaluation"
LOGS_DIR: Path = MODULE_DIR / "logs"

DATASETS_RAW_DIR: Path = PROJECT_ROOT / "datasets" / "raw"
DATASETS_PROCESSED_DIR: Path = PROJECT_ROOT / "datasets" / "processed"

# Evaluation-only datasets (Mode 2). None are required for Mode 1 (default)
# operation — MediaPipe's bundled pretrained models need no dataset at all.
MPIIGAZE_DIR: Path = DATASETS_RAW_DIR / "mpiigaze"
GAZECAPTURE_DIR: Path = DATASETS_RAW_DIR / "gazecapture"
ETH_XGAZE_DIR: Path = DATASETS_RAW_DIR / "eth_xgaze"

# Optional fine-tuning datasets (Mode 3). Not required, not auto-downloaded.
MPIIFACEGAZE_DIR: Path = DATASETS_RAW_DIR / "mpiifacegaze"
RT_GENE_DIR: Path = DATASETS_RAW_DIR / "rt_gene"

for _dir in (ARTIFACTS_DIR, EVALUATION_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# Unified evaluation manifest produced by dataset_preprocessing.ipynb from
# whichever raw dataset(s) are available (MPIIGaze / GazeCapture /
# ETH-XGaze each ship in different raw formats; preprocessing normalizes
# them into one CSV interchange format so trainer.py's evaluator does not
# need one bespoke parser per dataset).
GAZE_HEADPOSE_PROCESSED_DIR: Path = DATASETS_PROCESSED_DIR / "gaze_headpose"
EVAL_MANIFEST_CSV: Path = GAZE_HEADPOSE_PROCESSED_DIR / "eval_manifest.csv"
GAZE_HEADPOSE_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Expected columns in eval_manifest.csv (nullable except image_path):
#   image_path   - path to the face image, relative to GAZE_HEADPOSE_PROCESSED_DIR
#   yaw, pitch, roll        - ground-truth head pose in degrees (optional)
#   gaze_yaw, gaze_pitch    - ground-truth gaze angle in degrees (optional)
#   is_blink                - 1/0 ground-truth blink label for this frame (optional)
EVAL_MANIFEST_COLUMNS = (
    "image_path",
    "yaw",
    "pitch",
    "roll",
    "gaze_yaw",
    "gaze_pitch",
    "is_blink",
)

# ----------------------------------------------------------------------
# MPIIGaze on-disk layout
# ----------------------------------------------------------------------
# The official MPIIGaze download (commonly extracted as a folder named
# "MPIIGaze", mixed case, matched case-insensitively — see
# utils.resolve_dataset_dir) does NOT use a simple images/ + labels.csv
# convenience layout. Its real structure is:
#
#   <raw_dataset_root>/
#   |-- Data/
#   |   |-- Original/p00..p14/dayXX/*.jpg + annotation.txt
#   |   `-- Normalized/p00..p14/dayXX.mat
#   |-- Evaluation Subset/
#   |   |-- annotation for face image/p00.txt ... p14.txt
#   |   `-- image/p00..p14/dayXX/*.jpg
#   `-- 6 points-based face model.mat
#
# `preprocess_dataset.py` (invoked by `dataset_preprocessing.ipynb`) parses
# `Data/Normalized/*.mat` directly — confirmed via `scipy.io.loadmat` to
# contain a `data` struct with `left`/`right` sub-structs, each holding
# `image` (per-eye 36x60 crop), `gaze` (3D unit vector), and `pose` (3D
# head-rotation vector), plus a parallel `filenames` array. This is the
# ground-truth source actually present and verified on disk for this
# project; the "Evaluation Subset" text-annotation layout above is *not*
# parsed by the current pipeline (it was in an earlier version of this
# module, before the Normalized `.mat` layout was confirmed as what's
# actually available) — `MPII_FACE_MODEL_FILENAME` below is kept as a
# reference constant since the face-model file's name doesn't depend on
# which annotation source is used.
MPII_EVAL_SUBSET_DIRNAME = "Evaluation Subset"
MPII_EVAL_ANNOTATION_DIRNAME = "annotation for face image"
MPII_EVAL_IMAGE_DIRNAME = "image"
MPII_FACE_MODEL_FILENAME = "6 points-based face model.mat"

# Sanity-check ranges used by `preprocess_dataset.py` to reject a
# mis-parsed or implausible sample rather than write a bad value into the
# manifest (protects against silently writing garbage if a particular
# dataset mirror's `.mat` contents deviate from the confirmed layout).
MPII_HEAD_POSE_VALID_RANGE_DEG = (-90.0, 90.0)
MPII_GAZE_ANGLE_VALID_RANGE_DEG = (-90.0, 90.0)

# ----------------------------------------------------------------------
# Dataset registry (Mode 2 — Evaluation, Mode 3 — Optional Fine-Tuning)
# ----------------------------------------------------------------------
# Central, extensible registry. `landmark_detector.py`/`trainer.py` never
# hardcode a dataset name or path — they iterate this dict. Adding a new
# evaluation or fine-tuning dataset means adding one entry here.
EVALUATION_DATASETS = {
    "mpiigaze": {
        "path": MPIIGAZE_DIR,
        "description": "MPIIGaze — appearance-based gaze estimation in the wild.",
        "homepage": "https://www.perceptualui.org/research/datasets/MPIIGaze/",
        "task": "gaze",
    },
    "gazecapture": {
        "path": GAZECAPTURE_DIR,
        "description": "GazeCapture — large-scale mobile-device gaze dataset.",
        "homepage": "https://gazecapture.csail.mit.edu/",
        "task": "gaze",
    },
    "eth_xgaze": {
        "path": ETH_XGAZE_DIR,
        "description": "ETH-XGaze — large-scale gaze estimation with wide head-pose range.",
        "homepage": "https://ait.ethz.ch/xgaze",
        "task": "gaze",
    },
}

FINE_TUNE_DATASETS = {
    "mpiifacegaze": {
        "path": MPIIFACEGAZE_DIR,
        "description": "MPIIFaceGaze — full-face appearance-based gaze estimation.",
        "homepage": "https://www.perceptualui.org/research/datasets/MPIIFaceGaze/",
        "task": "gaze",
        "enabled": False,  # Mode 3 is opt-in and disabled by default
    },
    "rt_gene": {
        "path": RT_GENE_DIR,
        "description": "RT-GENE — real-time gaze estimation in natural environments.",
        "homepage": "https://github.com/Tobias-Fischer/rt_gene",
        "task": "gaze",
        "enabled": False,  # Mode 3 is opt-in and disabled by default
    },
}

# ----------------------------------------------------------------------
# MediaPipe FaceMesh configuration
# ----------------------------------------------------------------------
MEDIAPIPE_STATIC_IMAGE_MODE = False
MEDIAPIPE_MAX_NUM_FACES = 1
MEDIAPIPE_REFINE_LANDMARKS = True  # required for iris landmarks (468-477)
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5
MEDIAPIPE_MIN_TRACKING_CONFIDENCE = 0.5

TOTAL_FACE_LANDMARKS = 468
TOTAL_LANDMARKS_WITH_IRIS = 478  # 468 mesh + 10 iris (5 per eye w/ refinement)

# ----------------------------------------------------------------------
# Landmark index groups (MediaPipe FaceMesh topology)
# ----------------------------------------------------------------------
# 6-point head-pose model (classic solvePnP correspondence set)
POSE_LANDMARK_INDICES = {
    "nose_tip": 1,
    "chin": 152,
    "left_eye_left_corner": 33,
    "right_eye_right_corner": 263,
    "left_mouth_corner": 61,
    "right_mouth_corner": 291,
}

# Generic 3D face model points (mm, arbitrary origin at the nose tip) used
# as the object-space correspondence for cv2.solvePnP. This is the widely
# used canonical 6-point face model (not a trained model — a fixed
# geometric reference).
GENERIC_3D_FACE_MODEL = np.array(
    [
        (0.0, 0.0, 0.0),         # nose tip
        (0.0, -330.0, -65.0),    # chin
        (-225.0, 170.0, -135.0),  # left eye, left corner
        (225.0, 170.0, -135.0),  # right eye, right corner
        (-150.0, -150.0, -125.0),  # left mouth corner
        (150.0, -150.0, -125.0),  # right mouth corner
    ],
    dtype=np.float64,
)

# Eye landmark sets (6 points each, dlib-EAR-equivalent ordering:
# [left_corner, top_1, top_2, right_corner, bottom_1, bottom_2])
LEFT_EYE_EAR_INDICES = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_EAR_INDICES = [33, 160, 158, 133, 153, 144]

# Broader eye contour (used for eye-region cropping / occlusion checks)
LEFT_EYE_CONTOUR_INDICES = [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466]
RIGHT_EYE_CONTOUR_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]

# Iris landmark sets (only present when MEDIAPIPE_REFINE_LANDMARKS=True)
LEFT_IRIS_INDICES = [474, 475, 476, 477]
RIGHT_IRIS_INDICES = [469, 470, 471, 472]

# Face oval (used for bounding box / face-size / face-position checks)
FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378,
    400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21,
    54, 103, 67, 109,
]

# ----------------------------------------------------------------------
# Gaze estimation thresholds
# ----------------------------------------------------------------------
# Normalized horizontal/vertical iris-offset ratios (iris center position
# relative to the eye-corner span, roughly in [-1, 1]) beyond which gaze
# is classified away from center.
GAZE_HORIZONTAL_THRESHOLD = 0.18
GAZE_VERTICAL_THRESHOLD = 0.16
GAZE_CONFIDENCE_FLOOR = 0.35  # below this, gaze direction is reported as "uncertain"

# Virtual screen plane used for the reported "screen coordinate" gaze
# projection, expressed in normalized [0, 1] x [0, 1] screen space.
GAZE_SCREEN_PROJECTION_ENABLED = True

# ----------------------------------------------------------------------
# Head pose thresholds (degrees)
# ----------------------------------------------------------------------
HEAD_POSE_FOCUSED_YAW_DEG = 15.0
HEAD_POSE_FOCUSED_PITCH_DEG = 15.0
HEAD_POSE_SLIGHTLY_DISTRACTED_YAW_DEG = 30.0
HEAD_POSE_SLIGHTLY_DISTRACTED_PITCH_DEG = 25.0
# Beyond the "slightly distracted" bounds -> "looking_away"

# ----------------------------------------------------------------------
# Eye Aspect Ratio (EAR) / blink detection
# ----------------------------------------------------------------------
EAR_DEFAULT_THRESHOLD = 0.21          # initial static threshold before adaptation
EAR_ADAPTIVE_WINDOW_SECONDS = 30.0    # rolling window used to adapt the threshold
EAR_ADAPTIVE_ALPHA = 0.15             # weight of new EAR baseline samples
EAR_MIN_CONSEC_FRAMES_FOR_BLINK = 2   # frames below threshold to count as a blink
BLINK_MAX_DURATION_SECONDS = 0.5      # blinks longer than this are treated as eye closure, not a blink

# ----------------------------------------------------------------------
# Drowsiness detection
# ----------------------------------------------------------------------
DROWSINESS_EYE_CLOSED_ALERT_SECONDS = 1.0     # sustained closure -> "fatigued"
DROWSINESS_EYE_CLOSED_DROWSY_SECONDS = 2.0    # sustained closure -> "drowsy"
DROWSINESS_EYE_CLOSED_MICROSLEEP_SECONDS = 3.5  # sustained closure -> "microsleep"
DROWSINESS_BLINK_RATE_WINDOW_SECONDS = 60.0
DROWSINESS_HIGH_BLINK_RATE_PER_MIN = 25         # elevated blink rate is a fatigue signal

# ----------------------------------------------------------------------
# Face quality assessment
# ----------------------------------------------------------------------
FACE_QUALITY_MIN_SIZE_RATIO = 0.10     # face bounding box width / frame width
FACE_QUALITY_MAX_SIZE_RATIO = 0.85
FACE_QUALITY_MIN_BRIGHTNESS = 40       # mean grayscale intensity (0-255)
FACE_QUALITY_MAX_BRIGHTNESS = 235
FACE_QUALITY_MIN_SHARPNESS = 25.0      # variance of Laplacian
FACE_QUALITY_MAX_CENTER_OFFSET_RATIO = 0.35  # face-center distance from frame-center / frame diag
FACE_QUALITY_REJECT_THRESHOLD = 0.5    # overall quality score below this -> reject frame

# ----------------------------------------------------------------------
# Temporal smoothing
# ----------------------------------------------------------------------
EMA_ALPHA_GAZE = 0.35
EMA_ALPHA_HEAD_POSE = 0.30
EMA_ALPHA_EAR = 0.5
KALMAN_ENABLED_DEFAULT = False  # optional; EMA is the default smoothing strategy
KALMAN_PROCESS_NOISE = 1e-3
KALMAN_MEASUREMENT_NOISE = 1e-1

# ----------------------------------------------------------------------
# Confidence estimation weights
# ----------------------------------------------------------------------
# Overall per-frame confidence is a weighted blend of landmark-detection
# confidence, face-quality score, and temporal stability.
CONFIDENCE_WEIGHTS = {
    "detection": 0.4,
    "quality": 0.35,
    "stability": 0.25,
}

# ----------------------------------------------------------------------
# Evaluation
# ----------------------------------------------------------------------
EVALUATION_LATENCY_WARMUP_FRAMES = 10
EVALUATION_REPORT_JSON = EVALUATION_DIR / "evaluation_report.json"
EVALUATION_CONFUSION_MATRIX_PNG = EVALUATION_DIR / "head_pose_confusion_matrix.png"
EVALUATION_LATENCY_PLOT_PNG = EVALUATION_DIR / "latency_fps.png"

HEAD_POSE_CLASSES = ("focused", "slightly_distracted", "looking_away")
GAZE_DIRECTION_CLASSES = ("center", "left", "right", "up", "down")

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
LOG_FILE_PATH = LOGS_DIR / "gaze_headpose.log"
LOG_LEVEL = "INFO"

# ----------------------------------------------------------------------
# Inference defaults
# ----------------------------------------------------------------------
DEFAULT_CAMERA_INDEX = 0
DEFAULT_JPEG_QUALITY = 90
REALTIME_TARGET_FPS = 15  # matches the ~1-2fps sampling budget elsewhere in
                          # the system while allowing local smooth demo playback
