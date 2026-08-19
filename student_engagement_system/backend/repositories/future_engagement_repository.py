from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.future_engagement_prediction import FutureEngagementPrediction


class FutureEngagementRepository:

    @staticmethod
    def get_by_student(db: Session, student_id: int):

        return (
            db.query(FutureEngagementPrediction)
            .filter(FutureEngagementPrediction.student_id == student_id)
            .first()
        )

    @staticmethod
    def get_for_students(db: Session, student_ids: list):

        if not student_ids:
            return []

        return (
            db.query(FutureEngagementPrediction)
            .filter(FutureEngagementPrediction.student_id.in_(student_ids))
            .all()
        )

    @staticmethod
    def upsert(
        db: Session,
        student_id: int,
        status: str,
        prediction_score,
        historical_sessions_used: int,
        model_version,
        reason,
    ):
        """Create or update THIS student's one cached prediction row --
        never a second row for the same student (student_id is unique)."""

        existing = FutureEngagementRepository.get_by_student(db, student_id)

        now = datetime.now(timezone.utc)

        if existing:
            existing.status = status
            existing.prediction_score = prediction_score
            existing.historical_sessions_used = historical_sessions_used
            existing.model_version = model_version
            existing.reason = reason
            existing.generated_at = now

            db.commit()
            db.refresh(existing)

            return existing

        record = FutureEngagementPrediction(
            student_id=student_id,
            status=status,
            prediction_score=prediction_score,
            historical_sessions_used=historical_sessions_used,
            model_version=model_version,
            reason=reason,
            generated_at=now,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record
