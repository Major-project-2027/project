from flask import Blueprint, request, jsonify
import traceback
from schemas.classroom_update_schema import ClassroomUpdate

from database.database import SessionLocal
from models.session import Session
from schemas.teacher_schema import TeacherRegister
from schemas.teacher_login_schema import TeacherLogin
from schemas.classroom_schema import ClassroomCreate

from services.teacher_service import TeacherService
from services.classroom_service import ClassroomService
from services.jwt_service import JWTService
from services.session_service import SessionService
from services.class_status_service import ClassStatusService
from repositories.attendance_repository import AttendanceRepository
from repositories.alert_repository import AlertRepository
from models.engagement import EngagementRecord
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
                Student.name,
                Student.usn
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

        for student_id, student_name, student_usn in students:

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
        db.close()


@teacher_bp.route("/teacher/attendance", methods=["GET"])
def teacher_attendance():

    db = SessionLocal()

    try:
        auth = request.headers.get("Authorization")

        if not auth:
            raise Exception("Authorization token missing.")

        token = auth.split(" ")[1]
        payload = JWTService.verify_token(token)

        from models.student import Student
        from models.classroom import Classroom

        records = AttendanceRepository.get_for_teacher(
            db,
            payload["user_id"],
        )

        result = []

        for record in records:

            student = (
                db.query(Student)
                .filter(Student.student_id == record.student_id)
                .first()
            )

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
        db.close()

