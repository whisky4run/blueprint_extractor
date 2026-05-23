import time
from datetime import UTC, datetime
from pathlib import Path

from app import cu_detector, detector
from app.engines import normalize_engine
from app.header_position import HeaderPosition
from app.models import DetectionMetrics, DetectionRun
from app.title_position import TitlePosition


def run_detection(
    engine: str,
    pdf_path: Path,
    page_images: list[Path],
    title_position: TitlePosition = "top",
    header_position: HeaderPosition = "right",
    cu_analyzer_id: str | None = None,
    cu_api_version: str | None = None,
    azurecu_raw_output_path: Path | None = None,
) -> DetectionRun:
    engine_name = normalize_engine(engine)
    start = time.perf_counter()
    failure_reason: str | None = None
    parts = []
    header_items = []

    try:
        if engine_name == "opencv":
            for page_num, image_path in enumerate(page_images):
                parts.extend(detector.detect_parts(image_path, page_num))
        elif engine_name == "azure_cu":
            parts, header_items = cu_detector.detect_parts_from_pdf(
                pdf_path,
                page_images,
                title_position=title_position,
                header_position=header_position,
                cu_analyzer_id=cu_analyzer_id,
                cu_api_version=cu_api_version,
                raw_output_path=azurecu_raw_output_path,
            )
    except Exception as e:
        failure_reason = str(e)
        parts = []
        header_items = []

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    metrics = DetectionMetrics(
        process_ms=elapsed_ms,
        parts_count=len(parts),
        failure_reason=failure_reason,
    )
    return DetectionRun(
        engine=engine_name,
        parts=parts,
        header_items=header_items,
        metrics=metrics,
        executed_at=datetime.now(UTC).isoformat(),
    )
