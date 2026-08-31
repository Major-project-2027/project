import urllib.request
import json
from datetime import datetime, timezone

from config import FASTAPI_INTERNAL_URL

from models.session import Session
from repositories.active import (
    SessionRepository,
    ClassroomRepository,
    EngagementRepository,
    AttendanceRepository,
    EnrollmentRepository,
)

# The AI/monitoring pipeline runs in the separate FastAPI process (port 8000
# locally; a separate Render service in production) and keeps its own
# in-memory per-(session, student) state. This Flask process cannot reach
# into that memory directly, so ending a session here notifies the AI
# service over HTTP (best-effort -- ending the class must never fail just
# because the AI service happens to be unreachable).
AI_SERVICE_BASE_URL = FASTAPI_INTERNAL_URL

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

        enrollments = EnrollmentRepository.get_for_class(db, session.class_id)

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
    def _refresh_future_predictions(db, session):
        """Regenerate the cross-session HISTORICAL/FUTURE engagement
        prediction (EngagementPredictionService.get_future_prediction) for
        every student who actually produced engagement data in the
        session that was JUST finalized as completed -- the explicit
        event this feature's regeneration is tied to (never per-frame,
        never per-dashboard-poll; see that method's own staleness check
        for the read-side counterpart of this same policy)."""

        from services.engagement_prediction_service import EngagementPredictionService

        records = EngagementRepository.get_session_records(db, session.session_id)
        student_ids = {r.student_id for r in records}

        for student_id in student_ids:
            try:
                EngagementPredictionService.get_future_prediction(
                    db, student_id, force_refresh=True
                )
            except Exception:
                # Best-effort -- ending the class must never fail because
                # one student's historical prediction couldn't be
                # (re)computed.
                pass

    @staticmethod
    def _compute_cognitive_states(db, session):
        """Compute and persist the session-level cognitive-state summary
        (Focused/Neutral/Distracted/Drowsy -- see
        services/cognitive_state_service.py for the full method) for
        every student who actually produced engagement data in the
        session that was JUST finalized as completed. This is the ONE
        place this summary is calculated -- never recomputed on every
        teacher-dashboard read (see CognitiveStateRepository.get_by_session,
        the read-only path app/routes/teacher.py's class_history() uses)."""

        from services.cognitive_state_service import CognitiveStateService

        records = EngagementRepository.get_session_records(db, session.session_id)
        student_ids = {r.student_id for r in records}

        for student_id in student_ids:
            try:
                CognitiveStateService.compute_and_store(
                    db,
                    session_id=session.session_id,
                    class_id=session.class_id,
                    student_id=student_id,
                )
            except Exception:
                # Best-effort -- ending the class must never fail because
                # one student's cognitive-state summary couldn't be
                # computed.
                pass

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

        # A plain Python datetime (not sqlalchemy.sql.func.now(), a
        # server-side SQL expression object) -- works identically for
        # both the SQLite path (SQLAlchemy sends it as a literal UPDATE
        # parameter, same practical effect as NOW()) and the MongoDB
        # path (a real value pymongo can serialize; a func.now()
        # expression object cannot be).
        active_session.end_time = datetime.now(timezone.utc)

        session = SessionRepository.end_session(
            db,
            active_session,
        )

        SessionService._finalize_attendance(db, session)

        SessionService._refresh_future_predictions(db, session)

        SessionService._compute_cognitive_states(db, session)

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

