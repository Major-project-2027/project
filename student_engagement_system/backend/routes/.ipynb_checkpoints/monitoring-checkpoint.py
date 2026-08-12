import base64

import cv2
import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from services.monitoring_service import MonitoringService
from services.ai_service import process_frame
from database.database import SessionLocal
from models.engagement import EngagementRecord
from repositories.session_repository import SessionRepository

router = APIRouter(
    prefix="",
    tags=["monitoring"]
)


# ============================================================
# STORE LATEST AI RESULT FROM THE STUDENT'S BROWSER CAMERA
# ============================================================

latest_ai_result = None


# ============================================================
# HELPER: DETERMINE ACTIVE ALERT
# ============================================================

def get_active_alert(result):
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


# ============================================================
# LIVE MONITOR
# ============================================================

@router.get("/live-monitor")
def live_monitor():

    global latest_ai_result

    if latest_ai_result is None:
        return {
            "success": True,
            "data": []
        }

    data = latest_ai_result

    emotion = str(
        data.get("emotion", "Unknown")
    ).lower()

    engagement = int(
        data.get("engagement_score", 0)
    )

    head_pose = str(
        data.get("head_pose", "Unknown")
    )

    gaze = str(
        data.get("gaze", "Unknown")
    )

    phone_detected = bool(
        data.get("phone_detected", False)
    )

    person_count = int(
        data.get("person_count", 0)
    )

    active_alert = get_active_alert(data)

    # ========================================================
    # DETERMINE COGNITIVE STATE
    # ========================================================

    if engagement < 40:
        cognitive_state = "drowsy"

    elif (
        gaze.lower() not in ["center", "forward", "unknown"]
        or head_pose.lower() not in [
            "forward",
            "looking forward",
            "unknown"
        ]
    ):
        cognitive_state = "distracted"

    else:
        cognitive_state = "focused"

    # ========================================================
    # STUDENT DATA
    # ========================================================

    student = {
        "studentId": "Disha",
        "studentName": data.get(
            "name",
            "Disha"
        ),

        "currentEmotion": emotion,

        "currentEngagement": engagement,

        "authenticated": (
            data.get("name", "Unknown") != "Unknown"
        ),

        "cognitiveState": cognitive_state,

        "activeAlert": active_alert,

        "history": [
            engagement
        ],

        "micOn": False,

        # Real AI values
        "blinkCount": data.get(
            "blink_count",
            0
        ),

        "headPose": head_pose,

        "gaze": gaze,

        "phoneDetected": phone_detected,

        "personCount": person_count,
    }

    return {
        "success": True,
        "data": [student]
    }


# ============================================================
# WEBRTC SIGNALING
# ============================================================

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


# ============================================================
# BROWSER CAMERA → AI ANALYSIS
# ============================================================

class AIFrameRequest(BaseModel):
    frame: str
    class_id: int
    student_id: int
    student_name: str


@router.post("/ai/analyze-frame")
def analyze_frame(
    request: AIFrameRequest
):

    global latest_ai_result

    try:

        # ----------------------------------------------------
        # REMOVE DATA URL PREFIX
        # ----------------------------------------------------

        encoded = request.frame

        if "," in encoded:
            encoded = encoded.split(
                ",",
                1
            )[1]

        # ----------------------------------------------------
        # BASE64 → BYTES
        # ----------------------------------------------------

        image_bytes = base64.b64decode(
            encoded
        )

        # ----------------------------------------------------
        # BYTES → NUMPY ARRAY
        # ----------------------------------------------------

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        # ----------------------------------------------------
        # NUMPY ARRAY → OPENCV FRAME
        # ----------------------------------------------------

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:

            return {
                "success": False,
                "error": "Unable to decode camera frame"
            }

        # ----------------------------------------------------
        # RUN EXISTING AI PIPELINE
        # ----------------------------------------------------

        (
            result,
            MonitoringService.blink_counter,
            MonitoringService.blink_total,
        ) = process_frame(
            frame,
            MonitoringService.blink_counter,
            MonitoringService.blink_total,
        )
            db = SessionLocal()

    try:
        active_session = SessionRepository.get_active_session(
            db,
            request.class_id
        )

        if active_session:
            engagement_record = EngagementRecord(
                session_id=active_session.session_id,
                student_id=request.student_id,
                emotion=str(
                    result.get("emotion", "Unknown")
                ),
                blink_count=int(
                    result.get("blink_count", 0)
                ),
                head_pose=str(
                    result.get("head_pose", "Unknown")
                ),
                gaze=str(
                    result.get("gaze", "Unknown")
                ),
                phone_detected=bool(
                    result.get("phone_detected", False)
                ),
                multiple_person=bool(
                    result.get("person_count", 1) > 1
                ),
                engagement_score=float(
                    result.get("engagement_score", 0)
                ),
                engagement_status=str(
                    result.get(
                        "engagement_status",
                        "unknown"
                    )
                ),
            )

            db.add(engagement_record)
            db.commit()

    finally:
        db.close())

        # ----------------------------------------------------
        # DETERMINE ACTIVE ALERT
        # ----------------------------------------------------

        active_alert = get_active_alert(
            result
        )

        # ----------------------------------------------------
        # STORE LATEST RESULT
        # ----------------------------------------------------

        latest_ai_result = {
            "name": result.get(
                "name",
                "Unknown"
            ),

            "emotion": result.get(
                "emotion",
                "Unknown"
            ),

            "blink_count": result.get(
                "blink_count",
                0
            ),

            "head_pose": result.get(
                "head_pose",
                "Unknown"
            ),

            "gaze": result.get(
                "gaze",
                "Unknown"
            ),

            "phone_detected": result.get(
                "phone_detected",
                False
            ),

            "person_count": result.get(
                "person_count",
                1
            ),

            "engagement_score": result.get(
                "engagement_score",
                0
            ),

            "engagement_status": result.get(
                "engagement_status",
                "unknown"
            ),

            "active_alert": active_alert,
        }

        # ----------------------------------------------------
        # RETURN RESULT TO STUDENT FRONTEND
        # ----------------------------------------------------

        return {
            "success": True,
            "data": latest_ai_result
        }

    except Exception as exc:

        return {
            "success": False,
            "error": str(exc)
        }

