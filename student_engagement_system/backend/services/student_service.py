import re

from repositories.active import StudentRepository, EnrollmentRepository
from services.security_service import SecurityService
from models.student import Student
from services.jwt_service import JWTService
from services.class_status_service import ClassStatusService


class StudentService:

    @staticmethod
    def _generate_usn(db):
        """Generate a fresh, unused USN (STUDENT### ) for registrations
        that don't supply one -- the current register form collects no
        real USN, so one must be assigned server-side."""

        existing = StudentRepository.get_usns_starting_with(db, "STUDENT")

        max_num = 0
        for usn in existing:
            match = re.match(r"^STUDENT(\d+)$", usn or "")
            if match:
                max_num = max(max_num, int(match.group(1)))

        candidate_num = max_num + 1
        candidate = f"STUDENT{candidate_num:03d}"

        while StudentRepository.get_by_usn(db, candidate):
            candidate_num += 1
            candidate = f"STUDENT{candidate_num:03d}"

        return candidate

    @staticmethod
    def register_student(db, student_data):

        # Check email
        if StudentRepository.get_by_email(db, student_data.email):
            raise Exception("Email already registered.")

        usn = student_data.usn or StudentService._generate_usn(db)

        # Check USN
        if StudentRepository.get_by_usn(db, usn):
            raise Exception("USN already registered.")

        # Hash password
        hashed_password = SecurityService.hash_password(
            student_data.password
        )

        student = Student(
            usn=usn,
            name=student_data.name,
            email=student_data.email,
            password_hash=hashed_password,
            department=student_data.department,
            semester=student_data.semester,
            section=student_data.section
        )

        return StudentRepository.create_student(db, student)

    @staticmethod
    def login_student(db, login_data):
        student = StudentRepository.get_by_email(
            db,
            login_data.email
        )

        if not student:
            raise Exception("Student not found.")

        if not SecurityService.verify_password(
            login_data.password,
            student.password_hash
        ):
            raise Exception("Incorrect password.")

        token = JWTService.generate_token(
             user_id=student.student_id,
            role="student"
        )

        return {
            "student": student,
            "token": token
        }
    
    @staticmethod
    def get_my_classes(db, token):

        if token.startswith("Bearer "):
            token = token.split(" ")[1]

        payload = JWTService.verify_token(token)

        student_id = payload["user_id"]

        classes = EnrollmentRepository.get_student_classes(
            db,
            student_id
        )

        def serialize(classroom):
            summary = ClassStatusService.summarize(db, classroom)

            return {
                "class_id": classroom.class_id,
                "class_name": classroom.classroom_name,
                "subject": classroom.subject,
                "semester": classroom.semester,
                "section": classroom.section,
                "class_code": classroom.class_code,
                "status": summary["status"],
                "session_id": summary["session_id"],
                "start_time": summary["start_time"],
                "end_time": summary["end_time"],
                "students_enrolled": summary["students_enrolled"],
                "avg_engagement": summary["avg_engagement"],
            }

        return [serialize(c) for c in classes]
    @staticmethod
    def get_dashboard(db, student_id):

        classes = EnrollmentRepository.get_student_classes(
            db,
            student_id
        )

        return {
            "my_classes": len(classes),
            "upcoming_sessions": 0,
            "attendance_percentage": 0
        }

