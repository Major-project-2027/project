"""
Cognitive state and risk-flag vocabulary for the Phase 7 Cognitive
Monitoring Engine.

This module is pure data + pure logic (no I/O, no other Phase 7 module
imports) so it can be imported safely by every other Phase 7 module, the
FastAPI router, and any future Phase 8 ML-based monitor without creating
import cycles. Mirrors models/engagement_prediction/engagement_levels.py's
structure exactly.
"""
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Attention levels (score-tiered, derived from a 0-100 attention_score)
# ---------------------------------------------------------------------------
VERY_LOW = "VERY_LOW"
LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"
VERY_HIGH = "VERY_HIGH"

ALL_ATTENTION_LEVELS = (VERY_LOW, LOW, MODERATE, HIGH, VERY_HIGH)

# Inclusive (min, max) score ranges per attention level:
#   0-20 VERY_LOW, 21-40 LOW, 41-60 MODERATE, 61-80 HIGH, 81-100 VERY_HIGH
DEFAULT_ATTENTION_LEVEL_RANGES: Dict[str, Tuple[int, int]] = {
    VERY_LOW: (0, 20),
    LOW: (21, 40),
    MODERATE: (41, 60),
    HIGH: (61, 80),
    VERY_HIGH: (81, 100),
}


class InvalidLevelRangesError(ValueError):
    """Raised when a configured set of attention-level ranges is malformed
    (gaps, overlaps, or does not fully cover 0-100)."""


def validate_level_ranges(ranges: Dict[str, Tuple[int, int]],
                           expected_levels: Tuple[str, ...] = ALL_ATTENTION_LEVELS) -> None:
    """Validate that `ranges` fully and exclusively covers the closed
    interval [0, 100] with no gaps and no overlaps.

    Args:
        ranges: The candidate level -> (min, max) mapping to validate.
        expected_levels: The exact set of level names `ranges` must define.

    Raises:
        InvalidLevelRangesError: If validation fails.
    """
    if set(ranges.keys()) != set(expected_levels):
        raise InvalidLevelRangesError(
            f"Level ranges must define exactly {expected_levels}; got {sorted(ranges.keys())}."
        )
    ordered = sorted(ranges.values(), key=lambda pair: pair[0])
    if ordered[0][0] != 0:
        raise InvalidLevelRangesError("Level ranges must start at 0.")
    if ordered[-1][1] != 100:
        raise InvalidLevelRangesError("Level ranges must end at 100.")
    for (low, high), (next_low, _next_high) in zip(ordered, ordered[1:]):
        if high >= next_low:
            raise InvalidLevelRangesError(
                f"Level ranges must be contiguous and non-overlapping; "
                f"found ({low}, {high}) followed by ({next_low}, _)."
            )
        if next_low != high + 1:
            raise InvalidLevelRangesError(
                f"Level ranges must not have gaps; found a gap between {high} and {next_low}."
            )
    for low, high in ranges.values():
        if low > high:
            raise InvalidLevelRangesError(f"Invalid range ({low}, {high}): min exceeds max.")


def score_to_attention_level(score: float, ranges: Dict[str, Tuple[int, int]] = None) -> str:
    """Map a clamped 0-100 attention score to its attention level label.

    Args:
        score: Attention score, expected in [0, 100] (values outside this
            range are clamped before lookup).
        ranges: Optional custom level ranges (defaults to
            DEFAULT_ATTENTION_LEVEL_RANGES). Must satisfy validate_level_ranges().

    Returns:
        One of ALL_ATTENTION_LEVELS.
    """
    active_ranges = ranges if ranges is not None else DEFAULT_ATTENTION_LEVEL_RANGES
    clamped = max(0.0, min(100.0, float(score)))
    for level, (low, high) in active_ranges.items():
        if low <= clamped <= high:
            return level
    # Defensive fallback -- should be unreachable if ranges were validated.
    return VERY_HIGH if clamped >= 100 else VERY_LOW


# ---------------------------------------------------------------------------
# Cognitive states (categorical, rule-derived -- NOT score-tiered)
# ---------------------------------------------------------------------------
FOCUSED = "FOCUSED"
NEUTRAL = "NEUTRAL"
DISTRACTED = "DISTRACTED"
CONFUSED = "CONFUSED"
FATIGUED = "FATIGUED"
DISENGAGED = "DISENGAGED"
UNAVAILABLE = "UNAVAILABLE"

ALL_COGNITIVE_STATES = (FOCUSED, NEUTRAL, DISTRACTED, CONFUSED, FATIGUED, DISENGAGED, UNAVAILABLE)


def is_known_cognitive_state(state: str) -> bool:
    """Return True if `state` is one of the Phase 7 cognitive-state vocabulary."""
    return state in ALL_COGNITIVE_STATES


# ---------------------------------------------------------------------------
# Risk flags
# ---------------------------------------------------------------------------
PHONE_USAGE = "PHONE_USAGE"
MULTIPLE_PERSON = "MULTIPLE_PERSON"
LOOKING_AWAY = "LOOKING_AWAY"
HIGH_DISTRACTION = "HIGH_DISTRACTION"
FATIGUE_DETECTED = "FATIGUE_DETECTED"
CONFUSION_DETECTED = "CONFUSION_DETECTED"
LOW_ATTENTION = "LOW_ATTENTION"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
UNKNOWN_FACE = "UNKNOWN_FACE"
NO_FACE = "NO_FACE"

ALL_RISK_FLAGS = (
    PHONE_USAGE,
    MULTIPLE_PERSON,
    LOOKING_AWAY,
    HIGH_DISTRACTION,
    FATIGUE_DETECTED,
    CONFUSION_DETECTED,
    LOW_ATTENTION,
    LOW_CONFIDENCE,
    UNKNOWN_FACE,
    NO_FACE,
)


def is_known_risk_flag(flag: str) -> bool:
    """Return True if `flag` is one of the Phase 7 risk-flag vocabulary."""
    return flag in ALL_RISK_FLAGS