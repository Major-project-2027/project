from sqlalchemy.orm import Session

from models.engagement import EngagementRecord


class EngagementRepository:

    @staticmethod
    def create(db: Session, record: EngagementRecord):

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    @staticmethod
    def get_session_records(
        db: Session,
        session_id: int
    ):
        return (
            db.query(EngagementRecord)
            .filter(
                EngagementRecord.session_id == session_id
            )
            .order_by(
                EngagementRecord.timestamp.asc()
            )
            .all()
        )

    @staticmethod
    def get_student_session_records(
        db: Session,
        session_id: int,
        student_id: int
    ):
        return (
            db.query(EngagementRecord)
            .filter(
                EngagementRecord.session_id == session_id,
                EngagementRecord.student_id == student_id
            )
            .order_by(
                EngagementRecord.timestamp.asc()
            )
            .all()
        )

    @staticmethod
    def get_completed_session_records_for_student(
        db: Session,
        student_id: int,
    ):
        """This student's engagement_records from every session that has
        actually ENDED (Session.is_active == False), across their whole
        history -- ordered chronologically by session start_time then
        record timestamp. This is the raw material for the cross-session
        historical/future-engagement prediction (see
        EngagementPredictionService.get_future_prediction); the current
        live session (is_active == True) is always excluded, and results
        are never mixed across students."""

        from models.session import Session as ClassSession

        return (
            db.query(EngagementRecord)
            .join(
                ClassSession,
                EngagementRecord.session_id == ClassSession.session_id,
            )
            .filter(
                EngagementRecord.student_id == student_id,
                ClassSession.is_active == False,  # noqa: E712
            )
            .order_by(
                ClassSession.start_time.asc(),
                EngagementRecord.timestamp.asc(),
            )
            .all()
        )

    @staticmethod
    def get_recent_student_session_records(
        db: Session,
        session_id: int,
        student_id: int,
        since,
    ):
        """Same (session_id, student_id) isolation as
        get_student_session_records, but scoped to a recent time window
        (e.g. the last 30-60s) instead of the whole session -- used by the
        engagement prediction service so each prediction cycle only reads
        a bounded slice of history rather than the session's full,
        ever-growing record set."""

        return (
            db.query(EngagementRecord)
            .filter(
                EngagementRecord.session_id == session_id,
                EngagementRecord.student_id == student_id,
                EngagementRecord.timestamp >= since,
            )
            .order_by(
                EngagementRecord.timestamp.asc()
            )
            .all()
        )

