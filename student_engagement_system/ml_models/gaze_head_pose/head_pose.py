"""
Head pose estimation module built on MediaPipe Face Mesh landmark
detection plus OpenCV's solvePnP -- the classic 6-point PnP approach for
estimating yaw, pitch, and roll from 2-D facial landmarks.
"""
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ml_models.face_authentication.preprocessing import check_quality, QualityReport
from ml_models.gaze_head_pose.head_pose_utils import (
    HEAD_POSE_DIRECTIONS,
    MODEL_POINTS_3D,
    PNP_LANDMARK_INDICES,
    HeadPoseSmoother,
    PoseAngles,
    build_camera_matrix,
    classify_head_direction,
    compute_reprojection_confidence,
    rotation_matrix_to_euler_angles,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class HeadPoseEstimationError(Exception):
    """Raised when a head-pose prediction could not be generated for a frame."""


@dataclass
class HeadPoseResult:
    """Result of running head-pose estimation on a single video frame."""
    yaw: float
    pitch: float
    roll: float
    direction: str
    confidence: float
    processing_time_ms: float


class HeadPoseEstimator:
    """Estimates head orientation (yaw/pitch/roll) from a BGR video frame.

    MediaPipe is imported lazily inside __init__ so that modules which do
    not need head-pose estimation never pay the MediaPipe import cost --
    the same defensive pattern Phase 3's EmotionDetector used for
    DeepFace/TensorFlow.
    """

    def __init__(
        self,
        yaw_threshold: float = 15.0,
        pitch_threshold: float = 15.0,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        smoothing_alpha: float = 0.3,
        enforce_quality: bool = True,
    ) -> None:
        """
        Args:
            yaw_threshold: Degrees of |yaw| beyond which the head is
                classified as turned Left/Right.
            pitch_threshold: Degrees of |pitch| beyond which the head is
                classified as tilted Up/Down.
            min_detection_confidence: MediaPipe Face Mesh detection
                confidence threshold (0-1).
            min_tracking_confidence: MediaPipe Face Mesh tracking
                confidence threshold (0-1).
            smoothing_alpha: EMA weight for HeadPoseSmoother, in (0, 1].
            enforce_quality: If True (default), reject frames that fail
                Phase 2's check_quality() gate before running estimation.

        Raises:
            HeadPoseEstimationError: If MediaPipe is not installed, or the
                Face Mesh model fails to initialize.
        """
        try:
            import mediapipe as mp  # noqa: WPS433 -- deliberate lazy import
        except ImportError as exc:
            raise HeadPoseEstimationError(
                "MediaPipe is not installed. Run `pip install mediapipe` "
                "(see Phase 1 Section 4 special-installation notes)."
            ) from exc

        try:
            self._mp_face_mesh = mp.solutions.face_mesh
        except AttributeError as exc:
            raise HeadPoseEstimationError(
                "This MediaPipe installation does not expose the legacy "
                "`solutions.face_mesh` API. Install a MediaPipe version that includes "
                "it, e.g. `pip install mediapipe==0.10.9` "
                "(see Phase 1 Section 4 special-installation notes)."
            ) from exc

        self.yaw_threshold = yaw_threshold
        self.pitch_threshold = pitch_threshold
        self.enforce_quality = enforce_quality

        try:
            self._face_mesh = self._mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=False,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        except Exception as exc:  # noqa: BLE001 -- MediaPipe raises assorted exception types
            raise HeadPoseEstimationError(f"Failed to initialize MediaPipe Face Mesh: {exc}") from exc

        self._smoother = HeadPoseSmoother(alpha=smoothing_alpha)
        logger.info(
            f"HeadPoseEstimator ready -- backbone=MediaPipe Face Mesh + solvePnP "
            f"(yaw_threshold={yaw_threshold}, pitch_threshold={pitch_threshold})"
        )

    def estimate(self, frame_bgr: np.ndarray) -> HeadPoseResult:
        """Estimate head orientation for a single video frame.

        Args:
            frame_bgr: Full (or face-region) video frame, BGR uint8.

        Returns:
            A HeadPoseResult with yaw/pitch/roll (degrees), a coarse
            direction label, a confidence score in [0, 1], and processing
            time in milliseconds.

        Raises:
            HeadPoseEstimationError: If the frame is empty, fails the
                quality gate (when enforced), no face landmarks are
                detected, or solvePnP fails to converge.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            raise HeadPoseEstimationError("Received an empty video frame.")

        if self.enforce_quality:
            report: QualityReport = check_quality(frame_bgr)
            if not report.passed:
                raise HeadPoseEstimationError(
                    f"Frame failed quality gate for head-pose estimation: {report.reasons}"
                )

        start = time.perf_counter()

        height, width = frame_bgr.shape[:2]
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        try:
            mp_result = self._face_mesh.process(rgb_frame)
        except Exception as exc:  # noqa: BLE001 -- MediaPipe raises assorted exception types
            raise HeadPoseEstimationError(f"MediaPipe Face Mesh failed to process frame: {exc}") from exc

        if not mp_result.multi_face_landmarks:
            raise HeadPoseEstimationError("No face landmarks detected in frame.")

        landmarks = mp_result.multi_face_landmarks[0].landmark
        image_points = np.array(
            [(landmarks[idx].x * width, landmarks[idx].y * height) for idx in PNP_LANDMARK_INDICES],
            dtype=np.float64,
        )

        camera_matrix = build_camera_matrix(width, height)
        dist_coeffs = np.zeros((4, 1), dtype=np.float64)

        success, rotation_vector, translation_vector = cv2.solvePnP(
            MODEL_POINTS_3D, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not success:
            raise HeadPoseEstimationError("solvePnP failed to converge on the detected landmarks.")

        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        yaw, pitch, roll = rotation_matrix_to_euler_angles(rotation_matrix)

        projected_points, _ = cv2.projectPoints(
            MODEL_POINTS_3D, rotation_vector, translation_vector, camera_matrix, dist_coeffs,
        )
        reprojection_error = float(
            np.mean(np.linalg.norm(projected_points.reshape(-1, 2) - image_points, axis=1))
        )
        confidence = compute_reprojection_confidence(reprojection_error)

        smoothed = self._smoother.update(PoseAngles(yaw, pitch, roll))
        direction = classify_head_direction(
            smoothed.yaw, smoothed.pitch, self.yaw_threshold, self.pitch_threshold,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return HeadPoseResult(
            yaw=smoothed.yaw,
            pitch=smoothed.pitch,
            roll=smoothed.roll,
            direction=direction,
            confidence=confidence,
            processing_time_ms=elapsed_ms,
        )

    def estimate_safe(self, frame_bgr: np.ndarray) -> Optional[HeadPoseResult]:
        """Same as estimate(), but returns None instead of raising.

        Useful in real-time loops where one bad frame must never stop
        the pipeline -- exactly the "never crash" requirement for this
        module.

        Args:
            frame_bgr: Full (or face-region) video frame, BGR uint8.

        Returns:
            A HeadPoseResult, or None if estimation failed for any reason.
        """
        try:
            return self.estimate(frame_bgr)
        except HeadPoseEstimationError as exc:
            logger.warning(f"estimate_safe: head-pose estimation failed, returning None -- {exc}")
            return None

    def reset(self) -> None:
        """Reset the internal temporal smoother (e.g. on a new session/student)."""
        self._smoother.reset()
