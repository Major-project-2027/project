"""
utils.py
--------
Shared helper functions used across the emotion-detection notebooks and
scripts: reproducibility, FER2013 CSV <-> tensor conversion, plotting,
and small I/O helpers.

Kept dependency-light (numpy, pandas, matplotlib, sklearn, PIL) so it can
be imported from Colab/Kaggle notebooks as well as the local repo.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Iterable

import numpy as np

from config import (
    CLASS_NAMES,
    FER_NATIVE_SIZE,
    IMG_SIZE,
    NUM_CLASSES,
    RANDOM_SEED,
)


# ---------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------
def set_global_seed(seed: int = RANDOM_SEED) -> None:
    """Seed python, numpy, and (if importable) tensorflow for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import tensorflow as tf

        tf.random.set_seed(seed)
    except ImportError:
        pass


# ---------------------------------------------------------------------
# FER2013 CSV parsing
# ---------------------------------------------------------------------
def parse_fer_pixel_string(pixel_string: str) -> np.ndarray:
    """Convert a FER2013 CSV 'pixels' cell (space-separated ints) into a
    (48, 48) uint8 grayscale array."""
    values = np.fromstring(pixel_string, dtype=np.uint8, sep=" ")
    return values.reshape(FER_NATIVE_SIZE, FER_NATIVE_SIZE)


def grayscale_to_model_input(gray_48x48: np.ndarray, img_size: int = IMG_SIZE) -> np.ndarray:
    """Resize a (48, 48) grayscale array to (img_size, img_size, 3) float32
    in [0, 1], replicating the single channel across RGB so it is
    compatible with MobileNetV2's expected 3-channel input."""
    import cv2

    resized = cv2.resize(gray_48x48, (img_size, img_size), interpolation=cv2.INTER_AREA)
    rgb = np.repeat(resized[..., np.newaxis], 3, axis=-1)
    return rgb.astype("float32") / 255.0


def one_hot(labels: Iterable[int], num_classes: int = NUM_CLASSES) -> np.ndarray:
    labels = np.asarray(list(labels), dtype=np.int64)
    eye = np.eye(num_classes, dtype="float32")
    return eye[labels]


# ---------------------------------------------------------------------
# Small JSON helpers
# ---------------------------------------------------------------------
def save_json(obj, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def load_json(path: Path):
    with open(path, "r") as f:
        return json.load(f)


def save_label_map(path: Path, class_names: list[str] = CLASS_NAMES) -> None:
    """Persist the index->label mapping alongside the exported model so
    predictor.py never has to hardcode class order."""
    save_json({str(i): name for i, name in enumerate(class_names)}, path)


# ---------------------------------------------------------------------
# Plotting (matplotlib, no seaborn dependency required)
# ---------------------------------------------------------------------
def plot_training_curves(history_dict: dict, accuracy_out: Path, loss_out: Path) -> None:
    """Save accuracy and loss curves (train vs val) as separate PNGs.

    history_dict is expected to look like a keras History.history dict:
    {"accuracy": [...], "val_accuracy": [...], "loss": [...], "val_loss": [...]}
    """
    import matplotlib.pyplot as plt

    # Accuracy
    plt.figure(figsize=(8, 5))
    if "accuracy" in history_dict:
        plt.plot(history_dict["accuracy"], label="train_accuracy")
    if "val_accuracy" in history_dict:
        plt.plot(history_dict["val_accuracy"], label="val_accuracy")
    plt.title("Emotion Model — Accuracy over Epochs")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.legend()
    plt.grid(alpha=0.3)
    Path(accuracy_out).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(accuracy_out, bbox_inches="tight", dpi=150)
    plt.close()

    # Loss
    plt.figure(figsize=(8, 5))
    if "loss" in history_dict:
        plt.plot(history_dict["loss"], label="train_loss")
    if "val_loss" in history_dict:
        plt.plot(history_dict["val_loss"], label="val_loss")
    plt.title("Emotion Model — Loss over Epochs")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.legend()
    plt.grid(alpha=0.3)
    Path(loss_out).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(loss_out, bbox_inches="tight", dpi=150)
    plt.close()


def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_names: list[str],
    out_path: Path,
    normalize: bool = True,
) -> np.ndarray:
    """Compute and save a confusion matrix heatmap. Returns the matrix."""
    from sklearn.metrics import confusion_matrix
    import matplotlib.pyplot as plt

    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))
    cm_display = cm.astype("float") / cm.sum(axis=1, keepdims=True) if normalize else cm
    cm_display = np.nan_to_num(cm_display)

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(cm_display, interpolation="nearest", cmap="Blues")
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(len(class_names)),
        yticks=np.arange(len(class_names)),
        xticklabels=class_names,
        yticklabels=class_names,
        ylabel="True label",
        xlabel="Predicted label",
        title="Emotion Model — Confusion Matrix" + (" (normalized)" if normalize else ""),
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    fmt = ".2f" if normalize else "d"
    thresh = cm_display.max() / 2.0
    for i in range(cm_display.shape[0]):
        for j in range(cm_display.shape[1]):
            ax.text(
                j,
                i,
                format(cm_display[i, j], fmt),
                ha="center",
                va="center",
                color="white" if cm_display[i, j] > thresh else "black",
                fontsize=8,
            )

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return cm


# ---------------------------------------------------------------------
# Class weights (FER2013 is imbalanced — "disgust" has very few samples)
# ---------------------------------------------------------------------
def compute_class_weights(y_integer_labels: np.ndarray, num_classes: int = NUM_CLASSES) -> dict:
    from sklearn.utils.class_weight import compute_class_weight

    present_classes = np.unique(y_integer_labels)
    weights = compute_class_weight(
        class_weight="balanced", classes=present_classes, y=y_integer_labels
    )
    weight_map = {int(c): float(w) for c, w in zip(present_classes, weights)}
    # any class entirely absent from y (shouldn't happen with full FER2013)
    for c in range(num_classes):
        weight_map.setdefault(c, 1.0)
    return weight_map
