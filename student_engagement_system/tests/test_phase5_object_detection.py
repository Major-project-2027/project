"""
Phase 5 Object Detection and Classroom Monitoring -- pytest suite.

Covers: object_labels, detection_utils (filtering, IoU, person counting,
phone detection, temporal smoothing), object_detector (singleton, lazy
loading, validation, graceful degradation, multi-person / phone-detection
logic via a stubbed inference seam), configs/object_detection.yaml, the
FastAPI router, and backend/app/main.py registration.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml


def _detect_project_root(marker_dirs=("utils", "configs", "backend", "models")) -> Path:
    candidates = [Path.cwd() / "student_engagement_system", Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        if candidate.is_dir() and all((candidate / m).is_dir() for m in marker_dirs):
            return candidate.resolve()
    raise FileNotFoundError("Could not locate the project root for Phase 5 tests.")


PROJECT_ROOT = _detect_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.object_detection import object_labels  # noqa: E402
from models.object_detection import detection_utils  # noqa: E402
from models.object_detection import object_detector  # noqa: E402
from utils.common import load_yaml_config  # noqa: E402


# ---------------------------------------------------------------------------
# object_labels
# ---------------------------------------------------------------------------
class TestObjectLabels:
    def test_required_classes(self):
        assert object_labels.REQUIRED_CLASSES == {"person", "cell phone"}

    def test_optional_classes(self):
        assert object_labels.OPTIONAL_CLASSES == {
            "laptop", "book", "mouse", "keyboard", "monitor",
        }

    def test_all_target_classes_is_union(self):
        assert object_labels.ALL_TARGET_CLASSES == (
            object_labels.REQUIRED_CLASSES | object_labels.OPTIONAL_CLASSES
        )

    def test_is_target_class(self):
        assert object_labels.is_target_class("person") is True
        assert object_labels.is_target_class("cell phone") is True
        assert object_labels.is_target_class("dog") is False

    def test_class_id_for_name_known(self):
        assert object_labels.class_id_for_name("person") == 0
        assert object_labels.class_id_for_name("cell phone") == 67

    def test_class_id_for_name_unknown_raises(self):
        with pytest.raises(KeyError):
            object_labels.class_id_for_name("dog")

    def test_class_name_for_id_known(self):
        assert object_labels.class_name_for_id(0) == "person"
        assert object_labels.class_name_for_id(67) == "cell phone"

    def test_class_name_for_id_unknown_raises(self):
        with pytest.raises(KeyError):
            object_labels.class_name_for_id(999)


# ---------------------------------------------------------------------------
# detection_utils
# ---------------------------------------------------------------------------
class TestDetectionUtils:
    def test_iou_identical_boxes(self):
        assert abs(detection_utils.compute_iou((0, 0, 10, 10), (0, 0, 10, 10)) - 1.0) < 1e-6

    def test_iou_disjoint_boxes(self):
        assert detection_utils.compute_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0

    def test_iou_partial_overlap(self):
        iou = detection_utils.compute_iou((0, 0, 10, 10), (5, 5, 15, 15))
        assert 0.0 < iou < 1.0

    def test_filter_by_confidence(self):
        dets = [
            detection_utils.Detection("person", 0.95, (0, 0, 10, 10)),
            detection_utils.Detection("person", 0.40, (10, 10, 20, 20)),
        ]
        filtered = detection_utils.filter_by_confidence(dets, confidence_threshold=0.60)
        assert len(filtered) == 1
        assert filtered[0].confidence == 0.95

    def test_filter_by_target_classes(self):
        dets = [
            detection_utils.Detection("person", 0.9, (0, 0, 1, 1)),
            detection_utils.Detection("cell phone", 0.9, (0, 0, 1, 1)),
        ]
        filtered = detection_utils.filter_by_target_classes(dets, {"cell phone"})
        assert len(filtered) == 1
        assert filtered[0].class_name == "cell phone"

    def test_count_persons(self):
        dets = [
            detection_utils.Detection("person", 0.9, (0, 0, 1, 1)),
            detection_utils.Detection("person", 0.9, (0, 0, 1, 1)),
            detection_utils.Detection("cell phone", 0.9, (0, 0, 1, 1)),
        ]
        assert detection_utils.count_persons(dets) == 2
        assert detection_utils.count_persons([]) == 0

    def test_find_best_phone_detection_picks_highest_confidence(self):
        dets = [
            detection_utils.Detection("cell phone", 0.70, (0, 0, 1, 1)),
            detection_utils.Detection("cell phone", 0.93, (0, 0, 1, 1)),
        ]
        best = detection_utils.find_best_phone_detection(dets)
        assert best is not None
        assert best.confidence == 0.93

    def test_find_best_phone_detection_none_when_absent(self):
        dets = [detection_utils.Detection("person", 0.9, (0, 0, 1, 1))]
        assert detection_utils.find_best_phone_detection(dets) is None

    def test_detection_as_dict_shape(self):
        det = detection_utils.Detection("person", 0.95, (1.0, 2.0, 3.0, 4.0))
        as_dict = det.as_dict()
        assert as_dict == {"class": "person", "confidence": 0.95, "bbox": [1.0, 2.0, 3.0, 4.0]}

    def test_temporal_smoother_suppresses_single_noisy_frame(self):
        smoother = detection_utils.TemporalSmoother(window_size=5, min_true_ratio=0.6)
        results = [smoother.update(v) for v in [True, False, False, False, False]]
        assert results[-1] is False

    def test_temporal_smoother_reacts_to_sustained_signal(self):
        smoother = detection_utils.TemporalSmoother(window_size=5, min_true_ratio=0.6)
        results = [smoother.update(True) for _ in range(5)]
        assert results[-1] is True

    def test_temporal_smoother_reset(self):
        smoother = detection_utils.TemporalSmoother(window_size=3, min_true_ratio=0.6)
        for _ in range(3):
            smoother.update(True)
        smoother.reset()
        assert smoother.history == []

    def test_temporal_smoother_invalid_window_size(self):
        with pytest.raises(ValueError):
            detection_utils.TemporalSmoother(window_size=0)

    def test_temporal_smoother_invalid_ratio(self):
        with pytest.raises(ValueError):
            detection_utils.TemporalSmoother(window_size=5, min_true_ratio=0.0)


# ---------------------------------------------------------------------------
# object_detector
# ---------------------------------------------------------------------------
class TestObjectDetector:
    def test_singleton_returns_same_instance(self):
        object_detector.reset_object_detector()
        a = object_detector.get_object_detector()
        b = object_detector.get_object_detector()
        assert a is b

    def test_construction_does_not_load_model(self):
        detector = object_detector.ObjectDetector()
        assert detector._model is None

    def test_detect_rejects_none_frame(self):
        detector = object_detector.ObjectDetector()
        with pytest.raises(object_detector.InvalidFrameError):
            detector.detect(None)

    def test_detect_rejects_too_small_frame(self):
        detector = object_detector.ObjectDetector()
        with pytest.raises(object_detector.InvalidFrameError):
            detector.detect(np.zeros((5, 5, 3), dtype=np.uint8))

    def test_detect_rejects_non_ndarray_frame(self):
        detector = object_detector.ObjectDetector()
        with pytest.raises(object_detector.InvalidFrameError):
            detector.detect("not-an-array")

    def test_detect_safe_never_raises(self):
        detector = object_detector.ObjectDetector()
        result = detector.detect_safe(np.zeros((480, 640, 3), dtype=np.uint8))
        assert isinstance(result, object_detector.ObjectDetectionResult)
        assert isinstance(result.as_dict(), dict)

    def _stubbed_detector(self, detections):
        detector = object_detector.ObjectDetector()
        detector._run_inference = lambda frame: detections
        detector._person_smoother = detection_utils.TemporalSmoother(window_size=1, min_true_ratio=1.0)
        detector._phone_smoother = detection_utils.TemporalSmoother(window_size=1, min_true_ratio=1.0)
        return detector

    def test_multiple_person_true_when_two_or_more(self):
        detector = self._stubbed_detector([
            detection_utils.Detection("person", 0.98, (0, 0, 10, 10)),
            detection_utils.Detection("person", 0.96, (20, 0, 30, 10)),
        ])
        result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.person_count == 2
        assert result.multiple_person is True

    def test_multiple_person_false_when_single_student(self):
        detector = self._stubbed_detector([
            detection_utils.Detection("person", 0.98, (0, 0, 10, 10)),
        ])
        result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.person_count == 1
        assert result.multiple_person is False

    def test_phone_detected_true_and_confidence_reported(self):
        detector = self._stubbed_detector([
            detection_utils.Detection("cell phone", 0.93, (30, 30, 40, 40)),
        ])
        result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.phone_detected is True
        assert abs(result.phone_confidence - 0.93) < 1e-6

    def test_phone_detected_false_when_absent(self):
        detector = self._stubbed_detector([
            detection_utils.Detection("person", 0.98, (0, 0, 10, 10)),
        ])
        result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.phone_detected is False
        assert result.phone_confidence == 0.0

    def test_confidence_threshold_filters_low_confidence_detections(self):
        detector = self._stubbed_detector([
            detection_utils.Detection("person", 0.30, (0, 0, 10, 10)),
        ])
        result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        assert result.person_count == 0
        assert len(result.objects) == 0

    def test_result_payload_schema(self):
        detector = self._stubbed_detector([
            detection_utils.Detection("person", 0.98, (0, 0, 10, 10)),
            detection_utils.Detection("cell phone", 0.93, (30, 30, 40, 40)),
        ])
        result = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        payload = result.as_dict()
        for key in (
            "person_count", "multiple_person", "phone_detected", "phone_confidence",
            "objects", "processing_time_ms",
        ):
            assert key in payload
        for obj in payload["objects"]:
            assert set(obj.keys()) == {"class", "confidence", "bbox"}

    def test_temporal_smoothing_suppresses_single_noisy_frame(self):
        detector = object_detector.ObjectDetector()
        detector._person_smoother = detection_utils.TemporalSmoother(window_size=5, min_true_ratio=0.6)
        detector._phone_smoother = detection_utils.TemporalSmoother(window_size=5, min_true_ratio=0.6)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        one_person = [detection_utils.Detection("person", 0.9, (0, 0, 10, 10))]
        two_people = one_person + [detection_utils.Detection("person", 0.9, (20, 0, 30, 10))]

        flags = []
        for stub in [one_person, two_people, one_person, one_person, one_person]:
            detector._run_inference = (lambda dets: (lambda f: dets))(stub)
            flags.append(detector.detect(frame).multiple_person)

        assert flags[1] is False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
class TestObjectDetectionConfig:
    def test_config_file_exists(self):
        assert (PROJECT_ROOT / "configs" / "object_detection.yaml").exists()

    def test_config_loads_and_has_expected_values(self):
        config = load_yaml_config(PROJECT_ROOT / "configs" / "object_detection.yaml")
        assert config["thresholds"]["confidence_threshold"] == 0.60
        assert config["thresholds"]["iou_threshold"] == 0.45
        assert set(config["target_classes"]["required"]) == {"person", "cell phone"}
        assert "window_size" in config["smoothing"]

    def test_config_is_valid_yaml(self):
        raw = (PROJECT_ROOT / "configs" / "object_detection.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Router / main.py registration
# ---------------------------------------------------------------------------
class TestObjectDetectionRouter:
    def test_router_module_imports(self):
        import importlib
        module = importlib.import_module("backend.app.routers.object_detection")
        importlib.reload(module)
        assert hasattr(module, "router")

    def test_router_exposes_expected_routes(self):
        import importlib
        module = importlib.import_module("backend.app.routers.object_detection")
        importlib.reload(module)
        route_paths = sorted(r.path for r in module.router.routes)
        assert "/object-detection/detect" in route_paths
        assert "/object-detection/classes" in route_paths
        assert "/object-detection/health" in route_paths

    def test_main_py_registers_object_detection_router(self):
        main_source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        assert "from backend.app.routers import object_detection" in main_source
        assert "app.include_router(object_detection.router)" in main_source

    def test_classes_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/object-detection/classes")
        assert resp.status_code == 200
        assert set(resp.json()) >= {"person", "cell phone"}

    def test_health_endpoint_via_testclient(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/object-detection/health")
        assert resp.status_code == 200
        assert "model_loaded" in resp.json()

    def test_detect_endpoint_rejects_bad_input(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.post("/object-detection/detect", json={"frame_b64": "not-valid-base64!!!"})
        assert resp.status_code in (400, 422)

    def test_detect_endpoint_accepts_valid_frame(self):
        pytest.importorskip("fastapi")
        pytest.importorskip("cv2")
        import base64
        import cv2
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".jpg", blank_frame)
        assert success
        frame_b64 = base64.b64encode(encoded.tobytes()).decode("ascii")

        resp = client.post("/object-detection/detect", json={"frame_b64": frame_b64})
        assert resp.status_code == 200
        body = resp.json()
        for key in (
            "person_count", "multiple_person", "phone_detected", "phone_confidence",
            "objects", "processing_time_ms", "degraded",
        ):
            assert key in body
