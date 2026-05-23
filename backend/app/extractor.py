import re
import zipfile
import json
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.models import DetectedPart


def _safe_filename(title: str) -> str:
    """Remove characters not allowed in filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", title).strip()


def extract_parts(page_images: list[Path], parts: list[DetectedPart], out_dir: Path) -> list[Path]:
    """Crop each detected part from its page image and save as PNG."""
    out_paths: list[Path] = []

    for part in parts:
        src = page_images[part.page]
        img = Image.open(src)
        bb = part.bbox

        left = int(bb.x)
        upper = int(bb.y)
        right = int(bb.x + bb.w)
        lower = int(bb.y + bb.h)

        # Clamp to image bounds
        left = max(0, left)
        upper = max(0, upper)
        right = min(img.width, right)
        lower = min(img.height, lower)

        cropped = img.crop((left, upper, right, lower))
        filename = _safe_filename(part.title) + ".png"
        out_path = out_dir / filename
        cropped.save(str(out_path), format="PNG")
        out_paths.append(out_path)

    return out_paths


def build_zip(
    png_paths: list[Path],
    result_payload: dict | None = None,
    extra_files: list[tuple[Path, str]] | None = None,
) -> bytes:
    """Pack all PNG files into a ZIP archive and return as bytes."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in png_paths:
            zf.write(path, arcname=path.name)
        if extra_files:
            for path, arcname in extra_files:
                if path.exists() and path.is_file():
                    zf.write(path, arcname=arcname)
        if result_payload is not None:
            zf.writestr(
                "result.json",
                json.dumps(result_payload, ensure_ascii=False, indent=2),
            )
    return buf.getvalue()
