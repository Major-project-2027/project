"""
Phase 3 Emotion Recognition tests.

Run with:  pytest tests/test_phase3_emotion.py -v
"""
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMOTION_DIR = PROJECT_ROOT / "models" / "emotion_detection"


# --- Module files exist -----------------------------------------------

REQUIRED_MODULES = [
    "emotion_labels.py", "emotion_preprocessing.py", "emotion_utils.py", "emotion_detector.py",
]


@pytest.mark.parametrize("module_file", REQUIRED_MODULES)
def test_module_file_exists(module_file):
    assert (EMOTION_DIR / module_file).exists(), f"Missing module: {module_file}"


# --- Emotion labels -------------------------------------------------------

def test_emotion_labels_has_seven_classes():
    from ml_models.emotion_detection.emotion_labels import EMOTION_LABELS
    assert len(EMOTION_LABELS) == 7
    assert set(EMOTION_LABELS) == {
        "angry", "disgust", "fear", "happy", "sad", "surprise", "neutral",
    }


def test_validate_label_rejects_unsupported_label():
    from ml_models.emotion_detection.emotion_labels import validate_label, InvalidEmotionLabelError
    with pytest.raises(InvalidEmotionLabelError):
        validate_label("bored")


def test_get_polarity_matches_expected_mapping():
    from ml_models.emotion_detection.emotion_labels import get_polarity
    assert get_polarity("happy") == "positive"
    assert get_polarity("angry") == "negative"
    assert get_polarity("neutral") == "neutral"


# --- Preprocessing --------------------------------------------------------

def test_preprocess_for_emotion_output_shape_and_range():
    from ml_models.emotion_detection.emotion_preprocessing import preprocess_for_emotion
    rng = np.random.default_rng(0)
    crop = rng.integers(90, 200, size=(100, 90, 3), dtype=np.uint8)
    processed = preprocess_for_emotion(crop, target_size=(48, 48), grayscale=True)
    assert processed.shape == (48, 48)
    assert processed.dtype == np.float32
    assert 0.0 <= processed.min() and processed.max() <= 1.0


def test_preprocess_for_emotion_rejects_dark_crop():
    from ml_models.emotion_detection.emotion_preprocessing import (
        preprocess_for_emotion, EmotionPreprocessingError,
    )
    dark = np.full((150, 130, 3), 5, dtype=np.uint8)
    with pytest.raises(EmotionPreprocessingError):
        preprocess_for_emotion(dark, enforce_quality=True)


def test_preprocess_for_emotion_rejects_empty_crop():
    from ml_models.emotion_detection.emotion_preprocessing import (
        preprocess_for_emotion, EmotionPreprocessingError,
    )
    with pytest.raises(EmotionPreprocessingError):
        preprocess_for_emotion(np.zeros((0, 0, 3), dtype=np.uint8))


def test_to_model_input_adds_batch_dimension():
    from ml_models.emotion_detection.emotion_preprocessing import preprocess_for_emotion, to_model_input
    rng = np.random.default_rng(1)
    crop = rng.integers(90, 200, size=(100, 90, 3), dtype=np.uint8)
    processed = preprocess_for_emotion(crop, target_size=(48, 48), grayscale=True)
    model_input = to_model_input(processed)
    assert model_input.shape == (1, 48, 48, 1)


# --- Utils ---------------------------------------------------------

def test_normalize_scores_sums_to_one():
    from ml_models.emotion_detection.emotion_utils import normalize_scores
    normalized = normalize_scores({"happy": 70.0, "neutral": 20.0, "sad": 10.0})
    assert abs(sum(normalized.values()) - 1.0) < 1e-9


def test_normalize_scores_rejects_empty_dict():
    from ml_models.emotion_detection.emotion_utils import normalize_scores
    with pytest.raises(ValueError):
        normalize_scores({})


def test_top_emotion_selects_highest_score():
    from ml_models.emotion_detection.emotion_utils import top_emotion
    label, confidence = top_emotion({"happy": 0.7, "sad": 0.3})
    assert label == "happy"
    assert confidence == 0.7


def test_emotion_smoother_converges_toward_repeated_input():
    from ml_models.emotion_detection.emotion_utils import EmotionSmoother
    smoother = EmotionSmoother(alpha=0.5)
    first = smoother.update({"happy": 1.0})
    second = smoother.update({"happy": 1.0})
    assert second["happy"] >= first["happy"]


def test_emotion_smoother_rejects_invalid_alpha():
    from ml_models.emotion_detection.emotion_utils import EmotionSmoother
    with pytest.raises(ValueError):
        EmotionSmoother(alpha=0.0)


def test_summarize_session_reports_dominant_emotion():
    from ml_models.emotion_detection.emotion_utils import summarize_session
    summary = summarize_session(["happy", "happy", "sad"])
    assert summary.dominant_emotion == "happy"
    assert summary.num_frames == 3


def test_summarize_session_rejects_empty_list():
    from ml_models.emotion_detection.emotion_utils import summarize_session
    with pytest.raises(ValueError):
        summarize_session([])


# --- Detector (contract-level; DeepFace optional) -------------------------

def test_emotion_detector_rejects_empty_image_when_available():
    from ml_models.emotion_detection.emotion_detector import EmotionDetector, EmotionAnalysisError
    try:
        detector = EmotionDetector()
    except EmotionAnalysisError:
        pytest.skip("DeepFace/TensorFlow not installed in this environment.")
    with pytest.raises(EmotionAnalysisError):
        detector.analyze(np.zeros((0, 0, 3), dtype=np.uint8))


def test_emotion_detector_analyze_safe_never_raises():
    from ml_models.emotion_detection.emotion_detector import EmotionDetector, EmotionAnalysisError
    try:
        detector = EmotionDetector()
    except EmotionAnalysisError:
        pytest.skip("DeepFace/TensorFlow not installed in this environment.")
    result = detector.analyze_safe(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result is None


# --- Configuration ------------------------------------------------------

def test_emotion_detection_config_exists_and_parses():
    import yaml
    config_path = PROJECT_ROOT / "configs" / "emotion_detection.yaml"
    assert config_path.exists()
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert config["model"] == "Emotion"
    assert len(config["labels"]) == 7
    assert config["confidence_threshold"] == 0.4


# --- FastAPI integration ---------------------------------------------------

def test_emotion_router_registered_in_main():
    main_py = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text()
    assert "emotion" in main_py


def test_emotion_labels_endpoint_responds():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/emotion/labels")
    assert resp.status_code == 200
    assert len(resp.json()) == 7


def test_emotion_predict_endpoint_rejects_bad_input():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/emotion/predict", json={"face_crop_b64": "not-valid-base64!!!"})
    assert resp.status_code in (400, 422)
