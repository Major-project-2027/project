"""
Phase 6 Engagement Prediction Engine.

RULE-BASED ONLY (per the Phase 6 specification): this module combines the
outputs of Phase 2 (Face Authentication / Attendance), Phase 3 (Emotion
Detection), Phase 4 (Head Pose + Eye Gaze), and Phase 5 (Object Detection)
into a single weighted engagement score, engagement level, overall
confidence, risk flags, and human-readable reasons -- using a configurable
weighted-scoring formula, never a trained model.

The scoring engine is deliberately built behind the `EngagementScorer`
abstract interface so that Phase 8 can later introduce an ML-based scorer
(Random Forest / XGBoost / LSTM) that implements the exact same `predict()`
contract as a drop-in replacement for `RuleBasedEngagementPredictor`,
without requiring any change to the FastAPI router or to any caller of
`get_engagement_predictor()`.
"""
import abc
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ml_models.engagement_prediction.engagement_features import (
    EngagementFeatureError,
    EngagementPredictionInput,
)
from ml_models.engagement_prediction.engagement_levels import (
    DEFAULT_LEVEL_RANGES,
    score_to_level,
    validate_level_ranges,
)
from ml_models.engagement_prediction.engagement_utils import (
    classify_gaze,
    classify_head_pose,
    clamp,
    combine_confidences,
    compute_attendance_bonus,
    compute_distraction_score,
    compute_emotion_score,
    compute_face_authenticated_bonus,
    compute_gaze_score,
    compute_head_pose_score,
    compute_multiple_person_penalty,
    compute_phone_penalty,
    derive_risk_flags,
    generate_reasons,
)
from utils.common import load_yaml_config
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_RELATIVE_PATH = Path("configs") / "engagement_prediction.yaml"


class EngagementPredictionError(Exception):
    """Base exception for all Phase 6 engagement-prediction failures."""


class EngagementConfigError(EngagementPredictionError):
    """Raised when configs/engagement_prediction.yaml is missing required
    keys or contains invalid values."""


@dataclass(frozen=True)
class EngagementResult:
    """Structured result of running the engagement engine on one student's
    combined multimodal input for a single moment in time."""

    student_id: str
    engagement_score: float
    engagement_level: str
    overall_confidence: float

    emotion: Optional[str]
    head_pose: str
    gaze: str

    multiple_person: bool
    phone_detected: bool

    risk_flags: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    degraded: bool = False
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "engagement_score": round(float(self.engagement_score), 2),
            "engagement_level": self.engagement_level,
            "overall_confidence": round(float(self.overall_confidence), 4),
            "emotion": self.emotion,
            "head_pose": self.head_pose,
            "gaze": self.gaze,
            "multiple_person": self.multiple_person,
            "phone_detected": self.phone_detected,
            "risk_flags": list(self.risk_flags),
            "reasons": list(self.reasons),
            "degraded": self.degraded,
            "error_message": self.error_message,
            "processing_time_ms": round(float(self.processing_time_ms), 3),
        }


class EngagementScorer(abc.ABC):
    """Abstract engagement-scoring backend.

    `RuleBasedEngagementPredictor` (this phase) is the first implementation.
    Phase 8 may add e.g. `MLEngagementPredictor(EngagementScorer)` backed by
    a trained Random Forest / XGBoost / LSTM model -- as long as it
    implements `predict()` and `predict_safe()` with these exact signatures,
    every existing caller (including the FastAPI router) keeps working
    unmodified.
    """

    @abc.abstractmethod
    def predict(self, engagement_input: EngagementPredictionInput) -> EngagementResult:
        """Compute an EngagementResult for one combined multimodal input.

        Raises:
            EngagementPredictionError: If prediction fails.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def predict_safe(self, engagement_input: EngagementPredictionInput) -> EngagementResult:
        """Like predict(), but never raises -- returns a degraded=True
        EngagementResult on any failure instead."""
        raise NotImplementedError


def _default_config() -> Dict[str, Any]:
    """Fallback configuration used only if configs/engagement_prediction.yaml
    cannot be loaded, so the engine can still degrade gracefully rather than
    crash outright. The notebook always writes the real file, so this path
    is a defensive safety net, not the primary configuration source."""
    return {
        "weights": {
            "emotion": 0.25,
            "head_pose": 0.20,
            "gaze": 0.25,
        },
        "penalties": {
            "phone_usage": 20.0,
            "multiple_person": 15.0,
        },
        "bonuses": {
            "face_authenticated": 10.0,
            "attendance": 5.0,
        },
        "thresholds": {
            "yaw_norm_deg": 45.0,
            "pitch_norm_deg": 45.0,
            "roll_norm_deg": 30.0,
            "yaw_classification_deg": 15.0,
            "pitch_classification_deg": 15.0,
            "head_down_pitch_threshold_deg": 15.0,
            "low_confidence_threshold": 0.5,
        },
        "engagement_ranges": {
            "VERY_LOW": [0, 20],
            "LOW": [21, 40],
            "MEDIUM": [41, 60],
            "HIGH": [61, 80],
            "EXCELLENT": [81, 100],
        },
        "confidence_weights": {
            "emotion": 0.2,
            "face": 0.2,
            "gaze": 0.2,
            "head_pose": 0.2,
            "phone": 0.2,
        },
        "backend": "rule_based",
    }


class RuleBasedEngagementPredictor(EngagementScorer):
    """The Phase 6 rule-based engagement scoring engine.

    Configuration (weights, penalties, bonuses, thresholds, engagement-level
    ranges, and confidence-fusion weights) is loaded lazily from
    configs/engagement_prediction.yaml on first use and cached for the
    lifetime of the instance. Use :func:`get_engagement_predictor` to obtain
    the shared, process-wide singleton instead of constructing this class
    directly wherever possible.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        logger.info("RuleBasedEngagementPredictor instance created.")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _get_config(self) -> Dict[str, Any]:
        if self._config is None:
            config_path = self._config_path or (
                Path(__file__).resolve().parents[2] / "configs" / "engagement_prediction.yaml"
            )
            try:
                self._config = load_yaml_config(config_path)
                logger.info(f"Loaded engagement prediction config from {config_path}")
            except Exception as exc:  # noqa: BLE001 -- config load must never crash prediction.
                logger.error(f"Failed to load engagement_prediction.yaml ({exc}); using built-in defaults.")
                self._config = _default_config()
        return self._config

    def _level_ranges(self) -> Dict[str, tuple]:
        raw_ranges = self._get_config().get("engagement_ranges", DEFAULT_LEVEL_RANGES)
        ranges = {level: tuple(bounds) for level, bounds in raw_ranges.items()}
        validate_level_ranges(ranges)
        return ranges

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def predict(self, engagement_input: EngagementPredictionInput) -> EngagementResult:
        """Compute the engagement score/level/confidence/flags/reasons for
        one student's combined multimodal input.

        Raises:
            EngagementPredictionError: If the input is invalid or scoring
                otherwise fails.
        """
        start = time.perf_counter()
        if not isinstance(engagement_input, EngagementPredictionInput):
            raise EngagementPredictionError(
                f"Expected an EngagementPredictionInput, got {type(engagement_input)!r}."
            )

        config = self._get_config()
        weights = config.get("weights", {})
        penalties = config.get("penalties", {})
        bonuses = config.get("bonuses", {})
        thresholds = config.get("thresholds", {})
        confidence_weights = config.get("confidence_weights", {})

        face = engagement_input.face
        emotion = engagement_input.emotion
        head_pose = engagement_input.head_pose
        gaze = engagement_input.gaze
        objects = engagement_input.objects

        emotion_score = compute_emotion_score(emotion.emotion)
        head_pose_score = compute_head_pose_score(
            head_pose.yaw,
            head_pose.pitch,
            head_pose.roll,
            yaw_norm_deg=float(thresholds.get("yaw_norm_deg", 45.0)),
            pitch_norm_deg=float(thresholds.get("pitch_norm_deg", 45.0)),
            roll_norm_deg=float(thresholds.get("roll_norm_deg", 30.0)),
        )
        gaze_score = compute_gaze_score(
            gaze.looking_at_screen, gaze.looking_left, gaze.looking_right, gaze.looking_down
        )
        distraction_score = compute_distraction_score(objects.multiple_person, objects.phone_detected)

        phone_penalty = compute_phone_penalty(objects.phone_detected, float(penalties.get("phone_usage", 20.0)))
        multiple_person_penalty = compute_multiple_person_penalty(
            objects.multiple_person, float(penalties.get("multiple_person", 15.0))
        )
        face_authenticated_bonus = compute_face_authenticated_bonus(
            face.authenticated, float(bonuses.get("face_authenticated", 10.0))
        )
        attendance_bonus = compute_attendance_bonus(face.attendance, float(bonuses.get("attendance", 5.0)))

        raw_score = (
            emotion_score * float(weights.get("emotion", 0.25))
            + head_pose_score * float(weights.get("head_pose", 0.20))
            + gaze_score * float(weights.get("gaze", 0.25))
            + phone_penalty
            + multiple_person_penalty
            + face_authenticated_bonus
            + attendance_bonus
        )
        # A face that was never detected cannot be meaningfully "engaged".
        if not face.face_detected:
            raw_score = 0.0

        engagement_score = clamp(raw_score, 0.0, 100.0)
        engagement_level = score_to_level(engagement_score, ranges=self._level_ranges())

        overall_confidence = combine_confidences(
            emotion_confidence=emotion.emotion_confidence,
            face_confidence=face.authentication_confidence,
            gaze_confidence=gaze.gaze_confidence,
            head_pose_confidence=head_pose.head_pose_confidence,
            phone_confidence=objects.phone_confidence,
            weights=confidence_weights,
        )

        head_pose_label = classify_head_pose(
            head_pose.yaw,
            head_pose.pitch,
            yaw_threshold_deg=float(thresholds.get("yaw_classification_deg", 15.0)),
            pitch_threshold_deg=float(thresholds.get("pitch_classification_deg", 15.0)),
        )
        gaze_label = classify_gaze(gaze.looking_at_screen, gaze.looking_left, gaze.looking_right, gaze.looking_down)

        risk_flags = derive_risk_flags(
            engagement_input,
            engagement_level,
            overall_confidence,
            low_confidence_threshold=float(thresholds.get("low_confidence_threshold", 0.5)),
            head_down_pitch_threshold_deg=float(thresholds.get("head_down_pitch_threshold_deg", 15.0)),
        )
        reasons = generate_reasons(engagement_input, emotion_score, head_pose_label, gaze_label, risk_flags)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        result = EngagementResult(
            student_id=engagement_input.student_id,
            engagement_score=engagement_score,
            engagement_level=engagement_level,
            overall_confidence=overall_confidence,
            emotion=emotion.emotion,
            head_pose=head_pose_label,
            gaze=gaze_label,
            multiple_person=objects.multiple_person,
            phone_detected=objects.phone_detected,
            risk_flags=risk_flags,
            reasons=reasons,
            degraded=False,
            error_message=None,
            processing_time_ms=elapsed_ms,
        )
        logger.info(
            f"Engagement prediction: student_id={result.student_id} score={engagement_score:.2f} "
            f"level={engagement_level} confidence={overall_confidence:.3f} risk_flags={risk_flags} "
            f"time={elapsed_ms:.2f}ms"
        )
        # Distraction score is intentionally computed for interpretability /
        # future logging or ML feature-engineering use even though it is not
        # part of the returned payload's fixed schema.
        logger.info(f"Distraction score (informational): {distraction_score:.2f}")
        return result

    def predict_safe(self, engagement_input: EngagementPredictionInput) -> EngagementResult:
        """Like predict(), but degrades gracefully instead of raising.

        Returns an EngagementResult with degraded=True and an
        error_message set whenever prediction fails for any reason, so
        callers (e.g. the FastAPI router) never need to handle a raw
        exception.
        """
        start = time.perf_counter()
        try:
            return self.predict(engagement_input)
        except Exception as exc:  # noqa: BLE001 -- must never crash the caller.
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.error(f"Engagement prediction degraded gracefully: {exc}")
            fallback_student_id = "UNKNOWN"
            try:
                fallback_student_id = engagement_input.student_id
            except Exception:  # noqa: BLE001
                pass
            return EngagementResult(
                student_id=fallback_student_id,
                engagement_score=0.0,
                engagement_level=score_to_level(0.0),
                overall_confidence=0.0,
                emotion=None,
                head_pose="unknown",
                gaze="unknown",
                multiple_person=False,
                phone_detected=False,
                risk_flags=["LOW_CONFIDENCE"],
                reasons=["Engagement prediction failed; returning a safe, degraded default result."],
                degraded=True,
                error_message=str(exc),
                processing_time_ms=elapsed_ms,
            )


# ----------------------------------------------------------------------
# Process-wide singleton accessor (mirrors Phase 2/3/4/5's lazy-singleton
# pattern: get_face_matcher() / get_emotion_detector() /
# get_head_pose_estimator() / get_object_detector()).
# ----------------------------------------------------------------------
_engagement_predictor: Optional[EngagementScorer] = None


def get_engagement_predictor() -> EngagementScorer:
    """Return the shared, process-wide EngagementScorer singleton, creating
    it on first call using the backend named in configs/engagement_prediction.yaml
    (currently only "rule_based" is implemented; "ml" is reserved for Phase 8
    and currently falls back to "rule_based" with a warning)."""
    global _engagement_predictor
    if _engagement_predictor is None:
        _engagement_predictor = RuleBasedEngagementPredictor()
        backend = _engagement_predictor._get_config().get("backend", "rule_based")
        if backend not in ("rule_based",):
            logger.warning(
                f"Configured engagement backend '{backend}' is not yet implemented "
                "(reserved for Phase 8); falling back to 'rule_based'."
            )
    return _engagement_predictor


def reset_engagement_predictor() -> None:
    """Reset the singleton -- primarily useful for tests."""
    global _engagement_predictor
    _engagement_predictor = None