"""
Phase 6 Engagement Prediction Engine -- pytest suite.

Covers: engagement_levels (level/range logic), engagement_features (input
dataclasses + validation), engagement_utils (pure scoring/utility
functions), engagement_predictor (rule-based scoring engine, singleton,
graceful degradation), configs/engagement_prediction.yaml, the FastAPI
router, and backend/app/main.py registration.
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
    raise FileNotFoundError("Could not locate the project root for Phase 6 tests.")


PROJECT_ROOT = _detect_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_models.engagement_prediction import engagement_levels  # noqa: E402
from ml_models.engagement_prediction import engagement_features as ef  # noqa: E402
from ml_models.engagement_prediction import engagement_utils as eu  # noqa: E402
from ml_models.engagement_prediction import engagement_predictor as ep  # noqa: E402
from utils.common import load_yaml_config  # noqa: E402


# ---------------------------------------------------------------------------
# engagement_levels
# ---------------------------------------------------------------------------
class TestEngagementLevels:
    def test_default_ranges_are_valid(self):
        engagement_levels.validate_level_ranges(engagement_levels.DEFAULT_LEVEL_RANGES)

    @pytest.mark.parametrize("score,expected", [
        (0, "VERY_LOW"), (10, "VERY_LOW"), (20, "VERY_LOW"),
        (21, "LOW"), (30, "LOW"), (40, "LOW"),
        (41, "MEDIUM"), (50, "MEDIUM"), (60, "MEDIUM"),
        (61, "HIGH"), (70, "HIGH"), (80, "HIGH"),
        (81, "EXCELLENT"), (95, "EXCELLENT"), (100, "EXCELLENT"),
    ])
    def test_score_to_level_boundaries(self, score, expected):
        assert engagement_levels.score_to_level(score) == expected

    def test_score_to_level_clamps_above_100(self):
        assert engagement_levels.score_to_level(150) == "EXCELLENT"

    def test_score_to_level_clamps_below_0(self):
        assert engagement_levels.score_to_level(-25) == "VERY_LOW"

    def test_all_risk_flags_known(self):
        for flag in engagement_levels.ALL_RISK_FLAGS:
            assert engagement_levels.is_known_risk_flag(flag)

    def test_unknown_risk_flag_rejected(self):
        assert engagement_levels.is_known_risk_flag("NOT_A_REAL_FLAG") is False

    def test_invalid_ranges_missing_level_raises(self):
        bad = dict(engagement_levels.DEFAULT_LEVEL_RANGES)
        del bad["EXCELLENT"]
        with pytest.raises(engagement_levels.InvalidLevelRangesError):
            engagement_levels.validate_level_ranges(bad)

    def test_invalid_ranges_gap_raises(self):
        bad = {
            "VERY_LOW": (0, 19), "LOW": (21, 40), "MEDIUM": (41, 60),
            "HIGH": (61, 80), "EXCELLENT": (81, 100),
        }
        with pytest.raises(engagement_levels.InvalidLevelRangesError):
            engagement_levels.validate_level_ranges(bad)

    def test_invalid_ranges_overlap_raises(self):
        bad = {
            "VERY_LOW": (0, 25), "LOW": (21, 40), "MEDIUM": (41, 60),
            "HIGH": (61, 80), "EXCELLENT": (81, 100),
        }
        with pytest.raises(engagement_levels.InvalidLevelRangesError):
            engagement_levels.validate_level_ranges(bad)

    def test_invalid_ranges_not_starting_at_zero_raises(self):
        bad = {
            "VERY_LOW": (1, 20), "LOW": (21, 40), "MEDIUM": (41, 60),
            "HIGH": (61, 80), "EXCELLENT": (81, 100),
        }
        with pytest.raises(engagement_levels.InvalidLevelRangesError):
            engagement_levels.validate_level_ranges(bad)

    def test_invalid_ranges_not_ending_at_100_raises(self):
        bad = {
            "VERY_LOW": (0, 20), "LOW": (21, 40), "MEDIUM": (41, 60),
            "HIGH": (61, 80), "EXCELLENT": (81, 99),
        }
        with pytest.raises(engagement_levels.InvalidLevelRangesError):
            engagement_levels.validate_level_ranges(bad)


# ---------------------------------------------------------------------------
# engagement_features
# ---------------------------------------------------------------------------
class TestEngagementFeatures:
    def test_face_authentication_input_defaults(self):
        face = ef.FaceAuthenticationInput(student_id="s1")
        assert face.authenticated is True
        assert face.attendance is True

    def test_face_authentication_empty_student_id_raises(self):
        with pytest.raises(ef.EngagementFeatureError):
            ef.FaceAuthenticationInput(student_id="   ")

    def test_face_authentication_confidence_out_of_range_raises(self):
        with pytest.raises(ef.EngagementFeatureError):
            ef.FaceAuthenticationInput(student_id="s1", authentication_confidence=1.5)

    def test_face_not_detected_forces_unauthenticated(self):
        face = ef.FaceAuthenticationInput(student_id="s1", face_detected=False, authenticated=True)
        assert face.authenticated is False
        assert face.authentication_confidence == 0.0

    def test_emotion_input_lowercases_label(self):
        emotion = ef.EmotionInput(emotion="HAPPY", emotion_confidence=0.8)
        assert emotion.emotion == "happy"

    def test_emotion_confidence_out_of_range_raises(self):
        with pytest.raises(ef.EngagementFeatureError):
            ef.EmotionInput(emotion="happy", emotion_confidence=-0.1)

    def test_head_pose_input_casts_to_float(self):
        head_pose = ef.HeadPoseInput(yaw="5", pitch="0", roll="0", head_pose_confidence=0.9)
        assert isinstance(head_pose.yaw, float)

    def test_gaze_input_conflicting_flags_raises(self):
        with pytest.raises(ef.EngagementFeatureError):
            ef.GazeInput(looking_at_screen=True, looking_down=True)

    def test_gaze_input_valid_combo(self):
        gaze = ef.GazeInput(looking_at_screen=False, looking_left=True)
        assert gaze.looking_left is True

    def test_object_detection_negative_person_count_raises(self):
        with pytest.raises(ef.EngagementFeatureError):
            ef.ObjectDetectionInput(person_count=-3)

    def test_object_detection_phone_not_detected_zeroes_confidence(self):
        objects = ef.ObjectDetectionInput(phone_detected=False, phone_confidence=0.8)
        assert objects.phone_confidence == 0.0

    def test_object_detection_person_count_forces_multiple_person(self):
        objects = ef.ObjectDetectionInput(person_count=2, multiple_person=False)
        assert objects.multiple_person is True

    def test_from_dict_flat_payload_builds_input(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "emotion": "happy", "emotion_confidence": 0.9,
            "looking_at_screen": True, "gaze_confidence": 0.9,
            "yaw": 0.0, "pitch": 0.0, "roll": 0.0, "head_pose_confidence": 0.9,
            "phone_detected": False, "person_count": 1,
        })
        assert engagement_input.student_id == "s1"
        assert engagement_input.emotion.emotion == "happy"

    def test_from_dict_missing_student_id_raises(self):
        with pytest.raises(ef.EngagementFeatureError):
            ef.EngagementPredictionInput.from_dict({"emotion": "happy"})

    def test_from_dict_nested_payload_builds_input(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "face": {"student_id": "s2"},
            "emotion": {"emotion": "sad", "emotion_confidence": 0.6},
            "head_pose": {"yaw": 0, "pitch": 0, "roll": 0, "head_pose_confidence": 0.5},
            "gaze": {"looking_at_screen": True, "gaze_confidence": 0.5},
            "objects": {"person_count": 1},
        })
        assert engagement_input.student_id == "s2"
        assert engagement_input.emotion.emotion == "sad"


# ---------------------------------------------------------------------------
# engagement_utils
# ---------------------------------------------------------------------------
class TestEngagementUtils:
    def test_clamp_within_range(self):
        assert eu.clamp(50) == 50

    def test_clamp_above_range(self):
        assert eu.clamp(150) == 100

    def test_clamp_below_range(self):
        assert eu.clamp(-10) == 0

    def test_emotion_score_happy_is_high(self):
        assert eu.compute_emotion_score("happy") == 100.0

    def test_emotion_score_angry_is_low(self):
        assert eu.compute_emotion_score("angry") == 20.0

    def test_emotion_score_none_uses_default(self):
        assert eu.compute_emotion_score(None) == ef.DEFAULT_EMOTION_SCORE

    def test_emotion_score_unknown_label_uses_default(self):
        assert eu.compute_emotion_score("bewildered") == ef.DEFAULT_EMOTION_SCORE

    def test_head_pose_score_center_is_max(self):
        assert eu.compute_head_pose_score(0, 0, 0) == 100.0

    def test_head_pose_score_degrades_with_deviation(self):
        center_score = eu.compute_head_pose_score(0, 0, 0)
        off_center_score = eu.compute_head_pose_score(40, 40, 25)
        assert off_center_score < center_score

    def test_head_pose_score_extreme_deviation_is_zero(self):
        assert eu.compute_head_pose_score(90, 90, 90) == 0.0

    def test_classify_head_pose_center(self):
        assert eu.classify_head_pose(0, 0) == "center"

    def test_classify_head_pose_left(self):
        assert eu.classify_head_pose(-30, 0) == "left"

    def test_classify_head_pose_right(self):
        assert eu.classify_head_pose(30, 0) == "right"

    def test_classify_head_pose_down(self):
        assert eu.classify_head_pose(0, 25) == "down"

    def test_classify_head_pose_up(self):
        assert eu.classify_head_pose(0, -25) == "up"

    def test_gaze_score_screen_is_max(self):
        assert eu.compute_gaze_score(True, False, False, False) == 100.0

    def test_gaze_score_down_is_low(self):
        assert eu.compute_gaze_score(False, False, False, True) == 20.0

    def test_gaze_score_side_glance(self):
        assert eu.compute_gaze_score(False, True, False, False) == 45.0

    def test_classify_gaze_screen(self):
        assert eu.classify_gaze(True, False, False, False) == "screen"

    def test_classify_gaze_left(self):
        assert eu.classify_gaze(False, True, False, False) == "left"

    def test_classify_gaze_right(self):
        assert eu.classify_gaze(False, False, True, False) == "right"

    def test_classify_gaze_down(self):
        assert eu.classify_gaze(False, False, False, True) == "down"

    def test_classify_gaze_unknown(self):
        assert eu.classify_gaze(False, False, False, False) == "unknown"

    def test_distraction_score_no_distraction(self):
        assert eu.compute_distraction_score(False, False) == 100.0

    def test_distraction_score_phone_only(self):
        assert eu.compute_distraction_score(False, True) == 50.0

    def test_distraction_score_both(self):
        assert eu.compute_distraction_score(True, True) == 0.0

    def test_phone_penalty_applied(self):
        assert eu.compute_phone_penalty(True, 20.0) == -20.0

    def test_phone_penalty_not_applied(self):
        assert eu.compute_phone_penalty(False, 20.0) == 0.0

    def test_multiple_person_penalty_applied(self):
        assert eu.compute_multiple_person_penalty(True, 15.0) == -15.0

    def test_face_authenticated_bonus_applied(self):
        assert eu.compute_face_authenticated_bonus(True, 10.0) == 10.0

    def test_face_authenticated_bonus_not_applied(self):
        assert eu.compute_face_authenticated_bonus(False, 10.0) == 0.0

    def test_attendance_bonus_applied(self):
        assert eu.compute_attendance_bonus(True, 5.0) == 5.0

    def test_combine_confidences_all_high(self):
        combined = eu.combine_confidences(0.9, 0.9, 0.9, 0.9, 0.9)
        assert abs(combined - 0.9) < 1e-6

    def test_combine_confidences_zero_weights_returns_zero(self):
        assert eu.combine_confidences(0.9, 0.9, 0.9, 0.9, 0.9, weights={
            "emotion": 0.0, "face": 0.0, "gaze": 0.0, "head_pose": 0.0, "phone": 0.0,
        }) == 0.0

    def test_derive_risk_flags_phone_and_multiple_person(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "phone_detected": True, "person_count": 2,
        })
        flags = eu.derive_risk_flags(engagement_input, "MEDIUM", 0.9, 0.5)
        assert engagement_levels.PHONE_USAGE in flags
        assert engagement_levels.MULTIPLE_PERSON in flags

    def test_derive_risk_flags_no_face(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "face_detected": False,
        })
        flags = eu.derive_risk_flags(engagement_input, "VERY_LOW", 0.9, 0.5)
        assert engagement_levels.NO_FACE in flags
        assert engagement_levels.UNKNOWN_FACE not in flags

    def test_derive_risk_flags_unknown_face(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "face_detected": True, "authenticated": False,
        })
        flags = eu.derive_risk_flags(engagement_input, "MEDIUM", 0.9, 0.5)
        assert engagement_levels.UNKNOWN_FACE in flags

    def test_derive_risk_flags_low_confidence(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({"student_id": "s1"})
        flags = eu.derive_risk_flags(engagement_input, "MEDIUM", 0.2, 0.5)
        assert engagement_levels.LOW_CONFIDENCE in flags

    def test_derive_risk_flags_very_low_engagement(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({"student_id": "s1"})
        flags = eu.derive_risk_flags(engagement_input, "VERY_LOW", 0.9, 0.5)
        assert engagement_levels.VERY_LOW_ENGAGEMENT in flags

    def test_generate_reasons_nonempty(self):
        engagement_input = ef.EngagementPredictionInput.from_dict({"student_id": "s1"})
        reasons = eu.generate_reasons(engagement_input, 80.0, "center", "screen", [])
        assert len(reasons) > 0
        assert all(isinstance(r, str) for r in reasons)


# ---------------------------------------------------------------------------
# engagement_predictor
# ---------------------------------------------------------------------------
class TestEngagementPredictor:
    def test_singleton_returns_same_instance(self):
        ep.reset_engagement_predictor()
        a = ep.get_engagement_predictor()
        b = ep.get_engagement_predictor()
        assert a is b

    def test_predict_rejects_wrong_type(self):
        predictor = ep.RuleBasedEngagementPredictor()
        with pytest.raises(ep.EngagementPredictionError):
            predictor.predict("not-a-valid-input")

    def test_predict_safe_never_raises_on_bad_input(self):
        predictor = ep.RuleBasedEngagementPredictor()
        result = predictor.predict_safe("not-a-valid-input")
        assert result.degraded is True
        assert isinstance(result.as_dict(), dict)

    def test_high_engagement_scenario(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "22CS001", "emotion": "happy", "emotion_confidence": 0.9,
            "looking_at_screen": True, "gaze_confidence": 0.92,
            "yaw": 2.0, "pitch": -1.0, "roll": 0.5, "head_pose_confidence": 0.95,
            "phone_detected": False, "person_count": 1,
            "authenticated": True, "authentication_confidence": 0.98, "attendance": True,
        })
        result = predictor.predict(engagement_input)
        assert result.engagement_level in ("HIGH", "EXCELLENT")
        assert result.risk_flags == []
        assert result.phone_detected is False
        assert result.multiple_person is False

    def test_phone_usage_scenario_penalizes_score(self):
        predictor = ep.RuleBasedEngagementPredictor()
        baseline_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "emotion": "happy", "looking_at_screen": True,
        })
        phone_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "emotion": "happy", "looking_at_screen": True,
            "phone_detected": True, "phone_confidence": 0.9,
        })
        baseline_result = predictor.predict(baseline_input)
        phone_result = predictor.predict(phone_input)
        assert phone_result.engagement_score < baseline_result.engagement_score
        assert engagement_levels.PHONE_USAGE in phone_result.risk_flags

    def test_multiple_person_scenario_penalizes_score(self):
        predictor = ep.RuleBasedEngagementPredictor()
        baseline_input = ef.EngagementPredictionInput.from_dict({"student_id": "s1", "person_count": 1})
        crowd_input = ef.EngagementPredictionInput.from_dict({"student_id": "s1", "person_count": 3})
        baseline_result = predictor.predict(baseline_input)
        crowd_result = predictor.predict(crowd_input)
        assert crowd_result.engagement_score < baseline_result.engagement_score
        assert engagement_levels.MULTIPLE_PERSON in crowd_result.risk_flags

    def test_looking_away_scenario_flagged(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "looking_at_screen": False, "looking_left": True,
        })
        result = predictor.predict(engagement_input)
        assert engagement_levels.LOOKING_AWAY in result.risk_flags
        assert result.gaze == "left"

    def test_head_down_scenario_flagged(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "looking_at_screen": False, "looking_down": True, "pitch": 30.0,
        })
        result = predictor.predict(engagement_input)
        assert engagement_levels.HEAD_DOWN in result.risk_flags
        assert result.head_pose == "down"

    def test_no_face_scenario_zero_score(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "face_detected": False,
        })
        result = predictor.predict(engagement_input)
        assert result.engagement_score == 0.0
        assert result.engagement_level == "VERY_LOW"
        assert engagement_levels.NO_FACE in result.risk_flags

    def test_unknown_face_scenario_flagged(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "authenticated": False,
        })
        result = predictor.predict(engagement_input)
        assert engagement_levels.UNKNOWN_FACE in result.risk_flags

    def test_low_confidence_scenario_flagged(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "emotion_confidence": 0.05, "gaze_confidence": 0.05,
            "head_pose_confidence": 0.05, "authentication_confidence": 0.05,
        })
        result = predictor.predict(engagement_input)
        assert engagement_levels.LOW_CONFIDENCE in result.risk_flags

    def test_engagement_score_always_clamped(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "phone_detected": True, "person_count": 5,
        })
        result = predictor.predict(engagement_input)
        assert 0.0 <= result.engagement_score <= 100.0

    def test_result_payload_schema(self):
        predictor = ep.RuleBasedEngagementPredictor()
        engagement_input = ef.EngagementPredictionInput.from_dict({"student_id": "s1"})
        result = predictor.predict(engagement_input)
        payload = result.as_dict()
        for key in (
            "student_id", "engagement_score", "engagement_level", "overall_confidence",
            "emotion", "head_pose", "gaze", "multiple_person", "phone_detected",
            "risk_flags", "reasons", "degraded", "error_message", "processing_time_ms",
        ):
            assert key in payload

    def test_attendance_and_authentication_bonuses_increase_score(self):
        predictor = ep.RuleBasedEngagementPredictor()
        no_bonus_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "authenticated": False, "attendance": False,
        })
        with_bonus_input = ef.EngagementPredictionInput.from_dict({
            "student_id": "s1", "authenticated": True, "attendance": True,
        })
        no_bonus_result = predictor.predict(no_bonus_input)
        with_bonus_result = predictor.predict(with_bonus_input)
        assert with_bonus_result.engagement_score > no_bonus_result.engagement_score


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
class TestEngagementPredictionConfig:
    def test_config_file_exists(self):
        assert (PROJECT_ROOT / "configs" / "engagement_prediction.yaml").exists()

    def test_config_loads_and_has_expected_sections(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "engagement_prediction.yaml")
        for section in ("weights", "penalties", "bonuses", "thresholds", "engagement_ranges", "confidence_weights"):
            assert section in config

    def test_config_weights_match_specification(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "engagement_prediction.yaml")
        assert config["weights"]["emotion"] == 0.25
        assert config["weights"]["head_pose"] == 0.20
        assert config["weights"]["gaze"] == 0.25

    def test_config_penalties_match_specification(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "engagement_prediction.yaml")
        assert config["penalties"]["phone_usage"] == 20.0
        assert config["penalties"]["multiple_person"] == 15.0

    def test_config_bonuses_match_specification(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "engagement_prediction.yaml")
        assert config["bonuses"]["face_authenticated"] == 10.0
        assert config["bonuses"]["attendance"] == 5.0

    def test_config_is_valid_yaml(self):
        raw = (PROJECT_ROOT / "configs" / "engagement_prediction.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)
        assert isinstance(parsed, dict)

    def test_config_engagement_ranges_are_valid(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "engagement_prediction.yaml")
        ranges = {level: tuple(bounds) for level, bounds in config["engagement_ranges"].items()}
        engagement_levels.validate_level_ranges(ranges)


# ---------------------------------------------------------------------------
# Router / main.py registration
# ---------------------------------------------------------------------------
class TestEngagementPredictionRouter:
    def test_router_module_imports(self):
        import importlib
        module = importlib.import_module("backend.app.routers.engagement_prediction")
        importlib.reload(module)
        assert hasattr(module, "router")

    def test_router_exposes_expected_routes(self):
        import importlib
        module = importlib.import_module("backend.app.routers.engagement_prediction")
        importlib.reload(module)
        route_paths = sorted(r.path for r in module.router.routes)
        assert "/engagement/predict" in route_paths
        assert "/engagement/config" in route_paths
        assert "/engagement/health" in route_paths

    def test_main_py_registers_engagement_prediction_router(self):
        main_source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        assert "from backend.app.routers import engagement_prediction" in main_source
        assert "app.include_router(engagement_prediction.router)" in main_source

    def test_predict_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.post("/engagement/predict", json={
            "student_id": "22CS001", "emotion": "happy", "emotion_confidence": 0.9,
            "looking_at_screen": True, "gaze_confidence": 0.9,
            "yaw": 0.0, "pitch": 0.0, "roll": 0.0, "head_pose_confidence": 0.9,
            "phone_detected": False, "person_count": 1,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["student_id"] == "22CS001"
        assert 0.0 <= body["engagement_score"] <= 100.0

    def test_predict_endpoint_missing_student_id_rejected(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.post("/engagement/predict", json={"emotion": "happy"})
        assert resp.status_code == 422

    def test_config_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/engagement/config")
        assert resp.status_code == 200
        assert "weights" in resp.json()

    def test_health_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/engagement/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"