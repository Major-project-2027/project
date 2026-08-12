"""
Shared helper functions for the Head Pose Estimation subsystem: the 3-D
reference face model used by solvePnP, camera-matrix construction,
rotation-vector -> Euler-angle conversion, direction classification, and
temporal smoothing.

Every function here is pure / stateless (except HeadPoseSmoother, which
holds only its own running-average state) so it can be unit tested
without MediaPipe or a webcam -- exactly the same separation Phase 3 used
between emotion_utils.py (pure helpers) and emotion_detector.py (the
model-backed class).
"""
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------
# MediaPipe Face Mesh landmark indices used for the 6-point PnP model.
# ---------------------------------------------------------------------
NOSE_TIP_IDX = 1
CHIN_IDX = 152
LEFT_EYE_CORNER_IDX = 33
RIGHT_EYE_CORNER_IDX = 263
LEFT_MOUTH_CORNER_IDX = 61
RIGHT_MOUTH_CORNER_IDX = 291

PNP_LANDMARK_INDICES = [
    NOSE_TIP_IDX,
    CHIN_IDX,
    LEFT_EYE_CORNER_IDX,
    RIGHT_EYE_CORNER_IDX,
    LEFT_MOUTH_CORNER_IDX,
    RIGHT_MOUTH_CORNER_IDX,
]

# Generic 3-D face model (millimetres), in the same point order as
# PNP_LANDMARK_INDICES above. This is the classic 6-point model used
# throughout the head-pose-estimation literature (nose tip at the origin).
MODEL_POINTS_3D = np.array(
    [
        (0.0, 0.0, 0.0),        # Nose tip
        (0.0, -330.0, -65.0),   # Chin
        (-225.0, 170.0, -135.0),  # Left eye, left corner
        (225.0, 170.0, -135.0),   # Right eye, right corner
        (-150.0, -150.0, -125.0),  # Left mouth corner
        (150.0, -150.0, -125.0),   # Right mouth corner
    ],
    dtype=np.float64,
)

HEAD_POSE_DIRECTIONS = ["Forward", "Left", "Right", "Up", "Down"]


class InvalidHeadPoseDirectionError(ValueError):
    """Raised when a label outside HEAD_POSE_DIRECTIONS is used where a valid one is required."""


def is_valid_head_direction(label: str) -> bool:
    """Check whether a string is one of the 5 supported head-pose directions."""
    return label in HEAD_POSE_DIRECTIONS


def build_camera_matrix(frame_width: int, frame_height: int) -> np.ndarray:
    """Build an approximate pinhole camera intrinsic matrix for solvePnP.

    In the absence of a real camera calibration, the focal length is
    approximated as the frame width (a standard, widely used approximation
    for webcam-based head-pose estimation) and the principal point is
    assumed to be the frame centre.

    Args:
        frame_width: Width of the video frame in pixels.
        frame_height: Height of the video frame in pixels.

    Returns:
        A 3x3 float64 camera intrinsic matrix.

    Raises:
        ValueError: If frame_width or frame_height is not positive.
    """
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError(f"frame_width and frame_height must be positive, got "
                          f"({frame_width}, {frame_height}).")
    focal_length = float(frame_width)
    center = (frame_width / 2.0, frame_height / 2.0)
    return np.array(
        [
            [focal_length, 0.0, center[0]],
            [0.0, focal_length, center[1]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def rotation_matrix_to_euler_angles(rotation_matrix: np.ndarray) -> Tuple[float, float, float]:
    """Convert a 3x3 rotation matrix to (yaw, pitch, roll) in degrees.

    Args:
        rotation_matrix: 3x3 rotation matrix, as produced by cv2.Rodrigues()
            from a solvePnP rotation vector.

    Returns:
        A (yaw, pitch, roll) tuple in degrees. Positive yaw is a rightward
        turn, positive pitch is looking down, positive roll is a clockwise
        tilt (from the viewer's perspective).

    Raises:
        ValueError: If rotation_matrix is not a 3x3 matrix.
    """
    if rotation_matrix.shape != (3, 3):
        raise ValueError(f"rotation_matrix must be 3x3, got shape {rotation_matrix.shape}.")

    sy = math.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch = math.atan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
    else:
        pitch = math.atan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
        yaw = math.atan2(-rotation_matrix[2, 0], sy)
        roll = 0.0

    return (math.degrees(yaw), math.degrees(pitch), math.degrees(roll))


def classify_head_direction(
    yaw: float,
    pitch: float,
    yaw_threshold: float = 15.0,
    pitch_threshold: float = 15.0,
) -> str:
    """Classify a (yaw, pitch) angle pair into a coarse head-pose direction.

    Args:
        yaw: Yaw angle in degrees (positive = turned right).
        pitch: Pitch angle in degrees (positive = tilted down).
        yaw_threshold: Minimum |yaw| in degrees to be considered Left/Right.
        pitch_threshold: Minimum |pitch| in degrees to be considered Up/Down.

    Returns:
        One of HEAD_POSE_DIRECTIONS. Yaw is checked before pitch, so a
        strong horizontal turn takes priority over a milder vertical tilt.

    Raises:
        ValueError: If either threshold is not positive.
    """
    if yaw_threshold <= 0 or pitch_threshold <= 0:
        raise ValueError("yaw_threshold and pitch_threshold must be positive.")

    if abs(yaw) >= yaw_threshold:
        return "Right" if yaw > 0 else "Left"
    if abs(pitch) >= pitch_threshold:
        return "Down" if pitch > 0 else "Up"
    return "Forward"


@dataclass
class PoseAngles:
    """Container for a single (yaw, pitch, roll) reading, in degrees."""
    yaw: float
    pitch: float
    roll: float


class HeadPoseSmoother:
    """Exponential-moving-average smoother for (yaw, pitch, roll) triples.

    Mirrors Phase 3's EmotionSmoother pattern: reduces frame-to-frame
    jitter in live video by blending each new reading with the running
    average rather than trusting a single noisy frame.
    """

    def __init__(self, alpha: float = 0.3) -> None:
        """
        Args:
            alpha: Weight given to the newest reading, in (0, 1]. Higher
                values track new readings faster; lower values smooth more.

        Raises:
            ValueError: If alpha is not in (0, 1].
        """
        if not (0.0 < alpha <= 1.0):
            raise ValueError("alpha must be in (0, 1].")
        self.alpha = alpha
        self._state: Optional[PoseAngles] = None

    def update(self, angles: PoseAngles) -> PoseAngles:
        """Blend a new frame's angles into the running smoothed estimate.

        Args:
            angles: This frame's raw (yaw, pitch, roll) reading.

        Returns:
            The updated smoothed PoseAngles.
        """
        if self._state is None:
            self._state = PoseAngles(angles.yaw, angles.pitch, angles.roll)
        else:
            self._state = PoseAngles(
                yaw=self.alpha * angles.yaw + (1 - self.alpha) * self._state.yaw,
                pitch=self.alpha * angles.pitch + (1 - self.alpha) * self._state.pitch,
                roll=self.alpha * angles.roll + (1 - self.alpha) * self._state.roll,
            )
        return self._state

    def reset(self) -> None:
        """Clear the smoother's running state (e.g. on a new session/student)."""
        self._state = None


def compute_reprojection_confidence(
    reprojection_error_px: float,
    max_acceptable_error_px: float = 40.0,
) -> float:
    """Map a solvePnP mean reprojection error (pixels) to a 0-1 confidence.

    Args:
        reprojection_error_px: Mean Euclidean distance (pixels) between the
            original 2-D landmark points and their re-projected estimates.
        max_acceptable_error_px: Error (pixels) at or beyond which
            confidence is clamped to 0.0.

    Returns:
        A confidence score in [0, 1] -- 1.0 for a perfect fit, decaying
        linearly to 0.0 at max_acceptable_error_px.

    Raises:
        ValueError: If reprojection_error_px is negative or
            max_acceptable_error_px is not positive.
    """
    if reprojection_error_px < 0:
        raise ValueError("reprojection_error_px must not be negative.")
    if max_acceptable_error_px <= 0:
        raise ValueError("max_acceptable_error_px must be positive.")
    confidence = 1.0 - (reprojection_error_px / max_acceptable_error_px)
    return float(max(0.0, min(1.0, confidence)))
