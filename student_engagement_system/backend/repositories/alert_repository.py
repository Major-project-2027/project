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
    def counts_by_type_for_sessions(
        db: Session,
        student_id: int,
        session_ids: list,
    ):
        """Same (student_id-isolated) alert-type counts as counts_by_type,
        grouped by session too -- lets the historical future-engagement
        feature pipeline fetch every completed session's alert counts in
        one query instead of one per session.

        Returns {session_id: {alert_type: count}}.
        """

        if not session_ids:
            return {}

        rows = (
            db.query(Alert.session_id, Alert.alert_type, func.count(Alert.alert_id))
            .filter(
                Alert.student_id == student_id,
                Alert.session_id.in_(session_ids),
            )
            .group_by(Alert.session_id, Alert.alert_type)
            .all()
        )

        result: dict = {}
        for session_id, alert_type, count in rows:
            result.setdefault(session_id, {})[alert_type] = count

        return result

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
