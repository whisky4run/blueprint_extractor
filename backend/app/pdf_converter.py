import os
from pathlib import Path

import fitz  # pymupdf


DEFAULT_DPI = 300
MIN_DPI = 72
MAX_DPI = 600


def _render_dpi() -> int:
    raw_value = os.environ.get("PDF_RENDER_DPI", "").strip()
    if not raw_value:
        return DEFAULT_DPI
    try:
        dpi = int(raw_value)
    except ValueError:
        return DEFAULT_DPI
    return max(MIN_DPI, min(MAX_DPI, dpi))


def pdf_to_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Convert each PDF page to a PNG file. Returns list of output paths."""
    dpi = _render_dpi()
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    image_paths: list[Path] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
        out_path = out_dir / f"page_{page_num:03d}.png"
        pix.save(str(out_path))
        image_paths.append(out_path)

    doc.close()
    return image_paths
