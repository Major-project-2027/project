"""
config.py
---------
Centralized configuration for the Emotion Detection module.

Every notebook and script in this folder (train_model, evaluate_model,
inference, trainer.py, predictor.py) imports its paths and hyperparameters
from here so there is exactly one place to change them.

Folder context (already created in Phase 1):
    student-engagement-system/
        datasets/raw/            <- FER2013 archive/csv lands here
        datasets/processed/      <- preprocessed .npy tensors land here
        models/emotion/          <- final .keras model is exported here
        ml/training/emotion_model/  <- THIS module lives here
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------
# Project root resolution
# ---------------------------------------------------------------------
# This file lives at: <repo_root>/ml/training/emotion_model/config.py
# So the repo root is 3 levels up.
THIS_FILE = Path(__file__).resolve()
MODULE_DIR = THIS_FILE.parent
REPO_ROOT = MODULE_DIR.parents[2]

# Allow override via environment variable (useful in Colab/Kaggle where
# the repo may be cloned to an arbitrary path).
REPO_ROOT = Path(os.environ.get("ENGAGEMENT_REPO_ROOT", str(REPO_ROOT)))

# ---------------------------------------------------------------------
# Dataset paths
# ---------------------------------------------------------------------
DATASETS_RAW_DIR = REPO_ROOT / "datasets" / "raw" / "fer2013"
DATASETS_PROCESSED_DIR = REPO_ROOT / "datasets" / "processed" / "fer2013"

# The canonical FER2013 single-CSV distribution (Kaggle: "fer2013.csv")
# has columns: emotion, pixels, Usage
FER_CSV_PATH = DATASETS_RAW_DIR / "fer2013.csv"

# Some Kaggle mirrors distribute FER2013 as train/ and test/ folders of
# images instead of a single CSV (e.g. "Face expression recognition
# dataset"). Both layouts are supported by dataset_preprocessing.ipynb.
FER_IMAGE_TRAIN_DIR = DATASETS_RAW_DIR / "train"
FER_IMAGE_TEST_DIR = DATASETS_RAW_DIR / "test"

# Preprocessed, ready-to-train tensors (created by dataset_preprocessing.ipynb)
X_TRAIN_PATH = DATASETS_PROCESSED_DIR / "X_train.npy"
Y_TRAIN_PATH = DATASETS_PROCESSED_DIR / "y_train.npy"
X_VAL_PATH = DATASETS_PROCESSED_DIR / "X_val.npy"
Y_VAL_PATH = DATASETS_PROCESSED_DIR / "y_val.npy"
X_TEST_PATH = DATASETS_PROCESSED_DIR / "X_test.npy"
Y_TEST_PATH = DATASETS_PROCESSED_DIR / "y_test.npy"

# ---------------------------------------------------------------------
# Model output paths
# ---------------------------------------------------------------------
MODELS_DIR = REPO_ROOT / "models" / "emotion"
BEST_MODEL_PATH = MODELS_DIR / "emotion_model.keras"
CHECKPOINT_DIR = MODELS_DIR / "checkpoints"
LABEL_MAP_PATH = MODELS_DIR / "label_map.json"

# Evaluation artifacts
EVAL_DIR = MODULE_DIR / "evaluation_artifacts"
CONFUSION_MATRIX_PATH = EVAL_DIR / "confusion_matrix.png"
ACCURACY_PLOT_PATH = EVAL_DIR / "accuracy_curve.png"
LOSS_PLOT_PATH = EVAL_DIR / "loss_curve.png"
CLASSIFICATION_REPORT_PATH = EVAL_DIR / "classification_report.txt"
TRAINING_HISTORY_PATH = EVAL_DIR / "training_history.json"

# ---------------------------------------------------------------------
# FER2013 class labels (fixed order used by the canonical dataset)
# ---------------------------------------------------------------------
CLASS_NAMES = [
    "angry",
    "disgust",
    "fear",
    "happy",
    "sad",
    "surprise",
    "neutral",
]
NUM_CLASSES = len(CLASS_NAMES)

# The wider system (Section 4.1 / FR-4 of the architecture doc) targets
# a simplified emotion set: Happy / Neutral / Sad / Angry / Confused / Tired.
# FER2013 does not have "Confused" or "Tired" labels, so at inference time
# we optionally remap the 7 FER classes onto that simplified set. This
# mapping is documentation-only for now; predictor.py exposes both the
# raw FER label and the simplified label.
SIMPLIFIED_LABEL_MAP = {
    "angry": "Angry",
    "disgust": "Angry",       # closest proxy in the simplified set
    "fear": "Confused",       # closest proxy in the simplified set
    "happy": "Happy",
    "sad": "Sad",
    "surprise": "Confused",   # closest proxy in the simplified set
    "neutral": "Neutral",
}

# ---------------------------------------------------------------------
# Image / model hyperparameters
# ---------------------------------------------------------------------
# FER2013 native resolution is 48x48 grayscale. MobileNetV2 requires a
# minimum input of 32x32 and 3 channels, so images are upsampled to
# IMG_SIZE and replicated across 3 channels during preprocessing.
FER_NATIVE_SIZE = 48
IMG_SIZE = 96          # good accuracy/latency trade-off for MobileNetV2
IMG_CHANNELS = 3
INPUT_SHAPE = (IMG_SIZE, IMG_SIZE, IMG_CHANNELS)

VALIDATION_SPLIT = 0.1   # carved out of the FER "Training" split
RANDOM_SEED = 42

# ---------------------------------------------------------------------
# Training hyperparameters
# ---------------------------------------------------------------------
BATCH_SIZE = 64
EPOCHS_HEAD = 15          # phase 1: train classifier head, base frozen
EPOCHS_FINE_TUNE = 15     # phase 2: unfreeze top base layers, fine-tune
LEARNING_RATE_HEAD = 1e-3
LEARNING_RATE_FINE_TUNE = 1e-5
FINE_TUNE_AT_LAYER = 100  # unfreeze base model layers from this index onward
EARLY_STOPPING_PATIENCE = 6
REDUCE_LR_PATIENCE = 3
DROPOUT_RATE = 0.3

# Class weighting: FER2013 is imbalanced (very few "disgust" samples),
# so trainer.py computes balanced class weights by default.
USE_CLASS_WEIGHTS = True


def ensure_directories() -> None:
    """Create every directory this module writes to, if missing."""
    for d in (
        DATASETS_RAW_DIR,
        DATASETS_PROCESSED_DIR,
        MODELS_DIR,
        CHECKPOINT_DIR,
        EVAL_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_directories()
    print(f"REPO_ROOT             = {REPO_ROOT}")
    print(f"DATASETS_RAW_DIR       = {DATASETS_RAW_DIR}")
    print(f"DATASETS_PROCESSED_DIR = {DATASETS_PROCESSED_DIR}")
    print(f"MODELS_DIR             = {MODELS_DIR}")
    print(f"BEST_MODEL_PATH        = {BEST_MODEL_PATH}")
    print("All directories ensured to exist.")
