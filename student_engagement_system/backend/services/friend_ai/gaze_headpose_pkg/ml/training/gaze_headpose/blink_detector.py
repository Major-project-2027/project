"""
blink_detector.py
------------------
Eye Aspect Ratio (EAR) and blink detection for the Gaze & Head Pose
Estimation module.

Purpose
-------
Computes the classic Eye Aspect Ratio (Soukupová & Čech, 2016) from
MediaPipe FaceMesh eye landmarks, and maintains a small per-stream state
machine (`BlinkDetector`) that:

  - Adapts its closed-eye threshold to the individual/session (adaptive
    thresholding), rather than relying on a single fixed EAR cutoff.
  - Counts blinks (with a minimum consecutive-frame requirement to reject
    single-frame landmark noise).
  - Tracks blink duration (to distinguish a normal blink from a sustained
    eye closure — the latter feeds `drowsiness_detector.py`).
  - Tracks a rolling blink-rate-per-minute.

This module is stateful and intended to be instantiated once per active
monitoring session/stream (mirrors the "per student, per session" framing
used throughout the architecture document), then fed one frame's EAR at
a time via `update()`.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple

import numpy as np

from ml.training.gaze_headpose import config, utils
from ml.training.gaze_headpose.landmark_detector import FaceLandmarkResult

logger = utils.get_logger(__name__)


def compute_ear(eye_points: np.ndarray) -> float:
    """
    Compute the Eye Aspect Ratio for one eye.

    `eye_points` must be the 6 landmarks in the order defined by
    `config.LEFT_EYE_EAR_INDICES` / `RIGHT_EYE_EAR_INDICES`:
        [left_corner, top_1, top_2, right_corner, bottom_1, bottom_2]

    EAR = (||top_1 - bottom_1|| + ||top_2 - bottom_2||) / (2 * ||left_corner - right_corner||)
    """
    left_corner, top_1, top_2, right_corner, bottom_1, bottom_2 = eye_points[:, :2]

    vertical_1 = utils.euclidean_distance(top_1, bottom_1)
    vertical_2 = utils.euclidean_distance(top_2, bottom_2)
    horizontal = utils.euclidean_distance(left_corner, right_corner)

    if horizontal <= 1e-6:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


@dataclass
class BlinkFrameResult:
    """Per-frame EAR/blink output."""

    valid: bool
    left_ear: float = 0.0
    right_ear: float = 0.0
    average_ear: float = 0.0
    threshold: float = config.EAR_DEFAULT_THRESHOLD
    eyes_closed: bool = False
    is_blink_event: bool = False           # True on the frame a completed blink is registered
    last_blink_duration_ms: Optional[float] = None
    total_blink_count: int = 0
    blink_rate_per_minute: float = 0.0


@dataclass
class _ClosureState:
    is_closed: bool = False
    closure_start_time: Optional[float] = None
    consecutive_closed_frames: int = 0


class BlinkDetector:
    """
    Stateful blink detector. Instantiate once per monitored
    stream/session and call `update(landmark_result)` once per frame.
    """

    def __init__(
        self,
        initial_threshold: float = config.EAR_DEFAULT_THRESHOLD,
        adaptive_alpha: float = config.EAR_ADAPTIVE_ALPHA,
        min_consec_frames: int = config.EAR_MIN_CONSEC_FRAMES_FOR_BLINK,
        max_blink_duration_seconds: float = config.BLINK_MAX_DURATION_SECONDS,
        blink_rate_window_seconds: float = config.DROWSINESS_BLINK_RATE_WINDOW_SECONDS,
    ):
        self.threshold = initial_threshold
        self.adaptive_alpha = adaptive_alpha
        self.min_consec_frames = min_consec_frames
        self.max_blink_duration_seconds = max_blink_duration_seconds
        self.blink_rate_window_seconds = blink_rate_window_seconds

        self._open_eye_baseline: Optional[float] = None
        self._closure = _ClosureState()
        self._total_blinks = 0
        self._last_blink_duration_ms: Optional[float] = None
        self._blink_timestamps: Deque[float] = deque()
        self._current_closure_duration_s: float = 0.0

    def reset(self) -> None:
        """Reset all stateful counters (e.g. at the start of a new session)."""
        self.__init__(
            initial_threshold=config.EAR_DEFAULT_THRESHOLD,
            adaptive_alpha=self.adaptive_alpha,
            min_consec_frames=self.min_consec_frames,
            max_blink_duration_seconds=self.max_blink_duration_seconds,
            blink_rate_window_seconds=self.blink_rate_window_seconds,
        )

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------
    def update(
        self, landmark_result: FaceLandmarkResult, timestamp: Optional[float] = None
    ) -> BlinkFrameResult:
        if not landmark_result.detected or not landmark_result.is_valid:
            return BlinkFrameResult(valid=False, threshold=self.threshold, total_blink_count=self._total_blinks)

        left_eye = landmark_result.left_eye_points()
        right_eye = landmark_result.right_eye_points()
        if left_eye is None or right_eye is None:
            return BlinkFrameResult(valid=False, threshold=self.threshold, total_blink_count=self._total_blinks)

        now = timestamp if timestamp is not None else time.time()

        left_ear = compute_ear(left_eye)
        right_ear = compute_ear(right_eye)
        average_ear = (left_ear + right_ear) / 2.0

        eyes_closed = average_ear < self.threshold
        self._update_adaptive_threshold(average_ear, eyes_closed)

        is_blink_event, last_duration_ms = self._update_closure_state(eyes_closed, now)

        blink_rate = self._current_blink_rate(now)

        return BlinkFrameResult(
            valid=True,
            left_ear=left_ear,
            right_ear=right_ear,
            average_ear=average_ear,
            threshold=self.threshold,
            eyes_closed=eyes_closed,
            is_blink_event=is_blink_event,
            last_blink_duration_ms=last_duration_ms,
            total_blink_count=self._total_blinks,
            blink_rate_per_minute=blink_rate,
        )

    # ------------------------------------------------------------------
    # Adaptive threshold
    # ------------------------------------------------------------------
    def _update_adaptive_threshold(self, average_ear: float, eyes_closed: bool) -> None:
        """
        Adapts the closed-eye threshold to the current person/session by
        tracking an exponential moving average of "open eye" EAR samples,
        then setting the threshold at a fixed fraction below that
        baseline. Only updates the baseline on frames judged open, so a
        sustained closure does not drag the baseline (and therefore the
        threshold) downward.
        """
        if eyes_closed:
            return

        if self._open_eye_baseline is None:
            self._open_eye_baseline = average_ear
        else:
            self._open_eye_baseline = (
                self.adaptive_alpha * average_ear + (1 - self.adaptive_alpha) * self._open_eye_baseline
            )

        # Closed-eye threshold set at 75% of the adapted open-eye baseline,
        # never below the configured floor to avoid runaway adaptation on
        # noisy sessions.
        adapted = self._open_eye_baseline * 0.75
        self.threshold = max(adapted, config.EAR_DEFAULT_THRESHOLD * 0.5)

    # ------------------------------------------------------------------
    # Closure / blink state machine
    # ------------------------------------------------------------------
    def _update_closure_state(self, eyes_closed: bool, now: float) -> Tuple[bool, Optional[float]]:
        is_blink_event = False
        last_duration_ms = self._last_blink_duration_ms

        if eyes_closed:
            if not self._closure.is_closed:
                self._closure.is_closed = True
                self._closure.closure_start_time = now
                self._closure.consecutive_closed_frames = 1
            else:
                self._closure.consecutive_closed_frames += 1
            self._current_closure_duration_s = now - (self._closure.closure_start_time or now)
        else:
            if self._closure.is_closed:
                duration_s = now - (self._closure.closure_start_time or now)
                if (
                    self._closure.consecutive_closed_frames >= self.min_consec_frames
                    and duration_s <= self.max_blink_duration_seconds
                ):
                    self._total_blinks += 1
                    self._last_blink_duration_ms = duration_s * 1000.0
                    last_duration_ms = self._last_blink_duration_ms
                    self._blink_timestamps.append(now)
                    is_blink_event = True
                # else: too short (noise) or too long (sustained closure,
                # handled by drowsiness_detector.py, not counted as a blink)
            self._closure = _ClosureState()
            self._current_closure_duration_s = 0.0

        self._prune_blink_timestamps(now)
        return is_blink_event, last_duration_ms

    def _prune_blink_timestamps(self, now: float) -> None:
        cutoff = now - self.blink_rate_window_seconds
        while self._blink_timestamps and self._blink_timestamps[0] < cutoff:
            self._blink_timestamps.popleft()

    def _current_blink_rate(self, now: float) -> float:
        self._prune_blink_timestamps(now)
        if not self._blink_timestamps:
            return 0.0
        window = min(self.blink_rate_window_seconds, max(now - self._blink_timestamps[0], 1.0))
        return (len(self._blink_timestamps) / window) * 60.0

    # ------------------------------------------------------------------
    # Accessors used by drowsiness_detector.py
    # ------------------------------------------------------------------
    @property
    def current_closure_duration_seconds(self) -> float:
        """Seconds the eyes have been continuously closed as of the last update() call."""
        return self._current_closure_duration_s

    @property
    def is_currently_closed(self) -> bool:
        return self._closure.is_closed
