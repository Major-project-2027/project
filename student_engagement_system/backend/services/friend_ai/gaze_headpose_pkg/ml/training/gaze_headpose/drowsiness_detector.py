"""
drowsiness_detector.py
------------------------
Drowsiness classification for the Gaze & Head Pose Estimation module.

Purpose
-------
Combines sustained eye-closure duration and blink-rate signals (both
produced by `blink_detector.py`) into a four-level drowsiness
classification, per the module spec:

    alert -> fatigued -> drowsy -> microsleep

Classification rules
---------------------
- **microsleep**: eyes continuously closed beyond
  `config.DROWSINESS_EYE_CLOSED_MICROSLEEP_SECONDS`.
- **drowsy**: eyes continuously closed beyond
  `config.DROWSINESS_EYE_CLOSED_DROWSY_SECONDS`.
- **fatigued**: eyes continuously closed beyond
  `config.DROWSINESS_EYE_CLOSED_ALERT_SECONDS`, OR the rolling blink rate
  exceeds `config.DROWSINESS_HIGH_BLINK_RATE_PER_MIN` (an elevated blink
  rate is a well-documented fatigue indicator even without long closures).
- **alert**: none of the above.

A short temporal majority-vote is applied on top of the raw
frame-by-frame classification to avoid single-frame flicker between
adjacent severity levels.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Deque, List

from ml.training.gaze_headpose import config, utils
from ml.training.gaze_headpose.blink_detector import BlinkFrameResult

logger = utils.get_logger(__name__)

_SEVERITY_ORDER = ("alert", "fatigued", "drowsy", "microsleep")


@dataclass
class DrowsinessResult:
    """Per-frame drowsiness classification outcome."""

    valid: bool
    state: str = "alert"           # alert | fatigued | drowsy | microsleep
    confidence: float = 0.0
    closure_duration_seconds: float = 0.0
    blink_rate_per_minute: float = 0.0
    contributing_factors: List[str] = field(default_factory=list)


class DrowsinessDetector:
    """
    Stateful drowsiness classifier. Feed it the `BlinkFrameResult` and
    current closure duration produced by a `BlinkDetector` instance for
    the same stream, once per frame.
    """

    def __init__(self, smoothing_window: int = 5):
        self.smoothing_window = smoothing_window
        self._recent_states: Deque[str] = deque(maxlen=smoothing_window)
        self._microsleep_count = 0
        self._was_microsleep = False

    def reset(self) -> None:
        self._recent_states.clear()
        self._microsleep_count = 0
        self._was_microsleep = False

    def update(self, blink_result: BlinkFrameResult, closure_duration_seconds: float) -> DrowsinessResult:
        if not blink_result.valid:
            return DrowsinessResult(valid=False)

        raw_state, factors = self._classify(closure_duration_seconds, blink_result.blink_rate_per_minute)
        self._recent_states.append(raw_state)
        smoothed_state = self._majority_vote()

        if smoothed_state == "microsleep" and not self._was_microsleep:
            self._microsleep_count += 1
        self._was_microsleep = smoothed_state == "microsleep"

        confidence = self._estimate_confidence(closure_duration_seconds, blink_result.blink_rate_per_minute)

        return DrowsinessResult(
            valid=True,
            state=smoothed_state,
            confidence=confidence,
            closure_duration_seconds=closure_duration_seconds,
            blink_rate_per_minute=blink_result.blink_rate_per_minute,
            contributing_factors=factors,
        )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    @staticmethod
    def _classify(closure_duration_seconds: float, blink_rate_per_minute: float):
        factors: List[str] = []

        if closure_duration_seconds >= config.DROWSINESS_EYE_CLOSED_MICROSLEEP_SECONDS:
            factors.append(f"eyes closed for {closure_duration_seconds:.1f}s (>= microsleep threshold)")
            return "microsleep", factors

        if closure_duration_seconds >= config.DROWSINESS_EYE_CLOSED_DROWSY_SECONDS:
            factors.append(f"eyes closed for {closure_duration_seconds:.1f}s (>= drowsy threshold)")
            return "drowsy", factors

        if closure_duration_seconds >= config.DROWSINESS_EYE_CLOSED_ALERT_SECONDS:
            factors.append(f"eyes closed for {closure_duration_seconds:.1f}s (>= fatigue threshold)")
            return "fatigued", factors

        if blink_rate_per_minute >= config.DROWSINESS_HIGH_BLINK_RATE_PER_MIN:
            factors.append(f"elevated blink rate ({blink_rate_per_minute:.0f}/min)")
            return "fatigued", factors

        return "alert", factors

    def _majority_vote(self) -> str:
        """
        Returns the most severe state that appears at least twice in the
        recent window, falling back to the most recent raw classification
        if no state repeats (handles the smoothing_window==1 / cold-start
        case gracefully).
        """
        if not self._recent_states:
            return "alert"

        counts = Counter(self._recent_states)
        repeated = [state for state, count in counts.items() if count >= 2]
        if not repeated:
            return self._recent_states[-1]

        # pick the most severe among repeated states
        return max(repeated, key=_SEVERITY_ORDER.index)

    @staticmethod
    def _estimate_confidence(closure_duration_seconds: float, blink_rate_per_minute: float) -> float:
        # Confidence grows with how far past a threshold boundary the
        # current signal sits, capped at 1.0.
        margin = closure_duration_seconds - config.DROWSINESS_EYE_CLOSED_ALERT_SECONDS
        closure_component = utils.clamp(margin / 2.0, 0.0, 1.0)
        blink_component = utils.clamp(
            blink_rate_per_minute / (config.DROWSINESS_HIGH_BLINK_RATE_PER_MIN * 1.5), 0.0, 1.0
        )
        return utils.clamp(max(closure_component, blink_component), 0.1, 1.0)

    @property
    def microsleep_count(self) -> int:
        """Total number of distinct microsleep episodes observed so far in this session."""
        return self._microsleep_count
