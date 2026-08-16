from flask import Blueprint, request, jsonify
from services.monitoring_service import MonitoringService
from database.database import SessionLocal
from schemas.student_schema import StudentRegister
from schemas.login_schema import StudentLogin
from services.student_service import StudentService
from schemas.join_class_schema import JoinClass, JoinLiveClass
from services.enrollment_service import EnrollmentService
from services.jwt_service import JWTService
from models.session import Session
from models.student import Student
from models.classroom import Classroom
from models.teacher import Teacher
from models.enrollment import Enrollment
from repositories.session_repository import SessionRepository
from repositories.attendance_repository import AttendanceRepository
from repositories.alert_repository import AlertRepository
student_bp = Blueprint("student", __name__)


@student_bp.route("/register", methods=["POST"])
def register_student():

    db = SessionLocal()

    try:
        data = StudentRegister(**request.json)

        student = StudentService.register_student(
            db,
            data
        )

        return jsonify({
            "success": True,
            "student_id": student.student_id,
            "message": "Student Registered Successfully"
        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()
@student_bp.route("/login", methods=["POST"])
def login_student():

    db = SessionLocal()

    try:

        data = StudentLogin(**request.json)

        result = StudentService.login_student(
            db,
            data
        )

        return jsonify({
            "success": True,
            "message": "Login Successful",
            "student_id": result["student"].student_id,
            "name": result["student"].name,
            "token": result["token"]
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()
@student_bp.route("/join-class", methods=["POST"])
def join_class():

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        data = JoinClass(**request.json)

        classroom = EnrollmentService.join_class(
            db,
            payload["user_id"],
            data.class_code
        )

        return jsonify({
            "success": True,
            "message": "Joined Classroom Successfully",
            "class_id": classroom.class_id,
            "class_name": classroom.classroom_name
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()


@student_bp.route("/live-classes", methods=["GET"])
def live_classes():
    """Every class with an active session right now, across every
    teacher -- lets any authenticated student discover and join a live
    class from the dashboard without needing its code."""

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        JWTService.verify_token(token)

        active_sessions = SessionRepository.get_all_active_sessions(db)

        result = []

        for session in active_sessions:

            classroom = (
                db.query(Classroom)
                .filter(Classroom.class_id == session.class_id)
                .first()
            )

            if not classroom:
                continue

            teacher = (
                db.query(Teacher)
                .filter(Teacher.teacher_id == session.teacher_id)
                .first()
            )

            student_count = (
                db.query(Enrollment)
                .filter(Enrollment.class_id == session.class_id)
                .count()
            )

            result.append({
                "session_id": session.session_id,
                "class_id": session.class_id,
                "classroom_name": classroom.classroom_name,
                "subject": classroom.subject,
                "teacher_id": session.teacher_id,
                "teacher_name": teacher.name if teacher else "Unknown",
                "start_time": session.start_time,
                "student_count": student_count,
            })

        return jsonify({
            "success": True,
            "liveClasses": result,
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()


@student_bp.route("/join-live-class", methods=["POST"])
def join_live_class():
    """Direct join from the "Live Classes" dashboard section -- no class
    code required. Only succeeds while the class's session is actually
    active, and never creates a duplicate enrollment or a new session."""

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        data = JoinLiveClass(**request.json)

        classroom, session = EnrollmentService.join_live_class(
            db,
            payload["user_id"],
            data.class_id
        )

        return jsonify({
            "success": True,
            "message": "Joined Live Class Successfully",
            "class_id": classroom.class_id,
            "class_name": classroom.classroom_name,
            "session_id": session.session_id,
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()


@student_bp.route("/my-classes", methods=["GET"])
def my_classes():

    db = SessionLocal()

    try:
        token = request.headers.get("Authorization")

        if not token:
            raise Exception("Authorization token missing.")

        classes = StudentService.get_my_classes(
            db,
            token
        )

        return jsonify({
            "success": True,
            "classes": classes
        }), 200

    except Exception as e:

        print("MY CLASSES ERROR:", str(e))

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()
@student_bp.route("/dashboard", methods=["GET"])
def student_dashboard():

    db = SessionLocal()

    try:

        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        dashboard = StudentService.get_dashboard(
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
        db.close()
@student_bp.route("/live-monitor", methods=["GET"])
def live_monitor():

    try:

        data = MonitoringService.get_live_data()

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
@student_bp.route(
    "/history/class/<int:class_id>",
    methods=["GET"]
)
def student_class_history(class_id):

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]
        payload = JWTService.verify_token(token)

        student_id = payload["user_id"]

        from models.engagement import EngagementRecord
        from models.classroom import Classroom

        classroom = (
            db.query(Classroom)
            .filter(Classroom.class_id == class_id)
            .first()
        )

        if not classroom:
            raise Exception("Classroom not found.")

        # Find the student's records for this class.
        records = (
            db.query(EngagementRecord)
            .join(
                Session,
                EngagementRecord.session_id == Session.session_id
            )
            .filter(
                Session.class_id == class_id,
                EngagementRecord.student_id == student_id
            )
            .order_by(
                EngagementRecord.timestamp.asc()
            )
            .all()
        )

        if not records:
            return jsonify({
                "success": True,
                "history": None
            }), 200

        scores = [
            float(r.engagement_score or 0)
            for r in records
        ]

        student = (
            db.query(Student)
            .filter(
                Student.student_id == student_id
            )
            .first()
        )

        latest_session_id = records[-1].session_id

        attendance = AttendanceRepository.get_by_session_and_student(
            db,
            latest_session_id,
            student_id,
        )

        alert_counts = AlertRepository.counts_by_type(
            db,
            latest_session_id,
            student_id,
        )

        session = (
            db.query(Session)
            .filter(Session.session_id == latest_session_id)
            .first()
        )

        return jsonify({
            "success": True,
            "history": {
                "studentId": student_id,
                "studentName": (
                    student.name
                    if student
                    else "Student"
                ),
                "usn": student.usn if student else None,
                "classId": class_id,
                "className": classroom.classroom_name,
                "subject": classroom.subject,
                "sessionId": latest_session_id,
                "startTime": session.start_time if session else None,
                "endTime": session.end_time if session else None,

                "attendanceStatus": (
                    "present"
                    if attendance and attendance.status == 1
                    else "absent"
                    if attendance
                    else "unknown"
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
                    1
                    for r in records
                    if r.phone_detected
                ),

                "multiplePersonDetections": sum(
                    1
                    for r in records
                    if r.multiple_person
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
            }
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()


@student_bp.route("/student/attendance", methods=["GET"])
def student_attendance():

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]
        payload = JWTService.verify_token(token)
        student_id = payload["user_id"]

        from models.classroom import Classroom
        from models.engagement import EngagementRecord

        records = AttendanceRepository.get_for_student(
            db,
            student_id,
        )

        result = []

        for record in records:

            classroom = (
                db.query(Classroom)
                .filter(Classroom.class_id == record.class_id)
                .first()
            )

            session = (
                db.query(Session)
                .filter(Session.session_id == record.session_id)
                .first()
            )

            engagement_scores = [
                float(r.engagement_score or 0)
                for r in db.query(EngagementRecord).filter(
                    EngagementRecord.session_id == record.session_id,
                    EngagementRecord.student_id == record.student_id,
                ).all()
            ]

            avg_engagement = (
                round(sum(engagement_scores) / len(engagement_scores))
                if engagement_scores
                else None
            )

            result.append({
                "id": f"attendance-{record.attendance_id}",
                "studentId": record.student_id,
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

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()

