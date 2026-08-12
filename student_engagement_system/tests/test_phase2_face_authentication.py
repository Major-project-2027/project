"""
Phase 2 Face Authentication & Attendance tests.

Run with:  pytest tests/test_phase2_face_authentication.py -v
"""
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FACE_AUTH_DIR = PROJECT_ROOT / "models" / "face_authentication"


# --- Module files exist -----------------------------------------------

REQUIRED_MODULES = [
    "webcam.py", "face_detector.py", "preprocessing.py", "face_embedder.py",
    "face_registration.py", "face_matcher.py", "attendance_manager.py",
    "attendance_database.py",
]


@pytest.mark.parametrize("module_file", REQUIRED_MODULES)
def test_module_file_exists(module_file):
    assert (FACE_AUTH_DIR / module_file).exists(), f"Missing module: {module_file}"


# --- Webcam -------------------------------------------------------------

def test_webcam_verify_camera_does_not_raise():
    from ml_models.face_authentication.webcam import verify_camera
    ok, message = verify_camera(device_index=999)  # deliberately invalid index
    assert ok is False
    assert isinstance(message, str)


# --- Face detection -------------------------------------------------------

def test_face_detector_blank_frame_returns_empty_list():
    from ml_models.face_authentication.face_detector import FaceDetector
    detector = FaceDetector(min_confidence=0.6)
    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    assert detector.detect(blank) == []
    detector.close()


# --- Preprocessing --------------------------------------------------------

def test_preprocess_face_output_shape_and_range():
    from ml_models.face_authentication.preprocessing import preprocess_face
    rng = np.random.default_rng(0)
    crop = rng.integers(0, 255, size=(100, 90, 3), dtype=np.uint8)
    processed = preprocess_face(crop, target_size=(224, 224))
    assert processed.shape == (224, 224, 3)
    assert processed.dtype == np.float32
    assert 0.0 <= processed.min() and processed.max() <= 1.0


def test_check_quality_rejects_dark_image():
    from ml_models.face_authentication.preprocessing import check_quality
    dark = np.full((150, 130, 3), 5, dtype=np.uint8)
    report = check_quality(dark)
    assert report.passed is False
    assert any("lighting" in r for r in report.reasons)


# --- Embedding (contract-level; DeepFace optional) -------------------------

def test_average_embedding_is_unit_norm():
    from ml_models.face_authentication.face_embedder import average_embedding, EMBEDDING_DIM
    embeddings = np.random.default_rng(1).normal(size=(5, EMBEDDING_DIM)).astype(np.float32)
    avg = average_embedding(embeddings)
    assert avg.shape == (EMBEDDING_DIM,)
    assert abs(np.linalg.norm(avg) - 1.0) < 1e-4


# --- Registration ---------------------------------------------------------

def test_register_from_images_rejects_empty_list():
    from ml_models.face_authentication.face_registration import FaceRegistrar, RegistrationError
    registrar = FaceRegistrar(registered_faces_dir=FACE_AUTH_DIR / "registered_faces")
    with pytest.raises(RegistrationError):
        registrar.register_from_images("x", "x", "x", "x", "x", face_crops=[])


# --- Matching ---------------------------------------------------------

def test_cosine_similarity_identical_and_orthogonal_vectors():
    from ml_models.face_authentication.face_matcher import cosine_similarity
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([1.0, 0.0, 0.0])
    c = np.array([0.0, 1.0, 0.0])
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-9
    assert abs(cosine_similarity(a, c) - 0.0) < 1e-9


def test_matcher_reports_unknown_for_empty_gallery(tmp_path):
    from ml_models.face_authentication.face_matcher import FaceMatcher, UNKNOWN_LABEL
    empty_gallery_dir = tmp_path / "empty_registered_faces"
    empty_gallery_dir.mkdir()
    matcher = FaceMatcher(registered_faces_dir=empty_gallery_dir, similarity_threshold=0.68)
    result = matcher.match(np.random.default_rng(2).normal(size=512).astype(np.float32))
    assert result.matched is False
    assert result.student_id == UNKNOWN_LABEL


# --- Attendance ---------------------------------------------------------

def test_attendance_duplicate_prevention(tmp_path):
    from ml_models.face_authentication.attendance_manager import AttendanceManager, DuplicateAttendanceError
    manager = AttendanceManager(csv_path=tmp_path / "attendance.csv")
    manager.mark_attendance(student_id="S1", name="Student One", confidence=0.9)
    with pytest.raises(DuplicateAttendanceError):
        manager.mark_attendance(student_id="S1", name="Student One", confidence=0.85)


def test_attendance_allow_duplicate_bypasses_check(tmp_path):
    from ml_models.face_authentication.attendance_manager import AttendanceManager
    manager = AttendanceManager(csv_path=tmp_path / "attendance.csv")
    manager.mark_attendance(student_id="S2", name="Student Two", confidence=0.9)
    manager.mark_attendance(student_id="S2", name="Student Two", confidence=0.9, allow_duplicate=True)
    assert len(manager.store.read_all()) == 2


# --- Configuration ------------------------------------------------------

def test_face_authentication_config_exists_and_parses():
    import yaml
    config_path = PROJECT_ROOT / "configs" / "face_authentication.yaml"
    assert config_path.exists()
    with open(config_path) as f:
        config = yaml.safe_load(f)
    assert config["similarity_threshold"] == 0.68
    assert config["registration"]["num_images"] == 10


# --- FastAPI integration ---------------------------------------------------

def test_face_auth_router_registered_in_main():
    main_py = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text()
    assert "face_authentication" in main_py


def test_face_auth_endpoints_respond():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/face-auth/students")
    assert resp.status_code == 200
    resp2 = client.get("/face-auth/attendance")
    assert resp2.status_code == 200
