"""
temporal_filter.py
--------------------
Temporal smoothing utilities for the Gaze & Head Pose Estimation module.

Purpose
-------
Reduces frame-to-frame jitter in gaze ratios, head-pose angles, and EAR
values via:

  - `EMAFilter` — exponential moving average (the default smoothing
    strategy for this module; simple, fast, and effective for real-time
    per-signal smoothing).
  - `KalmanFilter1D` — an optional constant-velocity 1D Kalman filter for
    signals that benefit from velocity-aware prediction (e.g. gaze
    ratios during rapid saccades); disabled by default
    (`config.KALMAN_ENABLED_DEFAULT`).
  - `SignalStabilityTracker` — tracks recent variance of a signal to
    produce a `stability` score in [0, 1], used as one component of the
    overall per-frame confidence estimate.
  - `MultiSignalSmoother` — a convenience container that manages a named
    collection of filters (e.g. "yaw", "pitch", "horizontal_ratio") so
    callers don't have to instantiate/track one filter object per signal
    by hand.

This module contains no gaze/head-pose/blink domain logic — it operates
purely on plain floats/vectors.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional

import numpy as np

from ml.training.gaze_headpose import config


class EMAFilter:
    """Simple exponential moving average filter for a scalar or vector signal."""

    def __init__(self, alpha: float):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self._state: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._state = None

    def update(self, value) -> np.ndarray:
        value_arr = np.asarray(value, dtype=np.float64)
        if self._state is None:
            self._state = value_arr
        else:
            self._state = self.alpha * value_arr + (1 - self.alpha) * self._state
        return self._state

    @property
    def value(self) -> Optional[np.ndarray]:
        return self._state


class KalmanFilter1D:
    """
    Minimal constant-velocity Kalman filter for a single scalar signal.
    State vector: [position, velocity]. Implemented directly with NumPy
    (no dependency on `cv2.KalmanFilter`) for clarity and portability.
    """

    def __init__(
        self,
        process_noise: float = config.KALMAN_PROCESS_NOISE,
        measurement_noise: float = config.KALMAN_MEASUREMENT_NOISE,
        dt: float = 1.0,
    ):
        self.dt = dt
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise

        self._x = np.zeros((2, 1))  # [position, velocity]
        self._P = np.eye(2) * 1.0
        self._F = np.array([[1.0, dt], [0.0, 1.0]])
        self._H = np.array([[1.0, 0.0]])
        self._Q = np.eye(2) * process_noise
        self._R = np.array([[measurement_noise]])
        self._initialized = False

    def reset(self) -> None:
        self._x = np.zeros((2, 1))
        self._P = np.eye(2) * 1.0
        self._initialized = False

    def update(self, measurement: float) -> float:
        if not self._initialized:
            self._x[0, 0] = measurement
            self._initialized = True
            return float(self._x[0, 0])

        # Predict
        x_pred = self._F @ self._x
        p_pred = self._F @ self._P @ self._F.T + self._Q

        # Update
        y = np.array([[measurement]]) - self._H @ x_pred
        s = self._H @ p_pred @ self._H.T + self._R
        kalman_gain = p_pred @ self._H.T @ np.linalg.inv(s)

        self._x = x_pred + kalman_gain @ y
        self._P = (np.eye(2) - kalman_gain @ self._H) @ p_pred

        return float(self._x[0, 0])

    @property
    def value(self) -> float:
        return float(self._x[0, 0])

    @property
    def velocity(self) -> float:
        return float(self._x[1, 0])


class SignalStabilityTracker:
    """
    Tracks the recent variance of a scalar signal and converts it into a
    stability score in [0, 1] (1 = perfectly stable), used as one input
    to the overall per-frame confidence estimate (see
    `config.CONFIDENCE_WEIGHTS`).
    """

    def __init__(self, window: int = 15, reference_std: float = 5.0):
        self.window = window
        self.reference_std = reference_std
        self._values: Deque[float] = deque(maxlen=window)

    def reset(self) -> None:
        self._values.clear()

    def update(self, value: float) -> float:
        self._values.append(float(value))
        if len(self._values) < 2:
            return 1.0
        std = float(np.std(self._values))
        stability = max(0.0, 1.0 - (std / self.reference_std))
        return min(1.0, stability)


class MultiSignalSmoother:
    """
    Convenience wrapper managing one EMA (and optionally one Kalman)
    filter per named signal, e.g.:

        smoother = MultiSignalSmoother(["yaw", "pitch", "roll"])
        smoothed = smoother.update({"yaw": 12.3, "pitch": -4.1, "roll": 1.0})
    """

    def __init__(
        self,
        signal_names,
        alpha: float = config.EMA_ALPHA_HEAD_POSE,
        use_kalman: bool = config.KALMAN_ENABLED_DEFAULT,
    ):
        self.use_kalman = use_kalman
        self._ema_filters: Dict[str, EMAFilter] = {name: EMAFilter(alpha) for name in signal_names}
        self._kalman_filters: Dict[str, KalmanFilter1D] = (
            {name: KalmanFilter1D() for name in signal_names} if use_kalman else {}
        )
        self._stability_trackers: Dict[str, SignalStabilityTracker] = {
            name: SignalStabilityTracker() for name in signal_names
        }

    def reset(self) -> None:
        for f in self._ema_filters.values():
            f.reset()
        for f in self._kalman_filters.values():
            f.reset()
        for t in self._stability_trackers.values():
            t.reset()

    def update(self, values: Dict[str, float]) -> Dict[str, float]:
        smoothed = {}
        for name, raw_value in values.items():
            ema_value = float(np.asarray(self._ema_filters.setdefault(name, EMAFilter(config.EMA_ALPHA_HEAD_POSE)).update(raw_value)))

            if self.use_kalman:
                kalman = self._kalman_filters.setdefault(name, KalmanFilter1D())
                smoothed[name] = kalman.update(ema_value)
            else:
                smoothed[name] = ema_value

        return smoothed

    def stability_score(self, values: Dict[str, float]) -> float:
        """Average stability score (0-1) across all tracked signals for this update."""
        scores = []
        for name, value in values.items():
            tracker = self._stability_trackers.setdefault(name, SignalStabilityTracker())
            scores.append(tracker.update(value))
        return float(np.mean(scores)) if scores else 1.0
