"""
Typed input contracts for the Phase 7 Cognitive Monitoring Engine.

Phase 7 consumes the SAME raw per-modality signals Phase 6 does (Face
Authentication, Emotion Detection, Head Pose, Eye Gaze, Object Detection),
plus Phase 6's own output (the Engagement Prediction summary). Rather than
duplicating the four raw-modality dataclasses, this module reuses Phase 6's
`FaceAuthenticationInput`, `EmotionInput`, `HeadPoseInput`, `GazeInput`, and
`ObjectDetectionInput` directly (models/engagement_prediction/engagement_features.py
is Phase 6 code and is never modified by Phase 7 -- it is only imported),
and adds the one new dataclass Phase 7 needs: `EngagementSummaryInput`,
which models the subset of a Phase 6 `EngagementResult` that Phase 7's
scoring logic actually consumes.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ml_models.engagement_prediction.engagement_features import (
    EmotionInput,
    EngagementFeatureError,
    FaceAuthenticationInput,
    GazeInput,
    HeadPoseInput,
    ObjectDetectionInput,
)

# Re-exported so callers of this module never need to import Phase 6's
# engagement_features module directly to catch validation errors.
CognitiveFeatureError = EngagementFeatureError


def _validate_confidence(name: str, value: float) -> float:
    value = float(value)
    if not (0.0 <= value <= 1.0):
        raise CognitiveFeatureError(f"{name} must be within [0.0, 1.0]; got {value}.")
    return value


def _validate_score_0_100(name: str, value: float) -> float:
    value = float(value)
    if not (0.0 <= value <= 100.0):
        raise CognitiveFeatureError(f"{name} must be within [0.0, 100.0]; got {value}.")
    return value


@dataclass
class EngagementSummaryInput:
    """Subset of a Phase 6 `EngagementResult` (models/engagement_prediction/
    engagement_predictor.py) that the Phase 7 cognitive engine consumes.

    When Phase 7 is invoked through its FastAPI router, this is populated
    automatically by calling Phase 6's own `get_engagement_predictor()` --
    callers of the HTTP API never need to compute it themselves. When
    calling the cognitive engine directly (e.g. in tests), it can be
    constructed by hand or from an `EngagementResult.as_dict()` payload.
    """

    engagement_score: float = 50.0
    engagement_level: str = "MEDIUM"
    overall_confidence: float = 0.5
    risk_flags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.engagement_score = _validate_score_0_100("engagement_score", self.engagement_score)
        self.overall_confidence = _validate_confidence("overall_confidence", self.overall_confidence)
        if not self.engagement_level or not str(self.engagement_level).strip():
            raise CognitiveFeatureError("engagement_level must be a non-empty string.")
        self.engagement_level = str(self.engagement_level).strip().upper()


@dataclass
class CognitiveMonitoringInput:
    """The complete, combined input to the Phase 7 Cognitive Monitoring Engine."""

    face: FaceAuthenticationInput
    emotion: EmotionInput = field(default_factory=EmotionInput)
    head_pose: HeadPoseInput = field(default_factory=HeadPoseInput)
    gaze: GazeInput = field(default_factory=GazeInput)
    objects: ObjectDetectionInput = field(default_factory=ObjectDetectionInput)
    engagement: EngagementSummaryInput = field(default_factory=EngagementSummaryInput)

    @property
    def student_id(self) -> str:
        return self.face.student_id

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "CognitiveMonitoringInput":
        """Build a CognitiveMonitoringInput from a flat or nested dict.

        Accepts either the flat shape used by the FastAPI router (top-level
        keys like student_id, emotion, yaw, looking_at_screen, phone_detected,
        engagement_score, ...) or an already-nested shape with "face"/
        "emotion"/"head_pose"/"gaze"/"objects"/"engagement" sub-dicts.
        """
        is_nested = any(key in payload for key in ("face", "emotion", "head_pose", "gaze", "objects", "engagement")) and (
            isinstance(payload.get("face"), dict) or "face" in payload
        )
        if is_nested:
            face_dict = payload.get("face", {})
            emotion_dict = payload.get("emotion", {})
            head_pose_dict = payload.get("head_pose", {})
            gaze_dict = payload.get("gaze", {})
            objects_dict = payload.get("objects", {})
            engagement_dict = payload.get("engagement", {})
        else:
            face_dict = {
                "student_id": payload.get("student_id"),
                "face_detected": payload.get("face_detected", True),
                "authenticated": payload.get("authenticated", True),
                "authentication_confidence": payload.get("authentication_confidence", 1.0),
                "attendance": payload.get("attendance", True),
            }
            emotion_dict = {
                "emotion": payload.get("emotion"),
                "emotion_confidence": payload.get("emotion_confidence", 0.0),
            }
            head_pose_dict = {
                "yaw": payload.get("yaw", 0.0),
                "pitch": payload.get("pitch", 0.0),
                "roll": payload.get("roll", 0.0),
                "head_pose_confidence": payload.get("head_pose_confidence", 0.0),
            }
            gaze_dict = {
                "looking_at_screen": payload.get("looking_at_screen", True),
                "looking_left": payload.get("looking_left", False),
                "looking_right": payload.get("looking_right", False),
                "looking_down": payload.get("looking_down", False),
                "gaze_confidence": payload.get("gaze_confidence", 0.0),
            }
            objects_dict = {
                "person_count": payload.get("person_count", 1),
                "multiple_person": payload.get("multiple_person", False),
                "phone_detected": payload.get("phone_detected", False),
                "phone_confidence": payload.get("phone_confidence", 0.0),
                "objects": payload.get("object_list", payload.get("objects_detected", [])),
            }
            engagement_dict = {
                "engagement_score": payload.get("engagement_score", 50.0),
                "engagement_level": payload.get("engagement_level", "MEDIUM"),
                "overall_confidence": payload.get("engagement_confidence", 0.5),
                "risk_flags": payload.get("engagement_risk_flags", []),
            }

        if not face_dict.get("student_id"):
            raise CognitiveFeatureError("payload must include a non-empty 'student_id'.")

        return CognitiveMonitoringInput(
            face=FaceAuthenticationInput(**face_dict),
            emotion=EmotionInput(**emotion_dict),
            head_pose=HeadPoseInput(**head_pose_dict),
            gaze=GazeInput(**gaze_dict),
            objects=ObjectDetectionInput(**objects_dict),
            engagement=EngagementSummaryInput(**engagement_dict),
        )