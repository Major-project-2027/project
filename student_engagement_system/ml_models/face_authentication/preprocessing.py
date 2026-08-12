"""
Face image preprocessing and quality-gating for the Face Authentication subsystem.
"""
from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QualityReport:
    """Result of running all quality checks on a face crop."""
    passed: bool
    blur_score: float
    brightness: float
    face_size: Tuple[int, int]
    reasons: list


def pad_to_square(image: np.ndarray) -> np.ndarray:
    """Pad an image with black borders so it becomes square, avoiding
    distortion when it is later resized to a fixed model input size.

    Args:
        image: Source BGR image.

    Returns:
        A square, zero-padded copy of ``image``.
    """
    h, w = image.shape[:2]
    size = max(h, w)
    top = (size - h) // 2
    bottom = size - h - top
    left = (size - w) // 2
    right = size - w - left
    return cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))


def preprocess_face(image: np.ndarray, target_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
    """Pad, resize, and convert a face crop to normalized RGB, ready for embedding.

    Args:
        image: Cropped BGR face image.
        target_size: (width, height) expected by the embedding model.

    Returns:
        A float32 RGB array in [0, 1], shape (target_h, target_w, 3).
    """
    squared = pad_to_square(image)
    resized = cv2.resize(squared, target_size, interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    return normalized


def compute_blur_score(image: np.ndarray) -> float:
    """Variance of the Laplacian -- higher means sharper. Below ~80-100 on a
    typical webcam face crop usually indicates motion blur or defocus.

    Args:
        image: BGR or grayscale image.

    Returns:
        The blur score (variance of Laplacian).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def compute_brightness(image: np.ndarray) -> float:
    """Mean pixel brightness on a 0-255 grayscale scale.

    Args:
        image: BGR or grayscale image.

    Returns:
        Mean brightness value.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(gray.mean())


def check_quality(image: np.ndarray, min_blur: float = 60.0,
                   brightness_range: Tuple[float, float] = (40.0, 220.0),
                   min_face_size: Tuple[int, int] = (60, 60)) -> QualityReport:
    """Run every quality gate on a raw (un-preprocessed) face crop.

    Args:
        image: Cropped BGR face image, before padding/resizing/normalization.
        min_blur: Minimum acceptable blur score (variance of Laplacian).
        brightness_range: Acceptable (min, max) mean brightness.
        min_face_size: Minimum acceptable (width, height) in pixels.

    Returns:
        A QualityReport describing whether the crop passed and why (if not).
    """
    reasons = []
    h, w = image.shape[:2]

    blur_score = compute_blur_score(image)
    if blur_score < min_blur:
        reasons.append(f"too blurry (blur_score={blur_score:.1f} < {min_blur})")

    brightness = compute_brightness(image)
    if not (brightness_range[0] <= brightness <= brightness_range[1]):
        reasons.append(f"poor lighting (brightness={brightness:.1f}, expected "
                        f"{brightness_range[0]}-{brightness_range[1]})")

    if w < min_face_size[0] or h < min_face_size[1]:
        reasons.append(f"face too small ({w}x{h} < {min_face_size[0]}x{min_face_size[1]})")

    passed = len(reasons) == 0
    if not passed:
        logger.debug(f"Quality check failed: {reasons}")

    return QualityReport(passed=passed, blur_score=blur_score, brightness=brightness,
                          face_size=(w, h), reasons=reasons)
