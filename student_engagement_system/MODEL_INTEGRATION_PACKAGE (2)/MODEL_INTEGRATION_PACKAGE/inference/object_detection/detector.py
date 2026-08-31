"""
detector.py
-----------
Thin, production-hardened wrapper around Ultralytics YOLO for this
module's specific needs: automatic model selection (YOLOv11 -> YOLOv8m
fallback), CPU-friendly defaults, mapping the underlying model's native
class vocabulary onto our 17-class classroom taxonomy, and returning the
structured `utils.Detection` / `utils.FrameResult` types rather than raw
Ultralytics `Results` objects — every other file in this module (and any
future consumer, e.g. the LSTM fusion module) depends on this stable
output contract, not on Ultralytics' internal API.

No custom training happens here or anywhere in this module — every
weights file loaded is a stock pretrained release fetched by the
`ultralytics` package itself (auto-downloaded to its local cache on first
use; no manual download step).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np

import config
from utils import BoundingBox, Detection, FrameResult, build_frame_events, get_logger

logger = get_logger(__name__)


def _select_weights(performance_mode: str) -> tuple[str, str]:
    """Return (primary_weights, fallback_weights) file names for the
    requested performance mode ("accuracy" -> YOLOv11m/YOLOv8m,
    "speed" -> YOLOv11n/YOLOv8n)."""
    if performance_mode == "accuracy":
        return config.PRIMARY_WEIGHTS_ACCURACY, config.FALLBACK_WEIGHTS_ACCURACY
    if performance_mode == "speed":
        return config.PRIMARY_WEIGHTS_SPEED, config.FALLBACK_WEIGHTS_SPEED
    raise ValueError(f"Unknown PERFORMANCE_MODE '{performance_mode}' — expected 'accuracy' or 'speed'.")


def load_yolo_model(weights_name: str, fallback_weights_name: Optional[str] = None):
    """Load a YOLO model by weights filename, letting Ultralytics
    auto-download the pretrained checkpoint on first use. Falls back to
    `fallback_weights_name` (e.g. a YOLOv8 checkpoint) if the requested
    weights can't be loaded (older `ultralytics` install without YOLOv11
    support, network hiccup on first download, etc.) — logged clearly
    either way, never a silent substitution.
    """
    from ultralytics import YOLO

    try:
        model = YOLO(weights_name)
        logger.info("Loaded YOLO weights: %s", weights_name)
        return model, weights_name
    except Exception as primary_error:  # noqa: BLE001 - intentionally broad: many failure modes here
        logger.warning("Failed to load '%s' (%s).", weights_name, primary_error)
        if not fallback_weights_name:
            raise

        logger.warning("Falling back to '%s'.", fallback_weights_name)
        model = YOLO(fallback_weights_name)
        logger.info("Loaded fallback YOLO weights: %s", fallback_weights_name)
        return model, fallback_weights_name


def resolve_device(requested_device: str) -> str:
    """Fall back to CPU if the requested device (e.g. 'cuda:0') isn't
    actually available, rather than letting Ultralytics/torch raise deep
    inside a predict() call."""
    if requested_device == "cpu":
        return "cpu"

    try:
        import torch

        if requested_device.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("Requested device '%s' but CUDA is not available — using CPU.", requested_device)
            return "cpu"
        if requested_device == "mps" and not (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        ):
            logger.warning("Requested device 'mps' but MPS is not available — using CPU.")
            return "cpu"
    except ImportError:
        logger.warning("torch not importable — using CPU.")
        return "cpu"

    return requested_device


def validate_class_mapping(model_names: dict[int, str], name_to_target_map: dict[str, str], model_label: str) -> None:
    """Cross-check `name_to_target_map`'s source class names against the
    class names actually present on the loaded model (`model.names`).
    Logs a clear warning listing every target class this particular
    model/weights combination will NOT be able to produce — instead of
    silently assuming a mapping is correct. This is what lets
    config.OIV7_NAME_TO_TARGET's entries be trusted or distrusted
    per-deployment rather than accepted on faith.
    """
    available_source_names = set(model_names.values())
    missing = [src for src in name_to_target_map if src not in available_source_names]
    if missing:
        unmapped_targets = sorted({name_to_target_map[src] for src in missing})
        logger.warning(
            "[%s] %d expected source class name(s) not found in the loaded model's vocabulary — "
            "the following target classes will NOT be detected by this model: %s. "
            "(Missing source names: %s)",
            model_label, len(missing), unmapped_targets, missing,
        )
    else:
        logger.info("[%s] Class mapping fully validated against the loaded model's vocabulary.", model_label)


class ObjectDetector:
    """Loads the configured YOLO model(s) and runs single-frame inference,
    returning `utils.FrameResult`. Tracking (persistent IDs across frames)
    is layered on top by `tracker.py` / `predictor.py` — this class's
    `detect()` method is stateless per call by design, so it can also be
    used for plain single-image inference (dataset evaluation, batch
    folder inference) where tracking is meaningless.
    """

    def __init__(
        self,
        performance_mode: str = config.PERFORMANCE_MODE,
        device: str = config.DEVICE,
        confidence_threshold: float = config.CONFIDENCE_THRESHOLD,
        nms_iou_threshold: float = config.NMS_IOU_THRESHOLD,
        image_size: int = config.INFERENCE_IMAGE_SIZE,
        use_oiv7_secondary: bool = config.USE_OIV7_SECONDARY_MODEL,
    ) -> None:
        config.ensure_directories()

        self.device = resolve_device(device)
        self.confidence_threshold = confidence_threshold
        self.nms_iou_threshold = nms_iou_threshold
        self.image_size = image_size
        self.half_precision = config.HALF_PRECISION and self.device != "cpu"

        primary_weights, fallback_weights = _select_weights(performance_mode)
        self.model, self.loaded_weights_name = load_yolo_model(primary_weights, fallback_weights)
        self.model.to(self.device)

        validate_class_mapping(self.model.names, config.COCO_NAME_TO_TARGET, self.loaded_weights_name)

        self.oiv7_model = None
        self._frame_counter = 0
        if use_oiv7_secondary:
            try:
                self.oiv7_model, oiv7_loaded_name = load_yolo_model(config.OIV7_WEIGHTS)
                self.oiv7_model.to(self.device)
                validate_class_mapping(self.oiv7_model.names, config.OIV7_NAME_TO_TARGET, oiv7_loaded_name)
            except Exception as e:  # noqa: BLE001
                logger.error("Could not load OIV7 secondary model (%s) — continuing with primary model only.", e)
                self.oiv7_model = None

        logger.info(
            "ObjectDetector ready | weights=%s | device=%s | imgsz=%d | conf>=%.2f | iou<=%.2f | oiv7_secondary=%s",
            self.loaded_weights_name, self.device, self.image_size,
            self.confidence_threshold, self.nms_iou_threshold, self.oiv7_model is not None,
        )

    # ------------------------------------------------------------------
    def _map_result_to_detections(self, ultralytics_result, name_map: dict[str, str], source_label: str) -> list[Detection]:
        detections: list[Detection] = []
        if ultralytics_result.boxes is None:
            return detections

        boxes = ultralytics_result.boxes
        names = ultralytics_result.names

        for i in range(len(boxes)):
            raw_class_id = int(boxes.cls[i].item())
            raw_class_name = names[raw_class_id]
            confidence = float(boxes.conf[i].item())
            xyxy = boxes.xyxy[i].tolist()

            target_name = name_map.get(raw_class_name, config.UNKNOWN_CLASS_NAME)
            target_class_id = config.CLASS_TO_INDEX.get(target_name, config.CLASS_TO_INDEX[config.UNKNOWN_CLASS_NAME])

            track_id = None
            if getattr(boxes, "id", None) is not None:
                track_id = int(boxes.id[i].item())

            person_id = track_id if target_name in config.PERSON_LIKE_CLASSES else None

            detections.append(
                Detection(
                    class_id=target_class_id,
                    class_name=target_name,
                    confidence=confidence,
                    bbox=BoundingBox(xyxy[0], xyxy[1], xyxy[2], xyxy[3]),
                    track_id=track_id,
                    person_id=person_id,
                    source_model=source_label,
                )
            )
        return detections

    # ------------------------------------------------------------------
    def detect(
        self,
        frame: np.ndarray,
        track: bool = False,
        tracker_config: Optional[str] = None,
    ) -> FrameResult:
        """Run single-frame inference (optionally with Ultralytics'
        built-in tracker active) and return a fully populated
        `FrameResult` including derived `events`.

        Parameters
        ----------
        frame : np.ndarray
            BGR image (as read by cv2.imread / cv2.VideoCapture).
        track : bool
            If True, call the model's `.track()` API (persistent IDs
            across sequential calls on the same detector instance) rather
            than stateless `.predict()`. `tracker.py` is the intended
            caller for `track=True` — see that module for ID-persistence
            details.
        tracker_config : str, optional
            Ultralytics tracker YAML name (e.g. "bytetrack.yaml"); only
            used when `track=True`.
        """
        frame_start = time.perf_counter()
        self._frame_counter += 1

        predict_kwargs = dict(
            source=frame,
            conf=self.confidence_threshold,
            iou=self.nms_iou_threshold,
            imgsz=self.image_size,
            max_det=config.MAX_DETECTIONS_PER_IMAGE,
            device=self.device,
            half=self.half_precision,
            verbose=False,
        )

        if track:
            results = self.model.track(
                persist=config.TRACK_PERSIST,
                tracker=tracker_config or config.TRACKER_PRIMARY,
                **predict_kwargs,
            )
        else:
            results = self.model.predict(**predict_kwargs)

        detections = self._map_result_to_detections(results[0], config.COCO_NAME_TO_TARGET, "primary")

        if self.oiv7_model is not None:
            oiv7_results = self.oiv7_model.predict(**predict_kwargs)
            oiv7_detections = self._map_result_to_detections(oiv7_results[0], config.OIV7_NAME_TO_TARGET, "oiv7")
            # Only keep OIV7 detections for target classes the primary
            # (COCO) model cannot produce at all, to avoid double-counting
            # the same physical object (e.g. "Person") from both models.
            coco_coverable = set(config.COCO_NAME_TO_TARGET.values())
            detections.extend(d for d in oiv7_detections if d.class_name not in coco_coverable)

        processing_time_ms = (time.perf_counter() - frame_start) * 1000.0
        fps = 1000.0 / processing_time_ms if processing_time_ms > 0 else 0.0

        frame_result = FrameResult(
            timestamp=time.time(),
            frame_index=self._frame_counter,
            detections=detections,
            fps=fps,
            latency_ms=processing_time_ms,
            processing_time_ms=processing_time_ms,
        )
        frame_result.events = build_frame_events(detections)
        return frame_result

    def reset_tracker_state(self) -> None:
        """Clear Ultralytics' internal tracker state (call this between
        unrelated videos/streams so track IDs don't carry over)."""
        if hasattr(self.model, "predictor") and self.model.predictor is not None:
            self.model.predictor.trackers = []
        logger.info("Tracker state reset.")


if __name__ == "__main__":
    import numpy as np

    detector = ObjectDetector()
    dummy_frame = np.zeros((480, 640, 3), dtype="uint8")
    result = detector.detect(dummy_frame)
    print(result.to_dict())
