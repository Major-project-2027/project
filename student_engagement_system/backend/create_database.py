from database.database import engine
from database.base import Base

from models.teacher import Teacher
from models.student import Student
from models.classroom import Classroom
from models.session import Session
from models.engagement import EngagementRecord
from models.face_registration import FaceRegistration
from models.enrollment import Enrollment
from models.attendance import Attendance


print("=" * 60)
print("Creating Database...")
print("=" * 60)

Base.metadata.create_all(bind=engine)

print("\n✅ Database Created Successfully!")

print("\nCreated Tables:")

for table in Base.metadata.tables.keys():
    print(f"✔ {table}")

