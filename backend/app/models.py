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


class HeaderFieldItem(BaseModel):
    key: str
    value: str
    page: int | None = None
    bbox: BoundingBox | None = None
    source: str | None = None


EngineName = Literal["opencv", "azure_cu"]


class DetectionMetrics(BaseModel):
    process_ms: int
    parts_count: int
    failure_reason: str | None = None


class DetectionRun(BaseModel):
    engine: EngineName
    parts: list[DetectedPart]
    header_items: list[DetectedPart] = Field(default_factory=list)
    header_fields: list[HeaderFieldItem] = Field(default_factory=list)
    metrics: DetectionMetrics
    executed_at: str


class UploadResponse(BaseModel):
    session_id: str
    pages: int
    engine: EngineName
    parts: list[DetectedPart]
    metrics: DetectionMetrics


class PrepareResponse(BaseModel):
    session_id: str
    pages: int


class UiAnalyzerOption(BaseModel):
    analyzer_id: str
    description: str = ""
    status: str = ""
    created_at: str | None = None
    last_modified_at: str | None = None
    api_version: str = ""


class UiCuSelection(BaseModel):
    contents_analyzer_id: str = ""
    contents_api_version: str = ""
    header_analyzer_id: str = ""
    header_api_version: str = ""


class UiAnalyzerCache(BaseModel):
    api_version: str = ""
    fetched_at: str | None = None
    analyzers: list[UiAnalyzerOption] = Field(default_factory=list)


class UiPreferences(BaseModel):
    cu_selection: UiCuSelection = Field(default_factory=UiCuSelection)
    analyzer_cache: UiAnalyzerCache = Field(default_factory=UiAnalyzerCache)
