"""
utils.py
--------
Shared, dependency-light helper functions for the Gaze & Head Pose
Estimation module.

Purpose
-------
Houses everything used by more than one of `landmark_detector.py`,
`gaze_estimator.py`, `headpose_estimator.py`, `blink_detector.py`,
`drowsiness_detector.py`, `face_quality.py`, `temporal_filter.py`,
`trainer.py`, and `predictor.py`: logging setup, dataset
availability auto-detection (Mode 2/3), small geometry/math helpers, and
frame-annotation drawing utilities.

No landmark detection, gaze/pose math models, or inference-loop logic
lives here — only generic plumbing.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from ml.training.gaze_headpose import config


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
_LOGGER_CONFIGURED = False


def get_logger(name: str = "gaze_headpose") -> logging.Logger:
    """
    Returns a module-wide logger writing to both console and
    `config.LOG_FILE_PATH`. Configured once per process.
    """
    global _LOGGER_CONFIGURED
    logger = logging.getLogger(name)

    if not _LOGGER_CONFIGURED:
        config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        logger.setLevel(config.LOG_LEVEL)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(config.LOG_FILE_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.propagate = False
        _LOGGER_CONFIGURED = True

    return logger


# ----------------------------------------------------------------------
# Dataset auto-detection (Mode 2 — Evaluation, Mode 3 — Optional Fine-Tuning)
# ----------------------------------------------------------------------
def resolve_dataset_dir(expected_path: Path) -> Optional[Path]:
    """
    Resolve a dataset directory, tolerating case differences between the
    registry's expected path (e.g. `datasets/raw/mpiigaze`, lowercase by
    convention) and how a dataset archive actually gets extracted on disk
    (e.g. "MPIIGaze", mixed case, which is how the official downloads are
    named). Returns the expected path if it exists as-is; otherwise
    searches its parent directory for a case-insensitive name match;
    returns None if neither is found.

    This does not change any behavior on case-insensitive filesystems
    (Windows, default macOS) but is required for correct detection on
    case-sensitive filesystems (Linux) and is harmless/idempotent
    everywhere.
    """
    if expected_path.exists():
        return expected_path

    parent = expected_path.parent
    if not parent.exists():
        return None

    target_name = expected_path.name.lower()
    for candidate in parent.iterdir():
        if candidate.is_dir() and candidate.name.lower() == target_name:
            return candidate
    return None


def _looks_populated(path: Path) -> bool:
    """A dataset directory 'exists' if it is present and contains >= 1 file."""
    resolved = resolve_dataset_dir(path)
    if resolved is None or not resolved.is_dir():
        return False
    return any(resolved.rglob("*"))


def detect_available_evaluation_datasets() -> Dict[str, bool]:
    """
    Check `config.EVALUATION_DATASETS` and report which ones are actually
    present on disk. Never raises — used by notebooks/trainer to decide
    whether real-dataset evaluation is possible, falling back to a
    synthetic/instructional path otherwise.
    """
    return {name: _looks_populated(entry["path"]) for name, entry in config.EVALUATION_DATASETS.items()}


def detect_available_fine_tune_datasets() -> Dict[str, bool]:
    """Same as above, for the optional Mode 3 fine-tuning dataset registry."""
    return {
        name: _looks_populated(entry["path"])
        for name, entry in config.FINE_TUNE_DATASETS.items()
        if entry.get("enabled", False)
    }


def print_dataset_instructions() -> None:
    """
    Print clear, actionable instructions for obtaining each registered
    evaluation dataset. Called by notebooks when no dataset is found, so
    the notebook can continue gracefully instead of crashing.
    """
    print("No evaluation datasets were found under datasets/raw/.")
    print("This module works in Mode 1 (MediaPipe pretrained models) with")
    print("NO dataset at all — evaluation datasets are only needed for Mode 2.")
    print()
    print("To enable Mode 2 (quantitative evaluation against public datasets):")
    for name, entry in config.EVALUATION_DATASETS.items():
        print(f"  - {name}: {entry['description']}")
        print(f"      Homepage : {entry['homepage']}")
        print(f"      Expected path: {entry['path']}")
    print()
    print("Download the dataset(s) you want from the homepage(s) above and")
    print("place the extracted contents at the 'Expected path' shown, then")
    print("re-run this notebook.")


# ----------------------------------------------------------------------
# Geometry / math helpers
# ----------------------------------------------------------------------
def euclidean_distance(point_a: Iterable[float], point_b: Iterable[float]) -> float:
    a = np.asarray(point_a, dtype=np.float64)
    b = np.asarray(point_b, dtype=np.float64)
    return float(np.linalg.norm(a - b))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def rotation_matrix_to_euler_angles(rotation_matrix: np.ndarray) -> Tuple[float, float, float]:
    """
    Convert a 3x3 rotation matrix (from `cv2.Rodrigues`) to (pitch, yaw,
    roll) in degrees, using the standard aerospace (X-Y-Z) convention.
    """
    sy = math.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        pitch = math.atan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = 0.0

    return math.degrees(pitch), math.degrees(yaw), math.degrees(roll)


def landmarks_to_pixel_coords(
    landmarks, image_width: int, image_height: int
) -> np.ndarray:
    """
    Convert a MediaPipe `NormalizedLandmarkList`-like iterable (objects
    with `.x`, `.y`, `.z` in [0, 1]) to an (N, 3) array of pixel-space
    (x, y) plus the original normalized z (relative depth).
    """
    coords = np.array(
        [(lm.x * image_width, lm.y * image_height, lm.z) for lm in landmarks],
        dtype=np.float64,
    )
    return coords


# ----------------------------------------------------------------------
# Timing helper (used for latency/FPS evaluation)
# ----------------------------------------------------------------------
@dataclass
class Stopwatch:
    """Minimal context-manager stopwatch returning elapsed milliseconds."""

    label: str = ""
    elapsed_ms: float = 0.0

    def __enter__(self) -> "Stopwatch":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0


class FPSMeter:
    """Rolling FPS estimator over the last N frame timestamps."""

    def __init__(self, window: int = 30):
        self.window = window
        self._timestamps: List[float] = []

    def tick(self) -> float:
        now = time.perf_counter()
        self._timestamps.append(now)
        if len(self._timestamps) > self.window:
            self._timestamps.pop(0)
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        return (len(self._timestamps) - 1) / elapsed if elapsed > 0 else 0.0


# ----------------------------------------------------------------------
# Drawing / annotation helpers
# ----------------------------------------------------------------------
def draw_text_with_background(
    frame,
    text: str,
    origin: Tuple[int, int],
    color: Tuple[int, int, int] = (0, 200, 0),
    scale: float = 0.6,
) -> None:
    """Draw text with a filled background rectangle for readability on video frames."""
    import cv2

    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 2
    (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = origin
    cv2.rectangle(frame, (x - 2, y - text_h - 6), (x + text_w + 2, y + baseline), (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_landmarks_subset(frame, points_2d: np.ndarray, color=(0, 255, 255), radius: int = 1) -> None:
    """Draw a small circle for each 2D point (used for eye/iris/pose landmark overlays)."""
    import cv2

    for x, y in points_2d[:, :2].astype(int):
        cv2.circle(frame, (int(x), int(y)), radius, color, -1, lineType=cv2.LINE_AA)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
