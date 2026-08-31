from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.sql import func

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class CognitiveStateSummary(Base):
    """One row per (session, student) -- the student's session-level
    cognitive-state summary, computed ONCE when the class/session ends
    (see services/session_service.py's SessionService.end_session) and
    upserted, never duplicated on re-computation or on repeated
    teacher-dashboard reads.

    This is a NEW, deliberately-separate feature from engagement_records
    (per-frame raw signals) and from the LSTM-based engagement prediction
    (future_engagement_predictions / the live per-session forecast) --
    it aggregates THIS session's own engagement_records + alerts into a
    transparent, rule-based Focused/Neutral/Distracted/Drowsy summary.
    See services/cognitive_state_service.py for the exact classification
    logic and the honest reasoning for why this is NOT presented as a
    trained ML model.
    """

    __tablename__ = "cognitive_state_summaries"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.session_id"),
        nullable=False,
    )

    class_id = Column(
        Integer,
        ForeignKey("classrooms.class_id"),
        nullable=False,
    )

    student_id = Column(
        Integer,
        ForeignKey("students.student_id"),
        nullable=False,
    )

    # "ok" | "insufficient_data" -- see cognitive_state_service.py's
    # STATUS_* constants. Never a third, silently-guessed status.
    status = Column(String(30), nullable=False)

    # One of "focused" | "neutral" | "distracted" | "drowsy" -- only set
    # when status == "ok". Lowercase to match this project's existing
    # alert_type / cognitiveState string convention (see models/alert.py,
    # app/routers/monitoring.py's get_active_alert()).
    cognitive_state = Column(String(20), nullable=True)

    # Genuinely computed from this session's own classified records --
    # never fabricated, and never set when status != "ok".
    focused_percentage = Column(Float, nullable=True)
    neutral_percentage = Column(Float, nullable=True)
    distracted_percentage = Column(Float, nullable=True)

    # How many engagement_records rows (excluding "No Person Detected"
    # frames) actually contributed to the percentages above.
    valid_sample_count = Column(Integer, nullable=False, default=0)

    # Count of genuine, persisted "drowsiness" alert-table rows for this
    # (session, student) -- each one already required a real, continuous
    # >= SLEEP_THRESHOLD_SECONDS closed-eye episode to be created (see
    # ai_service.py). NOT a fabricated metric.
    drowsy_episode_count = Column(Integer, nullable=False, default=0)

    # Human-readable explanation, set whenever status != "ok" (mirrors
    # EngagementPredictionService's own reason-string pattern).
    reason = Column(String(255), nullable=True)

    calculated_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<CognitiveStateSummary session={self.session_id} student={self.student_id} state={self.cognitive_state}>"
