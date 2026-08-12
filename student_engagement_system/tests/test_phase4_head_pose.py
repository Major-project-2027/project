"""
Phase 4 Head Pose Estimation and Eye Gaze Estimation tests.

Run with:  pytest tests/test_phase4_head_pose.py -v
"""
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GAZE_HEAD_POSE_DIR = PROJECT_ROOT / "models" / "gaze_head_pose"


# --- Module files exist -----------------------------------------------

REQUIRED_MODULES = [
    "head_pose.py", "gaze_estimator.py", "gaze_utils.py", "head_pose_utils.py",
]


@pytest.mark.parametrize("module_file", REQUIRED_MODULES)
def test_module_file_exists(module_file):
    assert (GAZE_HEAD_POSE_DIR / module_file).exists(), f"Missing module: {module_file}"


# --- head_pose_utils.py -----------------------------------------------

def test_build_camera_matrix_shape_and_values():
    from ml_models.gaze_head_pose.head_pose_utils import build_camera_matrix
    matrix = build_camera_matrix(640, 480)
    assert matrix.shape == (3, 3)
    assert matrix[0, 2] == 320.0
    assert matrix[1, 2] == 240.0


def test_build_camera_matrix_rejects_non_positive_dimensions():
    from ml_models.gaze_head_pose.head_pose_utils import build_camera_matrix
    with pytest.raises(ValueError):
        build_camera_matrix(0, 480)


def test_rotation_matrix_to_euler_angles_identity_is_zero():
    from ml_models.gaze_head_pose.head_pose_utils import rotation_matrix_to_euler_angles
    yaw, pitch, roll = rotation_matrix_to_euler_angles(np.eye(3))
    assert abs(yaw) < 1e-6
    assert abs(pitch) < 1e-6
    assert abs(roll) < 1e-6


def test_rotation_matrix_to_euler_angles_rejects_bad_shape():
    from ml_models.gaze_head_pose.head_pose_utils import rotation_matrix_to_euler_angles
    with pytest.raises(ValueError):
        rotation_matrix_to_euler_angles(np.eye(4))


def test_rotation_matrix_to_euler_angles_recovers_known_yaw():
    import cv2
    from ml_models.gaze_head_pose.head_pose_utils import rotation_matrix_to_euler_angles
    rvec = np.array([0.0, np.radians(20.0), 0.0])
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    yaw, pitch, roll = rotation_matrix_to_euler_angles(rotation_matrix)
    assert abs(yaw - 20.0) < 1e-3
    assert abs(pitch) < 1e-3


@pytest.mark.parametrize(
    "yaw, pitch, expected",
    [
        (0.0, 0.0, "Forward"),
        (20.0, 0.0, "Right"),
        (-20.0, 0.0, "Left"),
        (0.0, 20.0, "Down"),
        (0.0, -20.0, "Up"),
        (2.0, 3.0, "Forward"),
    ],
)
def test_classify_head_direction(yaw, pitch, expected):
    from ml_models.gaze_head_pose.head_pose_utils import classify_head_direction
    assert classify_head_direction(yaw, pitch) == expected


def test_classify_head_direction_rejects_non_positive_thresholds():
    from ml_models.gaze_head_pose.head_pose_utils import classify_head_direction
    with pytest.raises(ValueError):
        classify_head_direction(0.0, 0.0, yaw_threshold=0.0)


def test_head_pose_smoother_converges_toward_repeated_input():
    from ml_models.gaze_head_pose.head_pose_utils import HeadPoseSmoother, PoseAngles
    smoother = HeadPoseSmoother(alpha=0.5)
    first = smoother.update(PoseAngles(10.0, 0.0, 0.0))
    second = smoother.update(PoseAngles(10.0, 0.0, 0.0))
    assert second.yaw >= first.yaw


def test_head_pose_smoother_stable_under_identical_repeated_input():
    # A stable (unchanging) output across repeated identical frames is
    # correct EMA behaviour, not a failure -- once converged, the smoothed
    # value should stop changing further.
    from ml_models.gaze_head_pose.head_pose_utils import HeadPoseSmoother, PoseAngles
    smoother = HeadPoseSmoother(alpha=0.5)
    for _ in range(20):
        result = smoother.update(PoseAngles(12.5, -3.0, 1.0))
    assert abs(result.yaw - 12.5) < 1e-6
    assert abs(result.pitch - (-3.0)) < 1e-6


def test_head_pose_smoother_reset_clears_state():
    from ml_models.gaze_head_pose.head_pose_utils import HeadPoseSmoother, PoseAngles
    smoother = HeadPoseSmoother(alpha=0.5)
    smoother.update(PoseAngles(30.0, 30.0, 30.0))
    smoother.reset()
    fresh = smoother.update(PoseAngles(5.0, 5.0, 5.0))
    assert fresh.yaw == 5.0


def test_head_pose_smoother_rejects_invalid_alpha():
    from ml_models.gaze_head_pose.head_pose_utils import HeadPoseSmoother
    with pytest.raises(ValueError):
        HeadPoseSmoother(alpha=0.0)


def test_compute_reprojection_confidence_bounds():
    from ml_models.gaze_head_pose.head_pose_utils import compute_reprojection_confidence
    assert compute_reprojection_confidence(0.0) == 1.0
    assert compute_reprojection_confidence(40.0) == 0.0
    assert compute_reprojection_confidence(1000.0) == 0.0


def test_compute_reprojection_confidence_rejects_negative_error():
    from ml_models.gaze_head_pose.head_pose_utils import compute_reprojection_confidence
    with pytest.raises(ValueError):
        compute_reprojection_confidence(-1.0)


# --- gaze_utils.py ------------------------------------------------------

def test_eye_aspect_ratio_open_eye_greater_than_closed_eye():
    from ml_models.gaze_head_pose.gaze_utils import eye_aspect_ratio
    open_eye = np.array([[0, 5], [2, 0], [4, 0], [6, 5], [4, 10], [2, 10]], dtype=float)
    closed_eye = np.array([[0, 5], [2, 4.5], [4, 4.5], [6, 5], [4, 5.5], [2, 5.5]], dtype=float)
    assert eye_aspect_ratio(open_eye) > eye_aspect_ratio(closed_eye)


def test_eye_aspect_ratio_rejects_wrong_shape():
    from ml_models.gaze_head_pose.gaze_utils import eye_aspect_ratio
    with pytest.raises(ValueError):
        eye_aspect_ratio(np.zeros((5, 2)))


def test_horizontal_gaze_ratio_midpoint_is_half():
    from ml_models.gaze_head_pose.gaze_utils import horizontal_gaze_ratio
    assert abs(horizontal_gaze_ratio(3.0, 0.0, 6.0) - 0.5) < 1e-9


def test_horizontal_gaze_ratio_rejects_degenerate_corners():
    from ml_models.gaze_head_pose.gaze_utils import horizontal_gaze_ratio
    with pytest.raises(ValueError):
        horizontal_gaze_ratio(3.0, 4.0, 4.0)


def test_vertical_gaze_ratio_clamped_to_unit_range():
    from ml_models.gaze_head_pose.gaze_utils import vertical_gaze_ratio
    assert vertical_gaze_ratio(-100.0, 0.0, 10.0) == 0.0
    assert vertical_gaze_ratio(100.0, 0.0, 10.0) == 1.0


@pytest.mark.parametrize(
    "h_ratio, v_ratio, expected",
    [
        (0.5, 0.5, "Center"),
        (0.1, 0.5, "Left"),
        (0.9, 0.5, "Right"),
        (0.5, 0.1, "Up"),
        (0.5, 0.9, "Down"),
    ],
)
def test_classify_gaze_direction(h_ratio, v_ratio, expected):
    from ml_models.gaze_head_pose.gaze_utils import classify_gaze_direction
    assert classify_gaze_direction(h_ratio, v_ratio) == expected


def test_classify_gaze_direction_rejects_out_of_range_ratio():
    from ml_models.gaze_head_pose.gaze_utils import classify_gaze_direction
    with pytest.raises(ValueError):
        classify_gaze_direction(1.5, 0.5)


def test_gaze_ratio_smoother_converges_toward_repeated_input():
    from ml_models.gaze_head_pose.gaze_utils import GazeRatioSmoother, GazeRatios
    smoother = GazeRatioSmoother(alpha=0.5)
    first = smoother.update(GazeRatios(0.8, 0.5))
    second = smoother.update(GazeRatios(0.8, 0.5))
    assert second.horizontal >= first.horizontal


def test_gaze_direction_smoother_majority_vote_stable_under_repeats():
    # Repeated identical labels producing the same, stable output is the
    # correct majority-vote behaviour -- not a bug to be flagged.
    from ml_models.gaze_head_pose.gaze_utils import GazeDirectionSmoother
    smoother = GazeDirectionSmoother(window_size=3)
    results = [smoother.update("Left") for _ in range(5)]
    assert all(label == "Left" for label in results)


def test_gaze_direction_smoother_resists_single_frame_flicker():
    from ml_models.gaze_head_pose.gaze_utils import GazeDirectionSmoother
    smoother = GazeDirectionSmoother(window_size=3)
    smoother.update("Center")
    smoother.update("Center")
    result = smoother.update("Left")  # one-off flicker in a window of mostly "Center"
    assert result == "Center"


def test_gaze_direction_smoother_rejects_invalid_direction():
    from ml_models.gaze_head_pose.gaze_utils import GazeDirectionSmoother, InvalidGazeDirectionError
    smoother = GazeDirectionSmoother(window_size=3)
    with pytest.raises(InvalidGazeDirectionError):
        smoother.update("Sideways")


def test_gaze_direction_smoother_reset_clears_window():
    from ml_models.gaze_head_pose.gaze_utils import GazeDirectionSmoother
    smoother = GazeDirectionSmoother(window_size=3)
    smoother.update("Left")
    smoother.update("Left")
    smoother.reset()
    result = smoother.update("Right")
    assert result == "Right"


def test_validate_gaze_direction_accepts_supported_labels():
    from ml_models.gaze_head_pose.gaze_utils import validate_gaze_direction, GAZE_DIRECTIONS
    for label in GAZE_DIRECTIONS:
        assert validate_gaze_direction(label) == label


# --- head_pose.py (contract-level; MediaPipe optional) ---------------

def test_head_pose_estimator_rejects_empty_frame_when_available():
    from ml_models.gaze_head_pose.head_pose import HeadPoseEstimator, HeadPoseEstimationError
    try:
        estimator = HeadPoseEstimator()
    except HeadPoseEstimationError:
        pytest.skip("MediaPipe Face Mesh (solutions API) not available in this environment.")
    with pytest.raises(HeadPoseEstimationError):
        estimator.estimate(np.zeros((0, 0, 3), dtype=np.uint8))


def test_head_pose_estimator_estimate_safe_never_raises():
    from ml_models.gaze_head_pose.head_pose import HeadPoseEstimator, HeadPoseEstimationError
    try:
        estimator = HeadPoseEstimator()
    except HeadPoseEstimationError:
        pytest.skip("MediaPipe Face Mesh (solutions API) not available in this environment.")
    result = estimator.estimate_safe(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result is None


def test_head_pose_estimator_raises_typed_error_when_backend_missing():
    # This test always runs (no skip) -- it verifies the *contract* that
    # HeadPoseEstimator either constructs successfully or raises the typed
    # HeadPoseEstimationError, never an uncaught/generic exception.
    from ml_models.gaze_head_pose.head_pose import HeadPoseEstimator, HeadPoseEstimationError
    try:
        HeadPoseEstimator()
    except HeadPoseEstimationError as exc:
        assert "MediaPipe" in str(exc)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Expected HeadPoseEstimationError or success, got {type(exc).__name__}: {exc}")


# --- gaze_estimator.py (contract-level; MediaPipe optional) ----------

def test_gaze_estimator_rejects_empty_frame_when_available():
    from ml_models.gaze_head_pose.gaze_estimator import GazeEstimator, GazeEstimationError
    try:
        estimator = GazeEstimator()
    except GazeEstimationError:
        pytest.skip("MediaPipe Face Mesh (solutions API) not available in this environment.")
    with pytest.raises(GazeEstimationError):
        estimator.estimate(np.zeros((0, 0, 3), dtype=np.uint8))


def test_gaze_estimator_estimate_safe_never_raises():
    from ml_models.gaze_head_pose.gaze_estimator import GazeEstimator, GazeEstimationError
    try:
        estimator = GazeEstimator()
    except GazeEstimationError:
        pytest.skip("MediaPipe Face Mesh (solutions API) not available in this environment.")
    result = estimator.estimate_safe(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result is None


def test_gaze_estimator_raises_typed_error_when_backend_missing():
    from ml_models.gaze_head_pose.gaze_estimator import GazeEstimator, GazeEstimationError
    try:
        GazeEstimator()
    except GazeEstimationError as exc:
        assert "MediaPipe" in str(exc)
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Expected GazeEstimationError or success, got {type(exc).__name__}: {exc}")


# --- Configuration ------------------------------------------------------

def test_head_pose_config_exists_and_parses():
    import yaml
    config_path = PROJECT_ROOT / "configs" / "head_pose.yaml"
    assert config_path.exists()
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert config["head_pose"]["yaw_threshold"] == 15.0
    assert config["gaze"]["ear_blink_threshold"] == 0.21
    assert set(config["gaze"]["directions"]) == {"Left", "Right", "Up", "Down", "Center"}


# --- FastAPI integration ---------------------------------------------------

def test_head_pose_router_registered_in_main():
    main_py = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "head_pose" in main_py


def test_head_pose_directions_endpoint_responds():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/head-pose/directions")
    assert resp.status_code == 200
    assert set(resp.json()) == {"Forward", "Left", "Right", "Up", "Down"}


def test_gaze_directions_endpoint_responds():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/gaze/directions")
    assert resp.status_code == 200
    assert set(resp.json()) == {"Left", "Right", "Up", "Down", "Center"}


def test_head_pose_estimate_endpoint_rejects_bad_input():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/head-pose/estimate", json={"frame_b64": "not-valid-base64!!!"})
    assert resp.status_code in (400, 422, 503)


def test_gaze_estimate_endpoint_rejects_bad_input():
    from backend.app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/gaze/estimate", json={"frame_b64": "not-valid-base64!!!"})
    assert resp.status_code in (400, 422, 503)
