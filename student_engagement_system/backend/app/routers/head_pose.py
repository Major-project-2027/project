"""
Head Pose Estimation and Eye Gaze Estimation router.
"""
import base64
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml_models.gaze_head_pose.gaze_estimator import GazeEstimationError, GazeEstimator
from ml_models.gaze_head_pose.gaze_utils import GAZE_DIRECTIONS
from ml_models.gaze_head_pose.head_pose import HeadPoseEstimationError, HeadPoseEstimator
from ml_models.gaze_head_pose.head_pose_utils import HEAD_POSE_DIRECTIONS
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["head-pose-gaze"])

# NOTE: both estimators load a MediaPipe Face Mesh model, an optional heavy
# dependency. We deliberately do NOT construct them at import time -- a
# missing/incompatible MediaPipe installation must never crash the whole
# API on startup. Instead each is created lazily, on first actual use, and
# cached -- exactly Phase 3's pattern for EmotionDetector.
_head_pose_estimator: Optional[HeadPoseEstimator] = None
_gaze_estimator: Optional[GazeEstimator] = None


def _get_head_pose_estimator() -> HeadPoseEstimator:
    global _head_pose_estimator
    if _head_pose_estimator is None:
        _head_pose_estimator = HeadPoseEstimator()
    return _head_pose_estimator


def _get_gaze_estimator() -> GazeEstimator:
    global _gaze_estimator
    if _gaze_estimator is None:
        _gaze_estimator = GazeEstimator()
    return _gaze_estimator


class FrameRequest(BaseModel):
    frame_b64: str = Field(..., description="Base64-encoded JPEG/PNG video frame.")
    student_id: Optional[str] = Field(None, description="Optional student ID for logging/correlation.")


class HeadPoseResponse(BaseModel):
    yaw: float
    pitch: float
    roll: float
    direction: str
    confidence: float
    processing_time: float


class GazeResponse(BaseModel):
    direction: str
    horizontal_ratio: float
    vertical_ratio: float
    ear_left: float
    ear_right: float
    is_blinking: bool
    confidence: float
    processing_time: float


def _decode_b64_image(frame_b64: str) -> Optional[np.ndarray]:
    """Decode a single base64 JPEG/PNG string into a BGR NumPy array."""
    try:
        raw_bytes = base64.b64decode(frame_b64)
        array = np.frombuffer(raw_bytes, dtype=np.uint8)
        return cv2.imdecode(array, cv2.IMREAD_COLOR)
    except Exception as exc:  # noqa: BLE001 -- malformed client input takes many shapes
        logger.warning(f"Failed to decode frame_b64: {exc}")
        return None


@router.post("/head-pose/estimate", response_model=HeadPoseResponse)
async def estimate_head_pose(payload: FrameRequest) -> HeadPoseResponse:
    """Estimate yaw/pitch/roll and a coarse direction for a base64 video frame."""
    image = _decode_b64_image(payload.frame_b64)
    if image is None:
        raise HTTPException(status_code=400, detail="frame_b64 could not be decoded as an image.")

    try:
        estimator = _get_head_pose_estimator()
    except HeadPoseEstimationError as exc:
        raise HTTPException(status_code=503, detail=f"Head-pose backend unavailable: {exc}") from exc

    try:
        result = estimator.estimate(image)
    except HeadPoseEstimationError as exc:
        raise HTTPException(status_code=422, detail=f"Head-pose estimation failed: {exc}") from exc

    if payload.student_id:
        logger.info(
            f"Head-pose estimate for student_id={payload.student_id}: "
            f"direction={result.direction}, yaw={result.yaw:.1f}, pitch={result.pitch:.1f}"
        )

    return HeadPoseResponse(
        yaw=result.yaw,
        pitch=result.pitch,
        roll=result.roll,
        direction=result.direction,
        confidence=result.confidence,
        processing_time=result.processing_time_ms,
    )


@router.get("/head-pose/directions", response_model=List[str])
async def list_head_pose_directions() -> List[str]:
    """List the 5 supported head-pose direction labels."""
    return list(HEAD_POSE_DIRECTIONS)


@router.post("/gaze/estimate", response_model=GazeResponse)
async def estimate_gaze(payload: FrameRequest) -> GazeResponse:
    """Estimate eye gaze direction and blink state for a base64 video frame."""
    image = _decode_b64_image(payload.frame_b64)
    if image is None:
        raise HTTPException(status_code=400, detail="frame_b64 could not be decoded as an image.")

    try:
        estimator = _get_gaze_estimator()
    except GazeEstimationError as exc:
        raise HTTPException(status_code=503, detail=f"Gaze estimation backend unavailable: {exc}") from exc

    try:
        result = estimator.estimate(image)
    except GazeEstimationError as exc:
        raise HTTPException(status_code=422, detail=f"Gaze estimation failed: {exc}") from exc

    if payload.student_id:
        logger.info(
            f"Gaze estimate for student_id={payload.student_id}: "
            f"direction={result.direction}, blinking={result.is_blinking}"
        )

    return GazeResponse(
        direction=result.direction,
        horizontal_ratio=result.horizontal_ratio,
        vertical_ratio=result.vertical_ratio,
        ear_left=result.ear_left,
        ear_right=result.ear_right,
        is_blinking=result.is_blinking,
        confidence=result.confidence,
        processing_time=result.processing_time_ms,
    )


@router.get("/gaze/directions", response_model=List[str])
async def list_gaze_directions() -> List[str]:
    """List the 5 supported eye-gaze direction labels."""
    return list(GAZE_DIRECTIONS)
