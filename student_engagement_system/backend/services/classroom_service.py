import random
import string

from models.classroom import Classroom
from repositories.classroom_repository import ClassroomRepository


class ClassroomService:

    @staticmethod
    def generate_class_code():

        return ''.join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )

    @staticmethod
    def create_classroom(db, teacher_id, classroom_data):

        class_code = ClassroomService.generate_class_code()

        while ClassroomRepository.get_by_code(db, class_code):
            class_code = ClassroomService.generate_class_code()

        classroom = Classroom(
            teacher_id=teacher_id,
            classroom_name=classroom_data.classroom_name,
            subject=classroom_data.subject,
            semester=classroom_data.semester,
            section=classroom_data.section,
            class_code=class_code
        )

        return ClassroomRepository.create_classroom(
            db,
            classroom
        )
    @staticmethod
    def get_teacher_classrooms(db, teacher_id):

        return ClassroomRepository.get_teacher_classrooms(
            db,
            teacher_id
        )
    @staticmethod
    def get_classroom(db, class_id):

        classroom = ClassroomRepository.get_by_id(
            db,
            class_id
        )

        if not classroom:
            raise Exception("Classroom not found.")

        return classroom
    @staticmethod
    def delete_classroom(db, class_id):

        classroom = ClassroomRepository.get_classroom_by_id(
            db,
            class_id
        )

        if not classroom:
            raise Exception("Classroom not found.")

        ClassroomRepository.delete_classroom(
            db,
            classroom
        )

        return True
    @staticmethod
    def update_classroom(db, class_id, teacher_id, classroom_data):

        classroom = ClassroomRepository.get_by_id(
            db,
            class_id
        )

        if not classroom:
            raise Exception("Classroom not found.")

        if classroom.teacher_id != teacher_id:
            raise Exception("Unauthorized.")

        classroom.classroom_name = classroom_data.classroom_name
        classroom.subject = classroom_data.subject
        classroom.semester = classroom_data.semester
        classroom.section = classroom_data.section

        return ClassroomRepository.update_classroom(
            db,
            classroom
        )

