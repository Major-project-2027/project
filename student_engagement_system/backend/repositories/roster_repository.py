from sqlalchemy.orm import Session

from models.teacher_roster import TeacherRoster


def _ensure_table(db: Session):
    # New, additive table: created on first use (checkfirst) so existing
    # SQLite databases don't need a manual create_database.py run.
    TeacherRoster.__table__.create(bind=db.get_bind(), checkfirst=True)


class RosterRepository:

    @staticmethod
    def get_student_ids(db: Session, teacher_id: int):
        _ensure_table(db)
        return sorted(
            row[0]
            for row in db.query(TeacherRoster.student_id)
            .filter(TeacherRoster.teacher_id == teacher_id)
        )

    @staticmethod
    def set_student_ids(db: Session, teacher_id: int, student_ids):
        _ensure_table(db)
        wanted = set(student_ids)
        current = set(RosterRepository.get_student_ids(db, teacher_id))
        if current - wanted:
            (
                db.query(TeacherRoster)
                .filter(
                    TeacherRoster.teacher_id == teacher_id,
                    TeacherRoster.student_id.in_(current - wanted),
                )
                .delete(synchronize_session=False)
            )
        for student_id in wanted - current:
            db.add(TeacherRoster(teacher_id=teacher_id, student_id=student_id))
        db.commit()
        return sorted(wanted)
