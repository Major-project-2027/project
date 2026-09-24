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

    @staticmethod
    def summarize_many(db, classrooms):
        """{class_id: summarize(db, classroom)} for a whole list at once.

        Same result as calling summarize() per classroom, but on MongoDB
        it batches the work: summarize() costs ~4 round trips per
        classroom and loads every engagement record of each session into
        Python just to average one field -- for a teacher with 45
        classrooms that was 178 sequential Atlas queries and ~9,000
        documents, long enough to exceed gunicorn's worker timeout on
        Render's free tier (the Teacher Dashboard's "Couldn't load
        this"). Here it's 4 queries total, plus the existing distinct-
        student query per LIVE session only, and the averages are summed
        in the database. SQLite keeps the original per-classroom path."""

        from config import DB_BACKEND

        if DB_BACKEND != "mongodb":
            return {
                classroom.class_id: ClassStatusService.summarize(db, classroom)
                for classroom in classrooms
            }

        from database.mongo import (
            COLLECTION_ATTENDANCE,
            COLLECTION_CLASS_SESSIONS,
            COLLECTION_ENGAGEMENT_RECORDS,
            COLLECTION_ENROLLMENTS,
        )

        class_ids = [classroom.class_id for classroom in classrooms]

        # Latest session per class -- same rule as
        # get_latest_session_for_class(): highest session_id wins.
        latest = {}
        for doc in db[COLLECTION_CLASS_SESSIONS].find({"class_id": {"$in": class_ids}}):
            current = latest.get(doc["class_id"])
            if current is None or doc["session_id"] > current["session_id"]:
                latest[doc["class_id"]] = doc

        enrolled = {}
        for doc in db[COLLECTION_ENROLLMENTS].find(
            {"class_id": {"$in": class_ids}}, {"class_id": 1}
        ):
            enrolled[doc["class_id"]] = enrolled.get(doc["class_id"], 0) + 1

        session_ids = [doc["session_id"] for doc in latest.values()]

        # Same filter as summarize()'s `r.status == 1`.
        present = {}
        for doc in db[COLLECTION_ATTENDANCE].find(
            {"session_id": {"$in": session_ids}}, {"session_id": 1, "status": 1}
        ):
            if doc.get("status") == 1:
                present[doc["session_id"]] = present.get(doc["session_id"], 0) + 1

        # Same values as summarize()'s float(r.engagement_score or 0),
        # averaged over every record of the session.
        score_totals = {
            row["_id"]: (row["total"], row["count"])
            for row in db[COLLECTION_ENGAGEMENT_RECORDS].aggregate([
                {"$match": {"session_id": {"$in": session_ids}}},
                {"$group": {
                    "_id": "$session_id",
                    "total": {"$sum": {"$ifNull": ["$engagement_score", 0]}},
                    "count": {"$sum": 1},
                }},
            ])
        }

        summaries = {}
        for class_id in class_ids:
            session = latest.get(class_id)
            students_enrolled = enrolled.get(class_id, 0)

            if session is None:
                summaries[class_id] = {
                    "status": "scheduled",
                    "session_id": None,
                    "start_time": None,
                    "end_time": None,
                    "students_enrolled": students_enrolled,
                    "students_present": 0,
                    "avg_engagement": None,
                }
                continue

            session_id = session["session_id"]
            status = "live" if session.get("is_active") else "completed"

            if status == "live":
                students_present = len(
                    EngagementRepository.get_distinct_student_ids_for_session(db, session_id)
                )
            else:
                students_present = present.get(session_id, 0)

            avg_engagement = None
            if session_id in score_totals:
                total, count = score_totals[session_id]
                avg_engagement = round(float(total) / count)

            summaries[class_id] = {
                "status": status,
                "session_id": session_id,
                "start_time": session.get("start_time"),
                "end_time": session.get("end_time"),
                "students_enrolled": students_enrolled,
                "students_present": students_present,
                "avg_engagement": avg_engagement,
            }

        return summaries
