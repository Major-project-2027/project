from pydantic import BaseModel


class ClassroomCreate(BaseModel):

    classroom_name: str

    subject: str

    semester: int

    section: str
