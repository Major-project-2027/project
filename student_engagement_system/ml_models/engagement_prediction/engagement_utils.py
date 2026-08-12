"""
Pure-logic scoring helpers for the Phase 6 Engagement Prediction Engine.

Every function here is a small, independently testable, side-effect-free
building block used by engagement_predictor.py's rule-based scorer. Keeping
them here (rather than inline in the predictor) means a future Phase 8 ML
predictor can still reuse the feature-engineering pieces (emotion score,
head-pose score, gaze score, risk-flag derivation, ...) even after the final
scoring formula itself is replaced by a trained model.
"""
from typing import Dict, List, Optional

from ml_models.engagement_prediction.engagement_features import (
    DEFAULT_EMOTION_SCORE,
    EMOTION_SCORE_MAP,
    EngagementPredictionInput,
)
from ml_models.engagement_prediction.engagement_levels import (
    HEAD_DOWN,
    LOOKING_AWAY,
    LOW_CONFIDENCE,
    MULTIPLE_PERSON,
    NO_FACE,
    PHONE_USAGE,
    UNKNOWN_FACE,
    VERY_LOW,
    VERY_LOW_ENGAGEMENT,
)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp `value` into the closed interval [low, high]."""
    return max(low, min(high, float(value)))


# ---------------------------------------------------------------------------
# Per-modality 0-100 feature scores
# ---------------------------------------------------------------------------
def compute_emotion_score(
    emotion: Optional[str],
    emotion_score_map: Optional[Dict[str, float]] = None,
    default_score: float = DEFAULT_EMOTION_SCORE,
) -> float:
    """Map an emotion label to an interpretable 0-100 desirability score."""
    active_map = emotion_score_map if emotion_score_map is not None else EMOTION_SCORE_MAP
    if not emotion:
        return clamp(default_score)
    return clamp(active_map.get(str(emotion).strip().lower(), default_score))


def compute_head_pose_score(
    yaw: float,
    pitch: float,
    roll: float,
    yaw_norm_deg: float = 45.0,
    pitch_norm_deg: float = 45.0,
    roll_norm_deg: float = 30.0,
) -> float:
    """Score head orientation 0-100: 100 == perfectly facing the screen,
    degrading linearly toward 0 as yaw/pitch/roll deviate from center.

    Each axis's deviation is normalized by its own "practically maximal"
    deviation in degrees (yaw_norm_deg / pitch_norm_deg / roll_norm_deg)
    before being averaged, so no single axis needs to hit exactly 90 degrees
    to fully zero out the score.
    """
    yaw_dev = clamp(abs(float(yaw)) / max(yaw_norm_deg, 1e-6), 0.0, 1.0)
    pitch_dev = clamp(abs(float(pitch)) / max(pitch_norm_deg, 1e-6), 0.0, 1.0)
    roll_dev = clamp(abs(float(roll)) / max(roll_norm_deg, 1e-6), 0.0, 1.0)
    average_deviation = (yaw_dev + pitch_dev + roll_dev) / 3.0
    return clamp(100.0 * (1.0 - average_deviation))


def classify_head_pose(
    yaw: float, pitch: float, yaw_threshold_deg: float = 15.0, pitch_threshold_deg: float = 15.0
) -> str:
    """Return a coarse, human-readable head-pose label: 'center', 'left',
    'right', 'up', or 'down'."""
    if abs(pitch) > pitch_threshold_deg and pitch > 0:
        return "down"
    if abs(pitch) > pitch_threshold_deg and pitch < 0:
        return "up"
    if abs(yaw) > yaw_threshold_deg:
        return "right" if yaw > 0 else "left"
    return "center"


def compute_gaze_score(
    looking_at_screen: bool,
    looking_left: bool,
    looking_right: bool,
    looking_down: bool,
    screen_score: float = 100.0,
    side_glance_score: float = 45.0,
    down_score: float = 20.0,
    unknown_score: float = 40.0,
) -> float:
    """Score gaze direction 0-100 based on where the student is looking."""
    if looking_at_screen:
        return clamp(screen_score)
    if looking_down:
        return clamp(down_score)
    if looking_left or looking_right:
        return clamp(side_glance_score)
    return clamp(unknown_score)


def classify_gaze(looking_at_screen: bool, looking_left: bool, looking_right: bool, looking_down: bool) -> str:
    """Return a coarse, human-readable gaze label: 'screen', 'left',
    'right', 'down', or 'unknown'."""
    if looking_at_screen:
        return "screen"
    if looking_down:
        return "down"
    if looking_left:
        return "left"
    if looking_right:
        return "right"
    return "unknown"


def compute_distraction_score(multiple_person: bool, phone_detected: bool) -> float:
    """A 0-100 *interpretable* distraction indicator (100 == no distraction
    detected at all) purely for reporting/explanation purposes -- the actual
    engagement-score penalties are applied separately via
    compute_phone_penalty() / compute_multiple_person_penalty() so the two
    concerns (explaining vs. scoring) stay independent and each stays easy
    to unit test in isolation."""
    score = 100.0
    if phone_detected:
        score -= 50.0
    if multiple_person:
        score -= 50.0
    return clamp(score)


# ---------------------------------------------------------------------------
# Penalties and bonuses (already expressed in "final score" points, i.e. the
# same units the weighted engagement score is computed in)
# ---------------------------------------------------------------------------
def compute_phone_penalty(phone_detected: bool, penalty_points: float) -> float:
    """Return the (negative) point adjustment for phone usage."""
    return -abs(penalty_points) if phone_detected else 0.0


def compute_multiple_person_penalty(multiple_person: bool, penalty_points: float) -> float:
    """Return the (negative) point adjustment for multiple people in frame."""
    return -abs(penalty_points) if multiple_person else 0.0


def compute_face_authenticated_bonus(authenticated: bool, bonus_points: float) -> float:
    """Return the (positive) point adjustment for a successfully
    authenticated face."""
    return abs(bonus_points) if authenticated else 0.0


def compute_attendance_bonus(attendance: bool, bonus_points: float) -> float:
    """Return the (positive) point adjustment for a marked-present student."""
    return abs(bonus_points) if attendance else 0.0


# ---------------------------------------------------------------------------
# Confidence fusion
# ---------------------------------------------------------------------------
def combine_confidences(
    emotion_confidence: float,
    face_confidence: float,
    gaze_confidence: float,
    head_pose_confidence: float,
    phone_confidence: float,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Combine five independent per-modality confidences into a single
    overall_confidence in [0, 1] using a configurable weighted average.

    phone_confidence is only meaningful when a phone was actually detected;
    callers should pass 0.0 for phone_confidence when no phone was detected
    so an always-absent phone does not artificially drag down confidence
    (this mirrors how the weight for "phone" is applied below: a phone
    weight is still included, but its contribution is proportional to
    whatever confidence value the caller supplies).
    """
    active_weights = weights if weights is not None else {
        "emotion": 0.2,
        "face": 0.2,
        "gaze": 0.2,
        "head_pose": 0.2,
        "phone": 0.2,
    }
    values = {
        "emotion": emotion_confidence,
        "face": face_confidence,
        "gaze": gaze_confidence,
        "head_pose": head_pose_confidence,
        "phone": phone_confidence,
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
    engagement_input: EngagementPredictionInput,
    engagement_level: str,
    overall_confidence: float,
    low_confidence_threshold: float,
    head_down_pitch_threshold_deg: float = 15.0,
) -> List[str]:
    """Derive the ordered list of applicable risk flags for one prediction."""
    flags: List[str] = []

    if not engagement_input.face.face_detected:
        flags.append(NO_FACE)
    elif not engagement_input.face.authenticated:
        flags.append(UNKNOWN_FACE)

    if engagement_input.objects.phone_detected:
        flags.append(PHONE_USAGE)
    if engagement_input.objects.multiple_person:
        flags.append(MULTIPLE_PERSON)

    gaze = engagement_input.gaze
    if not gaze.looking_at_screen and not gaze.looking_down:
        flags.append(LOOKING_AWAY)
    if gaze.looking_down or engagement_input.head_pose.pitch > head_down_pitch_threshold_deg:
        flags.append(HEAD_DOWN)

    if overall_confidence < low_confidence_threshold:
        flags.append(LOW_CONFIDENCE)

    if engagement_level == VERY_LOW:
        flags.append(VERY_LOW_ENGAGEMENT)

    return flags


def generate_reasons(
    engagement_input: EngagementPredictionInput,
    emotion_score: float,
    head_pose_label: str,
    gaze_label: str,
    risk_flags: List[str],
) -> List[str]:
    """Generate a short list of human-readable reasons explaining the score."""
    reasons: List[str] = []
    face = engagement_input.face
    emotion = engagement_input.emotion
    objects = engagement_input.objects

    if not face.face_detected:
        reasons.append("No face detected in frame")
    elif not face.authenticated:
        reasons.append("Face not authenticated / unknown identity")
    else:
        reasons.append("Face authenticated successfully")

    if face.attendance:
        reasons.append("Attendance marked present")
    else:
        reasons.append("Attendance not marked present")

    if gaze_label == "screen":
        reasons.append("Looking at screen")
    elif gaze_label == "down":
        reasons.append("Gaze directed downward, away from screen")
    elif gaze_label in ("left", "right"):
        reasons.append(f"Gaze directed to the {gaze_label}, away from screen")
    else:
        reasons.append("Gaze direction could not be determined")

    if emotion.emotion:
        descriptor = "Positive" if emotion_score >= 70 else ("Neutral" if emotion_score >= 50 else "Negative")
        reasons.append(f"{descriptor} emotion detected ({emotion.emotion})")
    else:
        reasons.append("No emotion detected")

    reasons.append(f"Head pose classified as '{head_pose_label}'")

    if objects.phone_detected:
        reasons.append("Mobile phone detected -- engagement penalized")
    else:
        reasons.append("No phone detected")

    if objects.multiple_person:
        reasons.append(f"Multiple persons detected in frame ({objects.person_count})")
    else:
        reasons.append("Only one student present")

    if VERY_LOW_ENGAGEMENT in risk_flags:
        reasons.append("Engagement level is very low -- immediate attention recommended")
    if LOW_CONFIDENCE in risk_flags:
        reasons.append("Overall confidence in this prediction is low")

    return reasons