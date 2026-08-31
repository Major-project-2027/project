from repositories.active import (
    SessionRepository,
    EnrollmentRepository,
    EngagementRepository,
    AttendanceRepository,
)


class ClassStatusService:
    """Computes the real, DB-backed status/summary of a classroom for the
    class list views (teacher + student). Nothing here is invented --
    'live'/'completed'/'scheduled' is derived strictly from whether a
    session row exists and whether it has been ended.

    Every query goes through repositories.active (backend-agnostic --
    SQLite or MongoDB, whichever config.DB_BACKEND selects) rather than
    inline SQLAlchemy queries, so this service works unchanged under
    either backend."""

    @staticmethod
    def get_latest_session(db, class_id):
        return SessionRepository.get_latest_session_for_class(db, class_id)

    @staticmethod
    def summarize(db, classroom):

        session = ClassStatusService.get_latest_session(
            db, classroom.class_id
        )

        students_enrolled = EnrollmentRepository.count_for_class(
            db, classroom.class_id
        )

        if session is None:
            return {
                "status": "scheduled",
                "session_id": None,
                "start_time": None,
                "end_time": None,
                "students_enrolled": students_enrolled,
                "students_present": 0,
                "avg_engagement": None,
            }

        status = "live" if session.is_active else "completed"

        students_present = 0
        avg_engagement = None

        if status == "live":
            present_ids = EngagementRepository.get_distinct_student_ids_for_session(
                db, session.session_id
            )
            students_present = len(present_ids)

            scores = [
                float(r.engagement_score or 0)
                for r in EngagementRepository.get_session_records(db, session.session_id)
            ]

            if scores:
                avg_engagement = round(sum(scores) / len(scores))
        else:
            present_rows = [
                r for r in AttendanceRepository.get_by_session(db, session.session_id)
                if r.status == 1
            ]
            students_present = len(present_rows)

            scores = [
                float(r.engagement_score or 0)
                for r in EngagementRepository.get_session_records(db, session.session_id)
            ]

            if scores:
                avg_engagement = round(sum(scores) / len(scores))

        return {
            "status": status,
            "session_id": session.session_id,
            "start_time": session.start_time,
            "end_time": session.end_time,
            "students_enrolled": students_enrolled,
            "students_present": students_present,
            "avg_engagement": avg_engagement,
        }
