"""
Shared helper functions for the Emotion Recognition subsystem: score
normalization, temporal smoothing, and session-level aggregation.
"""
from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

from ml_models.emotion_detection.emotion_labels import EMOTION_LABELS, validate_label
from utils.logger import get_logger

logger = get_logger(__name__)


def normalize_scores(raw_scores: Dict[str, float]) -> Dict[str, float]:
    """Normalize a raw per-class score dict into a probability distribution.

    Args:
        raw_scores: Mapping of emotion label -> raw score (e.g. percentages
            from DeepFace, which do not always sum to exactly 100).

    Returns:
        A new dict with the same keys, values rescaled to sum to 1.0.

    Raises:
        ValueError: If raw_scores is empty or every value is zero.
    """
    if not raw_scores:
        raise ValueError("raw_scores must not be empty.")
    total = sum(raw_scores.values())
    if total <= 0:
        raise ValueError("raw_scores must contain at least one positive value.")
    return {label: value / total for label, value in raw_scores.items()}


def top_emotion(scores: Dict[str, float]) -> Tuple[str, float]:
    """Return the (label, confidence) pair with the highest score.

    Args:
        scores: Mapping of emotion label -> score (normalized or raw).

    Returns:
        A (label, confidence) tuple for the highest-scoring emotion.

    Raises:
        ValueError: If scores is empty.
    """
    if not scores:
        raise ValueError("scores must not be empty.")
    label = max(scores, key=scores.get)
    return label, scores[label]


class EmotionSmoother:
    """Exponential-moving-average smoother for per-frame emotion scores.

    Reduces frame-to-frame flicker in live video by blending each new
    reading with the running average rather than trusting a single frame.

    Example:
        >>> smoother = EmotionSmoother(alpha=0.3)
        >>> smoothed = smoother.update({"happy": 0.9, "neutral": 0.1})
    """

    def __init__(self, alpha: float = 0.3) -> None:
        """
        Args:
            alpha: Weight given to the newest reading, in (0, 1]. Higher
                values track new readings faster; lower values smooth more.
        """
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must be in (0, 1].")
        self.alpha = alpha
        self._state: Optional[Dict[str, float]] = None

    def update(self, scores: Dict[str, float]) -> Dict[str, float]:
        """Blend a new frame's scores into the running smoothed estimate.

        Args:
            scores: This frame's (typically normalized) per-class scores.

        Returns:
            The updated smoothed score dict.
        """
        normalized = normalize_scores(scores)
        if self._state is None:
            self._state = dict(normalized)
        else:
            self._state = {
                label: self.alpha * normalized.get(label, 0.0)
                       + (1 - self.alpha) * self._state.get(label, 0.0)
                for label in EMOTION_LABELS
            }
        return dict(self._state)

    def reset(self) -> None:
        """Clear the smoother's running state (e.g. on a new session/student)."""
        self._state = None


@dataclass
class SessionEmotionSummary:
    """Aggregated emotion statistics over a sequence of frames."""
    dominant_emotion: str
    emotion_counts: Dict[str, int]
    emotion_percentages: Dict[str, float]
    num_frames: int


def summarize_session(frame_labels: List[str]) -> SessionEmotionSummary:
    """Aggregate a sequence of per-frame top-emotion labels into a summary.

    Args:
        frame_labels: List of emotion labels, one per analyzed frame
            (e.g. collected over a class session).

    Returns:
        A SessionEmotionSummary describing the dominant emotion and the
        full distribution.

    Raises:
        ValueError: If frame_labels is empty, or contains an unsupported label.
    """
    if not frame_labels:
        raise ValueError("frame_labels must not be empty.")
    validated = [validate_label(label) for label in frame_labels]
    counts = Counter(validated)
    total = len(validated)
    percentages = {label: (count / total) * 100.0 for label, count in counts.items()}
    dominant = counts.most_common(1)[0][0]
    return SessionEmotionSummary(
        dominant_emotion=dominant,
        emotion_counts=dict(counts),
        emotion_percentages=percentages,
        num_frames=total,
    )
