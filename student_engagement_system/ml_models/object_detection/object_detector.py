"""
Object Detection and Classroom Monitoring module.

Wraps YOLOv11 (Ultralytics) for real-time detection of classroom objects --
most importantly students (person) and mobile phones (cell phone), plus the
optional laptop / book / mouse / keyboard / monitor classes. Ultralytics is an
optional, heavy dependency: it is imported lazily (only when a detector
instance actually needs to run inference) so this module -- and anything that
imports it -- never crashes just because Ultralytics or its weights are
unavailable in the current environment. This mirrors Phase 2's DeepFace
handling and Phase 3/4's MediaPipe handling exactly.
"""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ml_models.object_detection.detection_utils import (
    Detection,
    TemporalSmoother,
    count_persons,
    filter_by_confidence,
    find_best_phone_detection,
)
from ml_models.object_detection.object_labels import ALL_TARGET_CLASSES, COCO_ID_TO_CLASS
from utils.common import load_yaml_config
from utils.logger import get_logger

logger = get_logger(__name__)


class ObjectDetectionError(Exception):
    """Base exception for all Phase 5 object-detection failures."""


class ModelLoadError(ObjectDetectionError):
    """Raised when the YOLO backend (Ultralytics) cannot be imported or its
    pretrained weights cannot be loaded."""


class InvalidFrameError(ObjectDetectionError):
    """Raised when the input frame fails basic quality/shape validation."""


@dataclass(frozen=True)
class ObjectDetectionResult:
    """Structured result of running object detection on a single frame."""

    person_count: int
    multiple_person: bool
    phone_detected: bool
    phone_confidence: float
    objects: List[Detection] = field(default_factory=list)
    processing_time_ms: float = 0.0
    degraded: bool = False
    error_message: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "person_count": self.person_count,
            "multiple_person": self.multiple_person,
            "phone_detected": self.phone_detected,
            "phone_confidence": round(float(self.phone_confidence), 4),
            "objects": [obj.as_dict() for obj in self.objects],
            "processing_time_ms": round(float(self.processing_time_ms), 3),
            "degraded": self.degraded,
            "error_message": self.error_message,
        }


def _validate_frame(frame: np.ndarray, min_size=(32, 32)) -> None:
    """Basic quality validation for an input frame.

    Raises:
        InvalidFrameError: If the frame is not a valid 3-channel image of at
            least min_size pixels in each dimension.
    """
    if frame is None:
        raise InvalidFrameError("Frame is None.")
    if not isinstance(frame, np.ndarray):
        raise InvalidFrameError(f"Frame must be a numpy.ndarray, got {type(frame)!r}.")
    if frame.ndim != 3 or frame.shape[2] not in (1, 3, 4):
        raise InvalidFrameError(f"Frame must have shape (H, W, C); got {frame.shape}.")
    height, width = frame.shape[0], frame.shape[1]
    min_h, min_w = min_size
    if height < min_h or width < min_w:
        raise InvalidFrameError(
            f"Frame too small ({width}x{height}); minimum is {min_w}x{min_h}."
        )


class ObjectDetector:
    """YOLOv11-based classroom object detector.

    The Ultralytics ``YOLO`` model is loaded lazily on first use and cached
    for the lifetime of this instance. Use :func:`get_object_detector` to
    obtain the shared, process-wide singleton instead of constructing this
    class directly wherever possible.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        self._model: Any = None  # Ultralytics YOLO instance, loaded lazily.
        self._model_load_failed = False
        self._person_smoother: Optional[TemporalSmoother] = None
        self._phone_smoother: Optional[TemporalSmoother] = None
        logger.info("ObjectDetector instance created (model not yet loaded -- lazy loading).")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _get_config(self) -> Dict[str, Any]:
        if self._config is None:
            config_path = self._config_path or (
                Path(__file__).resolve().parents[2] / "configs" / "object_detection.yaml"
            )
            self._config = load_yaml_config(config_path)
            logger.info(f"Loaded object detection config from {config_path}")
        return self._config

    def _get_person_smoother(self) -> TemporalSmoother:
        if self._person_smoother is None:
            smoothing_cfg = self._get_config().get("smoothing", {})
            self._person_smoother = TemporalSmoother(
                window_size=int(smoothing_cfg.get("window_size", 5)),
                min_true_ratio=float(smoothing_cfg.get("min_true_ratio", 0.6)),
            )
        return self._person_smoother

    def _get_phone_smoother(self) -> TemporalSmoother:
        if self._phone_smoother is None:
            smoothing_cfg = self._get_config().get("smoothing", {})
            self._phone_smoother = TemporalSmoother(
                window_size=int(smoothing_cfg.get("window_size", 5)),
                min_true_ratio=float(smoothing_cfg.get("min_true_ratio", 0.6)),
            )
        return self._phone_smoother

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------
    def _load_model(self) -> Any:
        """Lazily import Ultralytics and load YOLOv11 pretrained weights.

        Raises:
            ModelLoadError: If Ultralytics is not installed or the weights
                fail to load for any reason.
        """
        if self._model is not None:
            return self._model
        if self._model_load_failed:
            raise ModelLoadError("YOLO model previously failed to load; not retrying.")
        try:
            from ultralytics import YOLO  # Optional, heavy dependency -- imported lazily.
        except ImportError as exc:
            self._model_load_failed = True
            raise ModelLoadError(
                "Ultralytics is not installed. Install it with `pip install ultralytics` "
                "to enable object detection."
            ) from exc

        weights_name = self._get_config().get("model", {}).get("weights", "yolo11n.pt")
        try:
            model = YOLO(weights_name)
        except Exception as exc:  # noqa: BLE001 -- any backend failure must degrade gracefully.
            self._model_load_failed = True
            raise ModelLoadError(f"Failed to load YOLO weights '{weights_name}': {exc}") from exc

        self._model = model
        logger.info(f"YOLO model loaded successfully: {weights_name}")
        return self._model

    # ------------------------------------------------------------------
    # Inference seam -- swapping the detection backend only requires
    # reimplementing this one method.
    # ------------------------------------------------------------------
    def _run_inference(self, frame: np.ndarray) -> List[Detection]:
        model = self._load_model()
        config = self._get_config()
        confidence_threshold = float(config.get("thresholds", {}).get("confidence_threshold", 0.60))
        iou_threshold = float(config.get("thresholds", {}).get("iou_threshold", 0.45))

        results = model.predict(
            source=frame,
            conf=confidence_threshold,
            iou=iou_threshold,
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections

        names = getattr(model, "names", COCO_ID_TO_CLASS)
        for box in boxes:
            class_id = int(box.cls[0]) if hasattr(box, "cls") else int(box[5])
            confidence = float(box.conf[0]) if hasattr(box, "conf") else float(box[4])
            xyxy = box.xyxy[0].tolist() if hasattr(box, "xyxy") else list(box[:4])
            class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
            if class_name not in ALL_TARGET_CLASSES:
                continue
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=(float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
                )
            )
        return detections

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray) -> ObjectDetectionResult:
        """Run object detection on a single frame.

        Raises:
            InvalidFrameError: If the frame fails basic quality validation.
            ModelLoadError: If the YOLO backend cannot be loaded.
            ObjectDetectionError: For any other detection failure.
        """
        start = time.perf_counter()
        _validate_frame(frame)

        config = self._get_config()
        confidence_threshold = float(config.get("thresholds", {}).get("confidence_threshold", 0.60))

        try:
            raw_detections = self._run_inference(frame)
        except ObjectDetectionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ObjectDetectionError(f"Inference failed: {exc}") from exc

        filtered = filter_by_confidence(raw_detections, confidence_threshold)
        person_count = count_persons(filtered)
        raw_multiple_person = person_count > 1
        multiple_person = self._get_person_smoother().update(raw_multiple_person)

        best_phone = find_best_phone_detection(filtered)
        raw_phone_detected = best_phone is not None
        phone_detected = self._get_phone_smoother().update(raw_phone_detected)
        phone_confidence = best_phone.confidence if best_phone is not None else 0.0

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        result = ObjectDetectionResult(
            person_count=person_count,
            multiple_person=multiple_person,
            phone_detected=phone_detected,
            phone_confidence=phone_confidence,
            objects=filtered,
            processing_time_ms=elapsed_ms,
            degraded=False,
        )
        logger.info(
            f"Object detection: person_count={person_count} multiple_person={multiple_person} "
            f"phone_detected={phone_detected} objects={len(filtered)} "
            f"time={elapsed_ms:.2f}ms"
        )
        return result

    def detect_safe(self, frame: np.ndarray) -> ObjectDetectionResult:
        """Run detect(), degrading gracefully instead of raising on failure.

        Returns an ObjectDetectionResult with degraded=True and an
        error_message set whenever the underlying model/backend is
        unavailable or inference otherwise fails, so callers (e.g. the
        FastAPI router) never need to handle a raw exception.
        """
        start = time.perf_counter()
        try:
            return self.detect(frame)
        except ObjectDetectionError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.error(f"Object detection degraded gracefully: {exc}")
            return ObjectDetectionResult(
                person_count=0,
                multiple_person=False,
                phone_detected=False,
                phone_confidence=0.0,
                objects=[],
                processing_time_ms=elapsed_ms,
                degraded=True,
                error_message=str(exc),
            )


# ----------------------------------------------------------------------
# Process-wide singleton accessor (mirrors Phase 3's EmotionDetector /
# Phase 4's HeadPoseEstimator / GazeEstimator lazy-singleton pattern).
# ----------------------------------------------------------------------
_object_detector: Optional[ObjectDetector] = None


def get_object_detector() -> ObjectDetector:
    """Return the shared, process-wide ObjectDetector singleton, creating it
    on first call. The underlying YOLO model is still loaded lazily on first
    detect() call, not here."""
    global _object_detector
    if _object_detector is None:
        _object_detector = ObjectDetector()
    return _object_detector


def reset_object_detector() -> None:
    """Reset the singleton -- primarily useful for tests."""
    global _object_detector
    _object_detector = None
