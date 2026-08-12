"""
Emotion Recognition router.
"""
import base64
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml_models.emotion_detection.emotion_detector import EmotionDetector, EmotionAnalysisError
from ml_models.emotion_detection.emotion_labels import EMOTION_LABELS, EMOTION_METADATA
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/emotion", tags=["emotion-recognition"])

# NOTE: EmotionDetector loads a DeepFace/TensorFlow model, which can be slow
# and requires an optional heavy dependency. We deliberately do NOT construct
# it at import time -- a missing dependency must never crash the whole API on
# startup. Instead it is created lazily, on first actual use, and cached.
_detector: Optional[EmotionDetector] = None


def _get_detector() -> EmotionDetector:
    global _detector
    if _detector is None:
        _detector = EmotionDetector()
    return _detector


class PredictRequest(BaseModel):
    face_crop_b64: str = Field(..., description="Base64-encoded JPEG/PNG face crop.")
    student_id: Optional[str] = Field(None, description="Optional student ID for logging/correlation.")


class PredictResponse(BaseModel):
    emotion: str
    confidence: float
    processing_time: float
    scores: dict


class EmotionLabelInfo(BaseModel):
    label: str
    display_name: str
    icon: str
    polarity: str


def _decode_b64_image(face_crop_b64: str) -> Optional[np.ndarray]:
    """Decode a single base64 JPEG/PNG string into a BGR NumPy array."""
    try:
        raw_bytes = base64.b64decode(face_crop_b64)
        array = np.frombuffer(raw_bytes, dtype=np.uint8)
        return cv2.imdecode(array, cv2.IMREAD_COLOR)
    except Exception as exc:  # noqa: BLE001 -- malformed client input takes many shapes
        logger.warning(f"Failed to decode face_crop_b64: {exc}")
        return None


@router.post("/predict", response_model=PredictResponse)
async def predict_emotion(payload: PredictRequest) -> PredictResponse:
    """Analyze a base64-encoded face crop and return the predicted emotion."""
    image = _decode_b64_image(payload.face_crop_b64)
    if image is None:
        raise HTTPException(status_code=400, detail="face_crop_b64 could not be decoded as an image.")

    try:
        detector = _get_detector()
    except EmotionAnalysisError as exc:
        raise HTTPException(status_code=503, detail=f"Emotion analysis backend unavailable: {exc}") from exc

    try:
        result = detector.analyze(image)
    except EmotionAnalysisError as exc:
        raise HTTPException(status_code=422, detail=f"Emotion analysis failed: {exc}") from exc

    if payload.student_id:
        logger.info(
            f"Emotion prediction for student_id={payload.student_id}: "
            f"{result.emotion} ({result.confidence:.3f})"
        )

    return PredictResponse(
        emotion=result.emotion,
        confidence=result.confidence,
        processing_time=result.processing_time_ms,
        scores=result.scores,
    )


@router.get("/labels", response_model=List[EmotionLabelInfo])
async def list_emotion_labels() -> List[EmotionLabelInfo]:
    """List the 7 supported emotion labels with their display metadata."""
    return [
        EmotionLabelInfo(
            label=label,
            display_name=EMOTION_METADATA[label].display_name,
            icon=EMOTION_METADATA[label].icon,
            polarity=EMOTION_METADATA[label].polarity,
        )
        for label in EMOTION_LABELS
    ]
