from pydantic import BaseModel, EmailStr


class StudentRegister(BaseModel):

    usn: str

    name: str

    email: EmailStr

    password: str

    semester: int

    section: str

    department: str


class StudentLogin(BaseModel):

    email: EmailStr

    password: str
