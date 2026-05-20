import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app import detector, extractor, session
from app.models import UploadResponse
from app.pdf_converter import pdf_to_images

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile) -> UploadResponse:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF ファイルのみ受け付けます")

    session_id = session.create_session()
    sess_dir = session.session_dir(session_id)

    pdf_path = sess_dir / "input.pdf"
    pdf_path.write_bytes(await file.read())

    images_dir = sess_dir / "pages"
    images_dir.mkdir()
    page_images = pdf_to_images(pdf_path, images_dir)

    all_parts = []
    for page_num, image_path in enumerate(page_images):
        parts = detector.detect_parts(image_path, page_num)
        all_parts.extend(parts)

    parts_dir = sess_dir / "parts"
    parts_dir.mkdir()
    extractor.extract_parts(page_images, all_parts, parts_dir)

    session.set_session_parts(session_id, all_parts, len(page_images))

    return UploadResponse(
        session_id=session_id,
        pages=len(page_images),
        parts=all_parts,
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

    return JSONResponse(
        {
            "session_id": session_id,
            "pages": pages_data,
            "parts": [p.model_dump() for p in sess["parts"]],
        }
    )


@router.get("/download/{session_id}")
async def download_zip(session_id: str) -> Response:
    sess = session.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")

    parts_dir: Path = sess["dir"] / "parts"
    png_paths = sorted(parts_dir.glob("*.png"))

    if not png_paths:
        raise HTTPException(status_code=404, detail="切り出し済みのパーツがありません")

    zip_bytes = extractor.build_zip(png_paths)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=parts.zip"},
    )
