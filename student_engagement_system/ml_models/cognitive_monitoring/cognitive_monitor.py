"""
Phase 7 Cognitive Monitoring Engine.

RULE-BASED ONLY (per the Phase 7 specification): this module combines the
same raw modality outputs Phase 6 consumes (Face Authentication, Emotion
Detection, Head Pose, Eye Gaze, Object Detection) PLUS Phase 6's own
Engagement Prediction output into a single higher-level cognitive-state
assessment -- using a configurable rule/threshold system, never a trained
model.

The scoring engine is deliberately built behind the `CognitiveScorer`
abstract interface so that a future ML-based monitor can implement the
exact same `predict()` contract as a drop-in replacement for
`RuleBasedCognitiveMonitor`, without requiring any change to the FastAPI
router or to any caller of `get_cognitive_monitor()` -- mirroring Phase 6's
`EngagementScorer` / `RuleBasedEngagementPredictor` pattern exactly.
"""
import abc
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ml_models.cognitive_monitoring.cognitive_features import (
    CognitiveFeatureError,
    CognitiveMonitoringInput,
)
from ml_models.cognitive_monitoring.cognitive_levels import (
    DEFAULT_ATTENTION_LEVEL_RANGES,
    score_to_attention_level,
    validate_level_ranges,
)
from ml_models.cognitive_monitoring.cognitive_utils import (
    classify_cognitive_state,
    clamp,
    combine_confidences,
    compute_attention_score,
    compute_confusion_score,
    compute_distraction_score,
    compute_fatigue_score,
    compute_gaze_score,
    compute_head_pose_score,
    derive_risk_flags,
    generate_reasons,
)
from utils.common import load_yaml_config
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_RELATIVE_PATH = Path("configs") / "cognitive_monitoring.yaml"


class CognitiveMonitoringError(Exception):
    """Base exception for all Phase 7 cognitive-monitoring failures."""


class CognitiveConfigError(CognitiveMonitoringError):
    """Raised when configs/cognitive_monitoring.yaml is missing required
    keys or contains invalid values."""


@dataclass(frozen=True)
class CognitiveResult:
    """Structured result of running the cognitive monitor on one student's
    combined multimodal + engagement input for a single moment in time."""

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

    risk_flags: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    degraded: bool = False
    error_message: Optional[str] = None
    processing_time_ms: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "cognitive_state": self.cognitive_state,
            "attention_score": round(float(self.attention_score), 2),
            "attention_level": self.attention_level,
            "distraction_score": round(float(self.distraction_score), 2),
            "fatigue_score": round(float(self.fatigue_score), 2),
            "confusion_score": round(float(self.confusion_score), 2),
            "overall_confidence": round(float(self.overall_confidence), 4),
            "emotion": self.emotion,
            "head_pose": self.head_pose,
            "gaze": self.gaze,
            "multiple_person": self.multiple_person,
            "phone_detected": self.phone_detected,
            "engagement_score": round(float(self.engagement_score), 2),
            "engagement_level": self.engagement_level,
            "risk_flags": list(self.risk_flags),
            "reasons": list(self.reasons),
            "degraded": self.degraded,
            "error_message": self.error_message,
            "processing_time_ms": round(float(self.processing_time_ms), 3),
        }


class CognitiveScorer(abc.ABC):
    """Abstract cognitive-monitoring backend.

    `RuleBasedCognitiveMonitor` (this phase) is the first implementation.
    A future ML-based monitor may implement `predict()` / `predict_safe()`
    with these exact signatures as a drop-in replacement -- every existing
    caller (including the FastAPI router) keeps working unmodified.
    """

    @abc.abstractmethod
    def predict(self, cognitive_input: CognitiveMonitoringInput) -> CognitiveResult:
        """Compute a CognitiveResult for one combined multimodal + engagement input.

        Raises:
            CognitiveMonitoringError: If prediction fails.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def predict_safe(self, cognitive_input: CognitiveMonitoringInput) -> CognitiveResult:
        """Like predict(), but never raises -- returns a degraded=True
        CognitiveResult on any failure instead."""
        raise NotImplementedError


def _default_config() -> Dict[str, Any]:
    """Fallback configuration used only if configs/cognitive_monitoring.yaml
    cannot be loaded, so the engine can still degrade gracefully rather than
    crash outright. The notebook always writes the real file, so this path
    is a defensive safety net, not the primary configuration source."""
    return {
        "attention_weights": {"gaze": 0.35, "head_pose": 0.35, "engagement": 0.30},
        "distraction_penalties": {"phone": 50.0, "multiple_person": 50.0, "looking_away": 25.0},
        "fatigue_thresholds": {"tired_emotion_weight": 70.0, "sad_emotion_weight": 20.0, "head_down_weight": 40.0},
        "confusion_thresholds": {"confused_emotion_weight": 75.0, "fear_emotion_weight": 30.0},
        "focus_thresholds": {"focus_attention_threshold": 70.0, "low_attention_threshold": 40.0},
        "risk_thresholds": {
            "distraction_threshold": 50.0,
            "fatigue_threshold": 60.0,
            "confusion_threshold": 60.0,
            "low_attention_threshold": 40.0,
            "low_confidence_threshold": 0.5,
        },
        "confidence_weights": {
            "emotion": 0.2, "face": 0.2, "gaze": 0.2,
            "head_pose": 0.15, "phone": 0.1, "engagement": 0.15,
        },
        "cognitive_level_ranges": {
            "VERY_LOW": [0, 20], "LOW": [21, 40], "MODERATE": [41, 60],
            "HIGH": [61, 80], "VERY_HIGH": [81, 100],
        },
        "head_pose_norm": {"yaw_norm_deg": 45.0, "pitch_norm_deg": 45.0, "roll_norm_deg": 30.0},
        "head_pose_classification": {"yaw_classification_deg": 15.0, "pitch_classification_deg": 15.0},
        "backend": "rule_based",
    }


class RuleBasedCognitiveMonitor(CognitiveScorer):
    """The Phase 7 rule-based cognitive monitoring engine.

    Configuration (attention weights, distraction penalties, fatigue/
    confusion/focus/risk thresholds, confidence-fusion weights, and
    cognitive-level ranges) is loaded lazily from
    configs/cognitive_monitoring.yaml on first use and cached for the
    lifetime of the instance. Use :func:`get_cognitive_monitor` to obtain
    the shared, process-wide singleton instead of constructing this class
    directly wherever possible.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        logger.info("RuleBasedCognitiveMonitor instance created.")

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _get_config(self) -> Dict[str, Any]:
        if self._config is None:
            config_path = self._config_path or (
                Path(__file__).resolve().parents[2] / "configs" / "cognitive_monitoring.yaml"
            )
            try:
                self._config = load_yaml_config(config_path)
                logger.info(f"Loaded cognitive monitoring config from {config_path}")
            except Exception as exc:  # noqa: BLE001 -- config load must never crash prediction.
                logger.error(f"Failed to load cognitive_monitoring.yaml ({exc}); using built-in defaults.")
                self._config = _default_config()
        return self._config

    def _level_ranges(self) -> Dict[str, tuple]:
        raw_ranges = self._get_config().get("cognitive_level_ranges", DEFAULT_ATTENTION_LEVEL_RANGES)
        ranges = {level: tuple(bounds) for level, bounds in raw_ranges.items()}
        validate_level_ranges(ranges)
        return ranges

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def predict(self, cognitive_input: CognitiveMonitoringInput) -> CognitiveResult:
        """Compute the cognitive state/attention/distraction/fatigue/
        confusion/confidence/flags/reasons for one student's combined
        multimodal + engagement input.

        Raises:
            CognitiveMonitoringError: If the input is invalid or scoring
                otherwise fails.
        """
        start = time.perf_counter()
        if not isinstance(cognitive_input, CognitiveMonitoringInput):
            raise CognitiveMonitoringError(
                f"Expected a CognitiveMonitoringInput, got {type(cognitive_input)!r}."
            )

        config = self._get_config()
        attention_weights = config.get("attention_weights", {})
        distraction_penalties = config.get("distraction_penalties", {})
        fatigue_thresholds = config.get("fatigue_thresholds", {})
        confusion_thresholds = config.get("confusion_thresholds", {})
        focus_thresholds = config.get("focus_thresholds", {})
        risk_thresholds = config.get("risk_thresholds", {})
        confidence_weights = config.get("confidence_weights", {})
        head_pose_norm = config.get("head_pose_norm", {})
        head_pose_classification = config.get("head_pose_classification", {})

        face = cognitive_input.face
        emotion = cognitive_input.emotion
        head_pose = cognitive_input.head_pose
        gaze = cognitive_input.gaze
        objects = cognitive_input.objects
        engagement = cognitive_input.engagement

        gaze_score = compute_gaze_score(
            gaze.looking_at_screen, gaze.looking_left, gaze.looking_right, gaze.looking_down
        )
        head_pose_score = compute_head_pose_score(
            head_pose.yaw, head_pose.pitch, head_pose.roll,
            yaw_norm_deg=float(head_pose_norm.get("yaw_norm_deg", 45.0)),
            pitch_norm_deg=float(head_pose_norm.get("pitch_norm_deg", 45.0)),
            roll_norm_deg=float(head_pose_norm.get("roll_norm_deg", 30.0)),
        )

        attention_score = compute_attention_score(
            gaze_score, head_pose_score, engagement.engagement_score,
            gaze_weight=float(attention_weights.get("gaze", 0.35)),
            head_pose_weight=float(attention_weights.get("head_pose", 0.35)),
            engagement_weight=float(attention_weights.get("engagement", 0.30)),
        )
        distraction_score = compute_distraction_score(
            objects.phone_detected, objects.multiple_person, not gaze.looking_at_screen,
            phone_weight=float(distraction_penalties.get("phone", 50.0)),
            multiple_person_weight=float(distraction_penalties.get("multiple_person", 40.0)),
            looking_away_weight=float(distraction_penalties.get("looking_away", 25.0)),
        )
        fatigue_score = compute_fatigue_score(
            emotion.emotion, gaze.looking_down,
            tired_emotion_weight=float(fatigue_thresholds.get("tired_emotion_weight", 70.0)),
            sad_emotion_weight=float(fatigue_thresholds.get("sad_emotion_weight", 20.0)),
            head_down_weight=float(fatigue_thresholds.get("head_down_weight", 40.0)),
        )
        confusion_score = compute_confusion_score(
            emotion.emotion,
            confused_emotion_weight=float(confusion_thresholds.get("confused_emotion_weight", 75.0)),
            fear_emotion_weight=float(confusion_thresholds.get("fear_emotion_weight", 30.0)),
        )

        # An undetected face forces attention to 0 -- there is nothing to attend with.
        if not face.face_detected:
            attention_score = 0.0

        cognitive_state = classify_cognitive_state(
            face.face_detected, attention_score, distraction_score, fatigue_score, confusion_score,
            distraction_threshold=float(risk_thresholds.get("distraction_threshold", 50.0)),
            fatigue_threshold=float(risk_thresholds.get("fatigue_threshold", 60.0)),
            confusion_threshold=float(risk_thresholds.get("confusion_threshold", 60.0)),
            low_attention_threshold=float(focus_thresholds.get("low_attention_threshold", 40.0)),
            focus_attention_threshold=float(focus_thresholds.get("focus_attention_threshold", 70.0)),
        )
        attention_level = score_to_attention_level(attention_score, ranges=self._level_ranges())

        overall_confidence = combine_confidences(
            emotion_confidence=emotion.emotion_confidence,
            face_confidence=face.authentication_confidence,
            gaze_confidence=gaze.gaze_confidence,
            head_pose_confidence=head_pose.head_pose_confidence,
            phone_confidence=objects.phone_confidence,
            engagement_confidence=engagement.overall_confidence,
            weights=confidence_weights,
        )

        from ml_models.engagement_prediction.engagement_utils import classify_gaze, classify_head_pose
        head_pose_label = classify_head_pose(
            head_pose.yaw, head_pose.pitch,
            yaw_threshold_deg=float(head_pose_classification.get("yaw_classification_deg", 15.0)),
            pitch_threshold_deg=float(head_pose_classification.get("pitch_classification_deg", 15.0)),
        )
        gaze_label = classify_gaze(gaze.looking_at_screen, gaze.looking_left, gaze.looking_right, gaze.looking_down)

        risk_flags = derive_risk_flags(
            cognitive_input, distraction_score, fatigue_score, confusion_score, attention_score,
            overall_confidence,
            distraction_threshold=float(risk_thresholds.get("distraction_threshold", 50.0)),
            fatigue_threshold=float(risk_thresholds.get("fatigue_threshold", 60.0)),
            confusion_threshold=float(risk_thresholds.get("confusion_threshold", 60.0)),
            low_attention_threshold=float(focus_thresholds.get("low_attention_threshold", 40.0)),
            low_confidence_threshold=float(risk_thresholds.get("low_confidence_threshold", 0.5)),
        )
        reasons = generate_reasons(
            cognitive_input, cognitive_state, attention_score, distraction_score,
            fatigue_score, confusion_score, risk_flags,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        result = CognitiveResult(
            student_id=cognitive_input.student_id,
            cognitive_state=cognitive_state,
            attention_score=attention_score,
            attention_level=attention_level,
            distraction_score=distraction_score,
            fatigue_score=fatigue_score,
            confusion_score=confusion_score,
            overall_confidence=overall_confidence,
            emotion=emotion.emotion,
            head_pose=head_pose_label,
            gaze=gaze_label,
            multiple_person=objects.multiple_person,
            phone_detected=objects.phone_detected,
            engagement_score=engagement.engagement_score,
            engagement_level=engagement.engagement_level,
            risk_flags=risk_flags,
            reasons=reasons,
            degraded=False,
            error_message=None,
            processing_time_ms=elapsed_ms,
        )
        logger.info(
            f"Cognitive prediction: student_id={result.student_id} state={cognitive_state} "
            f"attention={attention_score:.2f} distraction={distraction_score:.2f} "
            f"fatigue={fatigue_score:.2f} confusion={confusion_score:.2f} "
            f"confidence={overall_confidence:.3f} risk_flags={risk_flags} time={elapsed_ms:.2f}ms"
        )
        return result

    def predict_safe(self, cognitive_input: CognitiveMonitoringInput) -> CognitiveResult:
        """Like predict(), but degrades gracefully instead of raising.

        Returns a CognitiveResult with degraded=True and an error_message
        set whenever prediction fails for any reason, so callers (e.g. the
        FastAPI router) never need to handle a raw exception.
        """
        start = time.perf_counter()
        try:
            return self.predict(cognitive_input)
        except Exception as exc:  # noqa: BLE001 -- must never crash the caller.
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.error(f"Cognitive prediction degraded gracefully: {exc}")
            fallback_student_id = "UNKNOWN"
            try:
                fallback_student_id = cognitive_input.student_id
            except Exception:  # noqa: BLE001
                pass
            return CognitiveResult(
                student_id=fallback_student_id,
                cognitive_state="UNAVAILABLE",
                attention_score=0.0,
                attention_level=score_to_attention_level(0.0),
                distraction_score=0.0,
                fatigue_score=0.0,
                confusion_score=0.0,
                overall_confidence=0.0,
                emotion=None,
                head_pose="unknown",
                gaze="unknown",
                multiple_person=False,
                phone_detected=False,
                engagement_score=0.0,
                engagement_level="VERY_LOW",
                risk_flags=["LOW_CONFIDENCE"],
                reasons=["Cognitive prediction failed; returning a safe, degraded default result."],
                degraded=True,
                error_message=str(exc),
                processing_time_ms=elapsed_ms,
            )


# ----------------------------------------------------------------------
# Process-wide singleton accessor (mirrors Phase 6's
# get_engagement_predictor() / reset_engagement_predictor() pattern).
# ----------------------------------------------------------------------
_cognitive_monitor: Optional[CognitiveScorer] = None


def get_cognitive_monitor() -> CognitiveScorer:
    """Return the shared, process-wide CognitiveScorer singleton, creating
    it on first call using the backend named in configs/cognitive_monitoring.yaml
    (currently only "rule_based" is implemented)."""
    global _cognitive_monitor
    if _cognitive_monitor is None:
        _cognitive_monitor = RuleBasedCognitiveMonitor()
        backend = _cognitive_monitor._get_config().get("backend", "rule_based")
        if backend not in ("rule_based",):
            logger.warning(
                f"Configured cognitive backend '{backend}' is not yet implemented; "
                "falling back to 'rule_based'."
            )
    return _cognitive_monitor


def reset_cognitive_monitor() -> None:
    """Reset the singleton -- primarily useful for tests."""
    global _cognitive_monitor
    _cognitive_monitor = None