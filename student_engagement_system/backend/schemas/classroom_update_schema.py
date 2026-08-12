from pydantic import BaseModel


class ClassroomUpdate(BaseModel):

    classroom_name: str

    subject: str

    semester: int

    section: str