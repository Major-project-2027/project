import base64
try:
    from database.database import SessionLocal
except ModuleNotFoundError:
    from backend.database.database import SessionLocal
from models.engagement import EngagementRecord
from models.student import Student  # noqa: F401 -- registers `students` table for EngagementRecord's FK
from repositories.session_repository import SessionRepository
import cv2
import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from services.monitoring_service import MonitoringService
from services.ai_service import process_frame


router = APIRouter(
    prefix="",
    tags=["monitoring"]
)

latest_ai_result = None


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
        data.get("emotion", "neutral")
    ).lower()

    engagement = int(
        data.get("engagement_score", 0)
    )

    head_pose = str(
        data.get("head_pose", "Forward")
    )

    gaze = str(
        data.get("gaze", "Center")
    )

    phone_detected = bool(
        data.get("phone_detected", False)
    )

    person_count = int(
        data.get("person_count", 1)
    )

    active_alert = None

    if phone_detected:
        active_alert = "phone_detected"

    elif person_count > 1:
        active_alert = "multiple_person"

    elif gaze.lower() not in [
        "center",
        "forward",
        "unknown"
    ]:
        active_alert = "looking_away"

    elif head_pose.lower() not in [
        "forward",
        "looking forward",
        "unknown"
    ]:
        active_alert = "looking_away"

    elif engagement < 40:
        active_alert = "attention_drop_predicted"

    if engagement < 40:
        cognitive_state = "drowsy"

    elif (
        gaze.lower() not in [
            "center",
            "forward",
            "unknown"
        ]
        or head_pose.lower() not in [
            "forward",
            "looking forward",
            "unknown"
        ]
    ):
        cognitive_state = "distracted"

    else:
        cognitive_state = "focused"

    student = {
        "studentId": data.get(
            "student_id",
            "Disha"
        ),

        "studentName": data.get(
            "name",
            "Disha"
        ),

        "currentEmotion": emotion,

        "currentEngagement": engagement,

        "authenticated": True,

        "cognitiveState": cognitive_state,

        "activeAlert": active_alert,

        "history": [
            engagement
        ],

        "micOn": False,

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
        "data": [
            student
        ]
    }

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

    global latest_ai_result

    db = None

    try:
        # ----------------------------------------------------
        # REMOVE DATA URL PREFIX
        # ----------------------------------------------------

        encoded = request.frame

        if "," in encoded:
            encoded = encoded.split(",", 1)[1]

        # ----------------------------------------------------
        # BASE64 -> BYTES
        # ----------------------------------------------------

        image_bytes = base64.b64decode(encoded)

        # ----------------------------------------------------
        # BYTES -> NUMPY ARRAY
        # ----------------------------------------------------

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        # ----------------------------------------------------
        # NUMPY ARRAY -> OPENCV FRAME
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

        # ----------------------------------------------------
        # SAVE AI RESULT TO DATABASE
        # ----------------------------------------------------

        db = SessionLocal()

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

        # ----------------------------------------------------
        # DETERMINE ACTIVE ALERT
        # ----------------------------------------------------

        active_alert = get_active_alert(result)

        # ----------------------------------------------------
        # STORE LATEST RESULT
        # ----------------------------------------------------

        latest_ai_result = {
            "name": request.student_name,

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

            "student_id": request.student_id,

            "class_id": request.class_id,
        }

        # ----------------------------------------------------
        # RETURN RESULT
        # ----------------------------------------------------

        return {
            "success": True,
            "data": latest_ai_result
        }

    except Exception as exc:

        if db is not None:
            db.rollback()

        return {
            "success": False,
            "error": str(exc)
        }

    finally:

        if db is not None:
            db.close()

        # ------------------------------------------------------------
        # Determine active alert from THIS student's camera frame
        # ------------------------------------------------------------

        active_alert = None

        if result.get(
            "phone_detected"
        ):

            active_alert = "phone_detected"

        elif result.get(
            "person_count",
            1
        ) > 1:

            active_alert = "multiple_person"

        elif result.get(
            "head_pose"
        ) not in (
            None,
            "Looking Forward",
            "Forward",
        ):

            active_alert = "looking_away"

        elif result.get(
            "gaze"
        ) not in (
            None,
            "Center",
        ):

            active_alert = "looking_away"

        elif result.get(
            "engagement_score",
            100
        ) < 40:

            active_alert = "attention_drop_predicted"

        return {

            "success": True,

            "data": {

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
                    "Center"
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
            },
        }

    