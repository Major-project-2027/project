"""AI pipeline latency changes (backend/services/ai_service.py): YOLO on
every frame, Haar only on emotion frames, 2-frame look-away confirmation,
strictly increasing MediaPipe timestamps, per-stage timing."""

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("AI_SLEEP_DEBUG", "0")

cv2 = pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
pytest.importorskip("onnxruntime")

from services import ai_service as ai  # noqa: E402
from services import ai_state  # noqa: E402

# A real photo mosaic with people (YOLO finds 2) whose faces are too small
# for the face landmarkers.
PEOPLE_IMAGE = PROJECT_ROOT / "ml_models/evaluation/reports/phone_person/baseline_test_eval/val_batch2_labels.jpg"


@pytest.fixture(scope="module")
def frame():
    if not PEOPLE_IMAGE.exists():
        pytest.skip("evaluation image not available")
    old_cwd = os.getcwd()
    os.chdir(BACKEND_ROOT)  # model paths are relative to backend/
    try:
        ai._ensure_models_loaded()
    finally:
        os.chdir(old_cwd)
    return cv2.resize(cv2.imread(str(PEOPLE_IMAGE)), (640, 480))


def fresh_state(student_id):
    return ai_state.get_state(900000, student_id)


def test_yolo_runs_from_the_first_frame(frame):
    state = fresh_state(1)
    for _ in range(3):
        result = ai.process_frame(frame.copy(), state)
        assert "yolo_ms" in result["timing"]
        assert result["person_count"] >= 1


def test_haar_only_on_emotion_frames(frame):
    state = fresh_state(2)
    ran = []
    for _ in range(ai.PROCESS_EVERY_FACE * 2):
        result = ai.process_frame(frame.copy(), state)
        ran.append("haar_ms" in result["timing"])
        assert result["timing"]["process_frame_ms"] > 0
    expected = [(i + 1) % ai.PROCESS_EVERY_FACE == 0 for i in range(len(ran))]
    assert ran == expected


def test_same_millisecond_frames_do_not_fail(frame, monkeypatch):
    state = fresh_state(3)
    frozen = ai.time.time()
    monkeypatch.setattr(ai.time, "time", lambda: frozen + 3600)
    ai.process_frame(frame.copy(), state)
    ai.process_frame(frame.copy(), state)  # raised "timestamp must be monotonically increasing" before


def test_looking_away_confirms_after_two_frames(frame):
    state = fresh_state(4)
    first = ai.process_frame(frame.copy(), state)
    if first["looking_away"] is False and state.get("away_streak") != 1:
        pytest.skip("a face was tracked in the test image")
    assert first["looking_away"] is False
    second = ai.process_frame(frame.copy(), state)
    assert second["looking_away"] is True
