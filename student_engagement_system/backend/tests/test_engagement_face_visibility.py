"""Engagement when the student's face is not visible
(backend/services/ai_service.apply_face_visibility and process_frame):
controlled decay while the face is missing, gradual recovery when it
returns, a separate "no_face_detected" state, and the reduced score
reaching the teacher."""

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("AI_SLEEP_DEBUG", "0")

from services import ai_service as ai  # noqa: E402
from services.ai_service import apply_face_visibility  # noqa: E402

FRAME_S = 0.5  # seconds between frames in the pure-function tests


# ---------------------------------------------------------------------------
# apply_face_visibility -- deterministic, no models
# ---------------------------------------------------------------------------

def run(state, raw, face, t, no_person=False):
    return apply_face_visibility(state, raw, face, no_person, t)


def test_face_visible_uses_the_real_score():
    state = {}
    assert run(state, 100, True, 0.0) == (100, False)
    assert run(state, 90, True, FRAME_S) == (90, False)


def test_one_missed_frame_starts_decreasing():
    state = {}
    run(state, 100, True, 0.0)
    score, no_face = run(state, 100, False, FRAME_S)
    assert score < 100
    assert score <= 100 - ai.NO_FACE_MIN_DROP_PER_FRAME
    assert no_face is False  # alert only after NO_FACE_CONFIRM_FRAMES


def test_continued_absence_reaches_zero_and_is_flagged():
    state = {}
    run(state, 100, True, 0.0)
    scores, flags = [], []
    t = 0.0
    for _ in range(8):
        t += FRAME_S
        score, no_face = run(state, 100, False, t)
        scores.append(score)
        flags.append(no_face)
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] == 0
    # 100 -> 0 within ~2.5s of continuous absence at this frame rate.
    assert scores.index(0) + 1 <= 6
    assert flags[0] is False and all(flags[1:])


def test_decay_is_time_based_not_frame_based():
    # Slow backend (Render): fewer, further-apart frames decay just as fast.
    state = {}
    run(state, 100, True, 0.0)
    score, _ = run(state, 100, False, 1.5)
    assert score == 100 - int(ai.NO_FACE_DECAY_PER_SECOND * 1.5)


def test_stale_score_is_not_reused():
    state = {}
    run(state, 100, True, 0.0)
    t = 0.0
    for _ in range(20):
        t += FRAME_S
        score, _ = run(state, 100, False, t)
    assert score == 0


def test_absent_score_never_exceeds_current_penalties():
    # A phone visible while the face is hidden still penalizes.
    state = {}
    score, _ = run(state, 70, False, 0.0)
    assert score <= 70 - ai.NO_FACE_MIN_DROP_PER_FRAME


def test_face_return_recovers_gradually_to_the_real_score():
    state = {}
    run(state, 100, True, 0.0)
    t = 0.0
    for _ in range(8):
        t += FRAME_S
        run(state, 100, False, t)
    assert state["last_engagement_score"] == 0

    t += FRAME_S
    first, no_face = run(state, 90, True, t)
    assert no_face is False
    assert 0 < first < 90  # recovering, not an instant jump

    recovered = [first]
    for _ in range(12):
        t += FRAME_S
        recovered.append(run(state, 90, True, t)[0])
    assert recovered == sorted(recovered)
    assert recovered[-1] == 90  # ends at the real calculated score

    # Once recovered, normal drops apply immediately again (no smoothing).
    t += FRAME_S
    assert run(state, 60, True, t)[0] == 60


def test_no_person_still_scores_zero_immediately():
    state = {}
    run(state, 100, True, 0.0)
    assert run(state, 0, False, FRAME_S, no_person=True) == (0, False)


# ---------------------------------------------------------------------------
# process_frame on real photos
# ---------------------------------------------------------------------------

cv2 = pytest.importorskip("cv2")
IMAGES = PROJECT_ROOT / "ml_models/research/phone_person/dataset/test/images"
FACE_IMAGE = IMAGES / "000000037945.jpg"   # one person, face visible
PHONE_IMAGE = IMAGES / "000000015055.jpg"  # person holding a phone, no face


@pytest.fixture(scope="module")
def frames():
    pytest.importorskip("mediapipe")
    pytest.importorskip("onnxruntime")
    if not FACE_IMAGE.exists() or not PHONE_IMAGE.exists():
        pytest.skip("test images not available")
    old_cwd = os.getcwd()
    os.chdir(BACKEND_ROOT)  # model paths are relative to backend/
    try:
        ai._ensure_models_loaded()
    finally:
        os.chdir(old_cwd)
    face = cv2.resize(cv2.imread(str(FACE_IMAGE)), (640, 480))
    hidden = face.copy()
    hidden[: int(480 * 0.35)] = 128  # face covered, body still in frame
    phone = cv2.resize(cv2.imread(str(PHONE_IMAGE)), (640, 480))
    return {"face": face, "hidden": hidden, "phone": phone}


def new_state(student_id):
    from services import ai_state
    return ai_state.get_state(910000, student_id)


def test_pipeline_face_visible_is_normal(frames):
    state = new_state(1)
    result = ai.process_frame(frames["face"].copy(), state)
    assert result["face_detected"] is True
    assert result["no_face_detected"] is False
    assert result["engagement_score"] == 100
    assert result["active_alert"] is None


def test_pipeline_face_hidden_decays_to_zero_then_recovers(frames, monkeypatch):
    clock = [ai.time.time()]
    monkeypatch.setattr(ai.time, "time", lambda: clock[0])

    def step(name):
        clock[0] += FRAME_S
        return ai.process_frame(frames[name].copy(), state)

    state = new_state(2)
    assert step("face")["engagement_score"] == 100

    hidden = [step("hidden") for _ in range(6)]
    scores = [r["engagement_score"] for r in hidden]
    assert all(r["person_count"] >= 1 for r in hidden)  # student still in frame
    assert all(r["face_detected"] is False for r in hidden)
    assert scores[0] < 100
    assert scores == sorted(scores, reverse=True)
    assert scores[-1] == 0
    assert hidden[-1]["no_face_detected"] is True
    assert hidden[-1]["active_alert"] == "no_face_detected"  # not looking_away
    assert hidden[-1]["engagement_status"] == "Face Not Detected"

    back = [step("face") for _ in range(8)]
    back_scores = [r["engagement_score"] for r in back]
    assert back[0]["face_detected"] is True
    assert 0 < back_scores[0] < 100
    assert back_scores == sorted(back_scores)
    assert back_scores[-1] == 100
    assert back[-1]["active_alert"] is None


def test_pipeline_phone_detected_on_first_frame(frames):
    state = new_state(3)
    result = ai.process_frame(frames["phone"].copy(), state)
    assert result["phone_detected"] is True
    assert result["active_alert"] == "phone_detected"  # outranks no-face


# ---------------------------------------------------------------------------
# The decayed score is what the student and teacher receive
# ---------------------------------------------------------------------------

def test_teacher_receives_reduced_score(frames, monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import monitoring

    monkeypatch.setattr(monitoring, "get_db", lambda: None)
    monkeypatch.setattr(monitoring, "close_db", lambda db: None)
    monkeypatch.setattr(monitoring, "_authorize_frame", lambda db, auth, req: None)
    monkeypatch.setattr(
        monitoring.SessionRepository, "get_active_session",
        staticmethod(lambda db, class_id: SimpleNamespace(session_id=920000 + class_id)),
    )
    monkeypatch.setattr(monitoring.EngagementRepository, "create", staticmethod(lambda db, record: None))
    alerts = []
    monkeypatch.setattr(
        monitoring.AlertRepository, "create",
        staticmethod(lambda db, **kwargs: alerts.append(kwargs["alert_type"])),
    )
    monkeypatch.setattr(
        monitoring.EngagementPredictionService, "predict",
        staticmethod(lambda db, session_id, student_id: {}),
    )
    monkeypatch.setattr(monitoring, "require_role", lambda payload, role: 1)
    monkeypatch.setattr(monitoring, "payload_from_auth_header", lambda header: {})
    monkeypatch.setattr(monitoring, "require_class_owner", lambda db, teacher_id, class_id: None)

    ok, jpg = cv2.imencode(".jpg", frames["face"])
    ok2, hidden_jpg = cv2.imencode(".jpg", frames["hidden"])
    import base64

    def body(image):
        return {
            "frame": "data:image/jpeg;base64," + base64.b64encode(image.tobytes()).decode(),
            "class_id": 77, "student_id": 5, "student_name": "disha",
        }

    app = FastAPI()
    app.include_router(monitoring.router)
    client = TestClient(app)

    first = client.post("/ai/analyze-frame", json=body(jpg)).json()
    assert first["data"]["engagement_score"] == 100

    responses = [client.post("/ai/analyze-frame", json=body(hidden_jpg)).json() for _ in range(6)]
    student_scores = [r["data"]["engagement_score"] for r in responses]
    assert student_scores[-1] == 0  # the student's own response
    assert responses[-1]["data"]["no_face_detected"] is True
    assert responses[-1]["data"]["active_alert"] == "no_face_detected"
    assert "no_face_detected" in alerts

    # Teacher's /live-monitor view: the same reduced score, not a stale 100.
    live = monitoring.live_monitor(class_id=77, authorization="Bearer x")["data"]
    assert live[0]["currentEngagement"] == 0
    assert live[0]["noFaceDetected"] is True
    assert live[0]["activeAlert"] == "no_face_detected"

    # Teacher's live tile: the student relays its result over the socket
    # and the teacher receives exactly that reduced score.
    identities = {
        "t": {"role": "teacher", "user_id": 1, "name": "Teacher"},
        "s": {"role": "student", "user_id": 5, "name": "disha"},
    }
    monkeypatch.setattr(monitoring, "_authorize_ws", lambda token, class_id: identities[token])
    monitoring._rooms.clear()
    with client.websocket_connect("/ws/classes/77/signaling?token=t") as teacher, \
            client.websocket_connect("/ws/classes/77/signaling?token=s") as student:
        student.send_json({"type": "ai_result", "data": responses[-1]["data"]})
        while True:
            message = teacher.receive_json()
            if message["type"] == "ai_result":
                break
        assert message["studentId"] == "5"
        assert message["data"]["engagement_score"] == 0
        assert message["data"]["no_face_detected"] is True
    monitoring._rooms.clear()
    monitoring._latest_results.pop(77, None)
