from pathlib import Path

import fitz  # pymupdf


DPI = 150
MATRIX = fitz.Matrix(DPI / 72, DPI / 72)


def pdf_to_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Convert each PDF page to a PNG file. Returns list of output paths."""
    doc = fitz.open(str(pdf_path))
    image_paths: list[Path] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=MATRIX, colorspace=fitz.csRGB)
        out_path = out_dir / f"page_{page_num:03d}.png"
        pix.save(str(out_path))
        image_paths.append(out_path)

    doc.close()
    return image_paths
