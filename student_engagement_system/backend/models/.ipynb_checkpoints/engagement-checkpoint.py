from sqlalchemy import Column, Integer, Float, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.sql import func

from database.base import Base


class EngagementRecord(Base):
    __tablename__ = "engagement_records"

    record_id = Column(Integer, primary_key=True, index=True)

    session_id = Column(Integer, ForeignKey("sessions.session_id"))

    student_id = Column(Integer, ForeignKey("students.student_id"))

    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    emotion = Column(String(50))

    blink_count = Column(Integer)

    head_pose = Column(String(50))

    gaze = Column(String(50))

    phone_detected = Column(Boolean)

    multiple_person = Column(Boolean)

    engagement_score = Column(Float)

    engagement_status = Column(String(50))

    fps = Column(Float)

    extra_metrics = Column(Text)

    camera_status = Column(String(30))

    internet_status = Column(String(30))

    device_type = Column(String(50))

    def __repr__(self):
        return f"<EngagementRecord {self.record_id}>"


