"""
Pure-logic helper functions and dataclasses for the Phase 5 Object Detection and
Classroom Monitoring module. Contains no Ultralytics/YOLO import so it stays
importable and unit-testable even when that optional dependency is missing.
"""
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Tuple

from ml_models.object_detection.object_labels import PERSON_CLASS_NAME, PHONE_CLASS_NAME

BBox = Tuple[float, float, float, float]  # (x1, y1, x2, y2)


@dataclass(frozen=True)
class Detection:
    """A single detected object in one video frame."""

    class_name: str
    confidence: float
    bbox: BBox

    def as_dict(self) -> Dict:
        return {
            "class": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "bbox": [round(float(v), 2) for v in self.bbox],
        }


def compute_iou(box_a: BBox, box_b: BBox) -> float:
    """Compute Intersection-over-Union between two (x1, y1, x2, y2) boxes.

    Returns:
        A float in [0.0, 1.0]. 0.0 if the boxes do not overlap or either box
        has non-positive area.
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def filter_by_confidence(detections: List[Detection], confidence_threshold: float) -> List[Detection]:
    """Keep only detections whose confidence meets confidence_threshold."""
    return [d for d in detections if d.confidence >= confidence_threshold]


def filter_by_target_classes(detections: List[Detection], target_classes) -> List[Detection]:
    """Keep only detections whose class_name is in target_classes."""
    target_set = set(target_classes)
    return [d for d in detections if d.class_name in target_set]


def count_persons(detections: List[Detection]) -> int:
    """Count how many 'person' detections are present in this frame."""
    return sum(1 for d in detections if d.class_name == PERSON_CLASS_NAME)


def find_best_phone_detection(detections: List[Detection]) -> "Detection | None":
    """Return the highest-confidence 'cell phone' detection, if any."""
    phone_detections = [d for d in detections if d.class_name == PHONE_CLASS_NAME]
    if not phone_detections:
        return None
    return max(phone_detections, key=lambda d: d.confidence)


class TemporalSmoother:
    """Majority-vote temporal smoothing over a sliding window of frames.

    Prevents a single noisy/false-positive frame from immediately flipping a
    boolean alert flag (e.g. multiple_person, phone_detected). A flag is only
    reported True once it has been True in at least `min_true_ratio` of the
    last `window_size` frames.
    """

    def __init__(self, window_size: int = 5, min_true_ratio: float = 0.6) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        if not (0.0 < min_true_ratio <= 1.0):
            raise ValueError("min_true_ratio must be in (0.0, 1.0]")
        self.window_size = window_size
        self.min_true_ratio = min_true_ratio
        self._history: Deque[bool] = deque(maxlen=window_size)

    def update(self, raw_value: bool) -> bool:
        """Push a new raw (single-frame) boolean reading and return the
        smoothed boolean decision for the current window."""
        self._history.append(bool(raw_value))
        if not self._history:
            return False
        true_ratio = sum(self._history) / len(self._history)
        return true_ratio >= self.min_true_ratio

    def reset(self) -> None:
        self._history.clear()

    @property
    def history(self) -> List[bool]:
        return list(self._history)
