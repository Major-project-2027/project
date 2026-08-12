from pydantic import BaseModel, EmailStr


class TeacherLogin(BaseModel):

    email: EmailStr

    password: str
