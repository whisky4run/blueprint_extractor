from pydantic import BaseModel, Field
from typing import Literal


class BoundingBox(BaseModel):
    x: float
    y: float
    w: float
    h: float


class DetectedPart(BaseModel):
    title: str
    bbox: BoundingBox
    page: int


EngineName = Literal["opencv", "azure_cu"]


class DetectionMetrics(BaseModel):
    process_ms: int
    parts_count: int
    failure_reason: str | None = None


class DetectionRun(BaseModel):
    engine: EngineName
    parts: list[DetectedPart]
    header_items: list[DetectedPart] = Field(default_factory=list)
    metrics: DetectionMetrics
    executed_at: str


class UploadResponse(BaseModel):
    session_id: str
    pages: int
    engine: EngineName
    parts: list[DetectedPart]
    metrics: DetectionMetrics
