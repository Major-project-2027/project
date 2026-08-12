"""
Pure-logic scoring helpers for the Phase 7 Cognitive Monitoring Engine.

Reuses Phase 6's `compute_gaze_score` / `compute_head_pose_score` /
`clamp` (models/engagement_prediction/engagement_utils.py) so gaze- and
head-pose-derived signals stay perfectly consistent between the
Engagement Prediction Engine (Phase 6) and the Cognitive Monitoring
Engine (Phase 7) rather than drifting apart via a second, slightly
different implementation. Every function here is a small, independently
testable, side-effect-free building block used by
cognitive_monitor.py's rule-based monitor.
"""
from typing import Dict, List, Optional

from ml_models.engagement_prediction.engagement_utils import (
    clamp,
    compute_gaze_score,
    compute_head_pose_score,
)
from ml_models.cognitive_monitoring.cognitive_features import CognitiveMonitoringInput
from ml_models.cognitive_monitoring.cognitive_levels import (
    CONFUSED,
    CONFUSION_DETECTED,
    DISENGAGED,
    DISTRACTED,
    FATIGUE_DETECTED,
    FATIGUED,
    FOCUSED,
    HIGH_DISTRACTION,
    LOOKING_AWAY,
    LOW_ATTENTION,
    LOW_CONFIDENCE,
    MULTIPLE_PERSON,
    NEUTRAL,
    NO_FACE,
    PHONE_USAGE,
    UNAVAILABLE,
    UNKNOWN_FACE,
)


# ---------------------------------------------------------------------------
# Attention score
# ---------------------------------------------------------------------------
def compute_attention_score(
    gaze_score: float,
    head_pose_score: float,
    engagement_score: float,
    gaze_weight: float = 0.35,
    head_pose_weight: float = 0.35,
    engagement_weight: float = 0.30,
) -> float:
    """Combine gaze focus, head-pose focus, and the Phase 6 engagement score
    into a single 0-100 attention_score."""
    total_weight = gaze_weight + head_pose_weight + engagement_weight
    if total_weight <= 0.0:
        return 0.0
    weighted_sum = gaze_score * gaze_weight + head_pose_score * head_pose_weight + engagement_score * engagement_weight
    return clamp(weighted_sum / total_weight, 0.0, 100.0)


# ---------------------------------------------------------------------------
# Distraction / fatigue / confusion scores
# ---------------------------------------------------------------------------
def compute_distraction_score(
    phone_detected: bool,
    multiple_person: bool,
    looking_away: bool,
    phone_weight: float = 50.0,
    multiple_person_weight: float = 50.0,
    looking_away_weight: float = 25.0,
) -> float:
    """A 0-100 distraction indicator: higher means more distracted."""
    score = 0.0
    if phone_detected:
        score += phone_weight
    if multiple_person:
        score += multiple_person_weight
    if looking_away:
        score += looking_away_weight
    return clamp(score, 0.0, 100.0)


def compute_fatigue_score(
    emotion: Optional[str],
    looking_down: bool,
    tired_emotion_weight: float = 70.0,
    sad_emotion_weight: float = 20.0,
    head_down_weight: float = 40.0,
) -> float:
    """A 0-100 fatigue indicator: higher means more fatigued/drowsy."""
    score = 0.0
    normalized_emotion = (emotion or "").strip().lower()
    if normalized_emotion == "tired":
        score += tired_emotion_weight
    elif normalized_emotion == "sad":
        score += sad_emotion_weight
    if looking_down:
        score += head_down_weight
    return clamp(score, 0.0, 100.0)


def compute_confusion_score(
    emotion: Optional[str],
    confused_emotion_weight: float = 75.0,
    fear_emotion_weight: float = 30.0,
) -> float:
    """A 0-100 confusion indicator: higher means more confused."""
    score = 0.0
    normalized_emotion = (emotion or "").strip().lower()
    if normalized_emotion == "confused":
        score += confused_emotion_weight
    elif normalized_emotion == "fear":
        score += fear_emotion_weight
    return clamp(score, 0.0, 100.0)


# ---------------------------------------------------------------------------
# Cognitive state classification (deterministic priority chain, mirrors
# engagement_utils's classify_head_pose()/classify_gaze() style)
# ---------------------------------------------------------------------------
def classify_cognitive_state(
    face_detected: bool,
    attention_score: float,
    distraction_score: float,
    fatigue_score: float,
    confusion_score: float,
    distraction_threshold: float = 50.0,
    fatigue_threshold: float = 60.0,
    confusion_threshold: float = 60.0,
    low_attention_threshold: float = 40.0,
    focus_attention_threshold: float = 70.0,
) -> str:
    """Classify the dominant cognitive state using a deterministic priority
    chain: an undetected face is always UNAVAILABLE; otherwise the highest
    urgency, best-supported signal wins in the order distraction -> fatigue
    -> confusion -> low attention -> high attention -> neutral."""
    if not face_detected:
        return UNAVAILABLE
    if distraction_score >= distraction_threshold:
        return DISTRACTED
    if fatigue_score >= fatigue_threshold:
        return FATIGUED
    if confusion_score >= confusion_threshold:
        return CONFUSED
    if attention_score < low_attention_threshold:
        return DISENGAGED
    if attention_score >= focus_attention_threshold:
        return FOCUSED
    return NEUTRAL


# ---------------------------------------------------------------------------
# Confidence fusion
# ---------------------------------------------------------------------------
def combine_confidences(
    emotion_confidence: float,
    face_confidence: float,
    gaze_confidence: float,
    head_pose_confidence: float,
    phone_confidence: float,
    engagement_confidence: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Combine six independent per-modality/per-phase confidences into a
    single overall_confidence in [0, 1] using a configurable weighted
    average (adds Phase 6's own overall_confidence as a sixth input on top
    of Phase 6's five)."""
    active_weights = weights if weights is not None else {
        "emotion": 0.2, "face": 0.2, "gaze": 0.2,
        "head_pose": 0.15, "phone": 0.1, "engagement": 0.15,
    }
    values = {
        "emotion": emotion_confidence,
        "face": face_confidence,
        "gaze": gaze_confidence,
        "head_pose": head_pose_confidence,
        "phone": phone_confidence,
        "engagement": engagement_confidence,
    }
    total_weight = sum(active_weights.get(key, 0.0) for key in values)
    if total_weight <= 0.0:
        return 0.0
    weighted_sum = sum(clamp(values[key], 0.0, 1.0) * active_weights.get(key, 0.0) for key in values)
    return clamp(weighted_sum / total_weight, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Risk flags and human-readable reasons
# ---------------------------------------------------------------------------
def derive_risk_flags(
    cognitive_input: CognitiveMonitoringInput,
    distraction_score: float,
    fatigue_score: float,
    confusion_score: float,
    attention_score: float,
    overall_confidence: float,
    distraction_threshold: float,
    fatigue_threshold: float,
    confusion_threshold: float,
    low_attention_threshold: float,
    low_confidence_threshold: float,
) -> List[str]:
    """Derive the ordered list of applicable risk flags for one prediction."""
    flags: List[str] = []

    if not cognitive_input.face.face_detected:
        flags.append(NO_FACE)
    elif not cognitive_input.face.authenticated:
        flags.append(UNKNOWN_FACE)

    if cognitive_input.objects.phone_detected:
        flags.append(PHONE_USAGE)
    if cognitive_input.objects.multiple_person:
        flags.append(MULTIPLE_PERSON)
    if not cognitive_input.gaze.looking_at_screen:
        flags.append(LOOKING_AWAY)

    if distraction_score >= distraction_threshold:
        flags.append(HIGH_DISTRACTION)
    if fatigue_score >= fatigue_threshold:
        flags.append(FATIGUE_DETECTED)
    if confusion_score >= confusion_threshold:
        flags.append(CONFUSION_DETECTED)
    if attention_score < low_attention_threshold:
        flags.append(LOW_ATTENTION)
    if overall_confidence < low_confidence_threshold:
        flags.append(LOW_CONFIDENCE)

    return flags


def generate_reasons(
    cognitive_input: CognitiveMonitoringInput,
    cognitive_state: str,
    attention_score: float,
    distraction_score: float,
    fatigue_score: float,
    confusion_score: float,
    risk_flags: List[str],
) -> List[str]:
    """Generate a short list of human-readable reasons explaining the
    cognitive-state classification."""
    reasons: List[str] = []
    face = cognitive_input.face
    emotion = cognitive_input.emotion
    engagement = cognitive_input.engagement

    if not face.face_detected:
        reasons.append("No face detected -- cognitive state cannot be assessed")
        return reasons
    if not face.authenticated:
        reasons.append("Face not authenticated / unknown identity")

    reasons.append(f"Attention score {attention_score:.1f}/100, informed by gaze, head pose, "
                    f"and the Phase 6 engagement score ({engagement.engagement_score:.1f})")

    if cognitive_state == FOCUSED:
        reasons.append("Student appears focused and attentive")
    elif cognitive_state == NEUTRAL:
        reasons.append("Student shows a neutral, moderate level of attention")
    elif cognitive_state == DISTRACTED:
        reasons.append(f"High distraction detected (distraction score {distraction_score:.1f}/100)")
    elif cognitive_state == FATIGUED:
        reasons.append(f"Signs of fatigue detected (fatigue score {fatigue_score:.1f}/100)")
    elif cognitive_state == CONFUSED:
        reasons.append(f"Signs of confusion detected (confusion score {confusion_score:.1f}/100)")
    elif cognitive_state == DISENGAGED:
        reasons.append(f"Attention score is low ({attention_score:.1f}/100) -- student appears disengaged")

    if emotion.emotion:
        reasons.append(f"Detected emotion: {emotion.emotion}")

    if cognitive_input.objects.phone_detected:
        reasons.append("Mobile phone detected in frame")
    if cognitive_input.objects.multiple_person:
        reasons.append(f"Multiple persons detected in frame ({cognitive_input.objects.person_count})")
    if not cognitive_input.gaze.looking_at_screen:
        reasons.append("Gaze directed away from the screen")

    if LOW_CONFIDENCE in risk_flags:
        reasons.append("Overall confidence in this prediction is low")

    return reasons