from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class Alert(Base):
    """A single AI-detected alert EVENT (not a per-frame snapshot).

    One row is written each time a student's active alert type changes
    (e.g. transitions from none -> phone_detected), so counts here reflect
    real, discrete incidents during a session rather than raw frame counts.
    """

    __tablename__ = "alerts"

    alert_id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("sessions.session_id"),
        nullable=False
    )

    student_id = Column(
        Integer,
        ForeignKey("students.student_id"),
        nullable=False
    )

    class_id = Column(
        Integer,
        ForeignKey("classrooms.class_id"),
        nullable=False
    )

    alert_type = Column(String(50), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
