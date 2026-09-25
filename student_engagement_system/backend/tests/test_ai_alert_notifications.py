"""AI_ALERT: a student's AI detection reaches the teacher of the SAME class
over the classroom WebSocket (backend/app/routers/monitoring.py). The event
is built from the server's own latest result, rate-limited per student and
alert type, and never crosses classes."""

import base64
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("AI_SLEEP_DEBUG", "0")

from app.routers import monitoring  # noqa: E402
from services.access_control import AccessDenied  # noqa: E402

IDENTITIES = {
    "teacher-101": ({"role": "teacher", "user_id": 1, "name": "Teacher A"}, {101}),
    "teacher-202": ({"role": "teacher", "user_id": 2, "name": "Teacher B"}, {202}),
    "student-5": ({"role": "student", "user_id": 5, "name": "disha"}, {101}),
    "student-6": ({"role": "student", "user_id": 6, "name": "ravi"}, {202}),
}


@pytest.fixture
def client(monkeypatch):
    def fake_authorize(token, class_id):
        identity, classes = IDENTITIES.get(token, (None, set()))
        if identity is None or class_id not in classes:
            raise AccessDenied("You are not authorized to join this class.")
        return identity

    monkeypatch.setattr(monitoring, "_authorize_ws", fake_authorize)
    monitoring._rooms.clear()
    monitoring._latest_results.clear()
    app = FastAPI()
    app.include_router(monitoring.router)
    yield TestClient(app)
    monitoring._rooms.clear()
    monitoring._latest_results.clear()


def connect(client, class_id, token):
    return client.websocket_connect(f"/ws/classes/{class_id}/signaling?token={token}")


def recv_until(ws, kind, seen=None):
    while True:
        message = ws.receive_json()
        if seen is not None:
            seen.append(message)
        if message["type"] == kind:
            return message


def sync(ws):
    """Everything the server sent `ws` before a ping round trip."""
    seen = []
    ws.send_json({"type": "ping"})
    recv_until(ws, "pong", seen)
    return seen


def set_result(class_id, student_id, alert, score=40):
    monitoring._latest_results.setdefault(class_id, {})[student_id] = {
        "active_alert": alert, "engagement_score": score,
    }


def trigger(student):
    student.send_json({"type": "AI_ALERT"})
    sync(student)  # the server has processed it


@pytest.mark.parametrize("alert, text", [
    ("phone_detected", "Phone detected — disha appears to be using a phone."),
    ("drowsiness", "disha may be sleeping."),
    ("looking_away", "disha is looking away from the screen."),
    ("multiple_person", "Multiple people detected in disha's camera."),
    ("no_person_detected", "disha is not in front of the camera."),
    ("no_face_detected", "disha's face is not visible to the camera."),
    ("attention_drop_predicted", "disha's attention is dropping."),
])
def test_every_student_alert_type_reaches_the_teacher(client, alert, text):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        set_result(101, 5, alert)
        trigger(student)
        event = recv_until(teacher, "AI_ALERT")
        assert event["alertType"] == alert
        assert event["message"] == text
        assert event["studentId"] == "5"
        assert event["studentName"] == "disha"
        assert isinstance(event["timestamp"], int)
        assert event["engagementScore"] == 40


def test_event_uses_server_result_not_client_claims(client):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        set_result(101, 5, "looking_away")
        student.send_json({
            "type": "AI_ALERT", "alertType": "phone_detected",
            "studentId": "6", "studentName": "someone else", "message": "fake",
        })
        sync(student)
        event = recv_until(teacher, "AI_ALERT")
        assert event["alertType"] == "looking_away"
        assert event["studentId"] == "5"
        assert event["studentName"] == "disha"
        assert event["message"] == "disha is looking away from the screen."


def test_no_active_alert_sends_nothing(client):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        trigger(student)  # no analyzed frame yet
        set_result(101, 5, None)
        trigger(student)
        assert not any(m["type"] == "AI_ALERT" for m in sync(teacher))


def test_same_alert_is_rate_limited_but_a_new_type_is_not(client, monkeypatch):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        set_result(101, 5, "phone_detected")
        for _ in range(5):  # e.g. a flickering detection / repeated signals
            trigger(student)
        received = [m for m in sync(teacher) if m["type"] == "AI_ALERT"]
        assert [m["alertType"] for m in received] == ["phone_detected"]

        set_result(101, 5, "drowsiness")
        trigger(student)
        received = [m for m in sync(teacher) if m["type"] == "AI_ALERT"]
        assert [m["alertType"] for m in received] == ["drowsiness"]

        # After the cooldown the same type can notify again.
        monkeypatch.setattr(monitoring, "AI_ALERT_COOLDOWN_SECONDS", 0.0)
        set_result(101, 5, "phone_detected")
        trigger(student)
        received = [m for m in sync(teacher) if m["type"] == "AI_ALERT"]
        assert [m["alertType"] for m in received] == ["phone_detected"]


def test_alerts_never_cross_classes(client):
    with connect(client, 101, "teacher-101") as teacher_a, \
            connect(client, 202, "teacher-202") as teacher_b, \
            connect(client, 101, "student-5") as student_a, \
            connect(client, 202, "student-6") as student_b:
        for ws in (teacher_a, teacher_b, student_a, student_b):
            recv_until(ws, "welcome")

        set_result(101, 5, "phone_detected")
        set_result(202, 6, "drowsiness")
        # Class B's latest result for student 5 doesn't exist: a class A
        # student can't raise anything in class B.
        set_result(202, 5, "multiple_person")

        trigger(student_a)
        trigger(student_b)

        a_alerts = [m for m in sync(teacher_a) if m["type"] == "AI_ALERT"]
        b_alerts = [m for m in sync(teacher_b) if m["type"] == "AI_ALERT"]
        assert [(m["studentId"], m["alertType"]) for m in a_alerts] == [("5", "phone_detected")]
        assert [(m["studentId"], m["alertType"]) for m in b_alerts] == [("6", "drowsiness")]

        # Students never receive AI_ALERT events.
        assert not any(m["type"] == "AI_ALERT" for m in sync(student_a))
        assert not any(m["type"] == "AI_ALERT" for m in sync(student_b))


def test_teacher_cannot_raise_ai_alerts(client):
    with connect(client, 101, "teacher-101") as teacher:
        recv_until(teacher, "welcome")
        set_result(101, 1, "phone_detected")
        teacher.send_json({"type": "AI_ALERT"})
        assert not any(m["type"] == "AI_ALERT" for m in sync(teacher))


# ---------------------------------------------------------------------------
# End to end: a real phone frame -> /ai/analyze-frame -> teacher's socket
# ---------------------------------------------------------------------------

PHONE_IMAGE = PROJECT_ROOT / "ml_models/research/phone_person/dataset/test/images/000000015055.jpg"


def test_phone_frame_alert_reaches_teacher(client, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("mediapipe")
    pytest.importorskip("onnxruntime")
    if not PHONE_IMAGE.exists():
        pytest.skip("test image not available")

    from services import ai_service as ai

    old_cwd = os.getcwd()
    os.chdir(BACKEND_ROOT)  # model paths are relative to backend/
    try:
        ai._ensure_models_loaded()
    finally:
        os.chdir(old_cwd)

    monkeypatch.setattr(monitoring, "get_db", lambda: None)
    monkeypatch.setattr(monitoring, "close_db", lambda db: None)
    monkeypatch.setattr(monitoring, "_authorize_frame", lambda db, auth, req: None)
    monkeypatch.setattr(
        monitoring.SessionRepository, "get_active_session",
        staticmethod(lambda db, class_id: SimpleNamespace(session_id=930000 + class_id)),
    )
    monkeypatch.setattr(monitoring.EngagementRepository, "create", staticmethod(lambda db, record: None))
    monkeypatch.setattr(monitoring.AlertRepository, "create", staticmethod(lambda db, **kwargs: None))
    monkeypatch.setattr(
        monitoring.EngagementPredictionService, "predict",
        staticmethod(lambda db, session_id, student_id: {}),
    )

    frame = cv2.resize(cv2.imread(str(PHONE_IMAGE)), (640, 480))
    ok, jpg = cv2.imencode(".jpg", frame)
    body = {
        "frame": "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode(),
        "class_id": 101, "student_id": 5, "student_name": "disha",
    }

    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")

        # What the student page does: analyze its frame, see a new alert,
        # signal AI_ALERT over its classroom socket.
        result = client.post("/ai/analyze-frame", json=body).json()
        assert result["data"]["active_alert"] == "phone_detected"
        student.send_json({"type": "AI_ALERT"})

        event = recv_until(teacher, "AI_ALERT")
        assert event["alertType"] == "phone_detected"
        assert event["studentName"] == "disha"
        assert event["message"] == "Phone detected — disha appears to be using a phone."
