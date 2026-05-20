from pydantic import BaseModel


class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class DetectedPart(BaseModel):
    title: str
    bbox: BoundingBox
    page: int


class UploadResponse(BaseModel):
    session_id: str
    pages: int
    parts: list[DetectedPart]
