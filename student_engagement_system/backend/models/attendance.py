from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class Attendance(Base):
    __tablename__ = "attendance"

    attendance_id = Column(Integer, primary_key=True, index=True)

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

    session_id = Column(
        Integer,
        ForeignKey("sessions.session_id"),
        nullable=True
    )

    status = Column(Integer, default=1)   # 1 = Present, 0 = Absent

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

