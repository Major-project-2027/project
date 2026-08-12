from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from database.base import Base


class Classroom(Base):
    __tablename__ = "classrooms"

    class_id = Column(Integer, primary_key=True, index=True)

    classroom_name = Column(String(100), nullable=False)

    subject = Column(String(100), nullable=False)

    semester = Column(Integer, nullable=False)

    section = Column(String(10), nullable=False)

    teacher_id = Column(Integer, ForeignKey("teachers.teacher_id"))

    class_code = Column(String(20), unique=True, nullable=False)

    meeting_link = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Classroom {self.classroom_name}>"

