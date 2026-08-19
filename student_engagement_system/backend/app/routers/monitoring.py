import base64
import time
from typing import Optional

try:
    from database.database import SessionLocal
except ModuleNotFoundError:
    from backend.database.database import SessionLocal
from models.engagement import EngagementRecord
from models.student import Student  # noqa: F401 -- registers `students` table for EngagementRecord's FK
from models.classroom import Classroom  # noqa: F401 -- registers `classrooms` table for Alert's FK
from models.teacher import Teacher  # noqa: F401 -- registers `teachers` table for Session's FK
from repositories.session_repository import SessionRepository
from repositories.alert_repository import AlertRepository
from services import ai_state
import cv2
import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
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

    if result.get("phone_detected"):
        return "phone_detected"

    if result.get("person_count", 1) > 1:
        return "multiple_person"

    if result.get("head_pose") not in (
        None,
        "Looking Forward",
        "Forward",
        "Unknown",
    ):
        return "looking_away"

    if result.get("gaze") not in (
        None,
        "Center",
        "Unknown",
    ):
        return "looking_away"

    if result.get("engagement_score", 100) < 40:
        return "attention_drop_predicted"

    return None


@router.get("/live-monitor")
def live_monitor(class_id: Optional[int] = Query(default=None)):
    """Latest known AI result per student, scoped to ONE class's current
    live session. Without a class_id (legacy callers) nothing is returned
    rather than falling back to some other class's data."""

    if class_id is None:
        return {"success": True, "data": []}

    db = SessionLocal()
    try:
        active_session = SessionRepository.get_active_session(db, class_id)
    finally:
        db.close()

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

        if engagement < 40:
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


# ---------------------------------------------------------------------------
# WebRTC signaling
# ---------------------------------------------------------------------------

_connections: dict[str, set[WebSocket]] = {}


@router.websocket(
    "/ws/classes/{class_id}/signaling"
)
async def classroom_signaling(
    websocket: WebSocket,
    class_id: str
):

    await websocket.accept()

    if class_id not in _connections:
        _connections[class_id] = set()

    _connections[class_id].add(websocket)

    try:

        while True:

            message = await websocket.receive_json()

            # Forward signaling messages to the other participant(s)
            # in the same classroom.

            for connection in _connections[class_id]:

                if connection is not websocket:

                    await connection.send_json(
                        message
                    )

    except WebSocketDisconnect:
        pass

    finally:

        _connections.get(
            class_id,
            set()
        ).discard(websocket)

        if (
            class_id in _connections
            and not _connections[class_id]
        ):
            del _connections[class_id]


# ---------------------------------------------------------------------------
# Browser camera -> AI analysis
# ---------------------------------------------------------------------------

class AIFrameRequest(BaseModel):
    frame: str
    class_id: int
    student_id: int
    student_name: str


@router.post("/ai/analyze-frame")
def analyze_frame(request: AIFrameRequest):

    db = SessionLocal()

    try:
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

        db.add(engagement_record)
        db.commit()

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

        db.rollback()

        return {
            "success": False,
            "session_active": True,
            "error": str(exc),
        }

    finally:

        db.close()


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
