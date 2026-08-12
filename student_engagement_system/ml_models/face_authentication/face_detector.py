"""
Face detection module built on MediaPipe Face Detection.

Supports both the legacy MediaPipe Solutions API and the newer MediaPipe
Tasks API transparently, so this module keeps working regardless of
which mediapipe version is installed.
"""
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List

import cv2
import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)
_MODEL_DIR = Path(__file__).resolve().parents[2] / "weights" / "face_detection"
_MODEL_PATH = _MODEL_DIR / "blaze_face_short_range.tflite"


@dataclass
class DetectedFace:
    """A single detected face within a frame."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    cropped_face: np.ndarray


def _download_task_model_if_missing() -> Path:
    """Download the BlazeFace Tasks-API model asset if not already cached.

    Returns:
        Path to the local .tflite model file.

    Raises:
        RuntimeError: If the model is missing and cannot be downloaded
            (e.g. no internet access).
    """
    if _MODEL_PATH.exists():
        return _MODEL_PATH
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        logger.info(f"Downloading MediaPipe Tasks face-detector model to {_MODEL_PATH} ...")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        return _MODEL_PATH
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "MediaPipe Tasks API model asset is not cached locally and could not be "
            f"downloaded ({exc}). Download it manually from {_MODEL_URL} and place it "
            f"at {_MODEL_PATH}."
        ) from exc


class FaceDetector:
    """Multi-face detector, backed by whichever MediaPipe API is available.

    Example:
        >>> detector = FaceDetector(min_confidence=0.6)
        >>> faces = detector.detect(frame)
    """

    def __init__(self, min_confidence: float = 0.6, model_selection: int = 1) -> None:
        """
        Args:
            min_confidence: Minimum detection confidence in [0, 1] to keep a face.
            model_selection: Legacy-API only: 0 for faces within ~2m of the
                camera (webcam use-case), 1 for a full-range model.
        """
        self.min_confidence = min_confidence
        self._backend = None       # "legacy" or "tasks"
        self._legacy_detector = None
        self._task_detector = None
        self._init_backend(model_selection)

    def _init_backend(self, model_selection: int) -> None:
        """Pick and initialize the legacy Solutions API if available,
        otherwise fall back to the Tasks API.
        """
        try:
            import mediapipe as mp
            mp_face_detection = mp.solutions.face_detection  # raises AttributeError if absent
            self._legacy_detector = mp_face_detection.FaceDetection(
                model_selection=model_selection, min_detection_confidence=self.min_confidence
            )
            self._backend = "legacy"
            logger.info("FaceDetector using legacy MediaPipe Solutions API.")
            return
        except AttributeError:
            logger.warning(
                "mediapipe.solutions is unavailable in this installation "
                "(removed in newer MediaPipe releases) -- falling back to the Tasks API."
            )

        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision as mp_vision

        model_path = _download_task_model_if_missing()
        base_options = mp_tasks.BaseOptions(model_asset_path=str(model_path))
        options = mp_vision.FaceDetectorOptions(
            base_options=base_options, min_detection_confidence=self.min_confidence
        )
        self._task_detector = mp_vision.FaceDetector.create_from_options(options)
        self._backend = "tasks"
        logger.info("FaceDetector using MediaPipe Tasks API.")

    def detect(self, frame: np.ndarray) -> List[DetectedFace]:
        """Detect all faces in a BGR frame above the confidence threshold.

        Args:
            frame: Input BGR image (as read from OpenCV/webcam).

        Returns:
            A list of DetectedFace objects, one per face found. Empty list
            if no face is found.
        """
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        detections: List[DetectedFace] = []

        if self._backend == "legacy":
            results = self._legacy_detector.process(rgb_frame)
            if not results.detections:
                return detections
            for det in results.detections:
                score = det.score[0] if det.score else 0.0
                if score < self.min_confidence:
                    continue
                box = det.location_data.relative_bounding_box
                x = max(0, int(box.xmin * w))
                y = max(0, int(box.ymin * h))
                box_w = min(int(box.width * w), w - x)
                box_h = min(int(box.height * h), h - y)
                if box_w <= 0 or box_h <= 0:
                    continue
                crop = frame[y:y + box_h, x:x + box_w].copy()
                detections.append(DetectedFace(x=x, y=y, width=box_w, height=box_h,
                                                confidence=float(score), cropped_face=crop))
        else:  # "tasks"
            import mediapipe as mp
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = self._task_detector.detect(mp_image)
            for det in result.detections:
                score = det.categories[0].score if det.categories else 0.0
                if score < self.min_confidence:
                    continue
                bbox = det.bounding_box
                x = max(0, bbox.origin_x)
                y = max(0, bbox.origin_y)
                box_w = min(bbox.width, w - x)
                box_h = min(bbox.height, h - y)
                if box_w <= 0 or box_h <= 0:
                    continue
                crop = frame[y:y + box_h, x:x + box_w].copy()
                detections.append(DetectedFace(x=x, y=y, width=box_w, height=box_h,
                                                confidence=float(score), cropped_face=crop))

        logger.debug(f"FaceDetector ({self._backend}) found {len(detections)} face(s) "
                     f"above threshold {self.min_confidence}")
        return detections

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self._legacy_detector is not None:
            self._legacy_detector.close()
        if self._task_detector is not None:
            self._task_detector.close()

    def __enter__(self) -> "FaceDetector":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
