"""Camera-off approval over the classroom WebSocket
(backend/app/routers/monitoring.py): a student's camera on -> off change
needs the teacher's approval, enforced by the server."""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routers import monitoring  # noqa: E402
from services.access_control import AccessDenied  # noqa: E402

# token -> (identity, classes this identity may join)
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
    app = FastAPI()
    app.include_router(monitoring.router)
    yield TestClient(app)
    monitoring._rooms.clear()


def connect(client, class_id, token):
    return client.websocket_connect(f"/ws/classes/{class_id}/signaling?token={token}")


def recv_until(ws, kind, seen=None):
    """Read messages until one of type `kind`; collect skipped ones."""
    while True:
        message = ws.receive_json()
        if seen is not None:
            seen.append(message)
        if message["type"] == kind:
            return message


def expect_status(ws, status):
    """Read camera_request_status messages until `status`; an earlier
    "pending" ack is skipped, any other status is a failure."""
    while True:
        message = recv_until(ws, "camera_request_status")
        if message["status"] == status:
            return message
        assert message["status"] == "pending", f"expected {status}, got {message['status']}"


def sync(ws):
    """Round-trip a ping so every earlier server message has arrived."""
    seen = []
    ws.send_json({"type": "ping"})
    recv_until(ws, "pong", seen)
    return seen


def camera_on(ws):
    ws.send_json({"type": "media_state", "camera": True, "mic": False, "hand": False})
    recv_until(ws, "participant_updated")


def test_unapproved_camera_off_is_refused(client):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        camera_on(student)

        # Direct bypass attempt: just claim the camera is off.
        student.send_json({"type": "media_state", "camera": False, "mic": False, "hand": False})
        expect_status(student, "not_approved")
        updated = recv_until(student, "participant_updated")
        assert updated["participant"]["media"]["camera"] is True

        blocked = recv_until(teacher, "camera_off_blocked")
        assert blocked["studentName"] == "disha"
        assert monitoring._rooms[101].members["student:5"].media["camera"] is True


def test_student_cannot_decide_own_request(client):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        camera_on(student)
        student.send_json({"type": "camera_off_request", "reason": "Privacy issue"})
        request = recv_until(teacher, "camera_request")["request"]

        student.send_json({"type": "camera_request_decision", "id": request["id"], "approve": True})
        error = recv_until(student, "error")
        assert error["code"] == 403
        assert 5 not in monitoring._rooms[101].camera_off_approved
        assert "student:5" in monitoring._rooms[101].camera_requests


def test_request_reject_then_approve(client):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        camera_on(student)

        student.send_json({"type": "camera_off_request", "reason": "Invalid reason"})
        expect_status(student, "invalid")

        student.send_json({"type": "camera_off_request", "reason": "Other", "note": "x" * 500})
        expect_status(student, "pending")
        request = recv_until(teacher, "camera_request")["request"]
        assert request["studentName"] == "disha"
        assert request["reason"] == "Other"
        assert len(request["note"]) == 200
        assert request["ts"]

        # Reject: camera must stay on.
        teacher.send_json({"type": "camera_request_decision", "id": request["id"], "approve": False})
        expect_status(student, "rejected")
        assert recv_until(teacher, "camera_request_removed")["id"] == request["id"]
        student.send_json({"type": "media_state", "camera": False, "mic": False, "hand": False})
        expect_status(student, "not_approved")

        # Approve: the camera-off change is now accepted and synced.
        student.send_json({"type": "camera_off_request", "reason": "Network issue"})
        request = recv_until(teacher, "camera_request")["request"]
        teacher.send_json({"type": "camera_request_decision", "id": request["id"], "approve": True})
        expect_status(student, "approved")
        student.send_json({"type": "media_state", "camera": False, "mic": False, "hand": False})
        updated = recv_until(teacher, "participant_updated")
        while updated["participant"]["media"]["camera"] is not False:
            updated = recv_until(teacher, "participant_updated")
        assert updated["participant"]["key"] == "student:5"

        # Turning the camera back on ends the approval.
        camera_on(student)
        student.send_json({"type": "media_state", "camera": False, "mic": False, "hand": False})
        expect_status(student, "not_approved")


def test_cancel_removes_pending_request(client):
    with connect(client, 101, "teacher-101") as teacher, connect(client, 101, "student-5") as student:
        recv_until(teacher, "welcome")
        recv_until(student, "welcome")
        camera_on(student)
        student.send_json({"type": "camera_off_request", "reason": "Camera problem"})
        request = recv_until(teacher, "camera_request")["request"]
        student.send_json({"type": "camera_off_cancel"})
        expect_status(student, "cancelled")
        assert recv_until(teacher, "camera_request_removed")["id"] == request["id"]
        assert monitoring._rooms[101].camera_requests == {}


def test_requests_are_scoped_to_their_class(client):
    with connect(client, 101, "teacher-101") as teacher_a, connect(client, 202, "teacher-202") as teacher_b, \
            connect(client, 101, "student-5") as student:
        recv_until(teacher_a, "welcome")
        recv_until(teacher_b, "welcome")
        recv_until(student, "welcome")
        camera_on(student)
        student.send_json({"type": "camera_off_request", "reason": "Privacy issue"})
        request = recv_until(teacher_a, "camera_request")["request"]

        seen = sync(teacher_b)
        assert not any(m["type"].startswith("camera_") for m in seen)

        # Teacher B can't decide class 101's request, even with its id.
        teacher_b.send_json({"type": "camera_request_decision", "id": request["id"], "approve": True})
        sync(teacher_b)
        assert "student:5" in monitoring._rooms[101].camera_requests
        assert 5 not in monitoring._rooms[101].camera_off_approved

    # A student can't join another class's socket at all.
    with connect(client, 202, "student-5") as intruder:
        assert intruder.receive_json()["code"] == 403


def test_reconnect_keeps_state(client):
    with connect(client, 101, "teacher-101") as teacher:
        welcome = recv_until(teacher, "welcome")
        assert welcome["cameraRequests"] == []

        with connect(client, 101, "student-5") as student:
            welcome = recv_until(student, "welcome")
            assert welcome["cameraOffApproved"] is False
            camera_on(student)
            student.send_json({"type": "camera_off_request", "reason": "Privacy issue"})
            request = recv_until(teacher, "camera_request")["request"]
            teacher.send_json({"type": "camera_request_decision", "id": request["id"], "approve": True})
            expect_status(student, "approved")

        # Leaving keeps the approval; the reconnecting client is told, and
        # its camera-off state is accepted (not treated as a bypass).
        with connect(client, 101, "student-5") as student:
            welcome = recv_until(student, "welcome")
            assert welcome["cameraOffApproved"] is True
            student.send_json({"type": "media_state", "camera": False, "mic": False, "hand": False})
            seen = sync(student)
            assert not any(m.get("status") == "not_approved" for m in seen)

        # Without approval, a reconnect does not inherit anything.
        monitoring._rooms[101].camera_off_approved.clear()
        with connect(client, 101, "student-5") as student:
            welcome = recv_until(student, "welcome")
            assert welcome["cameraOffApproved"] is False
            camera_on(student)
            student.send_json({"type": "media_state", "camera": False, "mic": False, "hand": False})
            expect_status(student, "not_approved")


def test_pending_request_shown_to_reconnecting_teacher_and_dropped_on_leave(client):
    with connect(client, 101, "student-5") as student:
        recv_until(student, "welcome")
        camera_on(student)
        student.send_json({"type": "camera_off_request", "reason": "Technical issue"})
        expect_status(student, "pending")

        with connect(client, 101, "teacher-101") as teacher:
            welcome = recv_until(teacher, "welcome")
            assert [r["reason"] for r in welcome["cameraRequests"]] == ["Technical issue"]

    assert 101 not in monitoring._rooms or monitoring._rooms[101].camera_requests == {}
