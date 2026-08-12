"""
Cognitive Monitoring router.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ml_models.cognitive_monitoring.cognitive_features import (
    CognitiveFeatureError,
    CognitiveMonitoringInput,
)
from ml_models.cognitive_monitoring.cognitive_monitor import (
    CognitiveMonitoringError,
    get_cognitive_monitor,
)
from ml_models.engagement_prediction.engagement_features import (
    EngagementFeatureError,
    EngagementPredictionInput,
)
from ml_models.engagement_prediction.engagement_predictor import get_engagement_predictor
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["cognitive-monitoring"])


class CognitivePredictRequest(BaseModel):
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


class CognitivePredictResponse(BaseModel):
    student_id: str
    cognitive_state: str
    attention_score: float
    attention_level: str
    distraction_score: float
    fatigue_score: float
    confusion_score: float
    overall_confidence: float
    emotion: Optional[str]
    head_pose: str
    gaze: str
    multiple_person: bool
    phone_detected: bool
    engagement_score: float
    engagement_level: str
    risk_flags: List[str]
    reasons: List[str]
    degraded: bool
    error_message: Optional[str] = None
    processing_time_ms: float


@router.post("/cognitive/predict", response_model=CognitivePredictResponse)
def predict_cognitive_state(request: CognitivePredictRequest) -> CognitivePredictResponse:
    """Compute the cognitive-state assessment for one student's combined
    multimodal input (Phases 2-5 outputs), automatically running Phase 6's
    Engagement Prediction Engine first and feeding its result in as one of
    Phase 7's own inputs."""
    payload = request.model_dump()

    try:
        engagement_input = EngagementPredictionInput.from_dict(payload)
    except EngagementFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    engagement_predictor = get_engagement_predictor()
    engagement_result = engagement_predictor.predict_safe(engagement_input)
    if engagement_result.degraded:
        logger.warning(
            f"Phase 6 engagement prediction degraded while serving Phase 7 request for "
            f"student_id={request.student_id}: {engagement_result.error_message}"
        )

    payload["engagement_score"] = engagement_result.engagement_score
    payload["engagement_level"] = engagement_result.engagement_level
    payload["engagement_confidence"] = engagement_result.overall_confidence
    payload["engagement_risk_flags"] = engagement_result.risk_flags

    try:
        cognitive_input = CognitiveMonitoringInput.from_dict(payload)
    except CognitiveFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    monitor = get_cognitive_monitor()
    try:
        result = monitor.predict(cognitive_input)
    except CognitiveMonitoringError:
        # The engine itself failed unexpectedly -- degrade gracefully via
        # predict_safe() rather than surfacing a raw 500.
        result = monitor.predict_safe(cognitive_input)
        if result.degraded:
            logger.warning(
                f"Cognitive prediction degraded for student_id={request.student_id}: "
                f"{result.error_message}"
            )

    return CognitivePredictResponse(**result.as_dict())


@router.get("/cognitive/config")
def get_cognitive_config() -> Dict[str, Any]:
    """Return the currently loaded cognitive-monitoring configuration
    (attention weights, distraction penalties, fatigue/confusion/focus/risk
    thresholds, confidence weights, cognitive level ranges)."""
    monitor = get_cognitive_monitor()
    return monitor._get_config()


@router.get("/cognitive/health")
def cognitive_health() -> Dict[str, Any]:
    """Report whether the cognitive monitoring engine is available and
    which scoring backend is currently active."""
    monitor = get_cognitive_monitor()
    config = monitor._get_config()
    return {
        "status": "ok",
        "backend": config.get("backend", "rule_based"),
    }