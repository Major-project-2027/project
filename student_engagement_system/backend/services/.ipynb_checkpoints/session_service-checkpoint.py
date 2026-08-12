from models.session import Session
from repositories.session_repository import SessionRepository
from repositories.classroom_repository import ClassroomRepository


class SessionService:

    @staticmethod
    def start_session(db, teacher_id, class_id):

        classroom = ClassroomRepository.get_classroom_by_id(
            db,
            class_id
        )

        if not classroom:
            raise Exception("Classroom not found.")

        if classroom.teacher_id != teacher_id:
            raise Exception("You are not authorized.")

        active = SessionRepository.get_active_session(
            db,
            class_id
        )

        if active:
            raise Exception("Session already active.")

        session = Session(
            class_id=class_id,
            teacher_id=teacher_id
        )

        return SessionRepository.create_session(
            db,
            session
        )

