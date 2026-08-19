from pydantic import BaseModel


class FaceSampleValidate(BaseModel):
    """One captured registration photo, checked for a single clear face
    before the frontend keeps it as one of the student's registered
    samples."""

    image: str  # base64 (data URL or raw), same convention as /ai/analyze-frame


class FaceRegister(BaseModel):
    """Every already-validated sample's embedding, submitted together once
    the guided capture flow finishes. Embeddings (not raw images) are sent
    here because each sample was already validated + embedded by
    /face/validate-sample; re-sending images would mean detecting faces
    twice for no benefit."""

    embeddings: list[list[float]]


class FaceVerifyLive(BaseModel):
    """One live camera frame, checked against the logged-in student's own
    registered face before they're allowed to join a live class."""

    image: str
    class_id: int
