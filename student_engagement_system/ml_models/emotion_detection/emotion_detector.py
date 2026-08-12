"""
Emotion detection module built on DeepFace's bundled emotion (FER) backbone.
"""
import time
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from ml_models.emotion_detection.emotion_labels import EMOTION_LABELS
from ml_models.emotion_detection.emotion_utils import normalize_scores, top_emotion
from utils.logger import get_logger

logger = get_logger(__name__)


class EmotionAnalysisError(Exception):
    """Raised when an emotion prediction could not be generated for a face image."""


@dataclass
class EmotionResult:
    """Result of running emotion analysis on a single face image."""
    emotion: str
    confidence: float
    scores: Dict[str, float]
    processing_time_ms: float


class EmotionDetector:
    """Classifies a face crop into one of the 7 supported emotions.

    DeepFace is imported lazily inside __init__ so that modules which do
    not need emotion analysis never pay the TensorFlow/DeepFace import
    cost -- the same defensive pattern Phase 2's FaceEmbedder used for
    the Facenet512 embedding backbone.
    """

    def __init__(self, confidence_threshold: float = 0.4) -> None:
        """
        Args:
            confidence_threshold: Minimum top-emotion confidence (0-1) for
                a prediction to be considered reliable. Predictions below
                this threshold are still returned, but flagged via
                EmotionResult.confidence for the caller to act on.

        Raises:
            EmotionAnalysisError: If DeepFace/TensorFlow is not installed.
        """
        try:
            from deepface import DeepFace  # noqa: WPS433 -- deliberate lazy import
        except ImportError as exc:
            raise EmotionAnalysisError(
                "DeepFace is not installed. Run `pip install deepface tensorflow` "
                "(see Phase 1 Section 4 special-installation notes)."
            ) from exc

        self._DeepFace = DeepFace
        self.confidence_threshold = confidence_threshold
        # Trigger a one-time model build/download so later calls are fast.
        try:
            self._DeepFace.build_model("Emotion")
        except Exception as exc:  # noqa: BLE001 -- DeepFace raises assorted exception types
            raise EmotionAnalysisError(f"Failed to load the DeepFace Emotion model: {exc}") from exc
        logger.info("EmotionDetector ready -- backbone=DeepFace Emotion (7-class FER)")

    def analyze(self, face_bgr: np.ndarray) -> EmotionResult:
        """Predict the emotion of a single face image.

        Args:
            face_bgr: Cropped face region, BGR uint8, as produced by
                Phase 2's face detection (detection/quality gating is the
                caller's responsibility -- this method trusts its input).

        Returns:
            An EmotionResult with the top emotion, its confidence, the
            full 7-class score distribution, and processing time in ms.

        Raises:
            EmotionAnalysisError: If DeepFace fails to produce a prediction.
        """
        if face_bgr is None or face_bgr.size == 0:
            raise EmotionAnalysisError("Received an empty face image.")

        start = time.perf_counter()
        try:
            result = self._DeepFace.analyze(
                img_path=face_bgr,
                actions=["emotion"],
                enforce_detection=False,  # we already ran our own MediaPipe detector
                detector_backend="skip",
            )
        except Exception as exc:  # noqa: BLE001 -- DeepFace raises assorted exception types
            raise EmotionAnalysisError(f"DeepFace failed to analyze emotion: {exc}") from exc
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        payload = result[0] if isinstance(result, list) else result
        raw_scores = payload.get("emotion")
        if not raw_scores:
            raise EmotionAnalysisError("DeepFace returned no emotion scores for the given face.")

        scores = normalize_scores({k.lower(): float(v) for k, v in raw_scores.items()})
        missing = set(EMOTION_LABELS) - set(scores)
        for label in missing:
            scores[label] = 0.0

        label, confidence = top_emotion(scores)
        if confidence < self.confidence_threshold:
            logger.info(
                f"Emotion prediction below confidence threshold: {label}={confidence:.3f} "
                f"< {self.confidence_threshold}"
            )

        return EmotionResult(
            emotion=label, confidence=confidence, scores=scores, processing_time_ms=elapsed_ms,
        )

    def analyze_safe(self, face_bgr: np.ndarray) -> Optional[EmotionResult]:
        """Same as analyze(), but returns None instead of raising.

        Useful in real-time loops where one bad frame must never stop
        the pipeline -- exactly the "never crash" requirement for this
        module.

        Args:
            face_bgr: Cropped face region, BGR uint8.

        Returns:
            An EmotionResult, or None if analysis failed for any reason.
        """
        try:
            return self.analyze(face_bgr)
        except EmotionAnalysisError as exc:
            logger.warning(f"analyze_safe: emotion analysis failed, returning None -- {exc}")
            return None
