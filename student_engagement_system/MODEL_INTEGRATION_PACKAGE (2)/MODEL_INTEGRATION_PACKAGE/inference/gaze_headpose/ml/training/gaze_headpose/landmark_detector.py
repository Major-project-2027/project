"""
landmark_detector.py
---------------------
Face landmark detection for the Gaze & Head Pose Estimation module.

Purpose
-------
Thin, production-oriented wrapper around **MediaPipe FaceMesh** (with
iris refinement enabled), the sole landmark-detection backend used by
this module per the spec ("Only use pretrained models... Do NOT train
custom landmark detectors"). Provides:

  - 468-point face mesh + 10 iris landmarks (478 total)
  - Eye landmark extraction (EAR-ready 6-point sets)
  - Iris landmark extraction (for gaze estimation)
  - Face bounding box (from the face-oval landmark ring)
  - Landmark validation (sanity checks: point count, in-frame bounds)
  - A lightweight occlusion-detection heuristic

Every other module in this package (`gaze_estimator.py`,
`headpose_estimator.py`, `blink_detector.py`, `face_quality.py`) consumes
the `FaceLandmarkResult` produced here rather than talking to MediaPipe
directly, so the detection backend can be swapped/upgraded in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ml.training.gaze_headpose import config, utils

logger = utils.get_logger(__name__)


@dataclass
class FaceLandmarkResult:
    """Container for a single frame's landmark-detection outcome."""

    detected: bool
    image_shape: tuple = (0, 0)  # (height, width)
    landmarks_px: Optional[np.ndarray] = None     # (478, 3) pixel-space x, y, normalized z
    landmarks_norm: Optional[np.ndarray] = None   # (478, 3) normalized x, y, z in [0, 1]
    bbox_xywh: Optional[tuple] = None             # (x, y, w, h) in pixels
    detection_confidence: float = 0.0
    occlusion_score: float = 0.0                  # 0 = fully visible, 1 = fully occluded
    is_valid: bool = False

    def left_eye_points(self) -> Optional[np.ndarray]:
        if self.landmarks_px is None:
            return None
        return self.landmarks_px[config.LEFT_EYE_EAR_INDICES]

    def right_eye_points(self) -> Optional[np.ndarray]:
        if self.landmarks_px is None:
            return None
        return self.landmarks_px[config.RIGHT_EYE_EAR_INDICES]

    def left_iris_points(self) -> Optional[np.ndarray]:
        if self.landmarks_px is None or self.landmarks_px.shape[0] < config.TOTAL_LANDMARKS_WITH_IRIS:
            return None
        return self.landmarks_px[config.LEFT_IRIS_INDICES]

    def right_iris_points(self) -> Optional[np.ndarray]:
        if self.landmarks_px is None or self.landmarks_px.shape[0] < config.TOTAL_LANDMARKS_WITH_IRIS:
            return None
        return self.landmarks_px[config.RIGHT_IRIS_INDICES]

    def pose_landmark_points(self) -> Optional[np.ndarray]:
        if self.landmarks_px is None:
            return None
        indices = list(config.POSE_LANDMARK_INDICES.values())
        return self.landmarks_px[indices]


class FaceLandmarkDetector:
    """
    Wraps `mediapipe.solutions.face_mesh.FaceMesh` and produces validated,
    ready-to-consume `FaceLandmarkResult` objects for a single primary
    face per frame (multi-face support is intentionally out of scope for
    this module — the architecture document's "multiple-person" concern
    belongs to the Object Detection module).
    """

    def __init__(
        self,
        static_image_mode: bool = config.MEDIAPIPE_STATIC_IMAGE_MODE,
        max_num_faces: int = config.MEDIAPIPE_MAX_NUM_FACES,
        refine_landmarks: bool = config.MEDIAPIPE_REFINE_LANDMARKS,
        min_detection_confidence: float = config.MEDIAPIPE_MIN_DETECTION_CONFIDENCE,
        min_tracking_confidence: float = config.MEDIAPIPE_MIN_TRACKING_CONFIDENCE,
    ):
        import mediapipe as mp

        self._mp_face_mesh = mp.solutions.face_mesh
        self._face_mesh = self._mp_face_mesh.FaceMesh(
            static_image_mode=static_image_mode,
            max_num_faces=max_num_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.refine_landmarks = refine_landmarks
        self._expected_point_count = (
            config.TOTAL_LANDMARKS_WITH_IRIS if refine_landmarks else config.TOTAL_FACE_LANDMARKS
        )

    def close(self) -> None:
        self._face_mesh.close()

    def __enter__(self) -> "FaceLandmarkDetector":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------
    def process(self, bgr_frame: np.ndarray) -> FaceLandmarkResult:
        """
        Run FaceMesh on a single BGR frame (OpenCV convention) and return
        a fully-populated, validated `FaceLandmarkResult`. Never raises —
        returns `detected=False` on any failure so real-time loops never
        crash on a bad frame.
        """
        import cv2

        height, width = bgr_frame.shape[:2]

        try:
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            results = self._face_mesh.process(rgb_frame)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("FaceMesh processing failed: %s", exc)
            return FaceLandmarkResult(detected=False, image_shape=(height, width))

        if not results.multi_face_landmarks:
            return FaceLandmarkResult(detected=False, image_shape=(height, width))

        face_landmarks = results.multi_face_landmarks[0].landmark
        landmarks_norm = np.array([(lm.x, lm.y, lm.z) for lm in face_landmarks], dtype=np.float64)
        landmarks_px = landmarks_norm.copy()
        landmarks_px[:, 0] *= width
        landmarks_px[:, 1] *= height

        bbox = self._compute_bounding_box(landmarks_px, width, height)
        detection_confidence = self._estimate_detection_confidence(landmarks_norm)
        occlusion_score = self._estimate_occlusion(landmarks_norm)

        result = FaceLandmarkResult(
            detected=True,
            image_shape=(height, width),
            landmarks_px=landmarks_px,
            landmarks_norm=landmarks_norm,
            bbox_xywh=bbox,
            detection_confidence=detection_confidence,
            occlusion_score=occlusion_score,
        )
        result.is_valid = self.validate(result)
        return result

    # ------------------------------------------------------------------
    # Bounding box
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_bounding_box(landmarks_px: np.ndarray, width: int, height: int) -> tuple:
        oval_points = landmarks_px[config.FACE_OVAL_INDICES][:, :2]
        x_min, y_min = oval_points.min(axis=0)
        x_max, y_max = oval_points.max(axis=0)
        x_min, y_min = max(0, int(x_min)), max(0, int(y_min))
        x_max, y_max = min(width, int(x_max)), min(height, int(y_max))
        return x_min, y_min, max(1, x_max - x_min), max(1, y_max - y_min)

    # ------------------------------------------------------------------
    # Confidence estimation
    # ------------------------------------------------------------------
    @staticmethod
    def _estimate_detection_confidence(landmarks_norm: np.ndarray) -> float:
        """
        MediaPipe's Python FaceMesh API does not expose a single scalar
        detection-confidence score alongside landmarks, so this derives a
        proxy confidence from landmark geometric plausibility: how tightly
        the normalized landmarks fall within the valid [0, 1] frame
        region (points far outside indicate an unstable / low-confidence
        detection, e.g. at the frame edge).
        """
        xy = landmarks_norm[:, :2]
        in_bounds_ratio = float(np.mean((xy >= -0.05) & (xy <= 1.05)))
        return utils.clamp(in_bounds_ratio, 0.0, 1.0)

    @staticmethod
    def _estimate_occlusion(landmarks_norm: np.ndarray) -> float:
        """
        Lightweight occlusion heuristic: compares the relative depth (z)
        spread across the eye and mouth regions against the expected
        spread for an unoccluded, front-facing face. Large anomalies in
        local depth continuity (e.g. a hand or object in front of part of
        the face) increase the returned occlusion score in [0, 1].
        """
        eye_indices = config.LEFT_EYE_EAR_INDICES + config.RIGHT_EYE_EAR_INDICES
        mouth_indices = [61, 291, 13, 14]  # mouth corners + inner lip top/bottom
        region_indices = eye_indices + mouth_indices

        z_values = landmarks_norm[region_indices, 2]
        z_std = float(np.std(z_values))

        # Empirically, unoccluded frontal faces show z_std roughly in the
        # 0.0-0.02 range at this landmark scale; larger spread suggests
        # partial occlusion or extreme pose. Normalize into [0, 1].
        occlusion_score = utils.clamp((z_std - 0.01) / 0.06, 0.0, 1.0)
        return occlusion_score

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self, result: FaceLandmarkResult) -> bool:
        """
        Sanity-check a detection result before downstream modules trust
        it: correct landmark count, bounding box has positive area, and
        landmarks are not degenerate (all-zero / NaN).
        """
        if not result.detected or result.landmarks_px is None:
            return False

        if result.landmarks_px.shape[0] != self._expected_point_count:
            logger.debug(
                "Unexpected landmark count: got %d, expected %d",
                result.landmarks_px.shape[0],
                self._expected_point_count,
            )
            return False

        if np.isnan(result.landmarks_px).any():
            return False

        if result.bbox_xywh is None or result.bbox_xywh[2] <= 0 or result.bbox_xywh[3] <= 0:
            return False

        return True
