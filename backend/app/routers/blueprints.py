import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app import cu_detector, extractor, session, ui_preferences
from app.detection_service import run_detection
from app.engines import DEFAULT_ENGINE, ENGINE_LABELS, normalize_engine
from app.header_position import DEFAULT_HEADER_POSITION, normalize_header_position
from app.models import PrepareResponse, UiPreferences, UploadResponse
from app.pdf_converter import pdf_to_images
from app.title_position import DEFAULT_TITLE_POSITION, normalize_title_position

router = APIRouter()


def _clear_pngs(parts_dir: Path) -> None:
    if not parts_dir.exists():
        return
    for png in parts_dir.glob("*.png"):
        png.unlink()


def _save_run_artifacts(session_id: str, page_images: list[Path], run) -> None:
    sess_dir = session.session_dir(session_id)
    parts_dir = sess_dir / "parts" / run.engine
    parts_dir.mkdir(parents=True, exist_ok=True)
    _clear_pngs(parts_dir)

    if run.parts:
        extractor.extract_parts(page_images, run.parts, parts_dir)

    # 最終処理結果を JSON として保存（AzureCU 生 JSON との比較用）
    result_payload = {
        "engine": run.engine,
        "executed_at": run.executed_at,
        "parts": [p.model_dump() for p in run.parts],
        "metrics": run.metrics.model_dump() if run.metrics else None,
    }
    (parts_dir / "result.json").write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    session.set_session_run(session_id, run)
    session.set_active_engine(session_id, run.engine)


def _azurecu_raw_output_path(sess_dir: Path, engine_name: str, kind: str) -> Path | None:
    if engine_name != "azure_cu":
        return None
    out_dir = sess_dir / "azurecu_result"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return out_dir / f"azurecu_raw_{kind}_{ts}.json"


def _resolve_cu_selection(
    engine_name: str,
    cu_contents_analyzer_id: str | None,
    cu_contents_api_version: str | None,
    cu_header_analyzer_id: str | None,
    cu_header_api_version: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    if engine_name != "azure_cu":
        return None, None, None, None

    contents_analyzer_id = (cu_contents_analyzer_id or "").strip() or None
    contents_api_version = (cu_contents_api_version or "").strip() or None
    header_analyzer_id = (cu_header_analyzer_id or "").strip() or None
    header_api_version = (cu_header_api_version or "").strip() or None
    return contents_analyzer_id, contents_api_version, header_analyzer_id, header_api_version


@router.get("/azurecu/analyzers")
async def list_azurecu_analyzers(api_version: str | None = None) -> JSONResponse:
    items = cu_detector.list_analyzers(api_version=api_version)
    resolved_api_version = (api_version or "").strip() or os.environ.get("AZURE_CU_API_VERSION", "2025-05-01-preview")

    analyzers = [
        {
            "analyzer_id": item.get("analyzerId"),
            "description": item.get("description", ""),
            "status": item.get("status", ""),
            "created_at": item.get("createdAt"),
            "last_modified_at": item.get("lastModifiedAt"),
            "api_version": resolved_api_version,
        }
        for item in items
        if isinstance(item.get("analyzerId"), str)
    ]
    analyzers.sort(key=lambda x: (x.get("analyzer_id") or ""))

    return JSONResponse(
        {
            "api_version": resolved_api_version,
            "count": len(analyzers),
            "fetched_at": datetime.now(UTC).isoformat(),
            "analyzers": analyzers,
        }
    )


@router.get("/ui/preferences", response_model=UiPreferences)
async def get_ui_preferences() -> UiPreferences:
    payload = ui_preferences.load_preferences()
    return UiPreferences.model_validate(payload)


@router.put("/ui/preferences", response_model=UiPreferences)
async def put_ui_preferences(prefs: UiPreferences) -> UiPreferences:
    payload = prefs.model_dump()
    saved = ui_preferences.save_preferences(payload)
    return UiPreferences.model_validate(saved)


def _apply_session_settings(
    session_id: str,
    engine: str = DEFAULT_ENGINE,
    title_position: str = DEFAULT_TITLE_POSITION,
    header_position: str = DEFAULT_HEADER_POSITION,
    cu_contents_analyzer_id: str | None = None,
    cu_contents_api_version: str | None = None,
    cu_header_analyzer_id: str | None = None,
    cu_header_api_version: str | None = None,
) -> tuple[str, str, str, str | None, str | None, str | None, str | None]:
    try:
        engine_name = normalize_engine(engine)
    except ValueError:
        raise HTTPException(status_code=400, detail="不明な切り出し方式です")
    try:
        normalized_title_position = normalize_title_position(title_position)
    except ValueError:
        raise HTTPException(status_code=400, detail="不明なタイトル位置です")
    try:
        normalized_header_position = normalize_header_position(header_position)
    except ValueError:
        raise HTTPException(status_code=400, detail="不明な図面ヘッダ位置です")
    session.set_title_position(session_id, normalized_title_position)
    session.set_header_position(session_id, normalized_header_position)
    (
        resolved_cu_contents_analyzer_id,
        resolved_cu_contents_api_version,
        resolved_cu_header_analyzer_id,
        resolved_cu_header_api_version,
    ) = _resolve_cu_selection(
        engine_name,
        cu_contents_analyzer_id,
        cu_contents_api_version,
        cu_header_analyzer_id,
        cu_header_api_version,
    )
    session.set_cu_selection(
        session_id,
        resolved_cu_contents_analyzer_id,
        resolved_cu_contents_api_version,
        resolved_cu_header_analyzer_id,
        resolved_cu_header_api_version,
    )

    return (
        engine_name,
        normalized_title_position,
        normalized_header_position,
        resolved_cu_contents_analyzer_id,
        resolved_cu_contents_api_version,
        resolved_cu_header_analyzer_id,
        resolved_cu_header_api_version,
    )


@router.post("/prepare", response_model=PrepareResponse)
async def prepare_pdf(
    file: UploadFile = File(...),
    engine: str = Form(DEFAULT_ENGINE),
    title_position: str = Form(DEFAULT_TITLE_POSITION),
    header_position: str = Form(DEFAULT_HEADER_POSITION),
    cu_contents_analyzer_id: str | None = Form(None),
    cu_contents_api_version: str | None = Form(None),
    cu_header_analyzer_id: str | None = Form(None),
    cu_header_api_version: str | None = Form(None),
) -> PrepareResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF ファイルのみ受け付けます")

    session_id = session.create_session()
    sess_dir = session.session_dir(session_id)
    pdf_path = sess_dir / "input.pdf"
    pdf_path.write_bytes(await file.read())

    images_dir = sess_dir / "pages"
    images_dir.mkdir()
    page_images = pdf_to_images(pdf_path, images_dir)
    session.set_page_count(session_id, len(page_images))
    (
        engine_name,
        _normalized_title_position,
        _normalized_header_position,
        _resolved_cu_contents_analyzer_id,
        _resolved_cu_contents_api_version,
        _resolved_cu_header_analyzer_id,
        _resolved_cu_header_api_version,
    ) = _apply_session_settings(
        session_id,
        engine=engine,
        title_position=title_position,
        header_position=header_position,
        cu_contents_analyzer_id=cu_contents_analyzer_id,
        cu_contents_api_version=cu_contents_api_version,
        cu_header_analyzer_id=cu_header_analyzer_id,
        cu_header_api_version=cu_header_api_version,
    )
    session.set_active_engine(session_id, engine_name)

    return PrepareResponse(session_id=session_id, pages=len(page_images))


@router.post("/run/{session_id}")
async def run_prepared_pdf(
    session_id: str,
    engine: str = Form(DEFAULT_ENGINE),
    title_position: str = Form(DEFAULT_TITLE_POSITION),
    header_position: str = Form(DEFAULT_HEADER_POSITION),
    cu_contents_analyzer_id: str | None = Form(None),
    cu_contents_api_version: str | None = Form(None),
    cu_header_analyzer_id: str | None = Form(None),
    cu_header_api_version: str | None = Form(None),
) -> JSONResponse:
    sess = session.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    sess_dir: Path = sess["dir"]
    pdf_path = sess_dir / "input.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="入力PDFが見つかりません")
    page_images = sorted((sess_dir / "pages").glob("page_*.png"))
    if not page_images:
        raise HTTPException(status_code=404, detail="ページ画像が見つかりません")

    (
        engine_name,
        normalized_title_position,
        normalized_header_position,
        resolved_cu_contents_analyzer_id,
        resolved_cu_contents_api_version,
        resolved_cu_header_analyzer_id,
        resolved_cu_header_api_version,
    ) = _apply_session_settings(
        session_id,
        engine=engine,
        title_position=title_position,
        header_position=header_position,
        cu_contents_analyzer_id=cu_contents_analyzer_id,
        cu_contents_api_version=cu_contents_api_version,
        cu_header_analyzer_id=cu_header_analyzer_id,
        cu_header_api_version=cu_header_api_version,
    )

    run = run_detection(
        engine_name,
        pdf_path,
        page_images,
        title_position=normalized_title_position,
        header_position=normalized_header_position,
        cu_analyzer_id=resolved_cu_contents_analyzer_id,
        cu_api_version=resolved_cu_contents_api_version,
        cu_header_analyzer_id=resolved_cu_header_analyzer_id,
        cu_header_api_version=resolved_cu_header_api_version,
        azurecu_raw_output_path=_azurecu_raw_output_path(sess_dir, engine_name, "contents"),
        azurecu_header_raw_output_path=_azurecu_raw_output_path(sess_dir, engine_name, "header"),
    )
    _save_run_artifacts(session_id, page_images, run)

    return JSONResponse(
        {
            "session_id": session_id,
            "engine": run.engine,
            "parts": [p.model_dump() for p in run.parts],
            "metrics": run.metrics.model_dump(),
            "executed_at": run.executed_at,
        }
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    engine: str = Form(DEFAULT_ENGINE),
    title_position: str = Form(DEFAULT_TITLE_POSITION),
    header_position: str = Form(DEFAULT_HEADER_POSITION),
    cu_contents_analyzer_id: str | None = Form(None),
    cu_contents_api_version: str | None = Form(None),
    cu_header_analyzer_id: str | None = Form(None),
    cu_header_api_version: str | None = Form(None),
) -> UploadResponse:
    prepared = await prepare_pdf(
        file=file,
        engine=engine,
        title_position=title_position,
        header_position=header_position,
        cu_contents_analyzer_id=cu_contents_analyzer_id,
        cu_contents_api_version=cu_contents_api_version,
        cu_header_analyzer_id=cu_header_analyzer_id,
        cu_header_api_version=cu_header_api_version,
    )
    await run_prepared_pdf(
        session_id=prepared.session_id,
        engine=engine,
        title_position=title_position,
        header_position=header_position,
        cu_contents_analyzer_id=cu_contents_analyzer_id,
        cu_contents_api_version=cu_contents_api_version,
        cu_header_analyzer_id=cu_header_analyzer_id,
        cu_header_api_version=cu_header_api_version,
    )
    run = session.get_active_run(prepared.session_id)
    if not run:
        raise HTTPException(status_code=500, detail="解析結果が取得できませんでした")
    return UploadResponse(
        session_id=prepared.session_id,
        pages=prepared.pages,
        engine=run.engine,
        parts=run.parts,
        metrics=run.metrics,
    )


@router.post("/reanalyze/{session_id}")
async def reanalyze(session_id: str, engine: str) -> JSONResponse:
    sess = session.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    try:
        engine_name = normalize_engine(engine)
    except ValueError:
        raise HTTPException(status_code=400, detail="不明な切り出し方式です")

    sess_dir: Path = sess["dir"]
    pdf_path = sess_dir / "input.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="入力PDFが見つかりません")

    page_images = sorted((sess_dir / "pages").glob("page_*.png"))
    if not page_images:
        raise HTTPException(status_code=404, detail="ページ画像が見つかりません")

    title_position = session.get_title_position(session_id)
    header_position = session.get_header_position(session_id)
    (
        cu_contents_analyzer_id,
        cu_contents_api_version,
        _cu_header_analyzer_id,
        _cu_header_api_version,
    ) = session.get_cu_selection(session_id)
    run = run_detection(
        engine_name,
        pdf_path,
        page_images,
        title_position=title_position,
        header_position=header_position,
        cu_analyzer_id=cu_contents_analyzer_id,
        cu_api_version=cu_contents_api_version,
        cu_header_analyzer_id=_cu_header_analyzer_id,
        cu_header_api_version=_cu_header_api_version,
        azurecu_raw_output_path=_azurecu_raw_output_path(sess_dir, engine_name, "contents"),
        azurecu_header_raw_output_path=_azurecu_raw_output_path(sess_dir, engine_name, "header"),
    )
    _save_run_artifacts(session_id, page_images, run)

    return JSONResponse(
        {
            "session_id": session_id,
            "engine": run.engine,
            "parts": [p.model_dump() for p in run.parts],
            "metrics": run.metrics.model_dump(),
            "executed_at": run.executed_at,
        }
    )


@router.get("/preview/{session_id}")
async def get_preview(session_id: str) -> JSONResponse:
    sess = session.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    sess_dir: Path = sess["dir"]
    images_dir = sess_dir / "pages"

    pages_data = []
    for image_path in sorted(images_dir.glob("page_*.png")):
        b64 = base64.b64encode(image_path.read_bytes()).decode()
        pages_data.append({"filename": image_path.name, "data": b64})

    active_engine = session.get_active_engine(session_id)
    active_run = session.get_active_run(session_id)
    runs = session.list_runs(session_id)
    title_position = session.get_title_position(session_id)
    header_position = session.get_header_position(session_id)
    (
        cu_contents_analyzer_id,
        cu_contents_api_version,
        cu_header_analyzer_id,
        cu_header_api_version,
    ) = session.get_cu_selection(session_id)

    return JSONResponse(
        {
            "session_id": session_id,
            "pages": pages_data,
            "active_engine": active_engine,
            "active_engine_label": ENGINE_LABELS[active_engine],
            "title_position": title_position,
            "header_position": header_position,
            "cu_contents_analyzer_id": cu_contents_analyzer_id,
            "cu_contents_api_version": cu_contents_api_version,
            "cu_header_analyzer_id": cu_header_analyzer_id,
            "cu_header_api_version": cu_header_api_version,
            "parts": [p.model_dump() for p in (active_run.parts if active_run else [])],
            "header_fields": [p.model_dump() for p in (active_run.header_fields if active_run else [])],
            "metrics": active_run.metrics.model_dump() if active_run else None,
            "has_downloadable_result": bool(active_run and active_run.parts),
            "runs": {
                engine: {
                    "engine_label": ENGINE_LABELS[engine],
                    "executed_at": run.executed_at,
                    "metrics": run.metrics.model_dump(),
                }
                for engine, run in runs.items()
            },
        }
    )


@router.get("/download/{session_id}")
async def download_zip(session_id: str) -> Response:
    sess = session.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    active_engine = session.get_active_engine(session_id)
    run = session.get_active_run(session_id)
    if not run or not run.parts:
        raise HTTPException(status_code=404, detail="切り出し済みのパーツがありません")

    parts_dir: Path = sess["dir"] / "parts" / active_engine
    png_paths = sorted(parts_dir.glob("*.png"))

    if not png_paths:
        raise HTTPException(status_code=404, detail="切り出し済みのパーツがありません")

    (
        cu_contents_analyzer_id,
        cu_contents_api_version,
        cu_header_analyzer_id,
        cu_header_api_version,
    ) = session.get_cu_selection(session_id)
    result_payload = {
        "session_id": session_id,
        "engine": active_engine,
        "engine_label": ENGINE_LABELS[active_engine],
        "executed_at": run.executed_at,
        "title_position": session.get_title_position(session_id),
        "header_position": session.get_header_position(session_id),
        "cu_contents_analyzer_id": cu_contents_analyzer_id,
        "cu_contents_api_version": cu_contents_api_version,
        "cu_header_analyzer_id": cu_header_analyzer_id,
        "cu_header_api_version": cu_header_api_version,
        "metrics": run.metrics.model_dump(),
        "detected_parts": [p.model_dump() for p in run.parts],
        "header_items": [p.model_dump() for p in run.header_items],
        "header_fields": [p.model_dump() for p in run.header_fields],
        "header_key_values": {f.key: f.value for f in run.header_fields},
    }
    extra_files: list[tuple[Path, str]] = []
    header_fields_json_path = sess["dir"] / "header_fields.json"
    header_fields_json_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "header_fields": [p.model_dump() for p in run.header_fields],
                "header_key_values": {f.key: f.value for f in run.header_fields},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    extra_files.append((header_fields_json_path, "header_fields.json"))
    azurecu_dir = sess["dir"] / "azurecu_result"
    if azurecu_dir.exists():
        for p in sorted(azurecu_dir.glob("*.json")):
            extra_files.append((p, f"azurecu_result/{p.name}"))

    zip_bytes = extractor.build_zip(
        png_paths,
        result_payload=result_payload,
        extra_files=extra_files,
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=parts.zip"},
    )
