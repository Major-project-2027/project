from pydantic import BaseModel


class StudentLogin(BaseModel):

    email: str

    password: str
