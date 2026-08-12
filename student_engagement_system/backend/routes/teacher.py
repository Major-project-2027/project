from flask import Blueprint, request, jsonify
import traceback
from schemas.classroom_update_schema import ClassroomUpdate

from database.database import SessionLocal
from models.session import Session
from repositories.session_repository import SessionRepository
from sqlalchemy.sql import func
from schemas.teacher_schema import TeacherRegister
from schemas.teacher_login_schema import TeacherLogin
from schemas.classroom_schema import ClassroomCreate

from services.teacher_service import TeacherService
from services.classroom_service import ClassroomService
from services.jwt_service import JWTService
from services.session_service import SessionService
teacher_bp = Blueprint("teacher", __name__)


@teacher_bp.route("/teacher/register", methods=["POST"])
def register_teacher():

    db = SessionLocal()

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
        db.close()


@teacher_bp.route("/teacher/login", methods=["POST"])
def login_teacher():

    db = SessionLocal()

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
        db.close()


@teacher_bp.route("/teacher/create-classroom", methods=["POST"])
def create_classroom():

    db = SessionLocal()

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
        db.close()
@teacher_bp.route("/teacher/classrooms", methods=["GET"])
def get_teacher_classrooms():

    db = SessionLocal()

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

        return jsonify({
            "success": True,
            "classrooms": [
                {
                    "class_id": classroom.class_id,
                    "classroom_name": classroom.classroom_name,
                    "subject": classroom.subject,
                    "semester": classroom.semester,
                    "section": classroom.section,
                    "class_code": classroom.class_code,
                    "meeting_link": classroom.meeting_link
                }
                for classroom in classrooms
            ]
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    finally:
        db.close()
@teacher_bp.route("/teacher/classroom/<int:class_id>", methods=["GET"])
def get_classroom(class_id):

    db = SessionLocal()

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
        db.close()
@teacher_bp.route("/teacher/classroom/<int:class_id>", methods=["PUT"])
def update_classroom(class_id):

    db = SessionLocal()

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
        db.close()
@teacher_bp.route("/teacher/classroom/<int:class_id>", methods=["DELETE"])
def delete_classroom(class_id):

    db = SessionLocal()

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
        db.close()
@teacher_bp.route("/dashboard", methods=["GET"])
def teacher_dashboard():

    db = SessionLocal()

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
        db.close()
@teacher_bp.route("/teacher/start-session/<int:class_id>", methods=["POST"])
def start_session(class_id):

    db = SessionLocal()

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
        db.close()

@teacher_bp.route("/teacher/end-session/<int:class_id>", methods=["POST"])
def end_session(class_id):

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]

        payload = JWTService.verify_token(token)

        active_session = SessionRepository.get_active_session(
            db,
            class_id
        )

        if not active_session:
            raise Exception("No active session found.")

        if active_session.teacher_id != payload["user_id"]:
            raise Exception("You are not authorized to end this session.")

        active_session.end_time = func.now()

        session = SessionRepository.end_session(
            db,
            active_session
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
        db.close()
@teacher_bp.route(
    "/teacher/classroom/<int:class_id>/history",
    methods=["GET"]
)
def class_history(class_id):

    db = SessionLocal()

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

        active_session = (
            db.query(Session)
            .filter(
                Session.class_id == class_id
            )
            .order_by(Session.session_id.desc())
            .first()
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

        from models.student import Student
        from models.enrollment import Enrollment

        students = (
            db.query(
                Student.student_id,
                Student.name
            )
            .join(
                EngagementRecord,
                EngagementRecord.student_id == Student.student_id
            )
            .filter(
                EngagementRecord.session_id ==
                active_session.session_id
            )
            .distinct()
            .all()
        )

        result = []

        for student_id, student_name in students:

            records = (
                db.query(EngagementRecord)
                .filter(
                    EngagementRecord.session_id ==
                    active_session.session_id,
                    EngagementRecord.student_id ==
                    student_id
                )
                .order_by(
                    EngagementRecord.timestamp.asc()
                )
                .all()
            )

            if not records:
                continue

            scores = [
                float(r.engagement_score or 0)
                for r in records
            ]

            result.append({
                "studentId": student_id,
                "studentName": student_name,

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
        db.close()

