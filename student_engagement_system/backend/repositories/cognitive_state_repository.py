from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.cognitive_state import CognitiveStateSummary


class CognitiveStateRepository:

    @staticmethod
    def get_by_session_and_student(
        db: Session,
        session_id: int,
        student_id: int,
    ):
        return (
            db.query(CognitiveStateSummary)
            .filter(
                CognitiveStateSummary.session_id == session_id,
                CognitiveStateSummary.student_id == student_id,
            )
            .first()
        )

    @staticmethod
    def get_by_session(db: Session, session_id: int):
        """All students' summaries for one session, keyed by student_id --
        lets the class-report route read every student's result in one
        query instead of one per student."""

        rows = (
            db.query(CognitiveStateSummary)
            .filter(CognitiveStateSummary.session_id == session_id)
            .all()
        )

        return {row.student_id: row for row in rows}

    @staticmethod
    def upsert(
        db: Session,
        session_id: int,
        class_id: int,
        student_id: int,
        status: str,
        cognitive_state,
        focused_percentage,
        neutral_percentage,
        distracted_percentage,
        valid_sample_count: int,
        drowsy_episode_count: int,
        reason,
    ):
        """Create or update THIS (session, student)'s one summary row --
        re-ending a session (or re-running finalization) must never create
        a duplicate row for the same session/student pair."""

        existing = CognitiveStateRepository.get_by_session_and_student(
            db, session_id, student_id,
        )

        now = datetime.now(timezone.utc)

        if existing:
            existing.status = status
            existing.cognitive_state = cognitive_state
            existing.focused_percentage = focused_percentage
            existing.neutral_percentage = neutral_percentage
            existing.distracted_percentage = distracted_percentage
            existing.valid_sample_count = valid_sample_count
            existing.drowsy_episode_count = drowsy_episode_count
            existing.reason = reason
            existing.calculated_at = now

            db.commit()
            db.refresh(existing)

            return existing

        record = CognitiveStateSummary(
            session_id=session_id,
            class_id=class_id,
            student_id=student_id,
            status=status,
            cognitive_state=cognitive_state,
            focused_percentage=focused_percentage,
            neutral_percentage=neutral_percentage,
            distracted_percentage=distracted_percentage,
            valid_sample_count=valid_sample_count,
            drowsy_episode_count=drowsy_episode_count,
            reason=reason,
            calculated_at=now,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record
