from pydantic import BaseModel, EmailStr


class TeacherRegister(BaseModel):

    name: str

    email: EmailStr

    password: str

    department: str | None = None