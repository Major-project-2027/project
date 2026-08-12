"""
Object Detection and Classroom Monitoring router.
"""
import base64
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml_models.object_detection.object_detector import (
    InvalidFrameError,
    ObjectDetectionError,
    get_object_detector,
)
from ml_models.object_detection.object_labels import ALL_TARGET_CLASSES
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["object-detection"])


class FrameRequest(BaseModel):
    frame_b64: str = Field(..., description="Base64-encoded JPEG/PNG video frame.")
    student_id: Optional[str] = Field(None, description="Optional student ID for logging/correlation.")


class DetectedObjectResponse(BaseModel):
    class_name: str = Field(..., alias="class")
    confidence: float
    bbox: List[float]

    class Config:
        populate_by_name = True


class ObjectDetectionResponse(BaseModel):
    person_count: int
    multiple_person: bool
    phone_detected: bool
    phone_confidence: float
    objects: List[DetectedObjectResponse]
    processing_time_ms: float
    degraded: bool
    error_message: Optional[str] = None


def _decode_frame(frame_b64: str) -> np.ndarray:
    try:
        raw_bytes = base64.b64decode(frame_b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid base64 frame data: {exc}") from exc

    np_buffer = np.frombuffer(raw_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode frame -- not a valid image.")
    return frame


@router.post("/object-detection/detect", response_model=ObjectDetectionResponse)
def detect_objects(request: FrameRequest) -> ObjectDetectionResponse:
    """Run object detection on a single video frame."""
    frame = _decode_frame(request.frame_b64)
    detector = get_object_detector()

    try:
        result = detector.detect(frame)
    except InvalidFrameError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ObjectDetectionError:
        # The model backend is genuinely unavailable -- degrade gracefully
        # via detect_safe() instead of surfacing a raw 500.
        result = detector.detect_safe(frame)
        if result.degraded:
            logger.warning(f"Object detection degraded for student_id={request.student_id}: "
                            f"{result.error_message}")

    payload = result.as_dict()
    payload["objects"] = [
        {"class": obj["class"], "confidence": obj["confidence"], "bbox": obj["bbox"]}
        for obj in payload["objects"]
    ]
    return ObjectDetectionResponse(**payload)


@router.get("/object-detection/classes")
def list_target_classes() -> List[str]:
    """Return the sorted list of classes this pipeline tracks."""
    return sorted(ALL_TARGET_CLASSES)


@router.get("/object-detection/health")
def object_detection_health() -> dict:
    """Report whether the YOLO backend is currently loaded and available."""
    detector = get_object_detector()
    return {
        "model_loaded": detector._model is not None,
        "model_load_failed": detector._model_load_failed,
    }
