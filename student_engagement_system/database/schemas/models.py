"""
MongoDB collection schemas for the Student Engagement Monitoring System.

Each Pydantic model documents and validates the shape of documents stored
in the corresponding MongoDB collection (see configs/database.yaml for
collection name mapping).
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CognitiveState(str, Enum):
    FOCUSED = "focused"
    NEUTRAL = "neutral"
    DISTRACTED = "distracted"
    TIRED = "tired"
    CONFUSED = "confused"


class EmotionLabel(str, Enum):
    HAPPY = "happy"
    NEUTRAL = "neutral"
    SAD = "sad"
    ANGRY = "angry"
    CONFUSED = "confused"
    TIRED = "tired"


class AlertType(str, Enum):
    LOW_ENGAGEMENT = "low_engagement"
    ATTENTION_DROP_PREDICTED = "attention_drop_predicted"
    PHONE_DETECTED = "phone_detected"
    MULTIPLE_PERSON_DETECTED = "multiple_person_detected"
    AUTH_FAILURE = "auth_failure"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"


# --- students -----------------------------------------------------------

class Student(BaseModel):
    """Document shape for the `students` collection."""
    student_id: str = Field(..., description="Unique student identifier, e.g. college USN")
    name: str
    email: str
    enrolled_courses: List[str] = Field(default_factory=list)
    face_embedding_ref: Optional[str] = Field(
        None, description="Path/key to the stored face embedding vector"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- sessions -------------------------------------------------------------

class Session(BaseModel):
    """Document shape for the `sessions` collection."""
    session_id: str
    course_id: str
    student_id: str
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE


# --- attendance -----------------------------------------------------------

class AttendanceRecord(BaseModel):
    """Document shape for the `attendance` collection."""
    session_id: str
    student_id: str
    verified: bool
    verification_confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- authentication ---------------------------------------------------------

class AuthenticationAttempt(BaseModel):
    """Document shape for the `authentication` collection (audit log)."""
    student_id: Optional[str] = None
    success: bool
    similarity_score: Optional[float] = None
    reason: Optional[str] = Field(None, description="Failure reason if success is False")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- engagement -------------------------------------------------------------

class EngagementRecord(BaseModel):
    """Document shape for the `engagement` collection."""
    session_id: str
    student_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    engagement_score: float = Field(..., ge=0.0, le=100.0)
    cognitive_state: CognitiveState
    emotion: Optional[EmotionLabel] = None
    eye_focus_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    head_pose_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    phone_detected: bool = False
    multiple_person_detected: bool = False


# --- predictions --------------------------------------------------------

class EngagementPrediction(BaseModel):
    """Document shape for the `predictions` collection."""
    session_id: str
    student_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    predicted_engagement_score: float = Field(..., ge=0.0, le=100.0)
    attention_drop_risk: str = Field(..., description="low | medium | high")
    horizon_seconds: int = Field(..., description="How far ahead this prediction looks")


# --- alerts --------------------------------------------------------------

class Alert(BaseModel):
    """Document shape for the `alerts` collection."""
    session_id: str
    student_id: str
    alert_type: AlertType
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False


# --- system_logs ---------------------------------------------------------

class SystemLogEntry(BaseModel):
    """Document shape for the `system_logs` collection (mirrors loguru records)."""
    level: str
    message: str
    module: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


COLLECTION_MODEL_MAP = {
    "students": Student,
    "sessions": Session,
    "attendance": AttendanceRecord,
    "authentication": AuthenticationAttempt,
    "engagement": EngagementRecord,
    "predictions": EngagementPrediction,
    "alerts": Alert,
    "system_logs": SystemLogEntry,
}
