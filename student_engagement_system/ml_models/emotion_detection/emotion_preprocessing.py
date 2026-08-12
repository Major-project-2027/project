"""
Face-crop preprocessing for the Emotion Recognition subsystem.

Quality gating (blur/brightness/size) is deliberately NOT reimplemented
here -- it is reused directly from Phase 2's
ml_models.face_authentication.preprocessing module, so a face crop is
held to the exact same quality bar before either embedding (Phase 2)
or emotion analysis (Phase 3).
"""
from typing import Tuple

import cv2
import numpy as np

from ml_models.face_authentication.preprocessing import check_quality, pad_to_square, QualityReport
from utils.logger import get_logger

logger = get_logger(__name__)


class EmotionPreprocessingError(Exception):
    """Raised when a face crop cannot be prepared for emotion analysis."""


def preprocess_for_emotion(
    face_bgr: np.ndarray,
    target_size: Tuple[int, int] = (48, 48),
    grayscale: bool = True,
    enforce_quality: bool = True,
) -> np.ndarray:
    """Prepare a raw BGR face crop for emotion classification.

    Args:
        face_bgr: Cropped face region straight from face detection, BGR uint8.
        target_size: (width, height) the emotion model expects. Defaults to
            48x48, the classic FER-2013 input size.
        grayscale: If True (default), convert to single-channel grayscale,
            matching the FER-2013 training format. If False, RGB is kept
            (DeepFace's own analyze() call handles color internally, so this
            flag mainly matters for custom/offline models).
        enforce_quality: If True (default), reject crops that fail Phase 2's
            check_quality() gate (too blurry, too dark/bright, too small).

    Returns:
        A float32 array normalized to [0, 1], shape (H, W) if grayscale else
        (H, W, 3).

    Raises:
        EmotionPreprocessingError: If the crop is empty, fails the quality
            gate (when enforced), or cannot be resized.
    """
    if face_bgr is None or face_bgr.size == 0:
        raise EmotionPreprocessingError("Received an empty face crop.")

    if enforce_quality:
        report: QualityReport = check_quality(face_bgr)
        if not report.passed:
            raise EmotionPreprocessingError(
                f"Face crop failed quality gate for emotion analysis: {report.reasons}"
            )

    squared = pad_to_square(face_bgr)

    try:
        resized = cv2.resize(squared, target_size, interpolation=cv2.INTER_AREA)
    except cv2.error as exc:
        raise EmotionPreprocessingError(f"Failed to resize face crop: {exc}") from exc

    if grayscale:
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        normalized = gray.astype(np.float32) / 255.0
    else:
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0

    return normalized


def to_model_input(normalized: np.ndarray) -> np.ndarray:
    """Add the batch (and channel, if grayscale) dimensions a CNN expects.

    Args:
        normalized: Output of preprocess_for_emotion(), shape (H, W) or (H, W, 3).

    Returns:
        A 4-D array of shape (1, H, W, 1) or (1, H, W, 3), ready for a
        batch-of-one CNN forward pass.
    """
    if normalized.ndim == 2:
        normalized = normalized[..., np.newaxis]
    return normalized[np.newaxis, ...]
