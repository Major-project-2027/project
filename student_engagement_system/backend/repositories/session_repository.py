from sqlalchemy.orm import Session

from models.session import Session as ClassSession


class SessionRepository:

    @staticmethod
    def create_session(db: Session, session: ClassSession):

        db.add(session)

        db.commit()

        db.refresh(session)

        return session

    @staticmethod
    def get_active_session(db: Session, class_id: int):

        return (
            db.query(ClassSession)
            .filter(
                ClassSession.class_id == class_id,
                ClassSession.is_active == True
            )
            .first()
        )

    @staticmethod
    def get_all_active_sessions(db: Session):
        """Every session currently marked live, across every teacher and
        class -- used to let any authenticated student discover and join
        a live class without needing its code."""

        return (
            db.query(ClassSession)
            .filter(ClassSession.is_active == True)
            .order_by(ClassSession.start_time.desc())
            .all()
        )

    @staticmethod
    def end_session(db: Session, session):

        session.is_active = False

        db.commit()

        db.refresh(session)

        return session

    @staticmethod
    def get_by_id(db: Session, session_id: int):
        return (
            db.query(ClassSession)
            .filter(ClassSession.session_id == session_id)
            .first()
        )

    @staticmethod
    def get_latest_session_for_class(db: Session, class_id: int):
        """Most recent session for this class REGARDLESS of active
        status -- distinct from get_active_session (is_active == True
        only). Used by class_history (teacher's class report always
        shows the latest session, live or completed) and
        ClassStatusService."""

        return (
            db.query(ClassSession)
            .filter(ClassSession.class_id == class_id)
            .order_by(ClassSession.session_id.desc())
            .first()
        )

