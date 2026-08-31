"""
config.py
---------
Centralized configuration for Module 5 — Object Detection.

Every path, threshold, and hyperparameter used by detector.py, tracker.py,
predictor.py, trainer.py, utils.py, and every notebook in this module is
defined here. Nothing downstream hardcodes a path or a magic number.

Follows the same layout convention as Modules 1-4 (see
ml/training/emotion_model/config.py): this file resolves REPO_ROOT
relative to its own location, so the module works unmodified whether run
locally, in Colab/Kaggle, or from within the full repo checkout.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------
# Project root resolution
# ---------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
MODULE_DIR = THIS_FILE.parent
REPO_ROOT = MODULE_DIR.parents[2]
REPO_ROOT = Path(os.environ.get("ENGAGEMENT_REPO_ROOT", str(REPO_ROOT)))

# ---------------------------------------------------------------------
# Dataset paths
# ---------------------------------------------------------------------
DATASETS_RAW_DIR = REPO_ROOT / "datasets" / "raw"
DATASETS_PROCESSED_DIR = REPO_ROOT / "datasets" / "processed" / "object_detection"

COCO_RAW_DIR = DATASETS_RAW_DIR / "coco2017"
COCO_TRAIN_IMAGES_DIR = COCO_RAW_DIR / "train2017"
COCO_VAL_IMAGES_DIR = COCO_RAW_DIR / "val2017"
COCO_ANNOTATIONS_DIR = COCO_RAW_DIR / "annotations"
COCO_TRAIN_ANNOTATIONS = COCO_ANNOTATIONS_DIR / "instances_train2017.json"
COCO_VAL_ANNOTATIONS = COCO_ANNOTATIONS_DIR / "instances_val2017.json"

# Optional supplementary sources (off by default — see README "Dataset"
# section for why COCO alone is the practical default for a *pretrained*
# detector, and when these are worth enabling).
OPEN_IMAGES_RAW_DIR = DATASETS_RAW_DIR / "open_images_v7"
ROBOFLOW_CLASSROOM_RAW_DIR = DATASETS_RAW_DIR / "roboflow_classroom"

USE_COCO = True
USE_OPEN_IMAGES = False
USE_ROBOFLOW_CLASSROOM = False

# Processed, YOLO-format dataset (images/ + labels/ per split + manifest.csv)
PROCESSED_TRAIN_DIR = DATASETS_PROCESSED_DIR / "train"
PROCESSED_VAL_DIR = DATASETS_PROCESSED_DIR / "val"
PROCESSED_TEST_DIR = DATASETS_PROCESSED_DIR / "test"
MANIFEST_CSV_PATH = DATASETS_PROCESSED_DIR / "manifest.csv"
DATASET_YAML_PATH = DATASETS_PROCESSED_DIR / "dataset.yaml"
DATASET_STATS_PATH = DATASETS_PROCESSED_DIR / "dataset_statistics.json"

TRAIN_VAL_TEST_SPLIT = (0.8, 0.1, 0.1)  # only used when re-splitting COCO val2017 into val/test
RANDOM_SEED = 42

# Development-time subsampling: cap how many images preprocessing /
# evaluation touch, so notebooks stay runnable on a laptop. Set to None
# for the full dataset.
MAX_SAMPLES_DEV = 2000

# ---------------------------------------------------------------------
# Model weights
# ---------------------------------------------------------------------
MODELS_DIR = REPO_ROOT / "models" / "object_detection"  # actually created by ensure_directories()

# Primary: YOLOv11, COCO-pretrained. Ultralytics auto-downloads these
# weight files on first use (cached under ~/.cache or the CWD) — no
# manual download step required.
PRIMARY_WEIGHTS_ACCURACY = "yolo11m.pt"   # higher accuracy, used when PERFORMANCE_MODE == "accuracy"
PRIMARY_WEIGHTS_SPEED = "yolo11n.pt"      # CPU real-time, used when PERFORMANCE_MODE == "speed"

# Fallback if YOLOv11 weights are unavailable in the installed
# `ultralytics` version (e.g. an older pin) — detector.py tries
# PRIMARY_* first and falls back to these automatically.
FALLBACK_WEIGHTS_ACCURACY = "yolov8m.pt"
FALLBACK_WEIGHTS_SPEED = "yolov8n.pt"

# Optional secondary model for extended classroom-object vocabulary
# beyond COCO-80 (see README "Class coverage" section). Also a stock
# pretrained release — no custom training involved.
OIV7_WEIGHTS = "yolov8x-oiv7.pt"
USE_OIV7_SECONDARY_MODEL = False

# "accuracy" -> PRIMARY_WEIGHTS_ACCURACY; "speed" -> PRIMARY_WEIGHTS_SPEED
PERFORMANCE_MODE = "speed"  # default to CPU-real-time-friendly, per the "must work efficiently on CPU" requirement

LOCAL_WEIGHTS_DIR = MODELS_DIR / "weights"  # where downloaded .pt files are cached, if redirected here

# ---------------------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.35
NMS_IOU_THRESHOLD = 0.45
MAX_DETECTIONS_PER_IMAGE = 100
INFERENCE_IMAGE_SIZE = 640  # YOLO's native training resolution; smaller (e.g. 480) trades accuracy for CPU speed
DEVICE = "cpu"  # "cpu" | "cuda:0" | "mps" — detector.py auto-falls-back to cpu if the requested device is unavailable
HALF_PRECISION = False  # only meaningful on CUDA; ignored on CPU

# ---------------------------------------------------------------------
# Target classroom taxonomy (17 classes, per spec)
# ---------------------------------------------------------------------
TARGET_CLASSES: list[str] = [
    "Person",
    "Cell Phone",
    "Laptop",
    "Book",
    "Notebook",
    "Pen",
    "Bottle",
    "Cup",
    "Chair",
    "Backpack",
    "Keyboard",
    "Mouse",
    "Monitor",
    "Tablet",
    "Calculator",
    "Headphones",
    "Unknown Object",
]
UNKNOWN_CLASS_NAME = "Unknown Object"
PERSON_CLASS_NAME = "Person"

# Which target classes represent a "student/person" for occupancy and
# count-based reasoning (kept as a set in case a future revision adds a
# separate "Teacher" role class fed in from Face Authentication).
PERSON_LIKE_CLASSES = {PERSON_CLASS_NAME}
# Classes a person can plausibly be "using" for interaction inference.
INTERACTABLE_CLASSES = {"Cell Phone", "Book", "Notebook", "Laptop", "Bottle", "Cup", "Headphones", "Tablet"}
SEATING_CLASS_NAME = "Chair"

# COCO-80 class name -> target taxonomy name. Only exact, unambiguous
# matches are included; "tv" is used as the closest available visual
# proxy for "Monitor" (COCO has no dedicated computer-monitor class).
# Anything COCO detects that is NOT a key here is bucketed to
# UNKNOWN_CLASS_NAME by detector.py (not silently dropped), so a
# real-but-unlabeled object still surfaces to the caller.
COCO_NAME_TO_TARGET: dict[str, str] = {
    "person": "Person",
    "cell phone": "Cell Phone",
    "laptop": "Laptop",
    "book": "Book",
    "bottle": "Bottle",
    "cup": "Cup",
    "chair": "Chair",
    "backpack": "Backpack",
    "keyboard": "Keyboard",
    "mouse": "Mouse",
    "tv": "Monitor",
}
# NOTE: COCO-80 has NO equivalent class for Notebook (as distinct from
# Book), Pen, Tablet, Calculator, or Headphones. With only the COCO-
# pretrained primary model loaded, detections of these physical objects
# will either be missed or (if a COCO class visually resembles them)
# mis-mapped — they do NOT silently appear as correctly labeled. Enable
# USE_OIV7_SECONDARY_MODEL for partial additional coverage; see README.

# Open Images V7 class name (as published by Ultralytics' yolov8x-oiv7.pt
# `model.names`) -> target taxonomy name. This mapping is validated at
# runtime by detector.py against the actually-loaded model's class list
# (detector.validate_class_mapping) — any entry below whose source name
# is NOT present in the loaded model is logged as unsupported rather than
# silently ignored, since OIV7's exact taxonomy strings should be
# confirmed against the installed model rather than assumed from memory.
OIV7_NAME_TO_TARGET: dict[str, str] = {
    "Person": "Person",
    "Mobile phone": "Cell Phone",
    "Laptop": "Laptop",
    "Book": "Book",
    "Pen": "Pen",
    "Bottle": "Bottle",
    "Coffee cup": "Cup",
    "Mug": "Cup",
    "Chair": "Chair",
    "Backpack": "Backpack",
    "Computer keyboard": "Keyboard",
    "Computer mouse": "Mouse",
    "Computer monitor": "Monitor",
    "Tablet computer": "Tablet",
    "Calculator": "Calculator",
    "Headphones": "Headphones",
}

CLASS_TO_INDEX: dict[str, int] = {name: i for i, name in enumerate(TARGET_CLASSES)}

# ---------------------------------------------------------------------
# Tracking
# ---------------------------------------------------------------------
TRACKER_PRIMARY = "bytetrack.yaml"   # Ultralytics built-in ByteTrack config
TRACKER_FALLBACK = "botsort.yaml"    # Ultralytics built-in BoT-SORT config
USE_CUSTOM_IOU_TRACKER_FALLBACK = True  # last-resort fallback if neither Ultralytics tracker is usable

TRACK_PERSIST = True  # persist track state across sequential .track() calls on a video/stream
CUSTOM_TRACKER_IOU_THRESHOLD = 0.3
CUSTOM_TRACKER_MAX_MISSED_FRAMES = 15

# ---------------------------------------------------------------------
# Event / interaction heuristics (documented as heuristics, not ground truth)
# ---------------------------------------------------------------------
CHAIR_OCCUPANCY_IOU_THRESHOLD = 0.15     # person-bbox / chair-bbox overlap to call a chair "occupied"
INTERACTION_DISTANCE_THRESHOLD_PX = 60   # max bbox-edge distance (px, at INFERENCE_IMAGE_SIZE) to call an object "in use"
SITTING_ASPECT_RATIO_THRESHOLD = 1.15    # bbox height/width above this -> "standing" heuristic; below -> "sitting"
TRACK_ABSENCE_FRAMES_FOR_LEFT_EVENT = 10  # frames a track must be missing before emitting "person_left"

# ---------------------------------------------------------------------
# Performance targets (used by evaluate_model.ipynb to report pass/fail —
# see README "Honest Performance Expectations" for what a stock,
# non-fine-tuned pretrained detector realistically achieves on COCO)
# ---------------------------------------------------------------------
TARGET_DETECTION_ACCURACY = 0.95
TARGET_PRECISION = 0.90
TARGET_RECALL = 0.90
TARGET_F1 = 0.90
TARGET_MAP50 = 0.90
TARGET_FPS_CPU = 10.0

# ---------------------------------------------------------------------
# Evaluation / output paths
# ---------------------------------------------------------------------
EVAL_DIR = MODULE_DIR / "evaluation_artifacts"
EVAL_METRICS_JSON = EVAL_DIR / "metrics_summary.json"
EVAL_CONFUSION_MATRIX_PNG = EVAL_DIR / "confusion_matrix.png"
EVAL_PR_CURVE_PNG = EVAL_DIR / "pr_curve.png"
EVAL_LATENCY_REPORT_JSON = EVAL_DIR / "latency_report.json"
EVAL_PER_CLASS_METRICS_CSV = EVAL_DIR / "per_class_metrics.csv"
EVAL_COUNT_ACCURACY_JSON = EVAL_DIR / "count_accuracy.json"
EVAL_ULTRALYTICS_RUN_DIR = EVAL_DIR / "ultralytics_val_run"

INFERENCE_OUTPUT_DIR = MODULE_DIR / "inference_outputs"

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FILE_PATH = MODULE_DIR / "object_detection.log"


@dataclass
class VisualizationConfig:
    """Grouped, adjustable visualization settings for predictor.py's
    overlay drawing — kept as a dataclass (rather than more module-level
    constants) since these are logically one cohesive settings object
    passed around together."""

    box_thickness: int = 2
    font_scale: float = 0.55
    font_thickness: int = 1
    show_confidence: bool = True
    show_track_id: bool = True
    show_class_name: bool = True
    show_person_count: bool = True
    show_object_count: bool = True
    show_fps: bool = True
    show_latency: bool = True
    box_color_by_class: bool = True
    default_box_color: tuple[int, int, int] = (0, 200, 0)  # BGR
    text_color: tuple[int, int, int] = (255, 255, 255)     # BGR
    hud_background_color: tuple[int, int, int] = (0, 0, 0)  # BGR
    hud_alpha: float = 0.5


VISUALIZATION = VisualizationConfig()


def ensure_directories() -> None:
    """Create every directory this module reads/writes, if missing."""
    for d in (
        COCO_RAW_DIR,
        COCO_TRAIN_IMAGES_DIR,
        COCO_VAL_IMAGES_DIR,
        COCO_ANNOTATIONS_DIR,
        OPEN_IMAGES_RAW_DIR,
        ROBOFLOW_CLASSROOM_RAW_DIR,
        DATASETS_PROCESSED_DIR,
        PROCESSED_TRAIN_DIR / "images",
        PROCESSED_TRAIN_DIR / "labels",
        PROCESSED_VAL_DIR / "images",
        PROCESSED_VAL_DIR / "labels",
        PROCESSED_TEST_DIR / "images",
        PROCESSED_TEST_DIR / "labels",
        MODELS_DIR,
        LOCAL_WEIGHTS_DIR,
        EVAL_DIR,
        EVAL_ULTRALYTICS_RUN_DIR,
        INFERENCE_OUTPUT_DIR,
    ):
        Path(d).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_directories()
    print(f"REPO_ROOT               = {REPO_ROOT}")
    print(f"DATASETS_PROCESSED_DIR   = {DATASETS_PROCESSED_DIR}")
    print(f"MODELS_DIR               = {MODELS_DIR}")
    print(f"PERFORMANCE_MODE         = {PERFORMANCE_MODE}")
    print(f"TARGET_CLASSES ({len(TARGET_CLASSES)})    = {TARGET_CLASSES}")
    print("All directories ensured to exist.")
