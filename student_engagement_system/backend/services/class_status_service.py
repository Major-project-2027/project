from models.session import Session
from models.enrollment import Enrollment
from models.engagement import EngagementRecord
from models.attendance import Attendance


class ClassStatusService:
    """Computes the real, DB-backed status/summary of a classroom for the
    class list views (teacher + student). Nothing here is invented --
    'live'/'completed'/'scheduled' is derived strictly from whether a
    session row exists and whether it has been ended."""

    @staticmethod
    def get_latest_session(db, class_id):

        return (
            db.query(Session)
            .filter(Session.class_id == class_id)
            .order_by(Session.session_id.desc())
            .first()
        )

    @staticmethod
    def summarize(db, classroom):

        session = ClassStatusService.get_latest_session(
            db, classroom.class_id
        )

        students_enrolled = (
            db.query(Enrollment)
            .filter(Enrollment.class_id == classroom.class_id)
            .count()
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
            present_ids = (
                db.query(EngagementRecord.student_id)
                .filter(EngagementRecord.session_id == session.session_id)
                .distinct()
                .all()
            )
            students_present = len(present_ids)

            scores = [
                float(r.engagement_score or 0)
                for r in (
                    db.query(EngagementRecord.engagement_score)
                    .filter(
                        EngagementRecord.session_id == session.session_id
                    )
                    .all()
                )
            ]

            if scores:
                avg_engagement = round(sum(scores) / len(scores))
        else:
            present_rows = (
                db.query(Attendance)
                .filter(
                    Attendance.session_id == session.session_id,
                    Attendance.status == 1,
                )
                .all()
            )
            students_present = len(present_rows)

            scores = [
                float(r.engagement_score or 0)
                for r in (
                    db.query(EngagementRecord.engagement_score)
                    .filter(
                        EngagementRecord.session_id == session.session_id
                    )
                    .all()
                )
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
