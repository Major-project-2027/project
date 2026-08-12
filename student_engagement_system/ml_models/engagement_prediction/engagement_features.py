"""
Typed input contracts for the Phase 6 Engagement Prediction Engine.

Each dataclass below models the subset of a previous phase's output that the
engagement engine actually consumes:

  - FaceAuthenticationInput  <- Phase 2 (Face Authentication / Attendance)
  - EmotionInput             <- Phase 3 (Emotion Detection)
  - HeadPoseInput            <- Phase 4 (Head Pose Estimation)
  - GazeInput                <- Phase 4 (Eye Gaze Estimation)
  - ObjectDetectionInput     <- Phase 5 (Object Detection)

These are intentionally decoupled from the Phase 2/3/4/5 modules themselves
(no imports from ml_models.face_authentication / ml_models.emotion_detection /
ml_models.gaze_head_pose / models.object_detection) so Phase 6 stays additive
and never imports internals it does not need -- callers (e.g. the FastAPI
router, or a future orchestration layer) are responsible for mapping each
phase's real output onto these simple, stable contracts.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Emotion vocabulary -- mirrors Phase 3's emotion label set.
# ---------------------------------------------------------------------------
KNOWN_EMOTIONS = {"happy", "neutral", "sad", "angry", "confused", "tired", "surprised", "fear", "disgust"}

# Base 0-100 desirability score per emotion. Unknown/None emotions fall back
# to DEFAULT_EMOTION_SCORE. Values are intentionally simple/interpretable so
# a human reviewer can sanity-check them at a glance.
EMOTION_SCORE_MAP: Dict[str, float] = {
    "happy": 100.0,
    "surprised": 75.0,
    "neutral": 80.0,
    "confused": 50.0,
    "tired": 35.0,
    "sad": 30.0,
    "disgust": 25.0,
    "fear": 25.0,
    "angry": 20.0,
}
DEFAULT_EMOTION_SCORE = 50.0


class EngagementFeatureError(ValueError):
    """Raised when an input dataclass fails validation."""


def _validate_confidence(name: str, value: float) -> float:
    value = float(value)
    if not (0.0 <= value <= 1.0):
        raise EngagementFeatureError(f"{name} must be within [0.0, 1.0]; got {value}.")
    return value


@dataclass
class FaceAuthenticationInput:
    """Subset of Phase 2 (Face Authentication + Attendance) output."""

    student_id: str
    face_detected: bool = True
    authenticated: bool = True
    authentication_confidence: float = 1.0
    attendance: bool = True

    def __post_init__(self) -> None:
        if not self.student_id or not str(self.student_id).strip():
            raise EngagementFeatureError("student_id must be a non-empty string.")
        self.authentication_confidence = _validate_confidence(
            "authentication_confidence", self.authentication_confidence
        )
        if not self.face_detected:
            # A face that was never detected cannot have been authenticated.
            self.authenticated = False
            self.authentication_confidence = 0.0


@dataclass
class EmotionInput:
    """Subset of Phase 3 (Emotion Detection) output."""

    emotion: Optional[str] = None
    emotion_confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.emotion is not None:
            self.emotion = str(self.emotion).strip().lower()
        self.emotion_confidence = _validate_confidence("emotion_confidence", self.emotion_confidence)


@dataclass
class HeadPoseInput:
    """Subset of Phase 4 (Head Pose Estimation) output. Angles in degrees."""

    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    head_pose_confidence: float = 0.0

    def __post_init__(self) -> None:
        self.yaw = float(self.yaw)
        self.pitch = float(self.pitch)
        self.roll = float(self.roll)
        self.head_pose_confidence = _validate_confidence(
            "head_pose_confidence", self.head_pose_confidence
        )


@dataclass
class GazeInput:
    """Subset of Phase 4 (Eye Gaze Estimation) output."""

    looking_at_screen: bool = True
    looking_left: bool = False
    looking_right: bool = False
    looking_down: bool = False
    gaze_confidence: float = 0.0

    def __post_init__(self) -> None:
        self.gaze_confidence = _validate_confidence("gaze_confidence", self.gaze_confidence)
        if self.looking_at_screen and (self.looking_left or self.looking_right or self.looking_down):
            raise EngagementFeatureError(
                "looking_at_screen cannot be True while looking_left/looking_right/looking_down is True."
            )


@dataclass
class ObjectDetectionInput:
    """Subset of Phase 5 (Object Detection) output."""

    person_count: int = 1
    multiple_person: bool = False
    phone_detected: bool = False
    phone_confidence: float = 0.0
    objects: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.person_count = int(self.person_count)
        if self.person_count < 0:
            raise EngagementFeatureError(f"person_count cannot be negative; got {self.person_count}.")
        self.phone_confidence = _validate_confidence("phone_confidence", self.phone_confidence)
        if not self.phone_detected:
            self.phone_confidence = 0.0
        if self.person_count > 1 and not self.multiple_person:
            # person_count is authoritative -- keep multiple_person consistent with it.
            self.multiple_person = True


@dataclass
class EngagementPredictionInput:
    """The complete, combined input to the Phase 6 Engagement Prediction Engine."""

    face: FaceAuthenticationInput
    emotion: EmotionInput = field(default_factory=EmotionInput)
    head_pose: HeadPoseInput = field(default_factory=HeadPoseInput)
    gaze: GazeInput = field(default_factory=GazeInput)
    objects: ObjectDetectionInput = field(default_factory=ObjectDetectionInput)

    @property
    def student_id(self) -> str:
        return self.face.student_id

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "EngagementPredictionInput":
        """Build an EngagementPredictionInput from a flat or nested dict.

        Accepts either the flat shape used by the FastAPI router (top-level
        keys like student_id, emotion, yaw, looking_at_screen, phone_detected,
        ...) or an already-nested shape with "face"/"emotion"/"head_pose"/
        "gaze"/"objects" sub-dicts.
        """
        if any(key in payload for key in ("face", "emotion", "head_pose", "gaze", "objects")) and (
            isinstance(payload.get("face"), dict) or "face" in payload
        ):
            face_dict = payload.get("face", {})
            emotion_dict = payload.get("emotion", {})
            head_pose_dict = payload.get("head_pose", {})
            gaze_dict = payload.get("gaze", {})
            objects_dict = payload.get("objects", {})
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

        if not face_dict.get("student_id"):
            raise EngagementFeatureError("payload must include a non-empty 'student_id'.")

        return EngagementPredictionInput(
            face=FaceAuthenticationInput(**face_dict),
            emotion=EmotionInput(**emotion_dict),
            head_pose=HeadPoseInput(**head_pose_dict),
            gaze=GazeInput(**gaze_dict),
            objects=ObjectDetectionInput(**objects_dict),
        )