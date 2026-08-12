"""
Canonical emotion label definitions for the Emotion Recognition subsystem.

This is the single source of truth for the 7 emotion classes supported
throughout Phase 3 and consumed by later phases (engagement scoring,
cognitive state classification). Every other Phase 3 module imports
its label constants from here rather than hard-coding strings.
"""
from dataclasses import dataclass
from typing import Dict, List

from utils.logger import get_logger

logger = get_logger(__name__)


# Order matches the class order DeepFace's "Emotion" model reports scores in.
EMOTION_LABELS: List[str] = [
    "angry",
    "disgust",
    "fear",
    "happy",
    "sad",
    "surprise",
    "neutral",
]


@dataclass(frozen=True)
class EmotionMeta:
    """Display metadata for one emotion label."""
    label: str
    display_name: str
    icon: str
    polarity: str  # "positive" | "neutral" | "negative"


EMOTION_METADATA: Dict[str, EmotionMeta] = {
    "angry":    EmotionMeta("angry",    "Angry",    "😠", "negative"),
    "disgust":  EmotionMeta("disgust",  "Disgust",  "🤢", "negative"),
    "fear":     EmotionMeta("fear",     "Fear",     "😨", "negative"),
    "happy":    EmotionMeta("happy",    "Happy",    "🙂", "positive"),
    "sad":      EmotionMeta("sad",      "Sad",      "😢", "negative"),
    "surprise": EmotionMeta("surprise", "Surprise", "😮", "neutral"),
    "neutral":  EmotionMeta("neutral",  "Neutral",  "😐", "neutral"),
}


class InvalidEmotionLabelError(ValueError):
    """Raised when a label outside EMOTION_LABELS is used where a valid one is required."""


def is_valid_label(label: str) -> bool:
    """Check whether a string is one of the 7 supported emotion labels.

    Args:
        label: Candidate label, matched case-insensitively.

    Returns:
        True if the label is supported, False otherwise.
    """
    return label.lower() in EMOTION_LABELS


def validate_label(label: str) -> str:
    """Validate and normalize an emotion label to lowercase.

    Args:
        label: Candidate label.

    Returns:
        The normalized (lowercase) label.

    Raises:
        InvalidEmotionLabelError: If the label is not one of EMOTION_LABELS.
    """
    normalized = label.lower().strip()
    if normalized not in EMOTION_LABELS:
        raise InvalidEmotionLabelError(
            f"'{label}' is not a supported emotion label. Expected one of {EMOTION_LABELS}."
        )
    return normalized


def get_display_name(label: str) -> str:
    """Return the teacher-facing display name for an emotion label."""
    normalized = validate_label(label)
    return EMOTION_METADATA[normalized].display_name


def get_polarity(label: str) -> str:
    """Return the coarse polarity ("positive"/"neutral"/"negative") for an emotion label."""
    normalized = validate_label(label)
    return EMOTION_METADATA[normalized].polarity
