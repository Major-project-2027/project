"""
headpose_estimator.py
----------------------
Head pose estimation for the Gaze & Head Pose Estimation module.

Purpose
-------
Estimates head orientation (pitch, yaw, roll) using a classic, purely
geometric approach: 6 MediaPipe FaceMesh landmarks are matched against a
generic 3D face model via `cv2.solvePnP`, and the resulting rotation
matrix is converted to Euler angles. No deep-learning head-pose model is
used, per the module spec's preference for geometric methods.

The estimated angles are then classified into the three attentiveness
buckets required by the module spec:
  - "focused"              — within the focused yaw/pitch bounds
  - "slightly_distracted"  — beyond focused but within the wider bounds
  - "looking_away"         — beyond the wider bounds
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ml.training.gaze_headpose import config, utils
from ml.training.gaze_headpose.landmark_detector import FaceLandmarkResult

logger = utils.get_logger(__name__)


@dataclass
class HeadPoseResult:
    """Container for a single frame's head-pose estimation outcome."""

    valid: bool
    pitch: float = 0.0
    yaw: float = 0.0
    roll: float = 0.0
    classification: str = "unknown"  # focused | slightly_distracted | looking_away | unknown
    confidence: float = 0.0
    rotation_vector: Optional[np.ndarray] = None
    translation_vector: Optional[np.ndarray] = None


class HeadPoseEstimator:
    """
    Per-frame geometric head-pose estimator using `cv2.solvePnP` against
    the generic 6-point 3D face model defined in `config.py`. The camera
    intrinsics are approximated from the frame size (no calibration file
    required), which is standard practice for this kind of real-time,
    single-camera classroom-monitoring use case.
    """

    def __init__(
        self,
        focused_yaw_deg: float = config.HEAD_POSE_FOCUSED_YAW_DEG,
        focused_pitch_deg: float = config.HEAD_POSE_FOCUSED_PITCH_DEG,
        distracted_yaw_deg: float = config.HEAD_POSE_SLIGHTLY_DISTRACTED_YAW_DEG,
        distracted_pitch_deg: float = config.HEAD_POSE_SLIGHTLY_DISTRACTED_PITCH_DEG,
    ):
        self.focused_yaw_deg = focused_yaw_deg
        self.focused_pitch_deg = focused_pitch_deg
        self.distracted_yaw_deg = distracted_yaw_deg
        self.distracted_pitch_deg = distracted_pitch_deg

    def estimate(self, landmark_result: FaceLandmarkResult) -> HeadPoseResult:
        if not landmark_result.detected or not landmark_result.is_valid:
            return HeadPoseResult(valid=False)

        import cv2

        pose_points_2d = landmark_result.pose_landmark_points()
        if pose_points_2d is None:
            return HeadPoseResult(valid=False)

        height, width = landmark_result.image_shape
        camera_matrix = self._build_camera_matrix(width, height)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        image_points = pose_points_2d[:, :2].astype(np.float64)

        success, rotation_vector, translation_vector = cv2.solvePnP(
            config.GENERIC_3D_FACE_MODEL,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            logger.debug("solvePnP failed to converge for this frame.")
            return HeadPoseResult(valid=False)

        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        pitch, yaw, roll = utils.rotation_matrix_to_euler_angles(rotation_matrix)

        # solvePnP's pitch convention often needs sign/offset correction to
        # match the intuitive "positive pitch = looking up" convention;
        # normalize into a [-90, 90] range for stable downstream logic.
        pitch = self._normalize_pitch(pitch)

        classification = self._classify(pitch, yaw)
        confidence = self._estimate_confidence(landmark_result, reprojection_ok=success)

        return HeadPoseResult(
            valid=True,
            pitch=pitch,
            yaw=yaw,
            roll=roll,
            classification=classification,
            confidence=confidence,
            rotation_vector=rotation_vector,
            translation_vector=translation_vector,
        )

    # ------------------------------------------------------------------
    # Camera intrinsics approximation
    # ------------------------------------------------------------------
    @staticmethod
    def _build_camera_matrix(width: int, height: int) -> np.ndarray:
        focal_length = float(width)
        center = (width / 2.0, height / 2.0)
        return np.array(
            [
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1],
            ],
            dtype=np.float64,
        )

    @staticmethod
    def _normalize_pitch(pitch_deg: float) -> float:
        # Map angles into a stable [-90, 90] range regardless of the raw
        # atan2 wraparound produced by rotation_matrix_to_euler_angles.
        if pitch_deg > 90:
            pitch_deg -= 180
        elif pitch_deg < -90:
            pitch_deg += 180
        return pitch_deg

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def _classify(self, pitch: float, yaw: float) -> str:
        abs_pitch, abs_yaw = abs(pitch), abs(yaw)

        if abs_pitch <= self.focused_pitch_deg and abs_yaw <= self.focused_yaw_deg:
            return "focused"
        if abs_pitch <= self.distracted_pitch_deg and abs_yaw <= self.distracted_yaw_deg:
            return "slightly_distracted"
        return "looking_away"

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------
    @staticmethod
    def _estimate_confidence(landmark_result: FaceLandmarkResult, reprojection_ok: bool) -> float:
        base = landmark_result.detection_confidence
        occlusion_penalty = landmark_result.occlusion_score
        raw = base * (1.0 - 0.5 * occlusion_penalty) * (1.0 if reprojection_ok else 0.0)
        return utils.clamp(raw, 0.0, 1.0)
