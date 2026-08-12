from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class Enrollment(Base):
    __tablename__ = "enrollments"

    enrollment_id = Column(Integer, primary_key=True, index=True)

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

    joined_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

