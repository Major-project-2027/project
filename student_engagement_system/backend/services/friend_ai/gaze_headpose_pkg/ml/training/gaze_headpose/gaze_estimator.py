"""
gaze_estimator.py
------------------
Eye gaze estimation for the Gaze & Head Pose Estimation module.

Purpose
-------
Estimates per-frame gaze direction using a **purely geometric** method
based on MediaPipe Iris landmarks relative to eye-corner landmarks — no
deep-learning gaze-regression model is used, per the module spec
("Avoid unnecessary deep learning models when geometric methods provide
better real-time performance").

Method
------
For each eye:
  1. Take the 4 iris-boundary landmarks and average them to approximate
     the iris center.
  2. Compute a horizontal ratio: where the iris center falls between the
     eye's left and right corner landmarks (0 = at left corner, 1 = at
     right corner, 0.5 = centered).
  3. Compute a vertical ratio similarly, using the eye's top/bottom
     midpoints.
  4. Re-center both ratios to a signed [-1, 1] scale and average across
     both eyes.

The signed horizontal/vertical values are then thresholded (per
`config.GAZE_HORIZONTAL_THRESHOLD` / `GAZE_VERTICAL_THRESHOLD`) into one
of: center, left, right, up, down.

A coarse 3D gaze vector and a normalized virtual-screen projection are
also produced for downstream consumers (e.g. a future attention heatmap),
clearly documented as an approximation rather than a calibrated
eye-tracker output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from ml.training.gaze_headpose import config, utils
from ml.training.gaze_headpose.landmark_detector import FaceLandmarkResult

logger = utils.get_logger(__name__)


@dataclass
class GazeEstimationResult:
    """Container for a single frame's gaze-estimation outcome."""

    valid: bool
    direction: str = "unknown"                 # center | left | right | up | down | unknown
    confidence: float = 0.0
    horizontal_ratio: float = 0.0               # signed, roughly [-1, 1]
    vertical_ratio: float = 0.0                 # signed, roughly [-1, 1]
    gaze_vector: Optional[np.ndarray] = None    # approximate unit vector (x, y, z)
    screen_coordinate: Optional[Tuple[float, float]] = None  # normalized [0,1]x[0,1]


class GazeEstimator:
    """Stateless, per-frame geometric gaze estimator."""

    def __init__(
        self,
        horizontal_threshold: float = config.GAZE_HORIZONTAL_THRESHOLD,
        vertical_threshold: float = config.GAZE_VERTICAL_THRESHOLD,
        confidence_floor: float = config.GAZE_CONFIDENCE_FLOOR,
    ):
        self.horizontal_threshold = horizontal_threshold
        self.vertical_threshold = vertical_threshold
        self.confidence_floor = confidence_floor

    def estimate(self, landmark_result: FaceLandmarkResult) -> GazeEstimationResult:
        """Compute gaze direction/vector/screen-coordinate from a landmark result."""
        if not landmark_result.detected or not landmark_result.is_valid:
            return GazeEstimationResult(valid=False)

        left_iris = landmark_result.left_iris_points()
        right_iris = landmark_result.right_iris_points()
        left_eye = landmark_result.left_eye_points()
        right_eye = landmark_result.right_eye_points()

        if left_iris is None or right_iris is None:
            logger.debug("Iris landmarks unavailable — enable MEDIAPIPE_REFINE_LANDMARKS.")
            return GazeEstimationResult(valid=False, direction="unknown", confidence=0.0)

        left_h, left_v = self._eye_ratios(left_eye, left_iris)
        right_h, right_v = self._eye_ratios(right_eye, right_iris)

        # Average both eyes; disagreement between eyes lowers confidence.
        horizontal_ratio = float(np.mean([left_h, right_h]))
        vertical_ratio = float(np.mean([left_v, right_v]))
        eye_agreement = 1.0 - utils.clamp(abs(left_h - right_h) + abs(left_v - right_v), 0.0, 1.0)

        direction = self._classify_direction(horizontal_ratio, vertical_ratio)

        confidence = self._estimate_confidence(
            landmark_result.detection_confidence, eye_agreement, landmark_result.occlusion_score
        )
        if confidence < self.confidence_floor:
            direction = "unknown"

        gaze_vector = self._build_gaze_vector(horizontal_ratio, vertical_ratio)
        screen_coordinate = (
            self._project_to_screen(horizontal_ratio, vertical_ratio)
            if config.GAZE_SCREEN_PROJECTION_ENABLED
            else None
        )

        return GazeEstimationResult(
            valid=True,
            direction=direction,
            confidence=confidence,
            horizontal_ratio=horizontal_ratio,
            vertical_ratio=vertical_ratio,
            gaze_vector=gaze_vector,
            screen_coordinate=screen_coordinate,
        )

    # ------------------------------------------------------------------
    # Per-eye ratio computation
    # ------------------------------------------------------------------
    @staticmethod
    def _eye_ratios(eye_points: np.ndarray, iris_points: np.ndarray) -> Tuple[float, float]:
        """
        eye_points ordering (see config.LEFT/RIGHT_EYE_EAR_INDICES):
            [left_corner, top_1, top_2, right_corner, bottom_1, bottom_2]
        Returns signed (horizontal_ratio, vertical_ratio) in roughly [-1, 1].
        """
        left_corner, top_1, top_2, right_corner, bottom_1, bottom_2 = eye_points[:, :2]
        iris_center = iris_points[:, :2].mean(axis=0)

        eye_width = max(np.linalg.norm(right_corner - left_corner), 1e-6)
        top_mid = (top_1 + top_2) / 2.0
        bottom_mid = (bottom_1 + bottom_2) / 2.0
        eye_height = max(np.linalg.norm(bottom_mid - top_mid), 1e-6)

        raw_h = np.dot(iris_center - left_corner, right_corner - left_corner) / (eye_width**2)
        raw_v = np.dot(iris_center - top_mid, bottom_mid - top_mid) / (eye_height**2)

        # Re-center 0..1 -> -1..1 (0 = center of eye)
        signed_h = float(utils.clamp((raw_h - 0.5) * 2.0, -1.5, 1.5))
        signed_v = float(utils.clamp((raw_v - 0.5) * 2.0, -1.5, 1.5))
        return signed_h, signed_v

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def _classify_direction(self, horizontal_ratio: float, vertical_ratio: float) -> str:
        if abs(horizontal_ratio) < self.horizontal_threshold and abs(vertical_ratio) < self.vertical_threshold:
            return "center"
        if abs(horizontal_ratio) >= abs(vertical_ratio):
            return "right" if horizontal_ratio > 0 else "left"
        return "down" if vertical_ratio > 0 else "up"

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------
    @staticmethod
    def _estimate_confidence(detection_confidence: float, eye_agreement: float, occlusion_score: float) -> float:
        raw = 0.5 * detection_confidence + 0.35 * eye_agreement + 0.15 * (1.0 - occlusion_score)
        return utils.clamp(raw, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Vector / screen projection (approximate, documented as such)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_gaze_vector(horizontal_ratio: float, vertical_ratio: float) -> np.ndarray:
        """
        Builds an approximate unit gaze vector (x, y, z) in a
        camera-relative frame, where +x is right, +y is down, and -z is
        "into the screen". This is a coarse geometric approximation for
        visualization/heatmap purposes, NOT a calibrated 3D gaze vector.
        """
        vector = np.array([horizontal_ratio, vertical_ratio, -1.0])
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector

    @staticmethod
    def _project_to_screen(horizontal_ratio: float, vertical_ratio: float) -> Tuple[float, float]:
        """
        Maps the signed gaze ratios onto a normalized [0, 1] x [0, 1]
        virtual screen plane, clamped at the configured thresholds' outer
        bound. This is an uncalibrated approximation intended for coarse
        visualization, not precision eye-tracking.
        """
        max_extent = 1.0
        x = utils.clamp((horizontal_ratio / max_extent + 1.0) / 2.0, 0.0, 1.0)
        y = utils.clamp((vertical_ratio / max_extent + 1.0) / 2.0, 0.0, 1.0)
        return x, y
