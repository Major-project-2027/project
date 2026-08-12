from repositories.teacher_repository import TeacherRepository
from services.security_service import SecurityService
from services.jwt_service import JWTService
from models.teacher import Teacher
from repositories.classroom_repository import ClassroomRepository
from repositories.enrollment_repository import EnrollmentRepository

class TeacherService:

    @staticmethod
    def register_teacher(db, teacher_data):

        if TeacherRepository.get_by_email(db, teacher_data.email):
            raise Exception("Email already registered.")

        hashed_password = SecurityService.hash_password(
            teacher_data.password
        )

        teacher = Teacher(
            name=teacher_data.name,
            email=teacher_data.email,
            password_hash=hashed_password,
            department=teacher_data.department
        )

        return TeacherRepository.create_teacher(
            db,
            teacher
        )

    @staticmethod
    def login_teacher(db, login_data):

        teacher = TeacherRepository.get_by_email(
            db,
            login_data.email
        )

        if not teacher:
            raise Exception("Teacher not found.")

        if not SecurityService.verify_password(
            login_data.password,
            teacher.password_hash
        ):
            raise Exception("Incorrect password.")

        token = JWTService.generate_token(
            user_id=teacher.teacher_id,
            role="teacher"
        )

        return {
            "teacher": teacher,
            "token": token
        }
    @staticmethod
    def get_dashboard(db, teacher_id):

        total_classes = ClassroomRepository.count_teacher_classes(
            db,
            teacher_id
        )

        total_students = EnrollmentRepository.count_teacher_students(
            db,
            teacher_id
        )

        total_sessions = 0

        return {
            "total_classes": total_classes,
            "total_students": total_students,
            "total_sessions": total_sessions
        }

