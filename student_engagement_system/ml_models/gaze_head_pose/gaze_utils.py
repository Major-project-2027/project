"""
Shared helper functions for the Eye Gaze Estimation subsystem: MediaPipe
Face Mesh eye/iris landmark indices, Eye Aspect Ratio (EAR) for blink
detection, horizontal/vertical gaze-ratio computation, direction
classification, and temporal smoothing.

Every function here is pure / stateless (except the smoother classes,
which hold only their own running state) so it can be unit tested without
MediaPipe or a webcam -- mirroring Phase 3's emotion_utils.py /
emotion_detector.py separation and this module's own head_pose_utils.py /
head_pose.py separation.
"""
from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, Optional, Sequence, Tuple

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------
# MediaPipe Face Mesh landmark indices for eyes and (with
# refine_landmarks=True) iris centers.
#
# The 6-point eye contours below follow the same convention widely used
# for Eye-Aspect-Ratio blink detection with MediaPipe's 468-point mesh,
# ordered (outer_corner, top_1, top_2, inner_corner, bottom_2, bottom_1)
# to match the classic 6-point EAR formula.
# ---------------------------------------------------------------------
RIGHT_EYE_EAR_INDICES = [33, 160, 158, 133, 153, 144]
LEFT_EYE_EAR_INDICES = [362, 385, 387, 263, 373, 380]

RIGHT_EYE_OUTER_IDX = 33
RIGHT_EYE_INNER_IDX = 133
RIGHT_EYE_TOP_IDX = 159
RIGHT_EYE_BOTTOM_IDX = 145

LEFT_EYE_INNER_IDX = 362
LEFT_EYE_OUTER_IDX = 263
LEFT_EYE_TOP_IDX = 386
LEFT_EYE_BOTTOM_IDX = 374

# Only valid when the Face Mesh is constructed with refine_landmarks=True.
RIGHT_IRIS_CENTER_IDX = 468
LEFT_IRIS_CENTER_IDX = 473

GAZE_DIRECTIONS = ["Left", "Right", "Up", "Down", "Center"]


class InvalidGazeDirectionError(ValueError):
    """Raised when a label outside GAZE_DIRECTIONS is used where a valid one is required."""


def is_valid_gaze_direction(label: str) -> bool:
    """Check whether a string is one of the 5 supported gaze directions."""
    return label in GAZE_DIRECTIONS


def validate_gaze_direction(label: str) -> str:
    """Validate a gaze-direction label.

    Args:
        label: Candidate direction label.

    Returns:
        The same label, unchanged, if valid.

    Raises:
        InvalidGazeDirectionError: If the label is not one of GAZE_DIRECTIONS.
    """
    if label not in GAZE_DIRECTIONS:
        raise InvalidGazeDirectionError(
            f"'{label}' is not a supported gaze direction. Expected one of {GAZE_DIRECTIONS}."
        )
    return label


def eye_aspect_ratio(eye_points: np.ndarray) -> float:
    """Compute the Eye Aspect Ratio (EAR) for one eye, for blink detection.

    Args:
        eye_points: A (6, 2) array of pixel coordinates in the order
            (outer_corner, top_1, top_2, inner_corner, bottom_2, bottom_1)
            -- see RIGHT_EYE_EAR_INDICES / LEFT_EYE_EAR_INDICES above.

    Returns:
        The EAR value. Values close to a person's normal open-eye baseline
        (typically ~0.25-0.35) indicate an open eye; a sharp drop indicates
        a blink or closed eye.

    Raises:
        ValueError: If eye_points does not have shape (6, 2).
    """
    eye_points = np.asarray(eye_points, dtype=np.float64)
    if eye_points.shape != (6, 2):
        raise ValueError(f"eye_points must have shape (6, 2), got {eye_points.shape}.")

    p1, p2, p3, p4, p5, p6 = eye_points
    vertical_1 = np.linalg.norm(p2 - p6)
    vertical_2 = np.linalg.norm(p3 - p5)
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal == 0:
        raise ValueError("Degenerate eye contour: outer and inner corners coincide.")
    return float((vertical_1 + vertical_2) / (2.0 * horizontal))


def horizontal_gaze_ratio(iris_x: float, corner_a_x: float, corner_b_x: float) -> float:
    """Compute the horizontal position of the iris within the eye contour.

    Args:
        iris_x: X pixel coordinate of the iris center.
        corner_a_x: X pixel coordinate of one eye corner.
        corner_b_x: X pixel coordinate of the other eye corner.

    Returns:
        A ratio in [0, 1] (clamped) describing where the iris sits between
        the two corners: 0.0 at corner_a, 1.0 at corner_b.

    Raises:
        ValueError: If the two corners coincide.
    """
    left_x, right_x = sorted((corner_a_x, corner_b_x))
    span = right_x - left_x
    if span == 0:
        raise ValueError("Degenerate eye contour: eye corners coincide horizontally.")
    ratio = (iris_x - left_x) / span
    if corner_a_x > corner_b_x:
        ratio = 1.0 - ratio
    return float(max(0.0, min(1.0, ratio)))


def vertical_gaze_ratio(iris_y: float, top_y: float, bottom_y: float) -> float:
    """Compute the vertical position of the iris within the eye contour.

    Args:
        iris_y: Y pixel coordinate of the iris center.
        top_y: Y pixel coordinate of the eyelid's top point.
        bottom_y: Y pixel coordinate of the eyelid's bottom point.

    Returns:
        A ratio in [0, 1] (clamped): 0.0 at the top of the eye, 1.0 at
        the bottom.

    Raises:
        ValueError: If top_y and bottom_y coincide.
    """
    span = bottom_y - top_y
    if span == 0:
        raise ValueError("Degenerate eye contour: top and bottom eyelid points coincide.")
    ratio = (iris_y - top_y) / span
    return float(max(0.0, min(1.0, ratio)))


def classify_gaze_direction(
    horizontal_ratio: float,
    vertical_ratio: float,
    horizontal_thresholds: Tuple[float, float] = (0.35, 0.65),
    vertical_thresholds: Tuple[float, float] = (0.35, 0.65),
) -> str:
    """Classify a (horizontal_ratio, vertical_ratio) pair into a gaze direction.

    Vertical deviation is checked before horizontal, so a strong up/down
    gaze takes priority over a milder left/right deviation.

    Args:
        horizontal_ratio: Output of horizontal_gaze_ratio(), in [0, 1].
        vertical_ratio: Output of vertical_gaze_ratio(), in [0, 1].
        horizontal_thresholds: (low, high) cutoffs; ratio < low -> Left,
            ratio > high -> Right.
        vertical_thresholds: (low, high) cutoffs; ratio < low -> Up,
            ratio > high -> Down.

    Returns:
        One of GAZE_DIRECTIONS.

    Raises:
        ValueError: If either ratio is outside [0, 1], or a threshold
            pair is not (low < high).
    """
    if not (0.0 <= horizontal_ratio <= 1.0):
        raise ValueError(f"horizontal_ratio must be in [0, 1], got {horizontal_ratio}.")
    if not (0.0 <= vertical_ratio <= 1.0):
        raise ValueError(f"vertical_ratio must be in [0, 1], got {vertical_ratio}.")
    h_low, h_high = horizontal_thresholds
    v_low, v_high = vertical_thresholds
    if not (h_low < h_high) or not (v_low < v_high):
        raise ValueError("Threshold pairs must satisfy low < high.")

    if vertical_ratio < v_low:
        return "Up"
    if vertical_ratio > v_high:
        return "Down"
    if horizontal_ratio < h_low:
        return "Left"
    if horizontal_ratio > h_high:
        return "Right"
    return "Center"


@dataclass
class GazeRatios:
    """Container for a single (horizontal_ratio, vertical_ratio) reading."""
    horizontal: float
    vertical: float


class GazeRatioSmoother:
    """Exponential-moving-average smoother for (horizontal, vertical) gaze ratios.

    Mirrors Phase 3's EmotionSmoother / this module's HeadPoseSmoother.
    """

    def __init__(self, alpha: float = 0.3) -> None:
        """
        Args:
            alpha: Weight given to the newest reading, in (0, 1].

        Raises:
            ValueError: If alpha is not in (0, 1].
        """
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must be in (0, 1].")
        self.alpha = alpha
        self._state: Optional[GazeRatios] = None

    def update(self, ratios: GazeRatios) -> GazeRatios:
        """Blend a new frame's ratios into the running smoothed estimate."""
        if self._state is None:
            self._state = GazeRatios(ratios.horizontal, ratios.vertical)
        else:
            self._state = GazeRatios(
                horizontal=self.alpha * ratios.horizontal + (1 - self.alpha) * self._state.horizontal,
                vertical=self.alpha * ratios.vertical + (1 - self.alpha) * self._state.vertical,
            )
        return self._state

    def reset(self) -> None:
        """Clear the smoother's running state (e.g. on a new session/student)."""
        self._state = None


class GazeDirectionSmoother:
    """Majority-vote smoother over a sliding window of discrete gaze labels.

    Discrete direction labels flicker more distractingly than continuous
    ratios do, so rather than smoothing the ratios alone, the final
    label is taken as the most common label seen in the last `window_size`
    frames -- a stable choice even if every individual frame agrees
    (repeating the same label simply keeps returning that label).
    """

    def __init__(self, window_size: int = 5) -> None:
        """
        Args:
            window_size: Number of recent frames to vote over.

        Raises:
            ValueError: If window_size is not a positive integer.
        """
        if window_size <= 0:
            raise ValueError("window_size must be a positive integer.")
        self._window: Deque[str] = deque(maxlen=window_size)

    def update(self, direction: str) -> str:
        """Add a new frame's direction label and return the smoothed majority label.

        Args:
            direction: This frame's raw classify_gaze_direction() output.

        Returns:
            The most frequent label in the current window. Ties are
            broken in favor of the most recently seen tied label.

        Raises:
            InvalidGazeDirectionError: If direction is not a supported label.
        """
        validate_gaze_direction(direction)
        self._window.append(direction)
        counts = Counter(self._window)
        max_count = max(counts.values())
        # Break ties by recency: scan the window from the most recent frame.
        for label in reversed(self._window):
            if counts[label] == max_count:
                return label
        return direction  # pragma: no cover -- unreachable, window is never empty here

    def reset(self) -> None:
        """Clear the smoother's running window (e.g. on a new session/student)."""
        self._window.clear()
