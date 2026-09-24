from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.sql import func

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class TeacherRoster(Base):
    """A teacher's managed student roster: the registered students the
    teacher has chosen to work with. Per-class join permission is still
    the class's enrollment rows; the roster is the list the teacher picks
    those from."""

    __tablename__ = "teacher_roster"
    __table_args__ = (UniqueConstraint("teacher_id", "student_id"),)

    roster_id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.teacher_id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
