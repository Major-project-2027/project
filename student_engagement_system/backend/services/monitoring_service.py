from ai.webcam import get_frame
from services.ai_service import process_frame
from services import ai_state

# This local-server-webcam path is unused by the real live classroom flow
# (the browser sends frames from the student's own camera to the FastAPI
# /ai/analyze-frame endpoint instead -- see app/routers/monitoring.py). It
# is kept only so this module still imports/runs cleanly; there is no real
# session for it, so it uses a single fixed state slot.
_LOCAL_WEBCAM_SESSION_ID = 0
_LOCAL_WEBCAM_STUDENT_ID = 0


class MonitoringService:

    @staticmethod
    def get_live_data():

        frame = get_frame()

        if frame is None:
            return {
                "success": False,
                "error": "Camera not found",
                "data": []
            }

        state = ai_state.get_state(
            _LOCAL_WEBCAM_SESSION_ID,
            _LOCAL_WEBCAM_STUDENT_ID,
        )

        result = process_frame(frame, state)

        # ============================================================
        # DETERMINE ACTIVE AI ALERT
        # ============================================================

        active_alert = None

        if result.get("phone_detected"):
            active_alert = "phone_detected"

        elif result.get("person_count", 1) > 1:
            active_alert = "multiple_person"

        elif result.get("head_pose") not in (
            None,
            "Looking Forward",
            "Forward",
        ):
            active_alert = "looking_away"

        elif result.get("gaze") not in (
            None,
            "Center",
        ):
            active_alert = "looking_away"

        elif result.get("engagement_score", 100) < 40:
            active_alert = "attention_drop_predicted"

        # ============================================================
        # RETURN AI RESULT
        # ============================================================

        return {
            "success": True,

            "name": result.get("name", "Unknown"),
            "emotion": result.get("emotion", "Unknown"),

            "blink_count": result.get("blink_count", 0),

            "head_pose": result.get("head_pose", "Unknown"),
            "gaze": result.get("gaze", "Unknown"),

            "phone_detected": result.get("phone_detected", False),
            "person_count": result.get("person_count", 1),

            "engagement_score": result.get("engagement_score", 0),
            "engagement_status": result.get(
                "engagement_status",
                "unknown"
            ),

            # NEW
            "active_alert": active_alert,
        }