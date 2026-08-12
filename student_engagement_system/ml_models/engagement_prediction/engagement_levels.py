"""
Engagement level and risk-flag vocabulary for the Phase 6 Engagement
Prediction Engine.

This module is pure data + pure logic (no I/O, no other Phase 6 module
imports) so it can be imported safely by every other Phase 6 module,
the FastAPI router, and any future Phase 8 ML-based predictor without
creating import cycles.
"""
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Engagement levels
# ---------------------------------------------------------------------------
VERY_LOW = "VERY_LOW"
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
EXCELLENT = "EXCELLENT"

ALL_ENGAGEMENT_LEVELS = (VERY_LOW, LOW, MEDIUM, HIGH, EXCELLENT)

# Inclusive (min, max) score ranges per level, per the Phase 6 specification:
#   0-20 VERY_LOW, 21-40 LOW, 41-60 MEDIUM, 61-80 HIGH, 81-100 EXCELLENT
DEFAULT_LEVEL_RANGES: Dict[str, Tuple[int, int]] = {
    VERY_LOW: (0, 20),
    LOW: (21, 40),
    MEDIUM: (41, 60),
    HIGH: (61, 80),
    EXCELLENT: (81, 100),
}


class InvalidLevelRangesError(ValueError):
    """Raised when a configured set of engagement-level ranges is malformed
    (gaps, overlaps, or does not fully cover 0-100)."""


def validate_level_ranges(ranges: Dict[str, Tuple[int, int]]) -> None:
    """Validate that `ranges` fully and exclusively covers the closed
    interval [0, 100] with no gaps and no overlaps.

    Raises:
        InvalidLevelRangesError: If validation fails.
    """
    if set(ranges.keys()) != set(ALL_ENGAGEMENT_LEVELS):
        raise InvalidLevelRangesError(
            f"Level ranges must define exactly {ALL_ENGAGEMENT_LEVELS}; got {sorted(ranges.keys())}."
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


def score_to_level(score: float, ranges: Dict[str, Tuple[int, int]] = None) -> str:
    """Map a clamped 0-100 engagement score to its engagement level label.

    Args:
        score: Engagement score, expected in [0, 100] (values outside this
            range are clamped before lookup).
        ranges: Optional custom level ranges (defaults to
            DEFAULT_LEVEL_RANGES). Must satisfy validate_level_ranges().

    Returns:
        One of ALL_ENGAGEMENT_LEVELS.
    """
    active_ranges = ranges if ranges is not None else DEFAULT_LEVEL_RANGES
    clamped = max(0.0, min(100.0, float(score)))
    for level, (low, high) in active_ranges.items():
        if low <= clamped <= high:
            return level
    # Defensive fallback -- should be unreachable if ranges were validated.
    return EXCELLENT if clamped >= 100 else VERY_LOW


# ---------------------------------------------------------------------------
# Risk flags
# ---------------------------------------------------------------------------
PHONE_USAGE = "PHONE_USAGE"
MULTIPLE_PERSON = "MULTIPLE_PERSON"
LOOKING_AWAY = "LOOKING_AWAY"
HEAD_DOWN = "HEAD_DOWN"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
UNKNOWN_FACE = "UNKNOWN_FACE"
NO_FACE = "NO_FACE"
VERY_LOW_ENGAGEMENT = "VERY_LOW_ENGAGEMENT"

ALL_RISK_FLAGS = (
    PHONE_USAGE,
    MULTIPLE_PERSON,
    LOOKING_AWAY,
    HEAD_DOWN,
    LOW_CONFIDENCE,
    UNKNOWN_FACE,
    NO_FACE,
    VERY_LOW_ENGAGEMENT,
)


def is_known_risk_flag(flag: str) -> bool:
    """Return True if `flag` is one of the Phase 6 risk-flag vocabulary."""
    return flag in ALL_RISK_FLAGS