import base64
import json
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

try:
    from database.db_provider import get_db, close_db, is_mongo
except ModuleNotFoundError:
    from backend.database.db_provider import get_db, close_db, is_mongo
from models.engagement import EngagementRecord
from models.student import Student  # noqa: F401 -- registers `students` table for EngagementRecord's FK
from models.classroom import Classroom  # noqa: F401 -- registers `classrooms` table for Alert's FK
from models.teacher import Teacher  # noqa: F401 -- registers `teachers` table for Session's FK
from repositories.active import SessionRepository, AlertRepository, EngagementRepository
from services import ai_state
from services.access_control import (
    AccessDenied,
    Unauthenticated,
    http_status_for,
    payload_from_auth_header,
    payload_from_token,
    require_class_member,
    require_class_owner,
    require_role,
    require_student_allowed,
)
import cv2
import numpy as np

from fastapi import APIRouter, Header, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from services.ai_service import process_frame
from services.engagement_prediction_service import (
    PREDICTION_INTERVAL_SECONDS,
    EngagementPredictionService,
    prediction_state_label,
)


router = APIRouter(
    prefix="",
    tags=["monitoring"]
)

# class_id -> { student_id: latest_result_dict }
# In-memory cache used only to serve /live-monitor between polls. It is
# always read alongside a fresh "is this class's session still active?"
# check, and is dropped as soon as that check fails, so a class that has
# ended (or a class belonging to a different teacher) can never leak
# results here.
_latest_results: dict[int, dict[int, dict]] = {}


def get_active_alert(result):
    # Highest priority: nobody is in frame at all, so every other signal
    # below (phone/gaze/head-pose) is stale or default and must not be
    # trusted. `no_person_detected` is the DEBOUNCED flag computed in
    # ai_service.process_frame (a short streak of confirmed-empty YOLO
    # reads), not a raw single-frame person_count==0 check, so a brief
    # camera stutter does not trigger this.
    if result.get("no_person_detected"):
        return "no_person_detected"

    # Sleeping ("both eyes closed for >= SLEEP_THRESHOLD_SECONDS", see
    # ai_service.process_frame's temporal tracker) ranks next -- a
    # confirmed multi-second closed-eye episode is a more certain,
    # more actionable signal than a phone sighting or an off-center
    # gaze, so it takes priority over those.
    if result.get("sleeping"):
        return "drowsiness"

    if result.get("phone_detected"):
        return "phone_detected"

    if result.get("person_count", 1) > 1:
        return "multiple_person"

    # Debounced "genuinely outside the acceptable laptop-screen viewing
    # zone" signal computed in ai_service.process_frame's LOOKING-AWAY
    # block -- requires several consecutive outside-zone frames (not a
    # single frame) AND treats natural small head/gaze movement as still
    # "on screen" (see that module for the exact dead-zone/hysteresis
    # logic). Replaces the old raw per-frame head_pose/gaze equality
    # checks, which fired on almost every frame.
    if result.get("looking_away"):
        return "looking_away"

    if result.get("engagement_score", 100) < 40:
        return "attention_drop_predicted"

    return None


def _error_response(exc):
    return JSONResponse(
        status_code=http_status_for(exc),
        content={"success": False, "error": str(exc)},
    )


@router.get("/live-monitor")
def live_monitor(
    class_id: Optional[int] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """Latest known AI result per student, scoped to ONE class's current
    live session -- for that class's own teacher only. Without a class_id
    (legacy callers) nothing is returned rather than falling back to some
    other class's data."""

    if class_id is None:
        return {"success": True, "data": []}

    db = get_db()
    try:
        try:
            teacher_id = require_role(payload_from_auth_header(authorization), "teacher")
            require_class_owner(db, teacher_id, class_id)
        except (Unauthenticated, AccessDenied) as exc:
            return _error_response(exc)
        active_session = SessionRepository.get_active_session(db, class_id)
    finally:
        close_db(db)

    if not active_session:
        # No live session for this class right now -- drop any cached
        # results so a later session never inherits stale data.
        _latest_results.pop(class_id, None)
        return {"success": True, "data": []}

    students_for_class = _latest_results.get(class_id, {})

    data = []

    for student_id, result in students_for_class.items():

        emotion = str(result.get("emotion", "neutral")).lower()
        engagement = int(result.get("engagement_score", 0))
        head_pose = str(result.get("head_pose", "Forward"))
        gaze = str(result.get("gaze", "Center"))
        phone_detected = bool(result.get("phone_detected", False))
        person_count = int(result.get("person_count", 1))
        no_person_detected = bool(result.get("no_person_detected", False))
        active_alert = result.get("active_alert")
        engagement_status = result.get("engagement_status", "unknown")

        predicted_engagement = result.get("predicted_engagement")
        prediction_status = result.get("prediction_status", "unavailable")
        attention_drop_predicted = bool(result.get("attention_drop_predicted", False))
        # Genuine temporal both-eyes-closed detection (see
        # ai_service.process_frame) -- NOT the same thing as the
        # engagement<40 heuristic below, which stays as a fallback only
        # for whatever it already covered before this existed.
        sleeping = bool(result.get("sleeping", False))

        if sleeping:
            cognitive_state = "drowsy"
        elif engagement < 40:
            cognitive_state = "drowsy"
        elif (
            gaze.lower() not in ["center", "forward", "unknown"]
            or head_pose.lower() not in ["forward", "looking forward", "unknown"]
        ):
            cognitive_state = "distracted"
        else:
            cognitive_state = "focused"

        data.append({
            "studentId": student_id,
            "studentName": result.get("name", "Student"),
            "currentEmotion": emotion,
            "currentEngagement": engagement,
            "authenticated": True,
            "cognitiveState": cognitive_state,
            "activeAlert": active_alert,
            "history": [engagement],
            "micOn": False,
            "blinkCount": result.get("blink_count", 0),
            "headPose": head_pose,
            "gaze": gaze,
            "phoneDetected": phone_detected,
            "personCount": person_count,
            "noPersonDetected": no_person_detected,
            "sleeping": sleeping,
            "engagementStatus": engagement_status,

            "predictedEngagement": predicted_engagement,
            "predictionStatus": prediction_status,
            "attentionDropPredicted": attention_drop_predicted,
            "predictionThreshold": result.get("prediction_threshold"),
            "predictionHorizonSeconds": result.get("prediction_horizon_seconds"),
            "predictionSequenceLength": result.get("prediction_sequence_length"),
            "predictionReason": result.get("prediction_reason"),
            "predictionTimestamp": result.get("prediction_timestamp"),
            "predictionLabel": result.get("prediction_label", "unavailable"),
        })

    return {"success": True, "data": data}


@router.get("/prediction/status")
def prediction_status():
    """Whether a real trained LSTM engagement-prediction model is actually
    loaded, and why not if it isn't -- for manual verification, never
    fabricated. See services/engagement_prediction_service.py."""

    return {"success": True, **EngagementPredictionService.model_status()}


@router.get("/ai/model-sources")
def ai_model_sources():
    """Which AI component sources are actually active right now --
    current (this project's own, pre-integration) vs friend (the
    integrated MODEL_INTEGRATION_PACKAGE components) -- for manual
    verification and for later A/B evaluation between the current and
    friend object-detection models. See services/friend_ai/loader.py;
    override with AI_OBJECT_DETECTION_MODEL / AI_LOOKING_AWAY_DROWSINESS_SOURCE
    / AI_EMOTION_MODEL_SOURCE."""

    from services.friend_ai import loader as friend_ai_loader

    return {"success": True, **friend_ai_loader.status()}


# ---------------------------------------------------------------------------
# WebRTC signaling + classroom hub (presence, chat, whiteboard)
# ---------------------------------------------------------------------------
#
# ONE authenticated WebSocket per participant per class, shared by WebRTC
# signaling, presence, chat, the whiteboard, AI results and "class ended".
#
# * Identity comes only from the JWT (?token=...), verified on connect:
#   the class's own teacher, or a student the teacher allowed while the
#   class is live. Anyone else gets {"type": "error", "code": 403} and the
#   socket is closed -- changing the class id in the URL doesn't help.
# * Every message is scoped to this class's room. WebRTC messages are
#   delivered only to their addressee ("to"); students can only address
#   the teacher. The server stamps the sender -- ids/names in client
#   messages are never trusted.
# * Whiteboard and class_ended are teacher-only (enforced here). Board
#   strokes and recent chat are kept in memory for the room's lifetime so
#   late joiners catch up; nothing here is written to the database.
#
# In-process state: FastAPI must keep running a single worker (see
# render.yaml), as for ai_state.


class _Member:
    __slots__ = ("websocket", "key", "role", "user_id", "name", "media", "connected_at")

    def __init__(self, websocket, role, user_id, name):
        self.websocket = websocket
        self.role = role
        self.user_id = user_id
        self.name = name
        self.key = f"{role}:{user_id}"
        self.media = {"camera": False, "mic": False, "screen": False, "hand": False}
        self.connected_at = datetime.now(timezone.utc).isoformat()

    def public(self):
        # Name + role + media state only -- nothing private.
        return {
            "key": self.key,
            "role": self.role,
            "userId": str(self.user_id),
            "name": self.name,
            "media": dict(self.media),
            "connectedAt": self.connected_at,
        }


class _Room:
    MAX_STROKES = 20000
    MAX_CHAT = 200

    def __init__(self):
        self.members: dict = {}
        self.whiteboard = {"open": False, "strokes": []}
        self.chat: deque = deque(maxlen=self.MAX_CHAT)


_rooms: dict = {}

_TEACHER_ONLY = {"wb_open", "wb_close", "wb_stroke", "wb_clear", "class_ended"}
_WEBRTC = {"offer", "answer", "candidate"}


async def _send(member, payload):
    try:
        await member.websocket.send_json(payload)
    except Exception:  # noqa: BLE001 -- a dead socket is cleaned up by its own handler
        pass


async def _broadcast(room, payload, exclude=None):
    for member in list(room.members.values()):
        if member.key != exclude:
            await _send(member, payload)


def _authorize_ws(token, class_id):
    db = get_db()
    try:
        payload = payload_from_token(token)
        return require_class_member(db, payload, class_id, require_live_for_students=True)
    finally:
        close_db(db)


def _clean_stroke(raw):
    """Validated whiteboard stroke chunk with normalized 0..1 points."""
    if not isinstance(raw, dict):
        return None
    points = raw.get("points")
    if not isinstance(points, list) or not (1 <= len(points) <= 1000):
        return None
    clean = []
    for point in points:
        if not (isinstance(point, (list, tuple)) and len(point) == 2):
            return None
        x, y = point
        if not all(isinstance(v, (int, float)) for v in (x, y)):
            return None
        clean.append([round(min(max(float(x), 0.0), 1.0), 4), round(min(max(float(y), 0.0), 1.0), 4)])
    width = raw.get("width", 3)
    width = min(max(float(width), 1.0), 60.0) if isinstance(width, (int, float)) else 3.0
    color = str(raw.get("color", "#111827"))[:16]
    mode = "erase" if raw.get("mode") == "erase" else "pen"
    return {"id": str(raw.get("id", ""))[:64], "points": clean, "width": width, "color": color, "mode": mode}


@router.websocket("/ws/classes/{class_id}/signaling")
async def classroom_signaling(
    websocket: WebSocket,
    class_id: int,
    token: Optional[str] = Query(default=None),
):
    await websocket.accept()

    try:
        identity = await run_in_threadpool(_authorize_ws, token, class_id)
    except (Unauthenticated, AccessDenied) as exc:
        await websocket.send_json({"type": "error", "code": http_status_for(exc), "message": str(exc)})
        await websocket.close(code=4401 if isinstance(exc, Unauthenticated) else 4403)
        return

    member = _Member(websocket, identity["role"], identity["user_id"], identity["name"])
    room = _rooms.setdefault(class_id, _Room())

    # One connection per person per class: a reload or second tab replaces
    # the old one instead of leaving a ghost participant behind.
    previous = room.members.get(member.key)
    room.members[member.key] = member
    if previous is not None:
        await _send(previous, {"type": "error", "code": 409, "message": "You joined this class from another tab or device."})
        try:
            await previous.websocket.close(code=4409)
        except Exception:  # noqa: BLE001
            pass

    await _send(member, {
        "type": "welcome",
        "self": member.public(),
        "participants": [m.public() for m in room.members.values() if m.key != member.key],
        "whiteboard": room.whiteboard,
        "chat": list(room.chat),
    })
    await _broadcast(room, {"type": "participant_joined", "participant": member.public()}, exclude=member.key)

    try:
        while True:
            text = await websocket.receive_text()
            try:
                message = json.loads(text)
            except ValueError:
                continue
            if not isinstance(message, dict):
                continue

            kind = message.get("type")

            if kind == "ping":
                await _send(member, {"type": "pong"})
                continue

            if kind in _TEACHER_ONLY and member.role != "teacher":
                await _send(member, {"type": "error", "code": 403, "message": "Only the teacher can do that."})
                continue

            if kind in _WEBRTC:
                target = message.get("to")
                if member.role == "student":
                    # Students talk to the teacher only.
                    recipients = [m for m in room.members.values() if m.role == "teacher"]
                else:
                    recipient = room.members.get(target) if isinstance(target, str) else None
                    recipients = [recipient] if recipient is not None and recipient.role == "student" else []
                relayed = {
                    "type": kind,
                    "from": member.key,
                    "fromRole": member.role,
                    "fromName": member.name,
                }
                if member.role == "student":
                    relayed["studentId"] = str(member.user_id)
                    relayed["studentName"] = member.name
                for field in ("offer", "answer", "candidate"):
                    if field in message:
                        relayed[field] = message[field]
                for recipient in recipients:
                    await _send(recipient, relayed)
                continue

            if kind == "ai_result":
                if member.role != "student":
                    continue
                payload = {
                    "type": "ai_result",
                    "studentId": str(member.user_id),
                    "studentName": member.name,
                    "data": message.get("data"),
                }
                for recipient in list(room.members.values()):
                    if recipient.role == "teacher":
                        await _send(recipient, payload)
                continue

            if kind == "media_state":
                for field in ("camera", "mic", "screen", "hand"):
                    if isinstance(message.get(field), bool):
                        if field == "screen" and member.role != "teacher":
                            continue  # students can't screen-share
                        member.media[field] = message[field]
                await _broadcast(room, {"type": "participant_updated", "participant": member.public()})
                continue

            if kind == "chat":
                body = str(message.get("text", "")).strip()[:1000]
                if not body:
                    continue
                chat = {
                    "type": "chat",
                    "id": uuid.uuid4().hex,
                    "senderKey": member.key,
                    "senderName": member.name,
                    "senderRole": member.role,
                    "text": body,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                room.chat.append(chat)
                await _broadcast(room, chat)
                continue

            if kind in ("wb_open", "wb_close"):
                room.whiteboard["open"] = kind == "wb_open"
                await _broadcast(room, {"type": kind}, exclude=member.key)
                continue

            if kind == "wb_stroke":
                stroke = _clean_stroke(message.get("stroke"))
                if stroke is None:
                    continue
                strokes = room.whiteboard["strokes"]
                strokes.append(stroke)
                if len(strokes) > _Room.MAX_STROKES:
                    del strokes[: len(strokes) - _Room.MAX_STROKES]
                await _broadcast(room, {"type": "wb_stroke", "stroke": stroke}, exclude=member.key)
                continue

            if kind == "wb_clear":
                room.whiteboard["strokes"] = []
                await _broadcast(room, {"type": "wb_clear"}, exclude=member.key)
                continue

            if kind == "class_ended":
                await _broadcast(room, {"type": "class_ended"}, exclude=member.key)
                continue

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 -- never let one bad socket kill the room
        pass

    finally:
        if room.members.get(member.key) is member:
            del room.members[member.key]
            await _broadcast(room, {"type": "participant_left", "key": member.key})
        if not room.members and _rooms.get(class_id) is room:
            del _rooms[class_id]


# ---------------------------------------------------------------------------
# Browser camera -> AI analysis
# ---------------------------------------------------------------------------

class AIFrameRequest(BaseModel):
    frame: str
    class_id: int
    student_id: int
    student_name: str


# (class_id, student_id) -> monotonic expiry of a successful
# "allowed in this class" check, so the per-frame path doesn't add a
# database round trip every frame. Revocations take effect within this
# window.
_frame_auth_cache: dict = {}
_FRAME_AUTH_TTL_SECONDS = 60.0


def _authorize_frame(db, authorization, request):
    """The frame must come from a logged-in STUDENT, for themselves, in a
    class their teacher allowed them into. student_id in the body must
    match the token -- a student can't submit frames as someone else."""
    student_id = require_role(payload_from_auth_header(authorization), "student")
    if student_id != request.student_id:
        raise AccessDenied("You can only submit frames for your own account.")
    key = (request.class_id, student_id)
    if _frame_auth_cache.get(key, 0.0) > time.monotonic():
        return
    require_student_allowed(db, student_id, request.class_id)
    _frame_auth_cache[key] = time.monotonic() + _FRAME_AUTH_TTL_SECONDS


@router.post("/ai/analyze-frame")
def analyze_frame(
    request: AIFrameRequest,
    authorization: Optional[str] = Header(default=None),
):

    db = get_db()

    try:
        try:
            _authorize_frame(db, authorization, request)
        except (Unauthenticated, AccessDenied) as exc:
            return _error_response(exc)

        # ----------------------------------------------------
        # A session must be live for this class, or there is
        # nothing to analyze -- and nothing further should run.
        # ----------------------------------------------------

        active_session = SessionRepository.get_active_session(
            db,
            request.class_id,
        )

        if not active_session:
            return {
                "success": True,
                "session_active": False,
                "data": None,
            }

        # ----------------------------------------------------
        # REMOVE DATA URL PREFIX, DECODE TO AN OPENCV FRAME
        # ----------------------------------------------------

        encoded = request.frame

        if "," in encoded:
            encoded = encoded.split(",", 1)[1]

        image_bytes = base64.b64decode(encoded)

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            return {
                "success": False,
                "session_active": True,
                "error": "Unable to decode camera frame",
            }

        # ----------------------------------------------------
        # RUN THE AI PIPELINE -- using THIS student's own
        # per-session state, never shared with any other
        # student or session.
        # ----------------------------------------------------

        state = ai_state.get_state(
            active_session.session_id,
            request.student_id,
        )

        result = process_frame(frame, state)

        # ----------------------------------------------------
        # SAVE AI RESULT TO DATABASE
        # ----------------------------------------------------

        engagement_record = EngagementRecord(
            session_id=active_session.session_id,
            student_id=request.student_id,

            emotion=str(result.get("emotion", "Unknown")),
            blink_count=int(result.get("blink_count", 0)),
            head_pose=str(result.get("head_pose", "Unknown")),
            gaze=str(result.get("gaze", "Unknown")),
            phone_detected=bool(result.get("phone_detected", False)),
            multiple_person=bool(result.get("person_count", 1) > 1),
            engagement_score=float(result.get("engagement_score", 0)),
            engagement_status=str(
                result.get("engagement_status", "unknown")
            ),
        )

        # EngagementRepository.create() handles both persistence
        # backends (SQLite: db.add()+db.commit(); MongoDB: insert_one()
        # with an auto-incremented record_id) -- see repositories.active
        # and repositories/mongo/engagement_repository.py.
        EngagementRepository.create(db, engagement_record)

        # ----------------------------------------------------
        # DETERMINE ACTIVE ALERT, AND PERSIST A NEW ALERT
        # EVENT ROW ONLY ON A STATE TRANSITION (so counts
        # reflect real discrete incidents, not raw frame
        # counts).
        # ----------------------------------------------------

        active_alert = get_active_alert(result)

        if active_alert != state.get("last_alert_type"):

            if active_alert is not None:
                AlertRepository.create(
                    db,
                    session_id=active_session.session_id,
                    class_id=request.class_id,
                    student_id=request.student_id,
                    alert_type=active_alert,
                )

            state["last_alert_type"] = active_alert

        # ----------------------------------------------------
        # FUTURE ENGAGEMENT PREDICTION (LSTM) -- runs on a fixed
        # interval (PREDICTION_INTERVAL_SECONDS), NOT on every
        # frame like the rest of this pipeline. Between cycles,
        # the last computed prediction is simply reused from this
        # student's own per-session state -- no re-inference, no
        # extra DB writes. EngagementPredictionService itself
        # enforces (session_id, student_id) isolation and excludes
        # no-person frames from the sequence; see that module for
        # why no real model is currently loaded.
        # ----------------------------------------------------

        now = time.time()

        if now - state.get("last_prediction_at", 0.0) >= PREDICTION_INTERVAL_SECONDS:

            prediction = EngagementPredictionService.predict(
                db,
                active_session.session_id,
                request.student_id,
            )

            state["last_prediction_at"] = now
            state["last_prediction"] = prediction

            prediction_label = prediction_state_label(prediction)

            # Only a genuine transition INTO the low-prediction tier
            # creates a new alert row -- never one per prediction
            # cycle -- so repeated "still predicted low" cycles don't
            # spam the alerts table.
            if (
                prediction_label == "attention_drop_predicted"
                and state.get("last_prediction_state") != "attention_drop_predicted"
            ):
                AlertRepository.create(
                    db,
                    session_id=active_session.session_id,
                    class_id=request.class_id,
                    student_id=request.student_id,
                    alert_type="predicted_attention_drop",
                )

            state["last_prediction_state"] = prediction_label

        prediction = state.get("last_prediction") or {}
        # Cheap pure computation -- recomputed from the (possibly cached,
        # possibly just-refreshed) prediction dict either way, so it's
        # always in sync with whatever `prediction` actually holds this
        # request, not just on cycles that ran fresh inference.
        prediction_label = prediction_state_label(prediction)

        # ----------------------------------------------------
        # STORE LATEST RESULT (for /live-monitor), SCOPED TO
        # THIS CLASS + STUDENT ONLY.
        # ----------------------------------------------------

        latest = {
            "name": request.student_name,
            "emotion": result.get("emotion", "Unknown"),
            "blink_count": result.get("blink_count", 0),
            "head_pose": result.get("head_pose", "Unknown"),
            "gaze": result.get("gaze", "Unknown"),
            "phone_detected": result.get("phone_detected", False),
            "person_count": result.get("person_count", 1),
            "no_person_detected": result.get("no_person_detected", False),
            "sleeping": result.get("sleeping", False),
            "engagement_score": result.get("engagement_score", 0),
            "engagement_status": result.get(
                "engagement_status", "unknown"
            ),
            "active_alert": active_alert,
            "student_id": request.student_id,
            "class_id": request.class_id,

            "predicted_engagement": prediction.get("predicted_engagement"),
            "prediction_status": prediction.get("status", "unavailable"),
            "attention_drop_predicted": bool(
                prediction.get("attention_drop_predicted", False)
            ),
            "prediction_threshold": prediction.get("threshold"),
            "prediction_horizon_seconds": prediction.get(
                "prediction_horizon_seconds"
            ),
            "prediction_sequence_length": prediction.get("sequence_length"),
            "prediction_reason": prediction.get("reason"),
            "prediction_timestamp": prediction.get("timestamp"),
            # Pre-computed 4-tier label ("stable" / "attention_may_decrease"
            # / "attention_drop_predicted" / "unavailable") using the
            # service's centrally-defined thresholds -- so the frontend
            # never needs its own copy of ATTENTION_DROP_THRESHOLD/
            # STABLE_THRESHOLD to decide what to display.
            "prediction_label": prediction_label,
        }

        _latest_results.setdefault(request.class_id, {})[
            request.student_id
        ] = latest

        # ----------------------------------------------------
        # RETURN RESULT
        # ----------------------------------------------------

        return {
            "success": True,
            "session_active": True,
            "data": latest,
        }

    except Exception as exc:

        # rollback() is SQLAlchemy-specific -- MongoDB has no equivalent
        # here (each write is already its own atomic operation, not part
        # of an open multi-statement transaction to unwind).
        if not is_mongo():
            db.rollback()

        return {
            "success": False,
            "session_active": True,
            "error": str(exc),
        }

    finally:

        close_db(db)


@router.post("/ai/clear-session/{session_id}")
def clear_session(session_id: int):
    """Drop in-memory per-student AI state for a session that just ended.

    Called (best-effort) by the Flask service when a teacher ends a class,
    since the two processes don't share memory. Safe to call even if the
    session has no in-memory state (e.g. AI service was restarted).
    """

    removed = ai_state.clear_session(session_id)

    return {
        "success": True,
        "cleared_student_states": removed,
    }
