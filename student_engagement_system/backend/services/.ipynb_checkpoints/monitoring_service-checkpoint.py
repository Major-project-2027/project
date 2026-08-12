from ai.webcam import get_frame
from services.ai_service import process_frame

class MonitoringService:

    blink_counter = 0
    blink_total = 0

    @staticmethod
    def get_live_data():

        frame = get_frame()

        if frame is None:
            return {
                "success": False,
                "error": "Camera not found",
                "data": []
            }

        result, MonitoringService.blink_counter, MonitoringService.blink_total = process_frame(
            frame,
            MonitoringService.blink_counter,
            MonitoringService.blink_total
        )

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