"""
face_quality.py
-----------------
Face quality assessment for the Gaze & Head Pose Estimation module.

Purpose
-------
Evaluates whether a detected face is of sufficient quality for reliable
downstream gaze/head-pose/blink analysis, considering:

  - Lighting (mean brightness of the face region)
  - Blur / sharpness (variance of Laplacian)
  - Occlusion (from `landmark_detector.py`'s occlusion heuristic)
  - Face size (bounding-box width relative to frame width)
  - Face position (offset of the face center from the frame center)

Produces a single `quality_score` in [0, 1] and an `accepted` flag so
real-time pipelines can cheaply reject poor-quality frames before running
the (comparatively) more expensive gaze/head-pose math on them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from ml.training.gaze_headpose import config, utils
from ml.training.gaze_headpose.landmark_detector import FaceLandmarkResult

logger = utils.get_logger(__name__)


@dataclass
class FaceQualityResult:
    """Per-frame face quality assessment outcome."""

    valid: bool
    brightness: float = 0.0
    sharpness: float = 0.0
    size_ratio: float = 0.0
    position_offset_ratio: float = 0.0
    occlusion_score: float = 0.0
    quality_score: float = 0.0
    accepted: bool = False
    reasons: List[str] = field(default_factory=list)


class FaceQualityAssessor:
    """Stateless per-frame face-quality scorer."""

    def __init__(
        self,
        min_brightness: int = config.FACE_QUALITY_MIN_BRIGHTNESS,
        max_brightness: int = config.FACE_QUALITY_MAX_BRIGHTNESS,
        min_sharpness: float = config.FACE_QUALITY_MIN_SHARPNESS,
        min_size_ratio: float = config.FACE_QUALITY_MIN_SIZE_RATIO,
        max_size_ratio: float = config.FACE_QUALITY_MAX_SIZE_RATIO,
        max_center_offset_ratio: float = config.FACE_QUALITY_MAX_CENTER_OFFSET_RATIO,
        reject_threshold: float = config.FACE_QUALITY_REJECT_THRESHOLD,
    ):
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_sharpness = min_sharpness
        self.min_size_ratio = min_size_ratio
        self.max_size_ratio = max_size_ratio
        self.max_center_offset_ratio = max_center_offset_ratio
        self.reject_threshold = reject_threshold

    def assess(self, bgr_frame: np.ndarray, landmark_result: FaceLandmarkResult) -> FaceQualityResult:
        if not landmark_result.detected or landmark_result.bbox_xywh is None:
            return FaceQualityResult(valid=False, reasons=["no_face_detected"])

        import cv2

        height, width = landmark_result.image_shape
        x, y, w, h = landmark_result.bbox_xywh
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        face_region = bgr_frame[y0:y1, x0:x1]

        if face_region.size == 0:
            return FaceQualityResult(valid=False, reasons=["empty_face_region"])

        gray_face = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)

        brightness = float(np.mean(gray_face))
        sharpness = float(cv2.Laplacian(gray_face, cv2.CV_64F).var())
        size_ratio = w / float(width) if width > 0 else 0.0
        position_offset_ratio = self._center_offset_ratio((x, y, w, h), width, height)
        occlusion_score = landmark_result.occlusion_score

        reasons: List[str] = []
        brightness_score = self._range_score(brightness, self.min_brightness, self.max_brightness, reasons, "lighting")
        sharpness_score = self._min_score(sharpness, self.min_sharpness, reasons, "blur")
        size_score = self._range_score(size_ratio, self.min_size_ratio, self.max_size_ratio, reasons, "face_size")
        position_score = self._max_score(
            position_offset_ratio, self.max_center_offset_ratio, reasons, "face_position"
        )
        occlusion_component = 1.0 - occlusion_score
        if occlusion_score > 0.5:
            reasons.append("occlusion")

        quality_score = float(
            np.mean([brightness_score, sharpness_score, size_score, position_score, occlusion_component])
        )
        accepted = quality_score >= self.reject_threshold

        return FaceQualityResult(
            valid=True,
            brightness=brightness,
            sharpness=sharpness,
            size_ratio=size_ratio,
            position_offset_ratio=position_offset_ratio,
            occlusion_score=occlusion_score,
            quality_score=quality_score,
            accepted=accepted,
            reasons=reasons if not accepted else [],
        )

    # ------------------------------------------------------------------
    # Sub-score helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _range_score(value: float, lower: float, upper: float, reasons: List[str], name: str) -> float:
        if lower <= value <= upper:
            return 1.0
        span = max(upper - lower, 1e-6)
        distance = (lower - value) if value < lower else (value - upper)
        score = utils.clamp(1.0 - (distance / span), 0.0, 1.0)
        if score < 0.7:
            reasons.append(name)
        return score

    @staticmethod
    def _min_score(value: float, minimum: float, reasons: List[str], name: str) -> float:
        score = utils.clamp(value / minimum, 0.0, 1.0) if minimum > 0 else 1.0
        if score < 0.7:
            reasons.append(name)
        return score

    @staticmethod
    def _max_score(value: float, maximum: float, reasons: List[str], name: str) -> float:
        score = utils.clamp(1.0 - (value / maximum), 0.0, 1.0) if maximum > 0 else 1.0
        if score < 0.7:
            reasons.append(name)
        return score

    @staticmethod
    def _center_offset_ratio(bbox_xywh: Tuple[int, int, int, int], width: int, height: int) -> float:
        x, y, w, h = bbox_xywh
        face_center = np.array([x + w / 2.0, y + h / 2.0])
        frame_center = np.array([width / 2.0, height / 2.0])
        offset = float(np.linalg.norm(face_center - frame_center))
        diagonal = math.hypot(width, height)
        return offset / diagonal if diagonal > 0 else 0.0
