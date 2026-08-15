from sqlalchemy import func
from sqlalchemy.orm import Session

from models.alert import Alert


class AlertRepository:

    @staticmethod
    def create(
        db: Session,
        session_id: int,
        class_id: int,
        student_id: int,
        alert_type: str,
    ):

        record = Alert(
            session_id=session_id,
            class_id=class_id,
            student_id=student_id,
            alert_type=alert_type,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    @staticmethod
    def counts_by_type(db: Session, session_id: int, student_id: int):

        rows = (
            db.query(Alert.alert_type, func.count(Alert.alert_id))
            .filter(
                Alert.session_id == session_id,
                Alert.student_id == student_id,
            )
            .group_by(Alert.alert_type)
            .all()
        )

        return {alert_type: count for alert_type, count in rows}

    @staticmethod
    def list_for_session_student(
        db: Session,
        session_id: int,
        student_id: int,
    ):

        return (
            db.query(Alert)
            .filter(
                Alert.session_id == session_id,
                Alert.student_id == student_id,
            )
            .order_by(Alert.created_at.asc())
            .all()
        )
