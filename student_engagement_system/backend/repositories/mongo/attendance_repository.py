try:
    from database.mongo import COLLECTION_ATTENDANCE
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_ATTENDANCE
try:
    from database.mongo_counters import next_id, COUNTER_ATTENDANCE_ID
except ModuleNotFoundError:
    from backend.database.mongo_counters import next_id, COUNTER_ATTENDANCE_ID
from models.attendance import Attendance
from repositories.mongo._common import doc_to_model, docs_to_models, utcnow


class AttendanceRepository:

    @staticmethod
    def upsert(db, session_id: int, class_id: int, student_id: int, status: int):
        existing = AttendanceRepository.get_by_session_and_student(db, session_id, student_id)

        if existing:
            db[COLLECTION_ATTENDANCE].update_one(
                {"session_id": session_id, "student_id": student_id},
                {"$set": {"status": status, "class_id": class_id}},
            )
            existing.status = status
            existing.class_id = class_id
            return existing

        attendance_id = next_id(db, COUNTER_ATTENDANCE_ID)
        created_at = utcnow()

        db[COLLECTION_ATTENDANCE].insert_one({
            "attendance_id": attendance_id,
            "session_id": session_id,
            "class_id": class_id,
            "student_id": student_id,
            "status": status,
            "created_at": created_at,
        })

        return Attendance(
            attendance_id=attendance_id,
            session_id=session_id,
            class_id=class_id,
            student_id=student_id,
            status=status,
            created_at=created_at,
        )

    @staticmethod
    def get_by_session(db, session_id: int):
        return docs_to_models(
            Attendance, db[COLLECTION_ATTENDANCE].find({"session_id": session_id})
        )

    @staticmethod
    def get_by_session_and_student(db, session_id: int, student_id: int):
        return doc_to_model(
            Attendance,
            db[COLLECTION_ATTENDANCE].find_one(
                {"session_id": session_id, "student_id": student_id}
            ),
        )

    @staticmethod
    def get_for_teacher(db, teacher_id: int):
        """App-level equivalent of the SQL double JOIN
        (attendance -> class_sessions -> classrooms, filtered by
        teacher_id)."""

        from database.mongo import COLLECTION_CLASSROOMS

        class_ids = [
            c["class_id"]
            for c in db[COLLECTION_CLASSROOMS].find(
                {"teacher_id": teacher_id}, {"class_id": 1}
            )
        ]

        if not class_ids:
            return []

        return docs_to_models(
            Attendance, db[COLLECTION_ATTENDANCE].find({"class_id": {"$in": class_ids}})
        )

    @staticmethod
    def get_for_student(db, student_id: int):
        return docs_to_models(
            Attendance, db[COLLECTION_ATTENDANCE].find({"student_id": student_id})
        )
