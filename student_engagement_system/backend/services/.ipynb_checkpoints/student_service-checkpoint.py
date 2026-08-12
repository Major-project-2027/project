from repositories.student_repository import StudentRepository
from services.security_service import SecurityService
from models.student import Student
from services.jwt_service import JWTService
from repositories.enrollment_repository import EnrollmentRepository


class StudentService:

    @staticmethod
    def register_student(db, student_data):

        # Check email
        if StudentRepository.get_by_email(db, student_data.email):
            raise Exception("Email already registered.")

        # Check USN
        if StudentRepository.get_by_usn(db, student_data.usn):
            raise Exception("USN already registered.")

        # Hash password
        hashed_password = SecurityService.hash_password(
            student_data.password
        )

        student = Student(
            usn=student_data.usn,
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

        return [
            {
                "class_id": c.class_id,
                "class_name": c.classroom_name,
                "subject": c.subject,
                "semester": c.semester,
                "section": c.section,
                "class_code": c.class_code
            }
            for c in classes
        ]
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

