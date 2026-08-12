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

