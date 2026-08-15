from sqlalchemy.orm import Session

from models.attendance import Attendance


class AttendanceRepository:

    @staticmethod
    def upsert(
        db: Session,
        session_id: int,
        class_id: int,
        student_id: int,
        status: int,
    ):
        """Create or update the attendance row for this (session, student).

        Re-ending a session (or re-running finalization) must not create
        duplicate rows for the same student/session pair.
        """

        existing = (
            db.query(Attendance)
            .filter(
                Attendance.session_id == session_id,
                Attendance.student_id == student_id,
            )
            .first()
        )

        if existing:
            existing.status = status
            db.commit()
            db.refresh(existing)
            return existing

        record = Attendance(
            session_id=session_id,
            class_id=class_id,
            student_id=student_id,
            status=status,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    @staticmethod
    def get_by_session(db: Session, session_id: int):

        return (
            db.query(Attendance)
            .filter(Attendance.session_id == session_id)
            .all()
        )

    @staticmethod
    def get_by_session_and_student(
        db: Session,
        session_id: int,
        student_id: int,
    ):

        return (
            db.query(Attendance)
            .filter(
                Attendance.session_id == session_id,
                Attendance.student_id == student_id,
            )
            .first()
        )

    @staticmethod
    def get_for_teacher(db: Session, teacher_id: int):

        from models.classroom import Classroom
        from models.session import Session as ClassSession

        return (
            db.query(Attendance)
            .join(
                ClassSession,
                Attendance.session_id == ClassSession.session_id,
            )
            .join(
                Classroom,
                Attendance.class_id == Classroom.class_id,
            )
            .filter(Classroom.teacher_id == teacher_id)
            .all()
        )

    @staticmethod
    def get_for_student(db: Session, student_id: int):

        return (
            db.query(Attendance)
            .filter(Attendance.student_id == student_id)
            .all()
        )
