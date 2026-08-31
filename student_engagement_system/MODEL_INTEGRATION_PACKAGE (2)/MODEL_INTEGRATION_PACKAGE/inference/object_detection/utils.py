"""
utils.py
--------
Shared dataclasses, logging setup, and helper functions for Module 5 —
Object Detection.

Contents
========
- `BoundingBox`, `Detection`, `FrameResult` — the structured, typed output
  contract every other file in this module produces/consumes.
- `detections_to_feature_vector` — converts a `FrameResult` (variable-
  length detection list) into a fixed-length numeric vector, which is the
  actual "ready for the LSTM without further preprocessing" output.
- Event/interaction heuristics: chair occupancy, sitting/standing,
  person-object interaction inference, and entering/leaving tracking
  across frames — all explicitly documented as spatial-proximity
  heuristics, not verified physical state.
- `draw_detections` — OpenCV overlay rendering used by predictor.py.
- `PerformanceTimer`, `get_system_usage` — latency/FPS/CPU/RAM
  measurement helpers used by trainer.py and predictor.py.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np

import config

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    """Module-wide logger factory: console + file handler, configured
    once from config.py's LOG_LEVEL/LOG_FORMAT/LOG_FILE_PATH."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers on re-import)

    logger.setLevel(config.LOG_LEVEL)
    formatter = logging.Formatter(config.LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        config.LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.LOG_FILE_PATH)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Read-only filesystem / no write permission — console-only logging is fine.
        pass

    return logger


logger = get_logger(__name__)


# ---------------------------------------------------------------------
# Core structured output types
# ---------------------------------------------------------------------
@dataclass
class BoundingBox:
    """Pixel-space axis-aligned bounding box, top-left origin."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(self.x2 - self.x1, 0.0)

    @property
    def height(self) -> float:
        return max(self.y2 - self.y1, 0.0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0

    @property
    def aspect_ratio(self) -> float:
        """height / width — used by the sitting/standing heuristic."""
        return self.height / self.width if self.width > 1e-6 else 0.0

    def iou(self, other: "BoundingBox") -> float:
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)
        inter_area = max(0.0, inter_x2 - inter_x1) * max(0.0, inter_y2 - inter_y1)
        if inter_area == 0.0:
            return 0.0
        union_area = self.area + other.area - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def edge_distance(self, other: "BoundingBox") -> float:
        """Shortest distance between the two boxes' edges (0 if overlapping)."""
        dx = max(other.x1 - self.x2, self.x1 - other.x2, 0.0)
        dy = max(other.y1 - self.y2, self.y1 - other.y2, 0.0)
        return float(np.hypot(dx, dy))

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass
class Detection:
    """A single detected object within one frame."""

    class_id: int
    class_name: str
    confidence: float
    bbox: BoundingBox
    track_id: Optional[int] = None
    person_id: Optional[int] = None  # == track_id, populated only for class_name == "Person"
    source_model: str = "primary"    # "primary" (COCO) or "oiv7" (Open Images secondary model)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FrameResult:
    """Structured per-frame output — the exact schema requested in the
    task spec (timestamp, person_count, object_count, detected_objects,
    bounding_boxes, class_ids, class_names, confidence_scores, track_ids,
    fps, latency, processing_time), plus an `events` list for the derived
    heuristic events described in this module's event-inference functions.
    """

    timestamp: float
    frame_index: int
    detections: list[Detection] = field(default_factory=list)
    fps: float = 0.0
    latency_ms: float = 0.0
    processing_time_ms: float = 0.0
    events: list[str] = field(default_factory=list)

    @property
    def person_count(self) -> int:
        return sum(1 for d in self.detections if d.class_name in config.PERSON_LIKE_CLASSES)

    @property
    def object_count(self) -> int:
        return len(self.detections)

    @property
    def detected_objects(self) -> list[str]:
        return [d.class_name for d in self.detections]

    @property
    def bounding_boxes(self) -> list[tuple[float, float, float, float]]:
        return [d.bbox.to_tuple() for d in self.detections]

    @property
    def class_ids(self) -> list[int]:
        return [d.class_id for d in self.detections]

    @property
    def class_names(self) -> list[str]:
        return [d.class_name for d in self.detections]

    @property
    def confidence_scores(self) -> list[float]:
        return [d.confidence for d in self.detections]

    @property
    def track_ids(self) -> list[Optional[int]]:
        return [d.track_id for d in self.detections]

    def to_dict(self) -> dict:
        """Full, JSON-serializable representation (variable-length — for
        logging/storage/debugging, NOT for direct LSTM consumption; use
        detections_to_feature_vector() for that)."""
        return {
            "timestamp": self.timestamp,
            "frame_index": self.frame_index,
            "person_count": self.person_count,
            "object_count": self.object_count,
            "detected_objects": self.detected_objects,
            "bounding_boxes": self.bounding_boxes,
            "class_ids": self.class_ids,
            "class_names": self.class_names,
            "confidence_scores": self.confidence_scores,
            "track_ids": self.track_ids,
            "fps": self.fps,
            "latency_ms": self.latency_ms,
            "processing_time_ms": self.processing_time_ms,
            "events": self.events,
        }


# ---------------------------------------------------------------------
# LSTM-ready fixed-length feature vector
# ---------------------------------------------------------------------
FEATURE_VECTOR_CLASS_NAMES = list(config.TARGET_CLASSES)
FEATURE_VECTOR_LENGTH = len(FEATURE_VECTOR_CLASS_NAMES) + 6
FEATURE_VECTOR_EXTRA_FIELDS = [
    "person_count", "object_count", "mean_confidence", "max_confidence", "fps", "timestamp",
]


def detections_to_feature_vector(frame_result: FrameResult) -> np.ndarray:
    """Convert one FrameResult into a fixed-length float32 vector suitable
    for direct consumption by a downstream LSTM (or any fixed-input-size
    model) with NO further preprocessing required — this is the actual
    integration contract with Module 6 (Student Engagement Prediction).

    Vector layout: [count_Person, count_Cell Phone, ..., count_Unknown Object,
                    person_count, object_count, mean_confidence,
                    max_confidence, fps, timestamp]
    Length == FEATURE_VECTOR_LENGTH (23 for the current 17-class taxonomy).
    """
    vector = np.zeros(FEATURE_VECTOR_LENGTH, dtype="float32")

    for class_name in frame_result.detected_objects:
        idx = config.CLASS_TO_INDEX.get(class_name)
        if idx is not None:
            vector[idx] += 1.0

    n_classes = len(FEATURE_VECTOR_CLASS_NAMES)
    confidences = frame_result.confidence_scores
    vector[n_classes + 0] = float(frame_result.person_count)
    vector[n_classes + 1] = float(frame_result.object_count)
    vector[n_classes + 2] = float(np.mean(confidences)) if confidences else 0.0
    vector[n_classes + 3] = float(np.max(confidences)) if confidences else 0.0
    vector[n_classes + 4] = float(frame_result.fps)
    vector[n_classes + 5] = float(frame_result.timestamp)

    return vector


def feature_vector_to_dict(vector: np.ndarray) -> dict:
    """Inverse of detections_to_feature_vector's layout — named lookup,
    useful for debugging/logging a feature vector without memorizing
    column order."""
    names = FEATURE_VECTOR_CLASS_NAMES + FEATURE_VECTOR_EXTRA_FIELDS
    return {name: float(vector[i]) for i, name in enumerate(names)}


# ---------------------------------------------------------------------
# Event / interaction heuristics
# ---------------------------------------------------------------------
def infer_chair_occupancy(detections: list[Detection]) -> dict[int, bool]:
    """For every Chair detection (keyed by its index in `detections`),
    return whether a Person bbox overlaps it above
    config.CHAIR_OCCUPANCY_IOU_THRESHOLD. Heuristic: true occupancy would
    need seat-level pose/contact estimation; bbox overlap is a reasonable
    but imperfect proxy (a person merely standing in front of a chair can
    trigger a false positive)."""
    persons = [d for d in detections if d.class_name in config.PERSON_LIKE_CLASSES]
    occupancy: dict[int, bool] = {}
    for i, det in enumerate(detections):
        if det.class_name != config.SEATING_CLASS_NAME:
            continue
        occupied = any(det.bbox.iou(p.bbox) >= config.CHAIR_OCCUPANCY_IOU_THRESHOLD for p in persons)
        occupancy[i] = occupied
    return occupancy


def infer_posture(detection: Detection) -> str:
    """Sitting/standing heuristic from bbox aspect ratio alone (a
    standing person's bbox is typically taller/narrower than a seated
    person's). This is NOT pose estimation — it is a coarse geometric
    proxy that can misclassify (e.g. a person leaning far forward). True
    posture classification belongs to the Gaze & Head Pose module's pose
    keypoints, if higher accuracy is required downstream."""
    if detection.class_name not in config.PERSON_LIKE_CLASSES:
        return "not_applicable"
    return "standing" if detection.bbox.aspect_ratio >= config.SITTING_ASPECT_RATIO_THRESHOLD else "sitting"


def infer_person_object_interactions(detections: list[Detection]) -> dict[int, list[str]]:
    """For every Person detection (keyed by its index in `detections`),
    return the list of INTERACTABLE_CLASSES object names whose bbox edge
    distance to that person is within
    config.INTERACTION_DISTANCE_THRESHOLD_PX (or which overlap the person
    bbox directly). This is a spatial-proximity heuristic ("this phone is
    near this person") — it does NOT verify grasp/contact/gaze-on-object,
    which would require hand/pose keypoints or gaze-target estimation
    (out of scope for a box-only detector)."""
    persons = [(i, d) for i, d in enumerate(detections) if d.class_name in config.PERSON_LIKE_CLASSES]
    objects = [d for d in detections if d.class_name in config.INTERACTABLE_CLASSES]

    interactions: dict[int, list[str]] = {i: [] for i, _ in persons}
    for i, person in persons:
        for obj in objects:
            if person.bbox.iou(obj.bbox) > 0.0 or person.bbox.edge_distance(obj.bbox) <= config.INTERACTION_DISTANCE_THRESHOLD_PX:
                interactions[i].append(obj.class_name)
    return interactions


def build_frame_events(detections: list[Detection]) -> list[str]:
    """Compose the human-readable, single-frame event strings requested
    in the spec (student using phone / reading book / etc., chair
    occupied/empty, sitting/standing) from the heuristics above. Events
    that require cross-frame state (entering/leaving) are handled
    separately by TrackLifecycleMonitor below, since they cannot be
    determined from one frame in isolation.
    """
    events: list[str] = []

    person_count = sum(1 for d in detections if d.class_name in config.PERSON_LIKE_CLASSES)
    if person_count == 0:
        events.append("no_student_present")
    elif person_count == 1:
        events.append("single_student_present")
    elif person_count == 2:
        events.append("two_students_present")
    elif person_count == 3:
        events.append("three_students_present")
    else:
        events.append("multiple_students_present")

    chair_occupancy = infer_chair_occupancy(detections)
    for i, occupied in chair_occupancy.items():
        events.append(f"chair_{i}_occupied" if occupied else f"chair_{i}_empty")

    interactions = infer_person_object_interactions(detections)
    person_indices = [i for i, d in enumerate(detections) if d.class_name in config.PERSON_LIKE_CLASSES]
    for i in person_indices:
        det = detections[i]
        posture = infer_posture(det)
        person_label = f"person_{det.track_id}" if det.track_id is not None else f"person_idx{i}"
        events.append(f"{person_label}_{posture}")
        for obj_name in interactions.get(i, []):
            action = _interaction_verb(obj_name)
            events.append(f"{person_label}_{action}")

    return events


def _interaction_verb(object_class_name: str) -> str:
    verb_map = {
        "Cell Phone": "using_phone",
        "Book": "reading_book",
        "Notebook": "writing_notebook",
        "Laptop": "using_laptop",
        "Bottle": "drinking_water",
        "Cup": "drinking",
        "Headphones": "wearing_headphones",
        "Tablet": "using_tablet",
    }
    return verb_map.get(object_class_name, f"near_{object_class_name.lower().replace(' ', '_')}")


class TrackLifecycleMonitor:
    """Maintains cross-frame state per track_id to emit "person entered
    frame" / "person left frame" events — genuinely cross-frame
    information that build_frame_events() cannot produce from a single
    frame. A track is considered "left" once it has been absent for
    config.TRACK_ABSENCE_FRAMES_FOR_LEFT_EVENT consecutive frames (not
    immediately on the first missed frame, to tolerate brief detector
    misses / occlusion without spamming spurious leave/re-enter events).
    """

    def __init__(self) -> None:
        self._active_track_ids: set[int] = set()
        self._missed_frame_counts: dict[int, int] = {}

    def update(self, frame_result: FrameResult) -> list[str]:
        events: list[str] = []
        person_tracks_this_frame = {
            d.track_id
            for d in frame_result.detections
            if d.class_name in config.PERSON_LIKE_CLASSES and d.track_id is not None
        }

        for track_id in person_tracks_this_frame:
            if track_id not in self._active_track_ids:
                self._active_track_ids.add(track_id)
                events.append(f"person_{track_id}_entered")
            self._missed_frame_counts[track_id] = 0

        for track_id in list(self._active_track_ids):
            if track_id in person_tracks_this_frame:
                continue
            self._missed_frame_counts[track_id] = self._missed_frame_counts.get(track_id, 0) + 1
            if self._missed_frame_counts[track_id] >= config.TRACK_ABSENCE_FRAMES_FOR_LEFT_EVENT:
                events.append(f"person_{track_id}_left")
                self._active_track_ids.discard(track_id)
                self._missed_frame_counts.pop(track_id, None)

        return events


# ---------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------
_CLASS_COLOR_CACHE: dict[str, tuple[int, int, int]] = {}


def _color_for_class(class_name: str) -> tuple[int, int, int]:
    """Deterministic, visually distinct BGR color per class name (hashed,
    not random-per-run, so the same class always renders the same color
    across frames/videos)."""
    if class_name in _CLASS_COLOR_CACHE:
        return _CLASS_COLOR_CACHE[class_name]
    h = abs(hash(class_name))
    color = (int(h % 200) + 30, int((h // 200) % 200) + 30, int((h // 40000) % 200) + 30)
    _CLASS_COLOR_CACHE[class_name] = color
    return color


def draw_detections(
    frame: np.ndarray,
    frame_result: FrameResult,
    viz_config: "config.VisualizationConfig" = config.VISUALIZATION,
) -> np.ndarray:
    """Draw bounding boxes, labels, confidence, track IDs, and a HUD
    (person/object counts, FPS, latency) onto a BGR frame in-place and
    return it. Used by predictor.py for image/video/webcam display."""
    import cv2

    for det in frame_result.detections:
        x1, y1, x2, y2 = (int(v) for v in det.bbox.to_tuple())
        color = _color_for_class(det.class_name) if viz_config.box_color_by_class else viz_config.default_box_color

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, viz_config.box_thickness)

        label_parts = []
        if viz_config.show_class_name:
            label_parts.append(det.class_name)
        if viz_config.show_track_id and det.track_id is not None:
            label_parts.append(f"#{det.track_id}")
        if viz_config.show_confidence:
            label_parts.append(f"{det.confidence * 100:.0f}%")
        label = " ".join(label_parts)

        if label:
            (text_w, text_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, viz_config.font_scale, viz_config.font_thickness
            )
            cv2.rectangle(frame, (x1, max(y1 - text_h - baseline - 4, 0)), (x1 + text_w + 4, y1), color, -1)
            cv2.putText(
                frame, label, (x1 + 2, max(y1 - 4, text_h)),
                cv2.FONT_HERSHEY_SIMPLEX, viz_config.font_scale, viz_config.text_color, viz_config.font_thickness,
            )

    hud_lines = []
    if viz_config.show_person_count:
        hud_lines.append(f"Persons: {frame_result.person_count}")
    if viz_config.show_object_count:
        hud_lines.append(f"Objects: {frame_result.object_count}")
    if viz_config.show_fps:
        hud_lines.append(f"FPS: {frame_result.fps:.1f}")
    if viz_config.show_latency:
        hud_lines.append(f"Latency: {frame_result.latency_ms:.1f}ms")

    if hud_lines:
        overlay = frame.copy()
        hud_height = 22 * len(hud_lines) + 10
        cv2.rectangle(overlay, (0, 0), (220, hud_height), viz_config.hud_background_color, -1)
        cv2.addWeighted(overlay, viz_config.hud_alpha, frame, 1 - viz_config.hud_alpha, 0, frame)
        for i, line in enumerate(hud_lines):
            cv2.putText(
                frame, line, (8, 20 + i * 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1,
            )

    return frame


# ---------------------------------------------------------------------
# Performance measurement
# ---------------------------------------------------------------------
class PerformanceTimer:
    """Simple context-manager latency timer. Usage:

        timer = PerformanceTimer()
        with timer:
            ... do work ...
        print(timer.elapsed_ms)
    """

    def __init__(self) -> None:
        self.elapsed_ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> "PerformanceTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0


class FPSCounter:
    """Exponential-moving-average FPS counter, matching the pattern used
    in Module 1's predictor.py for consistency across modules."""

    def __init__(self, smoothing: float = 0.9) -> None:
        self.smoothing = smoothing
        self._fps_ema: Optional[float] = None
        self._last_time = time.perf_counter()

    def tick(self) -> float:
        now = time.perf_counter()
        instant_fps = 1.0 / max(now - self._last_time, 1e-6)
        self._last_time = now
        self._fps_ema = instant_fps if self._fps_ema is None else (
            self.smoothing * self._fps_ema + (1 - self.smoothing) * instant_fps
        )
        return self._fps_ema


def get_system_usage() -> dict:
    """CPU % and RAM (MB) of the current process, via psutil. Returns
    zeros (with a logged warning) if psutil is unavailable rather than
    raising, since this is a diagnostic nicety, not a hard dependency of
    detection itself."""
    try:
        import psutil

        process = psutil.Process()
        return {
            "cpu_percent": process.cpu_percent(interval=0.1),
            "memory_mb": process.memory_info().rss / (1024 * 1024),
            "system_cpu_percent": psutil.cpu_percent(interval=0.1),
            "system_memory_percent": psutil.virtual_memory().percent,
        }
    except ImportError:
        logger.warning(
            "psutil not installed — get_system_usage() returning zeros. "
            "Install via requirements_additions.txt for real CPU/RAM metrics."
        )
        return {"cpu_percent": 0.0, "memory_mb": 0.0, "system_cpu_percent": 0.0, "system_memory_percent": 0.0}


def set_global_seed(seed: int = config.RANDOM_SEED) -> None:
    import random

    random.seed(seed)
    np.random.seed(seed)
