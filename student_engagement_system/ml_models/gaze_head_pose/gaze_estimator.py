"""
Eye gaze estimation module built on MediaPipe Face Mesh with iris
refinement enabled -- tracks the iris center relative to each eye's
contour to classify gaze direction and reports Eye Aspect Ratio (EAR)
for blink/drowsiness signals.
"""
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ml_models.face_authentication.preprocessing import check_quality, QualityReport
from ml_models.gaze_head_pose.gaze_utils import (
    GAZE_DIRECTIONS,
    LEFT_EYE_BOTTOM_IDX,
    LEFT_EYE_EAR_INDICES,
    LEFT_EYE_INNER_IDX,
    LEFT_EYE_OUTER_IDX,
    LEFT_EYE_TOP_IDX,
    LEFT_IRIS_CENTER_IDX,
    RIGHT_EYE_BOTTOM_IDX,
    RIGHT_EYE_EAR_INDICES,
    RIGHT_EYE_INNER_IDX,
    RIGHT_EYE_OUTER_IDX,
    RIGHT_EYE_TOP_IDX,
    RIGHT_IRIS_CENTER_IDX,
    GazeDirectionSmoother,
    GazeRatioSmoother,
    GazeRatios,
    classify_gaze_direction,
    eye_aspect_ratio,
    horizontal_gaze_ratio,
    vertical_gaze_ratio,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class GazeEstimationError(Exception):
    """Raised when a gaze prediction could not be generated for a frame."""


@dataclass
class GazeResult:
    """Result of running gaze estimation on a single video frame."""
    direction: str
    horizontal_ratio: float
    vertical_ratio: float
    ear_left: float
    ear_right: float
    is_blinking: bool
    confidence: float
    processing_time_ms: float


class GazeEstimator:
    """Estimates eye gaze direction (Left/Right/Up/Down/Center) and blink state.

    MediaPipe is imported lazily inside __init__, mirroring both Phase 3's
    EmotionDetector and this module's own HeadPoseEstimator: a missing
    dependency never crashes anything at import time, only (with a clear
    message) when a GazeEstimator is actually constructed.
    """

    def __init__(
        self,
        ear_blink_threshold: float = 0.21,
        horizontal_thresholds=(0.35, 0.65),
        vertical_thresholds=(0.35, 0.65),
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        ratio_smoothing_alpha: float = 0.3,
        direction_smoothing_window: int = 5,
        enforce_quality: bool = True,
    ) -> None:
        """
        Args:
            ear_blink_threshold: EAR below which an eye is considered closed.
            horizontal_thresholds: (low, high) horizontal gaze-ratio cutoffs.
            vertical_thresholds: (low, high) vertical gaze-ratio cutoffs.
            min_detection_confidence: MediaPipe Face Mesh detection
                confidence threshold (0-1).
            min_tracking_confidence: MediaPipe Face Mesh tracking
                confidence threshold (0-1).
            ratio_smoothing_alpha: EMA weight for GazeRatioSmoother, in (0, 1].
            direction_smoothing_window: Window size for the majority-vote
                GazeDirectionSmoother.
            enforce_quality: If True (default), reject frames that fail
                Phase 2's check_quality() gate before running estimation.

        Raises:
            GazeEstimationError: If MediaPipe is not installed, does not
                expose the legacy solutions.face_mesh API, or the Face
                Mesh model fails to initialize.
        """
        try:
            import mediapipe as mp  # noqa: WPS433 -- deliberate lazy import
        except ImportError as exc:
            raise GazeEstimationError(
                "MediaPipe is not installed. Run `pip install mediapipe` "
                "(see Phase 1 Section 4 special-installation notes)."
            ) from exc

        try:
            self._mp_face_mesh = mp.solutions.face_mesh
        except AttributeError as exc:
            raise GazeEstimationError(
                "This MediaPipe installation does not expose the legacy "
                "`solutions.face_mesh` API. Install a MediaPipe version that includes "
                "it, e.g. `pip install mediapipe==0.10.9` "
                "(see Phase 1 Section 4 special-installation notes)."
            ) from exc

        self.ear_blink_threshold = ear_blink_threshold
        self.horizontal_thresholds = horizontal_thresholds
        self.vertical_thresholds = vertical_thresholds
        self.enforce_quality = enforce_quality

        try:
            # refine_landmarks=True is required to obtain iris landmarks
            # (indices 468-477), which this module depends on.
            self._face_mesh = self._mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
        except Exception as exc:  # noqa: BLE001 -- MediaPipe raises assorted exception types
            raise GazeEstimationError(f"Failed to initialize MediaPipe Face Mesh: {exc}") from exc

        self._ratio_smoother = GazeRatioSmoother(alpha=ratio_smoothing_alpha)
        self._direction_smoother = GazeDirectionSmoother(window_size=direction_smoothing_window)
        logger.info(
            "GazeEstimator ready -- backbone=MediaPipe Face Mesh (iris-refined) "
            f"(ear_blink_threshold={ear_blink_threshold})"
        )

    def estimate(self, frame_bgr: np.ndarray) -> GazeResult:
        """Estimate gaze direction and blink state for a single video frame.

        Args:
            frame_bgr: Full (or face-region) video frame, BGR uint8.

        Returns:
            A GazeResult with the smoothed gaze direction, horizontal/
            vertical ratios, per-eye EAR values, a blink flag, a
            confidence score in [0, 1], and processing time in ms.

        Raises:
            GazeEstimationError: If the frame is empty, fails the quality
                gate (when enforced), or no face/iris landmarks are detected.
        """
        if frame_bgr is None or frame_bgr.size == 0:
            raise GazeEstimationError("Received an empty video frame.")

        if self.enforce_quality:
            report: QualityReport = check_quality(frame_bgr)
            if not report.passed:
                raise GazeEstimationError(
                    f"Frame failed quality gate for gaze estimation: {report.reasons}"
                )

        start = time.perf_counter()

        height, width = frame_bgr.shape[:2]
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        try:
            mp_result = self._face_mesh.process(rgb_frame)
        except Exception as exc:  # noqa: BLE001 -- MediaPipe raises assorted exception types
            raise GazeEstimationError(f"MediaPipe Face Mesh failed to process frame: {exc}") from exc

        if not mp_result.multi_face_landmarks:
            raise GazeEstimationError("No face/iris landmarks detected in frame.")

        landmarks = mp_result.multi_face_landmarks[0].landmark
        if len(landmarks) <= LEFT_IRIS_CENTER_IDX:
            raise GazeEstimationError(
                "Iris landmarks unavailable -- Face Mesh must be constructed with "
                "refine_landmarks=True."
            )

        def px(idx: int) -> np.ndarray:
            return np.array([landmarks[idx].x * width, landmarks[idx].y * height])

        right_eye_pts = np.array([px(i) for i in RIGHT_EYE_EAR_INDICES])
        left_eye_pts = np.array([px(i) for i in LEFT_EYE_EAR_INDICES])
        ear_right = eye_aspect_ratio(right_eye_pts)
        ear_left = eye_aspect_ratio(left_eye_pts)
        is_blinking = (ear_left < self.ear_blink_threshold) and (ear_right < self.ear_blink_threshold)

        right_iris = px(RIGHT_IRIS_CENTER_IDX)
        left_iris = px(LEFT_IRIS_CENTER_IDX)

        h_right = horizontal_gaze_ratio(right_iris[0], px(RIGHT_EYE_OUTER_IDX)[0], px(RIGHT_EYE_INNER_IDX)[0])
        h_left = horizontal_gaze_ratio(left_iris[0], px(LEFT_EYE_INNER_IDX)[0], px(LEFT_EYE_OUTER_IDX)[0])
        v_right = vertical_gaze_ratio(right_iris[1], px(RIGHT_EYE_TOP_IDX)[1], px(RIGHT_EYE_BOTTOM_IDX)[1])
        v_left = vertical_gaze_ratio(left_iris[1], px(LEFT_EYE_TOP_IDX)[1], px(LEFT_EYE_BOTTOM_IDX)[1])

        raw_ratios = GazeRatios(horizontal=(h_left + h_right) / 2.0, vertical=(v_left + v_right) / 2.0)
        smoothed_ratios = self._ratio_smoother.update(raw_ratios)

        raw_direction = classify_gaze_direction(
            smoothed_ratios.horizontal, smoothed_ratios.vertical,
            self.horizontal_thresholds, self.vertical_thresholds,
        )
        smoothed_direction = self._direction_smoother.update(raw_direction)

        # Confidence is reduced when the two eyes disagree substantially --
        # a sign of a noisy/partial detection (occlusion, extreme angle, etc.).
        eye_agreement = 1.0 - min(1.0, abs(h_left - h_right) + abs(v_left - v_right))
        confidence = float(max(0.0, min(1.0, eye_agreement)))

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return GazeResult(
            direction=smoothed_direction,
            horizontal_ratio=smoothed_ratios.horizontal,
            vertical_ratio=smoothed_ratios.vertical,
            ear_left=ear_left,
            ear_right=ear_right,
            is_blinking=is_blinking,
            confidence=confidence,
            processing_time_ms=elapsed_ms,
        )

    def estimate_safe(self, frame_bgr: np.ndarray) -> Optional[GazeResult]:
        """Same as estimate(), but returns None instead of raising.

        Useful in real-time loops where one bad frame must never stop
        the pipeline -- exactly the "never crash" requirement for this
        module.

        Args:
            frame_bgr: Full (or face-region) video frame, BGR uint8.

        Returns:
            A GazeResult, or None if estimation failed for any reason.
        """
        try:
            return self.estimate(frame_bgr)
        except GazeEstimationError as exc:
            logger.warning(f"estimate_safe: gaze estimation failed, returning None -- {exc}")
            return None

    def reset(self) -> None:
        """Reset the internal temporal smoothers (e.g. on a new session/student)."""
        self._ratio_smoother.reset()
        self._direction_smoother.reset()
