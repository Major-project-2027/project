"""
Phase 8 Dashboard & Analytics -- typed data contracts.

These dataclasses model one aggregation-layer event (a snapshot produced by
combining Phases 2-7 outputs, typically the response of Phase 7's
`POST /cognitive/predict`) plus the request-side filters the dashboard API
accepts. Nothing here duplicates Phase 2-7 prediction logic -- it only
shapes data for storage, querying, and display.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DashboardFeatureError(ValueError):
    """Raised when a dashboard event or query payload fails validation."""


VALID_PERIODS = ("daily", "weekly", "monthly", "student", "class")
VALID_METRICS = (
    "emotion",
    "engagement",
    "cognitive",
    "attention",
    "fatigue",
    "phone_detection",
    "multiple_people",
    "attendance",
    "session_duration",
    "risk_flags",
)


@dataclass(frozen=True)
class DashboardEvent:
    """One point-in-time snapshot recorded for the dashboard.

    Mirrors the shape of Phase 7's `CognitivePredictResponse` plus a
    handful of dashboard-only fields (`fps`, `session_id`). Every field
    has a safe default so a partial payload (e.g. only emotion, no
    cognitive fields yet) can still be recorded.
    """

    student_id: str
    timestamp: str = ""

    session_id: Optional[str] = None
    attendance: bool = True

    emotion: Optional[str] = None
    emotion_confidence: float = 0.0

    cognitive_state: Optional[str] = None
    attention_score: float = 0.0
    attention_level: Optional[str] = None
    distraction_score: float = 0.0
    fatigue_score: float = 0.0
    confusion_score: float = 0.0

    engagement_score: float = 0.0
    engagement_level: Optional[str] = None

    head_pose: Optional[str] = None
    gaze: Optional[str] = None
    multiple_person: bool = False
    phone_detected: bool = False

    overall_confidence: float = 0.0
    risk_flags: List[str] = field(default_factory=list)

    fps: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "attendance": self.attendance,
            "emotion": self.emotion,
            "emotion_confidence": self.emotion_confidence,
            "cognitive_state": self.cognitive_state,
            "attention_score": self.attention_score,
            "attention_level": self.attention_level,
            "distraction_score": self.distraction_score,
            "fatigue_score": self.fatigue_score,
            "confusion_score": self.confusion_score,
            "engagement_score": self.engagement_score,
            "engagement_level": self.engagement_level,
            "head_pose": self.head_pose,
            "gaze": self.gaze,
            "multiple_person": self.multiple_person,
            "phone_detected": self.phone_detected,
            "overall_confidence": self.overall_confidence,
            "risk_flags": list(self.risk_flags),
            "fps": self.fps,
        }

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "DashboardEvent":
        if not isinstance(payload, dict):
            raise DashboardFeatureError("Event payload must be a JSON object.")

        student_id = payload.get("student_id")
        if not student_id or not isinstance(student_id, str):
            raise DashboardFeatureError("Event payload requires a non-empty 'student_id' string.")

        timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()

        try:
            return DashboardEvent(
                student_id=student_id,
                timestamp=timestamp,
                session_id=payload.get("session_id"),
                attendance=bool(payload.get("attendance", True)),
                emotion=payload.get("emotion"),
                emotion_confidence=float(payload.get("emotion_confidence", 0.0) or 0.0),
                cognitive_state=payload.get("cognitive_state"),
                attention_score=float(payload.get("attention_score", 0.0) or 0.0),
                attention_level=payload.get("attention_level"),
                distraction_score=float(payload.get("distraction_score", 0.0) or 0.0),
                fatigue_score=float(payload.get("fatigue_score", 0.0) or 0.0),
                confusion_score=float(payload.get("confusion_score", 0.0) or 0.0),
                engagement_score=float(payload.get("engagement_score", 0.0) or 0.0),
                engagement_level=payload.get("engagement_level"),
                head_pose=payload.get("head_pose"),
                gaze=payload.get("gaze"),
                multiple_person=bool(payload.get("multiple_person", False)),
                phone_detected=bool(payload.get("phone_detected", False)),
                overall_confidence=float(payload.get("overall_confidence", 0.0) or 0.0),
                risk_flags=list(payload.get("risk_flags", []) or []),
                fps=float(payload.get("fps", 0.0) or 0.0),
            )
        except (TypeError, ValueError) as exc:
            raise DashboardFeatureError(f"Invalid event payload field types: {exc}") from exc


@dataclass(frozen=True)
class DashboardQuery:
    """Validated query parameters shared by the timeline/report endpoints."""

    range_: str = "today"
    student_id: Optional[str] = None
    metric: Optional[str] = None
    period: Optional[str] = None

    @staticmethod
    def from_params(
        range_: str = "today",
        student_id: Optional[str] = None,
        metric: Optional[str] = None,
        period: Optional[str] = None,
    ) -> "DashboardQuery":
        valid_ranges = ("today", "week", "month", "all")
        if range_ not in valid_ranges:
            raise DashboardFeatureError(f"'range' must be one of {valid_ranges}, got {range_!r}.")
        if metric is not None and metric not in VALID_METRICS:
            raise DashboardFeatureError(f"'metric' must be one of {VALID_METRICS}, got {metric!r}.")
        if period is not None and period not in VALID_PERIODS:
            raise DashboardFeatureError(f"'period' must be one of {VALID_PERIODS}, got {period!r}.")
        return DashboardQuery(range_=range_, student_id=student_id, metric=metric, period=period)
