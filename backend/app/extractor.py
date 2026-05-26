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
    # ページ → y → x 順でソートして連番割り当てを安定させる
    sorted_parts = sorted(parts, key=lambda p: (p.page, p.bbox.y, p.bbox.x))

    # 同一ベース名の出現数を事前カウント
    name_counts: dict[str, int] = {}
    for part in sorted_parts:
        base = _safe_filename(part.title)
        name_counts[base] = name_counts.get(base, 0) + 1

    # 連番カウンタ（重複名にのみ使用）
    name_seq: dict[str, int] = {}

    out_paths: list[Path] = []
    for part in sorted_parts:
        src = page_images[part.page]
        img = Image.open(src)
        bb = part.bbox

        left = max(0, int(bb.x))
        upper = max(0, int(bb.y))
        right = min(img.width, int(bb.x + bb.w))
        lower = min(img.height, int(bb.y + bb.h))

        cropped = img.crop((left, upper, right, lower))

        base = _safe_filename(part.title)
        if name_counts[base] > 1:
            # 重複がある場合は _1, _2, ... を付与
            name_seq[base] = name_seq.get(base, 0) + 1
            filename = f"{base}_{name_seq[base]}.png"
        else:
            filename = f"{base}.png"

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
