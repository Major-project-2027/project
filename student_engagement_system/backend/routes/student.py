from flask import Blueprint, request, jsonify
from services.monitoring_service import MonitoringService
from database.database import SessionLocal
from schemas.student_schema import StudentRegister
from schemas.login_schema import StudentLogin
from services.student_service import StudentService
from schemas.join_class_schema import JoinClass
from services.enrollment_service import EnrollmentService
from services.jwt_service import JWTService
from models.session import Session
from models.student import Student
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

        return jsonify({
            "success": True,
            "history": {
                "studentId": student_id,
                "studentName": (
                    student.name
                    if student
                    else "Student"
                ),
                "classId": class_id,
                "className": classroom.classroom_name,
                "subject": classroom.subject,

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

