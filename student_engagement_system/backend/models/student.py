from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class Student(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True, index=True)

    usn = Column(String(30), unique=True, nullable=False)

    name = Column(String(100), nullable=False)

    email = Column(String(100), unique=True, nullable=False)

    password_hash = Column(String(255), nullable=False)

    department = Column(String(100), nullable=False)

    semester = Column(Integer, nullable=False)

    section = Column(String(10), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Student {self.name}>"

