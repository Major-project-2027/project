from pydantic import BaseModel


class JoinClass(BaseModel):

    class_code: str


class JoinLiveClass(BaseModel):

    class_id: int