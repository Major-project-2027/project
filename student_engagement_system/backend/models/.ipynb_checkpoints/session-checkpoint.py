from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func

from database.base import Base


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(Integer, primary_key=True, index=True)

    class_id = Column(
        Integer,
        ForeignKey("classrooms.class_id"),
        nullable=False
    )

    teacher_id = Column(
        Integer,
        ForeignKey("teachers.teacher_id"),
        nullable=False
    )

    start_time = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    end_time = Column(
        DateTime(timezone=True),
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )

