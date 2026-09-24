from typing import List

from pydantic import BaseModel


class ClassroomCreate(BaseModel):

    classroom_name: str

    subject: str

    semester: int

    section: str
    # Students allowed to join this class (from the teacher's roster).
    # Optional: an empty list creates a class nobody can join yet.
    student_ids: List[int] = []
