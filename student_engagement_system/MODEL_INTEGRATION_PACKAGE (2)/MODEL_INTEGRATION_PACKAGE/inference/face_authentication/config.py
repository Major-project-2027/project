"""
ml/training/face_authentication/config.py
===========================================
Centralized configuration for the Face Authentication module (Module 2).

Every other file in this module (utils.py, embedding_model.py,
trainer.py, predictor.py, and all notebooks) imports its settings
from here. Nothing in this module reads environment variables or
hardcodes a path directly - change behavior by editing this file only.

This module is fully independent of Module 1 (Emotion Detection) and
does not import anything from ml/training/emotion_model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
MODULE_ROOT = Path(__file__).resolve().parent

DATASET_ROOT = MODULE_ROOT / "data"                       # raw + processed datasets
RAW_DATASET_DIR = DATASET_ROOT / "raw"
PROCESSED_DATASET_DIR = DATASET_ROOT / "processed"

EMBEDDINGS_DIR = MODULE_ROOT / "embeddings"                # registered-student embeddings (.npz/.pkl)
REGISTERED_STUDENTS_DIR = MODULE_ROOT / "registered_students"  # raw enrollment images + metadata JSON
CHECKPOINTS_DIR = MODULE_ROOT / "checkpoints"               # calibrated threshold / classifier head, if any
EVALUATION_ARTIFACTS_DIR = MODULE_ROOT / "evaluation_artifacts"  # ROC curves, confusion matrices, reports

for _dir in (
    DATASET_ROOT, RAW_DATASET_DIR, PROCESSED_DATASET_DIR,
    EMBEDDINGS_DIR, REGISTERED_STUDENTS_DIR, CHECKPOINTS_DIR,
    EVALUATION_ARTIFACTS_DIR,
):
    _dir.mkdir(parents=True, exist_ok=True)

STUDENT_REGISTRY_FILE = EMBEDDINGS_DIR / "student_registry.json"
CALIBRATED_THRESHOLD_FILE = CHECKPOINTS_DIR / "calibrated_threshold.json"


# ---------------------------------------------------------------------------
# Dataset configuration
# ---------------------------------------------------------------------------
DatasetName = Literal["lfw", "casia_webface", "vggface2"]

DATASET_REGISTRY: dict[str, dict] = {
    "lfw": {
        "display_name": "Labeled Faces in the Wild (LFW)",
        "download_url": "http://vis-www.cs.umass.edu/lfw/lfw.tgz",
        "pairs_url": "http://vis-www.cs.umass.edu/lfw/pairs.txt",
        "archive_name": "lfw.tgz",
        "extracted_dir_name": "lfw",
        "structure": "per_identity_folders",  # <person_name>/<person_name>_0001.jpg
        "license_note": "Free for academic/research use.",
    },
    "casia_webface": {
        "display_name": "CASIA-WebFace",
        "download_url": None,  # requires manual/gated download; see README
        "pairs_url": None,
        "archive_name": "casia-webface.zip",
        "extracted_dir_name": "casia-webface",
        "structure": "per_identity_folders",
        "license_note": "Requires accepting a license agreement from the original distributor; not auto-downloadable.",
    },
    "vggface2": {
        "display_name": "VGGFace2",
        "download_url": None,  # requires manual/gated download; see README
        "pairs_url": None,
        "archive_name": "vggface2.zip",
        "extracted_dir_name": "vggface2",
        "structure": "per_identity_folders",
        "license_note": "Requires accepting a license agreement; not auto-downloadable.",
    },
}

# Active dataset - change this single value to switch datasets across
# every notebook/script in the module.
ACTIVE_DATASET: DatasetName = "lfw"


def get_active_dataset_config() -> dict:
    return DATASET_REGISTRY[ACTIVE_DATASET]


def get_active_dataset_dir() -> Path:
    return RAW_DATASET_DIR / DATASET_REGISTRY[ACTIVE_DATASET]["extracted_dir_name"]


# ---------------------------------------------------------------------------
# Preprocessing configuration
# ---------------------------------------------------------------------------
TARGET_IMAGE_SIZE: tuple[int, int] = (160, 160)   # required input size for FaceNet/ArcFace/MobileFaceNet
IMAGE_CHANNELS: int = 3                            # RGB
NORMALIZE_METHOD: Literal["facenet", "arcface", "0_1", "-1_1"] = "arcface"

# Face detector backend used for BOTH preprocessing and real-time inference.
# Options supported by the `deepface` library: "opencv", "mtcnn",
# "retinaface", "mediapipe", "ssd", "dlib", "yolov8".
# "retinaface" gives the strongest alignment quality; "mediapipe" is the
# fastest and matches the detector already used elsewhere in the wider
# system (gaze/head-pose module) for consistency if latency matters more
# than alignment precision.
FACE_DETECTOR_BACKEND: Literal[
    "opencv", "mtcnn", "retinaface", "mediapipe", "ssd", "dlib", "yolov8"
] = "retinaface"

FACE_DETECTION_CONFIDENCE_THRESHOLD: float = 0.90
ENFORCE_SINGLE_FACE_ON_ENROLLMENT: bool = True
DUPLICATE_IMAGE_HASH_THRESHOLD: int = 4   # perceptual-hash Hamming distance; lower = stricter dedup
MIN_FACE_SIZE_PX: int = 40                 # discard detections smaller than this (likely false positives)


# ---------------------------------------------------------------------------
# Embedding model configuration
# ---------------------------------------------------------------------------
# Preferred order per project requirements: ArcFace > FaceNet > MobileFaceNet.
# All three are available as pretrained, frozen models via the `deepface`
# library (TensorFlow-backed) - no training from scratch is performed.
EmbeddingModelName = Literal["ArcFace", "Facenet512", "Facenet", "MobileFaceNet"]

EMBEDDING_MODEL_PRIORITY: list[EmbeddingModelName] = ["ArcFace", "Facenet512", "Facenet"]

# The active model. ArcFace natively outputs 512-D embeddings and is the
# first-priority model per requirements, so it is the default.
ACTIVE_EMBEDDING_MODEL: EmbeddingModelName = "ArcFace"

EMBEDDING_DIMENSIONS: dict[str, int] = {
    "ArcFace": 512,
    "Facenet512": 512,
    "Facenet": 128,
    "MobileFaceNet": 512,
}


def get_active_embedding_dim() -> int:
    return EMBEDDING_DIMENSIONS[ACTIVE_EMBEDDING_MODEL]


# ---------------------------------------------------------------------------
# Registration configuration
# ---------------------------------------------------------------------------
MIN_ENROLLMENT_IMAGES_PER_STUDENT: int = 3
MAX_ENROLLMENT_IMAGES_PER_STUDENT: int = 8
ENROLLMENT_EMBEDDING_AGGREGATION: Literal["mean", "median"] = "mean"


# ---------------------------------------------------------------------------
# Authentication / matching configuration
# ---------------------------------------------------------------------------
SIMILARITY_METRIC: Literal["cosine", "euclidean", "euclidean_l2"] = "cosine"

# Default acceptance threshold for cosine similarity (range -1..1, higher
# = more similar). This is overridden at runtime by the calibrated value
# in CALIBRATED_THRESHOLD_FILE once evaluate_model.ipynb has been run.
DEFAULT_COSINE_SIMILARITY_THRESHOLD: float = 0.68

# Confidence is derived from similarity via a simple linear rescaling
# between these two similarity bounds -> [0.0, 1.0] confidence range.
CONFIDENCE_LOW_SIMILARITY_BOUND: float = 0.40
CONFIDENCE_HIGH_SIMILARITY_BOUND: float = 0.90

MAX_AUTH_RETRIES: int = 3

# When multiple faces are visible in a single frame (multi-person
# authentication), the module authenticates every detected face rather
# than only the largest one.
MULTI_PERSON_AUTH_ENABLED: bool = True


def load_calibrated_threshold() -> float:
    """Return the calibrated cosine-similarity threshold produced by
    trainer.py / evaluate_model.ipynb, falling back to the static
    default above if calibration has not been run yet.
    """
    import json

    if CALIBRATED_THRESHOLD_FILE.exists():
        try:
            with open(CALIBRATED_THRESHOLD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return float(data.get("threshold", DEFAULT_COSINE_SIMILARITY_THRESHOLD))
        except (json.JSONDecodeError, ValueError, OSError):
            return DEFAULT_COSINE_SIMILARITY_THRESHOLD
    return DEFAULT_COSINE_SIMILARITY_THRESHOLD


# ---------------------------------------------------------------------------
# Webcam / real-time inference configuration
# ---------------------------------------------------------------------------
WEBCAM_DEVICE_INDEX: int = 0
WEBCAM_FRAME_WIDTH: int = 640
WEBCAM_FRAME_HEIGHT: int = 480
WEBCAM_AUTH_SAMPLING_INTERVAL_SECONDS: float = 1.0
FACE_TRACKING_MAX_DISAPPEARED_FRAMES: int = 15  # frames a tracked face may go undetected before its ID is dropped
FACE_TRACKING_IOU_MATCH_THRESHOLD: float = 0.3


# ---------------------------------------------------------------------------
# Logging configuration (module-local; independent of the main backend's
# root-level logging.py so this module remains fully standalone / can be
# executed from notebooks without the rest of the project on sys.path).
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("FACE_AUTH_LOG_LEVEL", "INFO")
LOG_DIR: Path = MODULE_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class FaceAuthConfig:
    """Immutable snapshot of the module configuration, for passing
    around explicitly (e.g. into classes) instead of relying on
    module-level globals everywhere. Constructed on demand via
    `get_config()`.
    """
    active_dataset: str = ACTIVE_DATASET
    active_embedding_model: str = ACTIVE_EMBEDDING_MODEL
    embedding_dim: int = field(default_factory=get_active_embedding_dim)
    target_image_size: tuple[int, int] = TARGET_IMAGE_SIZE
    face_detector_backend: str = FACE_DETECTOR_BACKEND
    similarity_metric: str = SIMILARITY_METRIC
    similarity_threshold: float = field(default_factory=load_calibrated_threshold)
    min_enrollment_images: int = MIN_ENROLLMENT_IMAGES_PER_STUDENT
    max_enrollment_images: int = MAX_ENROLLMENT_IMAGES_PER_STUDENT


def get_config() -> FaceAuthConfig:
    """Return a fresh, immutable configuration snapshot (re-reads the
    calibrated threshold from disk each call, so this reflects the
    latest calibration without needing a process restart).
    """
    return FaceAuthConfig()
