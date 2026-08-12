"""
Phase 7 Cognitive Monitoring Engine -- pytest suite.

Covers: cognitive_levels (attention-level/state/risk-flag vocabulary),
cognitive_features (input dataclasses + validation, reusing Phase 6's
FaceAuthenticationInput/EmotionInput/HeadPoseInput/GazeInput/
ObjectDetectionInput), cognitive_utils (pure scoring/classification
functions), cognitive_monitor (rule-based engine, singleton, graceful
degradation, every cognitive-state scenario), configs/cognitive_monitoring.yaml,
the FastAPI router, and backend/app/main.py registration.
"""
import sys
from pathlib import Path

import pytest
import yaml


def _detect_project_root(marker_dirs=("utils", "configs", "backend", "models")) -> Path:
    candidates = [Path.cwd() / "student_engagement_system", Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        if candidate.is_dir() and all((candidate / m).is_dir() for m in marker_dirs):
            return candidate.resolve()
    raise FileNotFoundError("Could not locate the project root for Phase 7 tests.")


PROJECT_ROOT = _detect_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.cognitive_monitoring import cognitive_levels  # noqa: E402
from models.cognitive_monitoring import cognitive_features as cf  # noqa: E402
from models.cognitive_monitoring import cognitive_utils as cu  # noqa: E402
from models.cognitive_monitoring import cognitive_monitor as cm  # noqa: E402
from utils.common import load_yaml_config  # noqa: E402


# ---------------------------------------------------------------------------
# cognitive_levels
# ---------------------------------------------------------------------------
class TestCognitiveLevels:
    def test_default_attention_ranges_are_valid(self):
        cognitive_levels.validate_level_ranges(cognitive_levels.DEFAULT_ATTENTION_LEVEL_RANGES)

    @pytest.mark.parametrize("score,expected", [
        (0, "VERY_LOW"), (10, "VERY_LOW"), (20, "VERY_LOW"),
        (21, "LOW"), (30, "LOW"), (40, "LOW"),
        (41, "MODERATE"), (50, "MODERATE"), (60, "MODERATE"),
        (61, "HIGH"), (70, "HIGH"), (80, "HIGH"),
        (81, "VERY_HIGH"), (95, "VERY_HIGH"), (100, "VERY_HIGH"),
    ])
    def test_score_to_attention_level_boundaries(self, score, expected):
        assert cognitive_levels.score_to_attention_level(score) == expected

    def test_score_to_attention_level_clamps_above_100(self):
        assert cognitive_levels.score_to_attention_level(150) == "VERY_HIGH"

    def test_score_to_attention_level_clamps_below_0(self):
        assert cognitive_levels.score_to_attention_level(-25) == "VERY_LOW"

    def test_all_cognitive_states_known(self):
        for state in cognitive_levels.ALL_COGNITIVE_STATES:
            assert cognitive_levels.is_known_cognitive_state(state)

    def test_unknown_cognitive_state_rejected(self):
        assert cognitive_levels.is_known_cognitive_state("NOT_A_REAL_STATE") is False

    def test_all_risk_flags_known(self):
        for flag in cognitive_levels.ALL_RISK_FLAGS:
            assert cognitive_levels.is_known_risk_flag(flag)

    def test_unknown_risk_flag_rejected(self):
        assert cognitive_levels.is_known_risk_flag("NOT_A_REAL_FLAG") is False

    def test_invalid_ranges_missing_level_raises(self):
        bad = dict(cognitive_levels.DEFAULT_ATTENTION_LEVEL_RANGES)
        del bad["VERY_HIGH"]
        with pytest.raises(cognitive_levels.InvalidLevelRangesError):
            cognitive_levels.validate_level_ranges(bad)

    def test_invalid_ranges_gap_raises(self):
        bad = {
            "VERY_LOW": (0, 19), "LOW": (21, 40), "MODERATE": (41, 60),
            "HIGH": (61, 80), "VERY_HIGH": (81, 100),
        }
        with pytest.raises(cognitive_levels.InvalidLevelRangesError):
            cognitive_levels.validate_level_ranges(bad)

    def test_invalid_ranges_overlap_raises(self):
        bad = {
            "VERY_LOW": (0, 25), "LOW": (21, 40), "MODERATE": (41, 60),
            "HIGH": (61, 80), "VERY_HIGH": (81, 100),
        }
        with pytest.raises(cognitive_levels.InvalidLevelRangesError):
            cognitive_levels.validate_level_ranges(bad)

    def test_invalid_ranges_not_starting_at_zero_raises(self):
        bad = {
            "VERY_LOW": (1, 20), "LOW": (21, 40), "MODERATE": (41, 60),
            "HIGH": (61, 80), "VERY_HIGH": (81, 100),
        }
        with pytest.raises(cognitive_levels.InvalidLevelRangesError):
            cognitive_levels.validate_level_ranges(bad)

    def test_invalid_ranges_not_ending_at_100_raises(self):
        bad = {
            "VERY_LOW": (0, 20), "LOW": (21, 40), "MODERATE": (41, 60),
            "HIGH": (61, 80), "VERY_HIGH": (81, 99),
        }
        with pytest.raises(cognitive_levels.InvalidLevelRangesError):
            cognitive_levels.validate_level_ranges(bad)


# ---------------------------------------------------------------------------
# cognitive_features
# ---------------------------------------------------------------------------
class TestCognitiveFeatures:
    def test_engagement_summary_input_defaults(self):
        summary = cf.EngagementSummaryInput()
        assert summary.engagement_score == 50.0
        assert summary.engagement_level == "MEDIUM"

    def test_engagement_summary_input_uppercases_level(self):
        summary = cf.EngagementSummaryInput(engagement_level="high")
        assert summary.engagement_level == "HIGH"

    def test_engagement_summary_score_out_of_range_raises(self):
        with pytest.raises(cf.CognitiveFeatureError):
            cf.EngagementSummaryInput(engagement_score=150.0)

    def test_engagement_summary_confidence_out_of_range_raises(self):
        with pytest.raises(cf.CognitiveFeatureError):
            cf.EngagementSummaryInput(overall_confidence=1.5)

    def test_engagement_summary_empty_level_raises(self):
        with pytest.raises(cf.CognitiveFeatureError):
            cf.EngagementSummaryInput(engagement_level="   ")

    def test_from_dict_flat_payload_builds_input(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s1", "emotion": "happy", "emotion_confidence": 0.9,
            "looking_at_screen": True, "gaze_confidence": 0.9,
            "yaw": 0.0, "pitch": 0.0, "roll": 0.0, "head_pose_confidence": 0.9,
            "phone_detected": False, "person_count": 1,
            "engagement_score": 75.0, "engagement_level": "high", "engagement_confidence": 0.8,
        })
        assert cognitive_input.student_id == "s1"
        assert cognitive_input.emotion.emotion == "happy"
        assert cognitive_input.engagement.engagement_score == 75.0
        assert cognitive_input.engagement.engagement_level == "HIGH"

    def test_from_dict_missing_student_id_raises(self):
        with pytest.raises(cf.CognitiveFeatureError):
            cf.CognitiveMonitoringInput.from_dict({"emotion": "happy"})

    def test_from_dict_nested_payload_builds_input(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "face": {"student_id": "s2"},
            "engagement": {"engagement_score": 10.0, "engagement_level": "very_low"},
        })
        assert cognitive_input.student_id == "s2"
        assert cognitive_input.engagement.engagement_level == "VERY_LOW"

    def test_from_dict_defaults_engagement_summary_when_absent(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s3"})
        assert cognitive_input.engagement.engagement_score == 50.0

    def test_reused_face_input_validation_still_applies(self):
        with pytest.raises(cf.CognitiveFeatureError):
            cf.CognitiveMonitoringInput.from_dict({"student_id": "   "})

    def test_reused_gaze_input_conflict_still_applies(self):
        with pytest.raises(cf.CognitiveFeatureError):
            cf.CognitiveMonitoringInput.from_dict({
                "student_id": "s4", "looking_at_screen": True, "looking_down": True,
            })

    def test_reused_object_detection_person_count_consistency(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s5", "person_count": 4})
        assert cognitive_input.objects.multiple_person is True


# ---------------------------------------------------------------------------
# cognitive_utils
# ---------------------------------------------------------------------------
class TestCognitiveUtils:
    def test_compute_attention_score_max(self):
        assert cu.compute_attention_score(100, 100, 100) == 100.0

    def test_compute_attention_score_min(self):
        assert cu.compute_attention_score(0, 0, 0) == 0.0

    def test_compute_attention_score_zero_weights_returns_zero(self):
        assert cu.compute_attention_score(100, 100, 100, gaze_weight=0, head_pose_weight=0, engagement_weight=0) == 0.0

    def test_distraction_score_phone_only(self):
        assert cu.compute_distraction_score(True, False, False) == 50.0

    def test_distraction_score_multiple_person_only(self):
        assert cu.compute_distraction_score(False, True, False) == 50.0

    def test_distraction_score_looking_away_only(self):
        assert cu.compute_distraction_score(False, False, True) == 25.0

    def test_distraction_score_none(self):
        assert cu.compute_distraction_score(False, False, False) == 0.0

    def test_distraction_score_clamped_at_100(self):
        assert cu.compute_distraction_score(True, True, True) == 100.0

    def test_fatigue_score_tired_emotion(self):
        assert cu.compute_fatigue_score("tired", False) == 70.0

    def test_fatigue_score_sad_emotion(self):
        assert cu.compute_fatigue_score("sad", False) == 20.0

    def test_fatigue_score_looking_down(self):
        assert cu.compute_fatigue_score(None, True) == 40.0

    def test_fatigue_score_none(self):
        assert cu.compute_fatigue_score("happy", False) == 0.0

    def test_fatigue_score_combined_clamped(self):
        assert cu.compute_fatigue_score("tired", True) == 100.0

    def test_confusion_score_confused_emotion(self):
        assert cu.compute_confusion_score("confused") == 75.0

    def test_confusion_score_fear_emotion(self):
        assert cu.compute_confusion_score("fear") == 30.0

    def test_confusion_score_none(self):
        assert cu.compute_confusion_score("happy") == 0.0

    def test_classify_cognitive_state_no_face_is_unavailable(self):
        assert cu.classify_cognitive_state(False, 80, 0, 0, 0) == cognitive_levels.UNAVAILABLE

    def test_classify_cognitive_state_high_attention_is_focused(self):
        assert cu.classify_cognitive_state(True, 80, 0, 0, 0) == cognitive_levels.FOCUSED

    def test_classify_cognitive_state_low_attention_is_disengaged(self):
        assert cu.classify_cognitive_state(True, 20, 0, 0, 0) == cognitive_levels.DISENGAGED

    def test_classify_cognitive_state_moderate_attention_is_neutral(self):
        assert cu.classify_cognitive_state(True, 50, 0, 0, 0) == cognitive_levels.NEUTRAL

    def test_classify_cognitive_state_high_distraction_wins(self):
        assert cu.classify_cognitive_state(True, 80, 60, 0, 0) == cognitive_levels.DISTRACTED

    def test_classify_cognitive_state_high_fatigue(self):
        assert cu.classify_cognitive_state(True, 80, 0, 70, 0) == cognitive_levels.FATIGUED

    def test_classify_cognitive_state_high_confusion(self):
        assert cu.classify_cognitive_state(True, 80, 0, 0, 75) == cognitive_levels.CONFUSED

    def test_classify_cognitive_state_distraction_takes_priority_over_fatigue(self):
        assert cu.classify_cognitive_state(True, 80, 60, 70, 0) == cognitive_levels.DISTRACTED

    def test_combine_confidences_all_high(self):
        combined = cu.combine_confidences(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
        assert abs(combined - 0.9) < 1e-6

    def test_combine_confidences_zero_weights_returns_zero(self):
        assert cu.combine_confidences(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, weights={
            "emotion": 0.0, "face": 0.0, "gaze": 0.0, "head_pose": 0.0, "phone": 0.0, "engagement": 0.0,
        }) == 0.0

    def test_derive_risk_flags_no_face(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s1", "face_detected": False})
        flags = cu.derive_risk_flags(cognitive_input, 0, 0, 0, 0, 0.9, 50, 60, 60, 40, 0.5)
        assert cognitive_levels.NO_FACE in flags
        assert cognitive_levels.UNKNOWN_FACE not in flags

    def test_derive_risk_flags_unknown_face(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s1", "authenticated": False})
        flags = cu.derive_risk_flags(cognitive_input, 0, 0, 0, 80, 0.9, 50, 60, 60, 40, 0.5)
        assert cognitive_levels.UNKNOWN_FACE in flags

    def test_derive_risk_flags_phone_and_crowd(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s1", "phone_detected": True, "person_count": 2,
        })
        flags = cu.derive_risk_flags(cognitive_input, 90, 0, 0, 80, 0.9, 50, 60, 60, 40, 0.5)
        assert cognitive_levels.PHONE_USAGE in flags
        assert cognitive_levels.MULTIPLE_PERSON in flags
        assert cognitive_levels.HIGH_DISTRACTION in flags

    def test_derive_risk_flags_low_confidence(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s1"})
        flags = cu.derive_risk_flags(cognitive_input, 0, 0, 0, 80, 0.1, 50, 60, 60, 40, 0.5)
        assert cognitive_levels.LOW_CONFIDENCE in flags

    def test_generate_reasons_nonempty(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s1"})
        reasons = cu.generate_reasons(cognitive_input, "FOCUSED", 80.0, 0.0, 0.0, 0.0, [])
        assert len(reasons) > 0
        assert all(isinstance(r, str) for r in reasons)

    def test_generate_reasons_no_face_short_circuits(self):
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s1", "face_detected": False})
        reasons = cu.generate_reasons(cognitive_input, "UNAVAILABLE", 0.0, 0.0, 0.0, 0.0, ["NO_FACE"])
        assert any("No face detected" in r for r in reasons)


# ---------------------------------------------------------------------------
# cognitive_monitor
# ---------------------------------------------------------------------------
class TestCognitiveMonitor:
    def test_singleton_returns_same_instance(self):
        cm.reset_cognitive_monitor()
        a = cm.get_cognitive_monitor()
        b = cm.get_cognitive_monitor()
        assert a is b

    def test_predict_rejects_wrong_type(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        with pytest.raises(cm.CognitiveMonitoringError):
            monitor.predict("not-a-valid-input")

    def test_predict_safe_never_raises_on_bad_input(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        result = monitor.predict_safe("not-a-valid-input")
        assert result.degraded is True
        assert isinstance(result.as_dict(), dict)

    def test_high_attention_scenario_is_focused(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "22CS001", "emotion": "happy", "emotion_confidence": 0.9,
            "looking_at_screen": True, "gaze_confidence": 0.92,
            "yaw": 2.0, "pitch": -1.0, "roll": 0.5, "head_pose_confidence": 0.95,
            "phone_detected": False, "person_count": 1,
            "authenticated": True, "authentication_confidence": 0.98, "attendance": True,
            "engagement_score": 90.0, "engagement_level": "EXCELLENT", "engagement_confidence": 0.95,
        })
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "FOCUSED"
        assert result.attention_level in ("HIGH", "VERY_HIGH")

    def test_low_attention_scenario_is_disengaged(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s1", "looking_at_screen": False, "looking_down": True,
            "engagement_score": 5.0, "yaw": 60.0, "pitch": 60.0,
        })
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "DISENGAGED"
        assert "LOW_ATTENTION" in result.risk_flags

    def test_confused_scenario(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s2", "emotion": "confused", "emotion_confidence": 0.8,
        })
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "CONFUSED"
        assert "CONFUSION_DETECTED" in result.risk_flags

    def test_fatigue_scenario(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s3", "emotion": "tired"})
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "FATIGUED"
        assert "FATIGUE_DETECTED" in result.risk_flags

    def test_distraction_phone_scenario(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s4", "phone_detected": True, "phone_confidence": 0.9,
        })
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "DISTRACTED"
        assert "PHONE_USAGE" in result.risk_flags
        assert "HIGH_DISTRACTION" in result.risk_flags

    def test_distraction_multiple_person_scenario(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s5", "person_count": 3})
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "DISTRACTED"
        assert "MULTIPLE_PERSON" in result.risk_flags

    def test_looking_away_scenario_flagged(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s6", "looking_at_screen": False, "looking_left": True, "engagement_score": 50.0,
        })
        result = monitor.predict(cognitive_input)
        assert "LOOKING_AWAY" in result.risk_flags
        assert result.gaze == "left"

    def test_no_face_scenario(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s7", "face_detected": False})
        result = monitor.predict(cognitive_input)
        assert result.cognitive_state == "UNAVAILABLE"
        assert result.attention_score == 0.0
        assert "NO_FACE" in result.risk_flags

    def test_unknown_face_scenario(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s8", "authenticated": False})
        result = monitor.predict(cognitive_input)
        assert "UNKNOWN_FACE" in result.risk_flags

    def test_missing_optional_inputs_use_safe_defaults(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s9"})
        result = monitor.predict(cognitive_input)
        assert 0.0 <= result.attention_score <= 100.0
        assert result.cognitive_state in cognitive_levels.ALL_COGNITIVE_STATES

    def test_malformed_input_type_uses_predict_safe(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        result = monitor.predict_safe({"not": "a CognitiveMonitoringInput"})
        assert result.degraded is True
        assert result.cognitive_state == "UNAVAILABLE"

    def test_scores_always_clamped(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s10", "phone_detected": True, "person_count": 5,
            "emotion": "tired", "looking_at_screen": False, "looking_down": True,
        })
        result = monitor.predict(cognitive_input)
        assert 0.0 <= result.attention_score <= 100.0
        assert 0.0 <= result.distraction_score <= 100.0
        assert 0.0 <= result.fatigue_score <= 100.0
        assert 0.0 <= result.confusion_score <= 100.0

    def test_result_payload_schema(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({"student_id": "s11"})
        result = monitor.predict(cognitive_input)
        payload = result.as_dict()
        for key in (
            "student_id", "cognitive_state", "attention_score", "attention_level",
            "distraction_score", "fatigue_score", "confusion_score", "overall_confidence",
            "emotion", "head_pose", "gaze", "multiple_person", "phone_detected",
            "engagement_score", "engagement_level", "risk_flags", "reasons",
            "degraded", "error_message", "processing_time_ms",
        ):
            assert key in payload

    def test_engagement_score_propagates_into_result(self):
        monitor = cm.RuleBasedCognitiveMonitor()
        cognitive_input = cf.CognitiveMonitoringInput.from_dict({
            "student_id": "s12", "engagement_score": 77.0, "engagement_level": "high",
        })
        result = monitor.predict(cognitive_input)
        assert result.engagement_score == 77.0
        assert result.engagement_level == "HIGH"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
class TestCognitiveMonitoringConfig:
    def test_config_file_exists(self):
        assert (PROJECT_ROOT / "configs" / "cognitive_monitoring.yaml").exists()

    def test_config_loads_and_has_expected_sections(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "cognitive_monitoring.yaml")
        for section in (
            "attention_weights", "distraction_penalties", "fatigue_thresholds",
            "confusion_thresholds", "focus_thresholds", "risk_thresholds",
            "confidence_weights", "cognitive_level_ranges", "backend",
        ):
            assert section in config

    def test_config_is_valid_yaml(self):
        raw = (PROJECT_ROOT / "configs" / "cognitive_monitoring.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)
        assert isinstance(parsed, dict)

    def test_config_cognitive_level_ranges_are_valid(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "cognitive_monitoring.yaml")
        ranges = {level: tuple(bounds) for level, bounds in config["cognitive_level_ranges"].items()}
        cognitive_levels.validate_level_ranges(ranges)

    def test_config_backend_is_rule_based(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "cognitive_monitoring.yaml")
        assert config["backend"] == "rule_based"


# ---------------------------------------------------------------------------
# Router / main.py registration
# ---------------------------------------------------------------------------
class TestCognitiveMonitoringRouter:
    def test_router_module_imports(self):
        import importlib
        module = importlib.import_module("backend.app.routers.cognitive_monitoring")
        importlib.reload(module)
        assert hasattr(module, "router")

    def test_router_exposes_expected_routes(self):
        import importlib
        module = importlib.import_module("backend.app.routers.cognitive_monitoring")
        importlib.reload(module)
        route_paths = sorted(r.path for r in module.router.routes)
        assert "/cognitive/predict" in route_paths
        assert "/cognitive/config" in route_paths
        assert "/cognitive/health" in route_paths

    def test_main_py_registers_cognitive_monitoring_router(self):
        main_source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        assert "from backend.app.routers import cognitive_monitoring" in main_source
        assert "app.include_router(cognitive_monitoring.router)" in main_source

    def test_predict_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.post("/cognitive/predict", json={
            "student_id": "22CS001", "emotion": "happy", "emotion_confidence": 0.9,
            "looking_at_screen": True, "gaze_confidence": 0.9,
            "yaw": 0.0, "pitch": 0.0, "roll": 0.0, "head_pose_confidence": 0.9,
            "phone_detected": False, "person_count": 1,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["student_id"] == "22CS001"
        assert body["cognitive_state"] in (
            "FOCUSED", "NEUTRAL", "DISTRACTED", "CONFUSED", "FATIGUED", "DISENGAGED", "UNAVAILABLE",
        )

    def test_predict_endpoint_missing_student_id_rejected(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.post("/cognitive/predict", json={"emotion": "happy"})
        assert resp.status_code == 422

    def test_config_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/cognitive/config")
        assert resp.status_code == 200
        assert "attention_weights" in resp.json()

    def test_health_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/cognitive/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"