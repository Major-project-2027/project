from flask import Blueprint, request, jsonify
import traceback
from schemas.classroom_update_schema import ClassroomUpdate

from database.db_provider import get_db, close_db, is_mongo
from schemas.teacher_schema import TeacherRegister
from schemas.teacher_login_schema import TeacherLogin
from schemas.classroom_schema import ClassroomCreate

from services.teacher_service import TeacherService
from services.classroom_service import ClassroomService
from services.jwt_service import JWTService
from services.session_service import SessionService
from services.class_status_service import ClassStatusService
from repositories.active import (
    AttendanceRepository,
    AlertRepository,
    CognitiveStateRepository,
    EngagementRepository,
    StudentRepository,
    ClassroomRepository,
    SessionRepository,
    EnrollmentRepository,
)
teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.route("/teacher/register", methods=["POST"])
def register_teacher():

    db = get_db()

    try:

        data = TeacherRegister(**request.json)

        teacher = TeacherService.register_teacher(db, data)

        return jsonify({
            "success": True,
            "teacher_id": teacher.teacher_id,
            "message": "Teacher Registered Successfully"
        }), 201

    except Exception as e:
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)


@teacher_bp.route("/teacher/login", methods=["POST"])
def login_teacher():

    db = get_db()

    try:

        data = TeacherLogin(**request.json)

        result = TeacherService.login_teacher(db, data)

        return jsonify({
            "success": True,
            "teacher_id": result["teacher"].teacher_id,
            "name": result["teacher"].name,
            "message": "Login Successful",
            "token": result["token"]
        })

    except Exception as e:
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)


@teacher_bp.route("/teacher/create-classroom", methods=["POST"])
def create_classroom():

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        data = ClassroomCreate(**request.json)

        classroom = ClassroomService.create_classroom(
            db,
            payload["user_id"],
            data
        )

        return jsonify({
            "success": True,
            "class_id": classroom.class_id,
            "class_code": classroom.class_code,
            "message": "Classroom Created Successfully"
        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route("/teacher/classrooms", methods=["GET"])
def get_teacher_classrooms():

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        classrooms = ClassroomService.get_teacher_classrooms(
            db,
            payload["user_id"]
        )

        def serialize(classroom):
            summary = ClassStatusService.summarize(db, classroom)

            return {
                "class_id": classroom.class_id,
                "classroom_name": classroom.classroom_name,
                "subject": classroom.subject,
                "semester": classroom.semester,
                "section": classroom.section,
                "class_code": classroom.class_code,
                "meeting_link": classroom.meeting_link,
                "status": summary["status"],
                "session_id": summary["session_id"],
                "start_time": summary["start_time"],
                "end_time": summary["end_time"],
                "students_enrolled": summary["students_enrolled"],
                "students_present": summary["students_present"],
                "avg_engagement": summary["avg_engagement"],
            }

        return jsonify({
            "success": True,
            "classrooms": [
                serialize(classroom)
                for classroom in classrooms
            ]
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route("/teacher/classroom/<int:class_id>", methods=["GET"])
def get_classroom(class_id):

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        JWTService.verify_token(token)

        classroom = ClassroomService.get_classroom(
            db,
            class_id
        )

        return jsonify({
            "success": True,
            "classroom": {
                "class_id": classroom.class_id,
                "classroom_name": classroom.classroom_name,
                "subject": classroom.subject,
                "semester": classroom.semester,
                "section": classroom.section,
                "teacher_id": classroom.teacher_id,
                "class_code": classroom.class_code,
                "meeting_link": classroom.meeting_link
            }
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route("/teacher/classroom/<int:class_id>", methods=["PUT"])
def update_classroom(class_id):

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        data = ClassroomUpdate(**request.json)

        classroom = ClassroomService.update_classroom(
            db,
            class_id,
            payload["user_id"],
            data
        )

        return jsonify({
            "success": True,
            "message": "Classroom Updated Successfully",
            "classroom": {
                "class_id": classroom.class_id,
                "classroom_name": classroom.classroom_name,
                "subject": classroom.subject,
                "semester": classroom.semester,
                "section": classroom.section,
                "class_code": classroom.class_code
            }
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route("/teacher/classroom/<int:class_id>", methods=["DELETE"])
def delete_classroom(class_id):

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        JWTService.verify_token(token)

        ClassroomService.delete_classroom(
            db,
            class_id
        )

        return jsonify({
            "success": True,
            "message": "Classroom Deleted Successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route("/dashboard", methods=["GET"])
def teacher_dashboard():

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        dashboard = TeacherService.get_dashboard(
            db,
            payload["user_id"]
        )

        return jsonify({
            "success": True,
            "dashboard": dashboard
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route("/teacher/start-session/<int:class_id>", methods=["POST"])
def start_session(class_id):

    db = get_db()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        session = SessionService.start_session(
            db,
            payload["user_id"],
            class_id
        )

        return jsonify({
            "success": True,
            "message": "Session Started Successfully",
            "session": {
                "session_id": session.session_id,
                "class_id": session.class_id,
                "teacher_id": session.teacher_id,
                "is_active": session.is_active
            }
        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)

@teacher_bp.route("/teacher/end-session/<int:class_id>", methods=["POST"])
def end_session(class_id):

    db = get_db()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        session = SessionService.end_session(
            db,
            payload["user_id"],
            class_id
        )

        return jsonify({
            "success": True,
            "message": "Session Ended Successfully",
            "session": {
                "session_id": session.session_id,
                "class_id": session.class_id,
                "teacher_id": session.teacher_id,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "is_active": session.is_active
            }
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)
@teacher_bp.route(
    "/teacher/classroom/<int:class_id>/history",
    methods=["GET"]
)
def class_history(class_id):

    db = get_db()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]
        payload = JWTService.verify_token(token)

        classroom = ClassroomService.get_classroom(
            db,
            class_id
        )

        if classroom.teacher_id != payload["user_id"]:
            raise Exception("You are not authorized.")

        active_session = SessionRepository.get_latest_session_for_class(
            db, class_id
        )

        if not active_session:
            return jsonify({
                "success": True,
                "class": {
                    "class_id": classroom.class_id,
                    "class_name": classroom.classroom_name,
                    "subject": classroom.subject,
                },
                "students": []
            })

        # Every distinct student with at least one engagement_records row
        # in this session, then each one's name/usn -- app-level
        # equivalent of the SQL INNER JOIN + DISTINCT (backend-agnostic:
        # both repository calls work identically under SQLite or
        # MongoDB, see repositories.active).
        distinct_student_ids = EngagementRepository.get_distinct_student_ids_for_session(
            db, active_session.session_id
        )

        students = []
        for student_id in distinct_student_ids:
            student = StudentRepository.get_by_id(db, student_id)
            if student:
                students.append((student.student_id, student.name, student.usn))

        result = []

        # One query for every student's cognitive-state summary in this
        # session, instead of one per student -- see
        # CognitiveStateRepository.get_by_session. Summaries are read-only
        # here: they were already computed ONCE when the session ended
        # (services/session_service.py's SessionService.end_session ->
        # _compute_cognitive_states), never recomputed on this GET.
        cognitive_states = CognitiveStateRepository.get_by_session(
            db,
            active_session.session_id,
        )

        for student_id, student_name, student_usn in students:

            records = EngagementRepository.get_student_session_records(
                db, active_session.session_id, student_id
            )

            if not records:
                continue

            scores = [
                float(r.engagement_score or 0)
                for r in records
            ]

            attendance = AttendanceRepository.get_by_session_and_student(
                db,
                active_session.session_id,
                student_id,
            )

            alert_counts = AlertRepository.counts_by_type(
                db,
                active_session.session_id,
                student_id,
            )

            result.append({
                "studentId": student_id,
                "studentName": student_name,
                "usn": student_usn,

                "attendanceStatus": (
                    "present"
                    if attendance and attendance.status == 1
                    else "absent"
                    if attendance
                    else "unknown"
                ),

                "averageEngagement": round(
                    sum(scores) / len(scores)
                ),

                "finalEngagement": round(
                    scores[-1]
                ),

                "minEngagement": round(
                    min(scores)
                ),

                "maxEngagement": round(
                    max(scores)
                ),

                "sampleCount": len(records),

                "phoneDetections": sum(
                    1 for r in records
                    if r.phone_detected
                ),

                "multiplePersonDetections": sum(
                    1 for r in records
                    if r.multiple_person
                ),

                "lookingAwayCount": alert_counts.get(
                    "looking_away", 0
                ),

                "attentionDropCount": alert_counts.get(
                    "attention_drop_predicted", 0
                ),

                "totalAlerts": sum(alert_counts.values()),

                "blinkCount": (
                    records[-1].blink_count
                    if records[-1].blink_count is not None
                    else 0
                ),

                # Session-level, rule-based cognitive-state summary (see
                # services/cognitive_state_service.py) -- read-only here.
                # None when the session hasn't ended yet (no summary
                # computed at all), never fabricated.
                "cognitiveState": (
                    {
                        "status": cognitive_states[student_id].status,
                        "state": cognitive_states[student_id].cognitive_state,
                        "focusedPercentage": cognitive_states[student_id].focused_percentage,
                        "neutralPercentage": cognitive_states[student_id].neutral_percentage,
                        "distractedPercentage": cognitive_states[student_id].distracted_percentage,
                        "drowsyEpisodeCount": cognitive_states[student_id].drowsy_episode_count,
                        "reason": cognitive_states[student_id].reason,
                    }
                    if student_id in cognitive_states
                    else {
                        "status": "not_available",
                        "state": None,
                        "focusedPercentage": None,
                        "neutralPercentage": None,
                        "distractedPercentage": None,
                        "drowsyEpisodeCount": 0,
                        "reason": (
                            "Not yet available -- calculated once the class ends."
                            if active_session.is_active
                            else "Not yet available for this session."
                        ),
                    }
                ),

                "snapshots": [
                    {
                        "timestamp": r.timestamp,
                        "engagementScore": r.engagement_score,
                        "emotion": r.emotion,
                        "blinkCount": r.blink_count,
                        "headPose": r.head_pose,
                        "gaze": r.gaze,
                        "phoneDetected": r.phone_detected,
                        "multiplePerson": r.multiple_person,
                        "engagementStatus": r.engagement_status,
                    }
                    for r in records
                ],
            })

        return jsonify({
            "success": True,
            "class": {
                "class_id": classroom.class_id,
                "class_name": classroom.classroom_name,
                "subject": classroom.subject,
                "session_id": active_session.session_id,
                "start_time": active_session.start_time,
                "end_time": active_session.end_time,
                "is_active": active_session.is_active,
            },
            "students": result,
        }), 200

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)


@teacher_bp.route("/teacher/future-engagement-predictions", methods=["GET"])
def teacher_future_engagement_predictions():
    """Every student enrolled in ANY of this teacher's classrooms (same
    Classroom.teacher_id authorization scoping used everywhere else in
    this file -- never a different teacher's students), each with their
    latest cross-session HISTORICAL/FUTURE engagement prediction.

    Returns two separate lists rather than one sortable-by-score list so
    the frontend never has to invent a sentinel score for "no prediction
    yet" -- `ready` is sorted ascending by predictedScore (lowest first,
    per spec); `insufficient` (insufficient_data/unavailable/error) is
    returned separately and must never be treated as, or sorted as if
    it were, a 0% prediction.
    """

    db = get_db()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]
        payload = JWTService.verify_token(token)
        teacher_id = payload["user_id"]

        from services.engagement_prediction_service import (
            EngagementPredictionService,
            future_prediction_status_label,
        )

        students = EnrollmentRepository.get_teacher_students(db, teacher_id)

        ready = []
        insufficient = []

        for student in students:

            result = EngagementPredictionService.get_future_prediction(
                db, student.student_id
            )

            row = {
                "studentId": student.student_id,
                "studentName": student.name,
                "usn": student.usn,
                "status": result["status"],
                "predictionScore": result["prediction_score"],
                "statusLabel": future_prediction_status_label(result),
                "historicalSessionsUsed": result["historical_sessions_used"],
                "generatedAt": result["generated_at"],
                "reason": result["reason"],
            }

            if result["status"] == "ready" and result["prediction_score"] is not None:
                ready.append(row)
            else:
                insufficient.append(row)

        ready.sort(key=lambda r: r["predictionScore"])

        return jsonify({
            "success": True,
            "ready": ready,
            "insufficient": insufficient,
        }), 200

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)


@teacher_bp.route("/teacher/attendance", methods=["GET"])
def teacher_attendance():

    db = get_db()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]
        payload = JWTService.verify_token(token)

        records = AttendanceRepository.get_for_teacher(
            db,
            payload["user_id"],
        )

        result = []

        for record in records:

            student = StudentRepository.get_by_id(db, record.student_id)

            classroom = ClassroomRepository.get_by_id(db, record.class_id)

            session = SessionRepository.get_by_id(db, record.session_id)

            engagement_scores = [
                float(r.engagement_score or 0)
                for r in EngagementRepository.get_student_session_records(
                    db, record.session_id, record.student_id
                )
            ]

            avg_engagement = (
                round(sum(engagement_scores) / len(engagement_scores))
                if engagement_scores
                else None
            )

            result.append({
                "id": f"attendance-{record.attendance_id}",
                "studentId": record.student_id,
                "studentName": student.name if student else "Unknown",
                "usn": student.usn if student else None,
                "classId": record.class_id,
                "className": (
                    classroom.classroom_name if classroom else "Unknown"
                ),
                "sessionId": record.session_id,
                "date": (
                    session.start_time.isoformat()
                    if session and session.start_time
                    else record.created_at.isoformat()
                    if record.created_at
                    else None
                ),
                "startTime": (
                    session.start_time.isoformat()
                    if session and session.start_time
                    else None
                ),
                "endTime": (
                    session.end_time.isoformat()
                    if session and session.end_time
                    else None
                ),
                "status": "present" if record.status == 1 else "absent",
                "engagementAvg": avg_engagement,
            })

        return jsonify({
            "success": True,
            "attendance": result,
        }), 200

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        close_db(db)

