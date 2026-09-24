try:
    from database.mongo import COLLECTION_TEACHER_ROSTER
except ModuleNotFoundError:
    from backend.database.mongo import COLLECTION_TEACHER_ROSTER
from repositories.mongo._common import utcnow


class RosterRepository:
    """A teacher's managed student roster -- {teacher_id, student_id}
    documents. Per-class join permission is still the class's enrollment
    documents; the roster is the list the teacher picks those from."""

    @staticmethod
    def get_student_ids(db, teacher_id: int):
        return sorted(
            db[COLLECTION_TEACHER_ROSTER].distinct("student_id", {"teacher_id": teacher_id})
        )

    @staticmethod
    def set_student_ids(db, teacher_id: int, student_ids):
        wanted = set(student_ids)
        current = set(RosterRepository.get_student_ids(db, teacher_id))
        if current - wanted:
            db[COLLECTION_TEACHER_ROSTER].delete_many(
                {"teacher_id": teacher_id, "student_id": {"$in": list(current - wanted)}}
            )
        if wanted - current:
            now = utcnow()
            db[COLLECTION_TEACHER_ROSTER].insert_many([
                {"teacher_id": teacher_id, "student_id": student_id, "added_at": now}
                for student_id in sorted(wanted - current)
            ])
        return sorted(wanted)
