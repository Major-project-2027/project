from database.database import SessionLocal
from models.classroom import Classroom

db = SessionLocal()

classes = db.query(Classroom).all()

print("\n===== CLASSROOMS =====")

if not classes:
    print("No classrooms found.")
else:
    for c in classes:
        print(
            f"ID: {c.class_id} | "
            f"Name: {c.classroom_name} | "
            f"Teacher ID: {c.teacher_id} | "
            f"Code: {c.class_code}"
        )

db.close()

