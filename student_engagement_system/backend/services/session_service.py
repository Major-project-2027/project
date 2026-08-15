import urllib.request
import json

from models.session import Session
from repositories.session_repository import SessionRepository
from repositories.classroom_repository import ClassroomRepository
from repositories.engagement_repository import EngagementRepository
from repositories.attendance_repository import AttendanceRepository

# The AI/monitoring pipeline runs in the separate FastAPI process (port 8000)
# and keeps its own in-memory per-(session, student) state. This Flask
# process cannot reach into that memory directly, so ending a session here
# notifies the AI service over HTTP (best-effort -- ending the class must
# never fail just because the AI service happens to be unreachable).
AI_SERVICE_BASE_URL = "http://127.0.0.1:8000"

# Attendance rule: PRESENT only if the student actually generated engagement
# samples AND both their average AND their latest engagement score exceed
# this threshold. Mirrors the spec used elsewhere in this project.
ATTENDANCE_ENGAGEMENT_THRESHOLD = 50


class SessionService:

    @staticmethod
    def _notify_ai_service_session_ended(session_id):
        try:
            request = urllib.request.Request(
                f"{AI_SERVICE_BASE_URL}/ai/clear-session/{session_id}",
                method="POST",
            )
            urllib.request.urlopen(request, timeout=2)
        except Exception:
            # Best-effort only -- the FastAPI process may be down, or the
            # session may simply have no AI state to clear.
            pass

    @staticmethod
    def _finalize_attendance(db, session):
        """Compute and persist attendance for every student who actually
        joined this class, using ONLY real engagement_records already
        collected during the session. No values are invented: a student
        with zero samples is marked absent, never silently skipped."""

        from models.enrollment import Enrollment

        enrollments = (
            db.query(Enrollment)
            .filter(Enrollment.class_id == session.class_id)
            .all()
        )

        records = EngagementRepository.get_session_records(
            db,
            session.session_id,
        )

        records_by_student = {}
        for record in records:
            records_by_student.setdefault(
                record.student_id, []
            ).append(record)

        for enrollment in enrollments:
            student_records = records_by_student.get(
                enrollment.student_id, []
            )

            if not student_records:
                status = 0
            else:
                scores = [
                    float(r.engagement_score or 0)
                    for r in student_records
                ]

                average_engagement = sum(scores) / len(scores)
                latest_engagement = scores[-1]

                status = (
                    1
                    if (
                        average_engagement > ATTENDANCE_ENGAGEMENT_THRESHOLD
                        and latest_engagement > ATTENDANCE_ENGAGEMENT_THRESHOLD
                    )
                    else 0
                )

            AttendanceRepository.upsert(
                db,
                session_id=session.session_id,
                class_id=session.class_id,
                student_id=enrollment.student_id,
                status=status,
            )

    @staticmethod
    def end_session(db, teacher_id, class_id):

        active_session = SessionRepository.get_active_session(
            db,
            class_id,
        )

        if not active_session:
            raise Exception("No active session found.")

        if active_session.teacher_id != teacher_id:
            raise Exception("You are not authorized to end this session.")

        from sqlalchemy.sql import func as sql_func
        active_session.end_time = sql_func.now()

        session = SessionRepository.end_session(
            db,
            active_session,
        )

        SessionService._finalize_attendance(db, session)

        SessionService._notify_ai_service_session_ended(
            session.session_id
        )

        return session

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

