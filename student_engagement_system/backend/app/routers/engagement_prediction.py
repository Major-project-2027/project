"""
Engagement Prediction router.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml_models.engagement_prediction.engagement_features import (
    EngagementFeatureError,
    EngagementPredictionInput,
)
from ml_models.engagement_prediction.engagement_predictor import (
    EngagementPredictionError,
    get_engagement_predictor,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["engagement-prediction"])


class EngagementPredictRequest(BaseModel):
    student_id: str = Field(..., description="Unique student identifier.")

    # Face Authentication / Attendance (Phase 2)
    face_detected: bool = Field(True, description="Whether a face was detected in frame.")
    authenticated: bool = Field(True, description="Whether the detected face was authenticated.")
    authentication_confidence: float = Field(1.0, ge=0.0, le=1.0)
    attendance: bool = Field(True, description="Whether the student is marked present.")

    # Emotion Detection (Phase 3)
    emotion: Optional[str] = Field(None, description="Detected emotion label.")
    emotion_confidence: float = Field(0.0, ge=0.0, le=1.0)

    # Head Pose (Phase 4)
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    head_pose_confidence: float = Field(0.0, ge=0.0, le=1.0)

    # Eye Gaze (Phase 4)
    looking_at_screen: bool = True
    looking_left: bool = False
    looking_right: bool = False
    looking_down: bool = False
    gaze_confidence: float = Field(0.0, ge=0.0, le=1.0)

    # Object Detection (Phase 5)
    person_count: int = Field(1, ge=0)
    multiple_person: bool = False
    phone_detected: bool = False
    phone_confidence: float = Field(0.0, ge=0.0, le=1.0)
    object_list: List[str] = Field(default_factory=list)


class EngagementPredictResponse(BaseModel):
    student_id: str
    engagement_score: float
    engagement_level: str
    overall_confidence: float
    emotion: Optional[str]
    head_pose: str
    gaze: str
    multiple_person: bool
    phone_detected: bool
    risk_flags: List[str]
    reasons: List[str]
    degraded: bool
    error_message: Optional[str] = None
    processing_time_ms: float


@router.post("/engagement/predict", response_model=EngagementPredictResponse)
def predict_engagement(request: EngagementPredictRequest) -> EngagementPredictResponse:
    """Compute the engagement score/level/confidence/flags/reasons for one
    student's combined multimodal input (Phases 2-5 outputs)."""
    payload = request.model_dump()
    try:
        engagement_input = EngagementPredictionInput.from_dict(payload)
    except EngagementFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    predictor = get_engagement_predictor()
    try:
        result = predictor.predict(engagement_input)
    except EngagementPredictionError:
        # The engine itself failed unexpectedly -- degrade gracefully via
        # predict_safe() rather than surfacing a raw 500.
        result = predictor.predict_safe(engagement_input)
        if result.degraded:
            logger.warning(
                f"Engagement prediction degraded for student_id={request.student_id}: "
                f"{result.error_message}"
            )

    return EngagementPredictResponse(**result.as_dict())


@router.get("/engagement/config")
def get_engagement_config() -> Dict[str, Any]:
    """Return the currently loaded engagement-prediction configuration
    (weights, penalties, bonuses, thresholds, ranges, confidence weights)."""
    predictor = get_engagement_predictor()
    return predictor._get_config()


@router.get("/engagement/health")
def engagement_health() -> Dict[str, Any]:
    """Report whether the engagement prediction engine is available and
    which scoring backend is currently active."""
    predictor = get_engagement_predictor()
    config = predictor._get_config()
    return {
        "status": "ok",
        "backend": config.get("backend", "rule_based"),
    }