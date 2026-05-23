import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request

from PIL import Image

from app.cv_detector import detect_all_cells
from app.header_position import HeaderPosition
from app.models import BoundingBox, DetectedPart, HeaderFieldItem
from app.title_position import TitlePosition

_SOURCE_PATTERN = re.compile(r"D\(([^)]+)\)")


@dataclass(frozen=True)
class _PageCrop:
    page_idx: int
    image_path: Path
    offset_x: float
    offset_y: float
    bbox: BoundingBox


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} が未設定です")
    return value


def _cu_headers(api_key: str) -> dict[str, str]:
    return {
        "Ocp-Apim-Subscription-Key": api_key,
        "Accept": "application/json",
    }


def _http_json(method: str, url: str, headers: dict[str, str], data: bytes | None = None) -> tuple[int, dict, bytes]:
    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=180) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), body
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"AzureCU API エラー: status={e.code} body={detail[:500]}") from e
    except error.URLError as e:
        raise RuntimeError(f"AzureCU API 接続エラー: {e}") from e


def _default_api_version() -> str:
    return os.environ.get("AZURE_CU_API_VERSION", "2025-05-01-preview")


def list_analyzers(api_version: str | None = None) -> list[dict]:
    endpoint = _required_env("AZURE_CU_ENDPOINT").rstrip("/")
    api_key = _required_env("AZURE_CU_API_KEY")
    resolved_api_version = (api_version or "").strip() or _default_api_version()

    headers = _cu_headers(api_key)
    url = f"{endpoint}/contentunderstanding/analyzers?api-version={resolved_api_version}"

    items: list[dict] = []
    while True:
        _, _, body = _http_json("GET", url, headers)
        payload = json.loads(body.decode("utf-8"))
        value = payload.get("value")
        if isinstance(value, list):
            items.extend(v for v in value if isinstance(v, dict))
        next_link = payload.get("nextLink")
        if not isinstance(next_link, str) or not next_link:
            break
        url = next_link

    return items


def _analyze_binary(
    input_path: Path,
    analyzer_id: str | None = None,
    api_version: str | None = None,
    content_type: str = "application/octet-stream",
) -> dict:
    endpoint = _required_env("AZURE_CU_ENDPOINT").rstrip("/")
    api_key = _required_env("AZURE_CU_API_KEY")
    resolved_analyzer_id = (analyzer_id or "").strip() or _required_env("AZURE_CU_ANALYZER_ID")
    resolved_api_version = (api_version or "").strip() or _default_api_version()

    # Binary file input is supported by :analyzeBinary.
    analyze_url = (
        f"{endpoint}/contentunderstanding/analyzers/{resolved_analyzer_id}:analyzeBinary"
        f"?api-version={resolved_api_version}"
    )
    headers = _cu_headers(api_key)
    headers["Content-Type"] = content_type
    status, res_headers, body = _http_json(
        "POST",
        analyze_url,
        headers,
        data=input_path.read_bytes(),
    )

    if status == 200:
        return json.loads(body.decode("utf-8"))

    operation_location = res_headers.get("Operation-Location")
    if not operation_location:
        raise RuntimeError("AzureCU の Operation-Location ヘッダーがありません")

    poll_interval_sec = float(os.environ.get("AZURE_CU_POLL_INTERVAL_SEC", "1.0"))
    timeout_sec = float(os.environ.get("AZURE_CU_POLL_TIMEOUT_SEC", "180"))
    deadline = time.time() + timeout_sec

    poll_headers = _cu_headers(api_key)
    while True:
        if time.time() > deadline:
            raise RuntimeError("AzureCU の解析結果待機がタイムアウトしました")
        time.sleep(poll_interval_sec)
        _, _, poll_body = _http_json("GET", operation_location, poll_headers)
        payload = json.loads(poll_body.decode("utf-8"))
        status_text = (payload.get("status") or "").lower()

        if status_text == "succeeded":
            return payload
        if status_text in {"failed", "canceled"}:
            raise RuntimeError(f"AzureCU 解析失敗: status={status_text}")


def _analyze_pdf(
    pdf_path: Path,
    analyzer_id: str | None = None,
    api_version: str | None = None,
) -> dict:
    return _analyze_binary(
        pdf_path,
        analyzer_id=analyzer_id,
        api_version=api_version,
        content_type="application/pdf",
    )


def _analyze_image(
    image_path: Path,
    analyzer_id: str | None = None,
    api_version: str | None = None,
) -> dict:
    return _analyze_binary(
        image_path,
        analyzer_id=analyzer_id,
        api_version=api_version,
        content_type="image/png",
    )


def _field_to_object(field: object) -> dict:
    if isinstance(field, dict):
        value_obj = field.get("valueObject")
        if isinstance(value_obj, dict):
            return value_obj
        return field
    return {}


def _field_to_array(field: object) -> list:
    if isinstance(field, list):
        return field
    if isinstance(field, dict):
        value = field.get("valueArray")
        if isinstance(value, list):
            return value
    return []


def _field_to_string(field: object) -> str:
    if isinstance(field, str):
        return field.strip()
    if isinstance(field, (int, float)):
        return str(field)
    if isinstance(field, dict):
        for key in ("valueString", "content", "text"):
            v = field.get(key)
            if isinstance(v, str):
                return v.strip()
        v = field.get("value")
        if isinstance(v, str):
            return v.strip()
    return ""


def _field_value_to_string(field: object) -> str:
    if isinstance(field, str):
        return field.strip()
    if isinstance(field, (int, float)):
        return str(field)
    if isinstance(field, dict):
        for key in (
            "valueString",
            "valueDate",
            "valueTime",
            "valuePhoneNumber",
            "valueCountryRegion",
            "valueSelectionMark",
            "content",
            "text",
        ):
            v = field.get(key)
            if isinstance(v, str):
                return v.strip()
        for key in ("valueInteger", "valueNumber"):
            v = field.get(key)
            if isinstance(v, (int, float)):
                return str(v)
    return _field_to_string(field)


def _field_to_int(field: object) -> int | None:
    if isinstance(field, int):
        return field
    if isinstance(field, float):
        return int(field)
    if isinstance(field, str):
        s = field.strip()
        return int(s) if s.isdigit() else None
    if isinstance(field, dict):
        for key in ("valueInteger", "valueNumber", "value"):
            v = field.get(key)
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, str) and v.strip().isdigit():
                return int(v.strip())
    return None


def _field_to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("valueNumber", "valueInteger", "value"):
            candidate = value.get(key)
            if isinstance(candidate, (int, float)):
                return float(candidate)
            if isinstance(candidate, str):
                try:
                    return float(candidate.strip())
                except ValueError:
                    pass
    return None


def _parse_source(source: str) -> tuple[int, list[float], list[float]] | None:
    for match in _SOURCE_PATTERN.finditer(source):
        raw = [p.strip() for p in match.group(1).split(",")]
        if len(raw) < 5:
            continue

        try:
            page_num = int(float(raw[0]))
        except ValueError:
            continue

        coords: list[float] = []
        for part in raw[1:]:
            try:
                coords.append(float(part))
            except ValueError:
                pass

        if len(coords) < 4:
            continue

        xs = coords[0::2]
        ys = coords[1::2]
        if not xs or not ys:
            continue

        return page_num, xs, ys

    return None


def _bbox_from_field(field: object, page_w: int, page_h: int) -> BoundingBox | None:
    obj = _field_to_object(field)
    if obj:
        x = _field_to_float(obj.get("x"))
        y = _field_to_float(obj.get("y"))
        w = _field_to_float(obj.get("w"))
        h = _field_to_float(obj.get("h"))
        if None not in (x, y, w, h):
            return _normalize_bbox(float(x), float(y), float(w), float(h), page_w, page_h)

    if isinstance(field, dict):
        polygon = field.get("polygon")
        if isinstance(polygon, list):
            bb = _bbox_from_polygon(polygon, page_w, page_h)
            if bb:
                return bb

    return None


def _bbox_from_polygon(polygon: list, page_w: int, page_h: int) -> BoundingBox | None:
    numbers = [float(v) for v in polygon if isinstance(v, (int, float))]
    if len(numbers) < 4:
        return None
    xs = numbers[0::2]
    ys = numbers[1::2]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    return _normalize_bbox(x1, y1, x2 - x1, y2 - y1, page_w, page_h)


def _bbox_from_source(
    source: str,
    page_w_px: int,
    page_h_px: int,
    source_page_w: float | None = None,
    source_page_h: float | None = None,
) -> tuple[int, BoundingBox] | None:
    parsed = _parse_source(source)
    if not parsed:
        return None

    page_num, xs, ys = parsed
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)

    if source_page_w and source_page_h and source_page_w > 0 and source_page_h > 0:
        x1 = (x1 / source_page_w) * page_w_px
        x2 = (x2 / source_page_w) * page_w_px
        y1 = (y1 / source_page_h) * page_h_px
        y2 = (y2 / source_page_h) * page_h_px
    elif 0 <= x2 <= 1.0 and 0 <= y2 <= 1.0:
        x1 *= page_w_px
        x2 *= page_w_px
        y1 *= page_h_px
        y2 *= page_h_px

    bbox = _normalize_bbox(x1, y1, x2 - x1, y2 - y1, page_w_px, page_h_px)
    return page_num, bbox


def _normalize_bbox(x: float, y: float, w: float, h: float, page_w: int, page_h: int) -> BoundingBox:
    # 0-1 の正規化座標ならピクセルへ変換
    if 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1:
        x *= page_w
        y *= page_h
        w *= page_w
        h *= page_h

    left = max(0.0, min(float(page_w), x))
    top = max(0.0, min(float(page_h), y))
    right = max(left, min(float(page_w), x + w))
    bottom = max(top, min(float(page_h), y + h))
    return BoundingBox(x=left, y=top, w=right - left, h=bottom - top)


def _extract_page_size_map(payload: dict) -> dict[int, tuple[float, float]]:
    page_sizes: dict[int, tuple[float, float]] = {}

    def _put_page(item: dict) -> None:
        page_num = _field_to_int(item.get("pageNumber"))
        width = _field_to_float(item.get("width"))
        height = _field_to_float(item.get("height"))
        if page_num and width and height and width > 0 and height > 0:
            page_sizes[page_num] = (width, height)

    result = payload.get("result", {})

    pages = result.get("pages")
    if isinstance(pages, list):
        for page in pages:
            if isinstance(page, dict):
                _put_page(page)

    contents = result.get("contents")
    if isinstance(contents, list):
        for content in contents:
            if not isinstance(content, dict):
                continue
            content_pages = content.get("pages")
            if isinstance(content_pages, list):
                for page in content_pages:
                    if isinstance(page, dict):
                        _put_page(page)

    return page_sizes


def _extract_rows(payload: dict) -> list[dict]:
    rows: list[dict] = []
    result = payload.get("result", {})

    parts_field_name = os.environ.get("AZURE_CU_PARTS_FIELD", "parts")
    title_field_name = os.environ.get("AZURE_CU_TITLE_FIELD", "title")
    page_field_name = os.environ.get("AZURE_CU_PAGE_FIELD", "page")
    bbox_field_name = os.environ.get("AZURE_CU_BBOX_FIELD", "bbox")

    # 1) 標準想定: result.fields.parts.valueArray[].valueObject
    fields = result.get("fields", {})
    if isinstance(fields, dict):
        part_rows = _field_to_array(fields.get(parts_field_name))
        for row in part_rows:
            row_obj = _field_to_object(row)
            title_field = row_obj.get(title_field_name)
            source_field = row_obj.get("source")
            if isinstance(title_field, dict):
                source_field = source_field or title_field.get("source")
            rows.append(
                {
                    "title": title_field,
                    "page": row_obj.get(page_field_name),
                    "bbox": row_obj.get(bbox_field_name),
                    "source": source_field,
                }
            )

    if rows:
        return rows

    # 2) サンプルJSON想定: result.contents[].fields.<custom-title-field>
    contents = result.get("contents")
    if not isinstance(contents, list):
        return rows

    for content in contents:
        if not isinstance(content, dict):
            continue
        content_fields = content.get("fields")
        if not isinstance(content_fields, dict):
            continue

        for _, field in content_fields.items():
            if not isinstance(field, dict):
                continue

            value_obj = field.get("valueObject")
            if isinstance(value_obj, dict):
                title_field = value_obj.get(title_field_name)
                source_field = value_obj.get("source")
                if isinstance(title_field, dict):
                    source_field = source_field or title_field.get("source")
                rows.append(
                    {
                        "title": title_field,
                        "page": value_obj.get(page_field_name),
                        "bbox": value_obj.get(bbox_field_name),
                        "source": source_field,
                    }
                )
                continue

            title = _field_to_string(field)
            if not title:
                continue
            rows.append(
                {
                    "title": title,
                    "page": field.get(page_field_name),
                    "bbox": field.get(bbox_field_name),
                    "source": field.get("source"),
                }
            )

    return rows


def _extract_header_fields(payload: dict, page_images: list[Path]) -> tuple[list[HeaderFieldItem], dict[str, str]]:
    result = payload.get("result", {})
    contents = result.get("contents")
    if not isinstance(contents, list):
        return [], {}

    page_size_map = _extract_page_size_map(payload)
    items: list[HeaderFieldItem] = []
    key_values: dict[str, str] = {}

    for content in contents:
        if not isinstance(content, dict):
            continue
        fields = content.get("fields")
        if not isinstance(fields, dict):
            continue

        for key, field in fields.items():
            if not isinstance(field, dict):
                continue

            value = _field_value_to_string(field)
            if not value:
                continue

            source = _field_to_string(field.get("source")) or None
            page_idx: int | None = None
            bbox: BoundingBox | None = None

            if source:
                source_parsed = _parse_source(source)
                if source_parsed:
                    page_num = source_parsed[0]
                    parsed_page_idx = page_num - 1
                    if 0 <= parsed_page_idx < len(page_images):
                        with Image.open(page_images[parsed_page_idx]) as page_img:
                            page_w_px, page_h_px = page_img.width, page_img.height

                        source_page_w = None
                        source_page_h = None
                        dims = page_size_map.get(page_num)
                        if dims:
                            source_page_w, source_page_h = dims

                        parsed_bbox = _bbox_from_source(
                            source,
                            page_w_px,
                            page_h_px,
                            source_page_w=source_page_w,
                            source_page_h=source_page_h,
                        )
                        if parsed_bbox:
                            _, src_bbox = parsed_bbox
                            bbox = src_bbox
                            page_idx = parsed_page_idx

            items.append(
                HeaderFieldItem(
                    key=str(key),
                    value=value,
                    page=page_idx,
                    bbox=bbox,
                    source=source,
                )
            )
            key_values[str(key)] = value

    return items, key_values


def _intersection_area(a: BoundingBox, b: BoundingBox) -> float:
    ax2 = a.x + a.w
    ay2 = a.y + a.h
    bx2 = b.x + b.w
    by2 = b.y + b.h
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    return (x2 - x1) * (y2 - y1)


def _contains_point(bb: BoundingBox, x: float, y: float, tol: float = 1.0) -> bool:
    return (bb.x - tol) <= x <= (bb.x + bb.w + tol) and (bb.y - tol) <= y <= (bb.y + bb.h + tol)


def _bbox_center(bb: BoundingBox) -> tuple[float, float]:
    return bb.x + bb.w / 2.0, bb.y + bb.h / 2.0


def _find_title_cell_index(cells: list[BoundingBox], title_bbox: BoundingBox) -> int | None:
    if not cells:
        return None

    best_idx = None
    best_overlap = 0.0
    for i, cell in enumerate(cells):
        overlap = _intersection_area(cell, title_bbox)
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = i
    if best_idx is not None and best_overlap > 0:
        return best_idx

    cx, cy = _bbox_center(title_bbox)
    for i, cell in enumerate(cells):
        if _contains_point(cell, cx, cy):
            return i

    # Fallback: nearest cell center
    nearest_idx = 0
    nearest_dist = float("inf")
    for i, cell in enumerate(cells):
        ccx, ccy = _bbox_center(cell)
        dist = (ccx - cx) ** 2 + (ccy - cy) ** 2
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_idx = i
    return nearest_idx


def _same_column(a: BoundingBox, b: BoundingBox, tol: float) -> bool:
    return abs(a.x - b.x) <= tol and abs(a.w - b.w) <= tol


def _same_row(a: BoundingBox, b: BoundingBox, tol: float) -> bool:
    return abs(a.y - b.y) <= tol and abs(a.h - b.h) <= tol


def _next_cell_index(
    cells: list[BoundingBox],
    current_idx: int,
    anchor_idx: int,
    direction: str,
    tol: float,
) -> int | None:
    current = cells[current_idx]
    anchor = cells[anchor_idx]
    best_idx = None
    best_gap = float("inf")

    for i, cand in enumerate(cells):
        if i == current_idx:
            continue

        if direction in {"down", "up"}:
            if not _same_column(cand, anchor, tol):
                continue
        else:
            if not _same_row(cand, anchor, tol):
                continue

        gap = None
        if direction == "down":
            edge = current.y + current.h
            if cand.y >= edge - tol:
                gap = abs(cand.y - edge)
        elif direction == "up":
            edge = current.y
            cand_edge = cand.y + cand.h
            if cand_edge <= edge + tol:
                gap = abs(edge - cand_edge)
        elif direction == "right":
            edge = current.x + current.w
            if cand.x >= edge - tol:
                gap = abs(cand.x - edge)
        elif direction == "left":
            edge = current.x
            cand_edge = cand.x + cand.w
            if cand_edge <= edge + tol:
                gap = abs(edge - cand_edge)

        if gap is None:
            continue

        if gap < best_gap:
            best_gap = gap
            best_idx = i

    return best_idx


def _merge_cell_bboxes(cells: list[BoundingBox]) -> BoundingBox:
    x1 = min(c.x for c in cells)
    y1 = min(c.y for c in cells)
    x2 = max(c.x + c.w for c in cells)
    y2 = max(c.y + c.h for c in cells)
    return BoundingBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1)


def _expand_parts_by_grid(
    page_images: list[Path],
    parts: list[DetectedPart],
    title_position: TitlePosition,
) -> list[DetectedPart]:
    if not parts:
        return parts

    growth_by_title_position = {
        "top": "down",
        "bottom": "up",
        "left": "right",
        "right": "left",
    }
    direction = growth_by_title_position[title_position]

    by_page: dict[int, list[tuple[int, DetectedPart]]] = {}
    for idx, part in enumerate(parts):
        by_page.setdefault(part.page, []).append((idx, part))

    expanded: list[DetectedPart] = list(parts)
    tol = 6.0

    for page_idx, indexed_parts in by_page.items():
        if page_idx < 0 or page_idx >= len(page_images):
            continue

        cells = detect_all_cells(page_images[page_idx])
        if not cells:
            continue

        part_to_cell: dict[int, int] = {}
        for idx, part in indexed_parts:
            title_cell_idx = _find_title_cell_index(cells, part.bbox)
            if title_cell_idx is not None:
                part_to_cell[idx] = title_cell_idx

        title_cell_indices = set(part_to_cell.values())

        for idx, part in indexed_parts:
            start_idx = part_to_cell.get(idx)
            if start_idx is None:
                continue

            visited = {start_idx}
            chain_indices = [start_idx]
            current_idx = start_idx

            while True:
                nxt = _next_cell_index(cells, current_idx, start_idx, direction, tol)
                if nxt is None or nxt in visited:
                    break
                if nxt in title_cell_indices and nxt != start_idx:
                    break
                visited.add(nxt)
                chain_indices.append(nxt)
                current_idx = nxt

            merged = _merge_cell_bboxes([cells[i] for i in chain_indices])
            expanded[idx] = DetectedPart(title=part.title, bbox=merged, page=part.page)

    return expanded


def _is_in_header_band(
    bbox: BoundingBox,
    page_w: int,
    page_h: int,
    header_position: HeaderPosition,
    band_ratio: float,
) -> bool:
    cx = bbox.x + bbox.w / 2.0
    cy = bbox.y + bbox.h / 2.0

    if header_position == "right":
        return cx >= page_w * (1.0 - band_ratio)
    if header_position == "left":
        return cx <= page_w * band_ratio
    if header_position == "top":
        return cy <= page_h * band_ratio
    if header_position == "bottom":
        return cy >= page_h * (1.0 - band_ratio)
    return False


def _split_header_items(
    page_images: list[Path],
    parts: list[DetectedPart],
    header_position: HeaderPosition,
) -> tuple[list[DetectedPart], list[DetectedPart]]:
    if not parts:
        return [], []

    band_ratio = float(os.environ.get("HEADER_BAND_RATIO", "0.24"))
    band_ratio = max(0.05, min(0.45, band_ratio))

    page_sizes: dict[int, tuple[int, int]] = {}
    for p in parts:
        if p.page in page_sizes:
            continue
        if p.page < 0 or p.page >= len(page_images):
            continue
        with Image.open(page_images[p.page]) as img:
            page_sizes[p.page] = (img.width, img.height)

    kept: list[DetectedPart] = []
    headers: list[DetectedPart] = []
    for p in parts:
        dims = page_sizes.get(p.page)
        if not dims:
            kept.append(p)
            continue
        page_w, page_h = dims
        if _is_in_header_band(
            p.bbox,
            page_w=page_w,
            page_h=page_h,
            header_position=header_position,
            band_ratio=band_ratio,
        ):
            headers.append(p)
        else:
            kept.append(p)

    return kept, headers


def _filter_header_field_items(
    page_images: list[Path],
    items: list[HeaderFieldItem],
    header_position: HeaderPosition,
) -> list[HeaderFieldItem]:
    if not items:
        return items

    band_ratio = float(os.environ.get("HEADER_BAND_RATIO", "0.24"))
    band_ratio = max(0.05, min(0.45, band_ratio))

    page_sizes: dict[int, tuple[int, int]] = {}
    for p in items:
        if p.page is None or p.page in page_sizes:
            continue
        if p.page < 0 or p.page >= len(page_images):
            continue
        with Image.open(page_images[p.page]) as img:
            page_sizes[p.page] = (img.width, img.height)

    filtered: list[HeaderFieldItem] = []
    for item in items:
        if item.page is None or item.bbox is None:
            filtered.append(item)
            continue
        dims = page_sizes.get(item.page)
        if not dims:
            filtered.append(item)
            continue
        page_w, page_h = dims
        if _is_in_header_band(
            item.bbox,
            page_w=page_w,
            page_h=page_h,
            header_position=header_position,
            band_ratio=band_ratio,
        ):
            filtered.append(item)

    return filtered


def _fallback_header_rect(page_w: int, page_h: int, header_position: HeaderPosition) -> BoundingBox:
    band_ratio = float(os.environ.get("HEADER_BAND_RATIO", "0.24"))
    band_ratio = max(0.05, min(0.45, band_ratio))
    if header_position == "right":
        x = page_w * (1.0 - band_ratio)
        return BoundingBox(x=x, y=0, w=page_w - x, h=page_h)
    if header_position == "left":
        w = page_w * band_ratio
        return BoundingBox(x=0, y=0, w=w, h=page_h)
    if header_position == "top":
        h = page_h * band_ratio
        return BoundingBox(x=0, y=0, w=page_w, h=h)
    h = page_h * band_ratio
    return BoundingBox(x=0, y=page_h - h, w=page_w, h=h)


def _detect_header_rect(image_path: Path, header_position: HeaderPosition) -> BoundingBox:
    with Image.open(image_path) as img:
        page_w, page_h = img.width, img.height

    cells = detect_all_cells(image_path)
    if not cells:
        return _fallback_header_rect(page_w, page_h, header_position)

    band_ratio = float(os.environ.get("HEADER_BAND_RATIO", "0.24"))
    band_ratio = max(0.05, min(0.45, band_ratio))
    candidates = [
        c
        for c in cells
        if _is_in_header_band(
            c,
            page_w=page_w,
            page_h=page_h,
            header_position=header_position,
            band_ratio=band_ratio,
        )
    ]
    if not candidates:
        return _fallback_header_rect(page_w, page_h, header_position)

    merged = _merge_cell_bboxes(candidates)
    if header_position == "right":
        return BoundingBox(x=merged.x, y=0, w=page_w - merged.x, h=page_h)
    if header_position == "left":
        right = merged.x + merged.w
        return BoundingBox(x=0, y=0, w=right, h=page_h)
    if header_position == "top":
        bottom = merged.y + merged.h
        return BoundingBox(x=0, y=0, w=page_w, h=bottom)
    return BoundingBox(x=0, y=merged.y, w=page_w, h=page_h - merged.y)


def _content_rect_from_header(
    page_w: int,
    page_h: int,
    header_rect: BoundingBox,
    header_position: HeaderPosition,
) -> BoundingBox:
    if header_position == "right":
        return BoundingBox(x=0, y=0, w=header_rect.x, h=page_h)
    if header_position == "left":
        x = header_rect.x + header_rect.w
        return BoundingBox(x=x, y=0, w=page_w - x, h=page_h)
    if header_position == "top":
        y = header_rect.y + header_rect.h
        return BoundingBox(x=0, y=y, w=page_w, h=page_h - y)
    return BoundingBox(x=0, y=0, w=page_w, h=header_rect.y)


def _save_crop(page_image: Path, bbox: BoundingBox, out_dir: Path, name: str, page_idx: int) -> _PageCrop | None:
    with Image.open(page_image) as img:
        page_w, page_h = img.width, img.height
        left = max(0, min(page_w, int(round(bbox.x))))
        top = max(0, min(page_h, int(round(bbox.y))))
        right = max(left, min(page_w, int(round(bbox.x + bbox.w))))
        bottom = max(top, min(page_h, int(round(bbox.y + bbox.h))))
        if right <= left or bottom <= top:
            return None

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}_page_{page_idx + 1}.png"
        img.crop((left, top, right, bottom)).save(out_path, format="PNG")

    crop_bbox = BoundingBox(x=float(left), y=float(top), w=float(right - left), h=float(bottom - top))
    return _PageCrop(
        page_idx=page_idx,
        image_path=out_path,
        offset_x=crop_bbox.x,
        offset_y=crop_bbox.y,
        bbox=crop_bbox,
    )


def _prepare_azurecu_image_inputs(
    pdf_path: Path,
    page_images: list[Path],
    header_position: HeaderPosition,
) -> tuple[list[_PageCrop], list[_PageCrop]]:
    out_dir = pdf_path.parent / "azurecu_inputs"
    content_crops: list[_PageCrop] = []
    header_crops: list[_PageCrop] = []

    for page_idx, page_image in enumerate(page_images):
        with Image.open(page_image) as img:
            page_w, page_h = img.width, img.height

        header_rect = _detect_header_rect(page_image, header_position)
        content_rect = _content_rect_from_header(page_w, page_h, header_rect, header_position)

        content_crop = _save_crop(page_image, content_rect, out_dir, "contents", page_idx)
        header_crop = _save_crop(page_image, header_rect, out_dir, "header", page_idx)
        if content_crop:
            content_crops.append(content_crop)
        if header_crop:
            header_crops.append(header_crop)

    return content_crops, header_crops


def _offset_bbox(bbox: BoundingBox, crop: _PageCrop) -> BoundingBox:
    return BoundingBox(
        x=bbox.x + crop.offset_x,
        y=bbox.y + crop.offset_y,
        w=bbox.w,
        h=bbox.h,
    )


def _write_analysis_artifact(output_path: Path | None, kind: str, analyses: list[tuple[_PageCrop, dict]]) -> None:
    if output_path is None:
        return
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": kind,
            "input": "image",
            "items": [
                {
                    "page": crop.page_idx,
                    "image": str(crop.image_path),
                    "offset": {"x": crop.offset_x, "y": crop.offset_y},
                    "bbox": crop.bbox.model_dump(),
                    "payload": payload,
                }
                for crop, payload in analyses
            ],
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _extract_header_fields_from_crop(payload: dict, crop: _PageCrop) -> list[HeaderFieldItem]:
    result = payload.get("result", {})
    contents = result.get("contents")
    if not isinstance(contents, list):
        return []

    page_size_map = _extract_page_size_map(payload)
    items: list[HeaderFieldItem] = []

    with Image.open(crop.image_path) as img:
        crop_w_px, crop_h_px = img.width, img.height

    for content in contents:
        if not isinstance(content, dict):
            continue
        fields = content.get("fields")
        if not isinstance(fields, dict):
            continue

        for key, field in fields.items():
            if not isinstance(field, dict):
                continue

            value = _field_value_to_string(field)
            if not value:
                continue

            source = _field_to_string(field.get("source")) or None
            bbox: BoundingBox | None = None
            if source:
                source_parsed = _parse_source(source)
                source_page_w = None
                source_page_h = None
                if source_parsed:
                    dims = page_size_map.get(source_parsed[0])
                    if dims:
                        source_page_w, source_page_h = dims

                parsed_bbox = _bbox_from_source(
                    source,
                    crop_w_px,
                    crop_h_px,
                    source_page_w=source_page_w,
                    source_page_h=source_page_h,
                )
                if parsed_bbox:
                    _, src_bbox = parsed_bbox
                    bbox = _offset_bbox(src_bbox, crop)

            items.append(
                HeaderFieldItem(
                    key=str(key),
                    value=value,
                    page=crop.page_idx,
                    bbox=bbox,
                    source=source,
                )
            )

    return items


def detect_parts_from_pdf(
    pdf_path: Path,
    page_images: list[Path],
    title_position: TitlePosition = "top",
    header_position: HeaderPosition = "right",
    cu_analyzer_id: str | None = None,
    cu_api_version: str | None = None,
    raw_output_path: Path | None = None,
    cu_header_analyzer_id: str | None = None,
    cu_header_api_version: str | None = None,
    header_raw_output_path: Path | None = None,
) -> tuple[list[DetectedPart], list[DetectedPart], list[HeaderFieldItem]]:
    content_crops, header_crops = _prepare_azurecu_image_inputs(
        pdf_path,
        page_images,
        header_position=header_position,
    )

    content_analyses: list[tuple[_PageCrop, dict]] = []
    for crop in content_crops:
        payload = _analyze_image(
            crop.image_path,
            analyzer_id=cu_analyzer_id,
            api_version=cu_api_version,
        )
        content_analyses.append((crop, payload))
    _write_analysis_artifact(raw_output_path, "contents", content_analyses)

    detected_parts: list[DetectedPart] = []
    seen: set[tuple] = set()

    for crop, payload in content_analyses:
        page_size_map = _extract_page_size_map(payload)
        rows = _extract_rows(payload)

        with Image.open(crop.image_path) as crop_img:
            crop_w_px, crop_h_px = crop_img.width, crop_img.height

        for row in rows:
            title = _field_to_string(row.get("title"))
            if not title:
                continue

            source = _field_to_string(row.get("source"))
            source_parsed = _parse_source(source) if source else None

            page_num = _field_to_int(row.get("page"))
            if page_num is None and source_parsed:
                page_num = source_parsed[0]
            if page_num is None:
                page_num = 1

            bbox = _bbox_from_field(row.get("bbox"), crop_w_px, crop_h_px)

            if not bbox and source:
                source_page_w = None
                source_page_h = None
                dims = page_size_map.get(page_num)
                if dims:
                    source_page_w, source_page_h = dims

                parsed_bbox = _bbox_from_source(
                    source,
                    crop_w_px,
                    crop_h_px,
                    source_page_w=source_page_w,
                    source_page_h=source_page_h,
                )
                if parsed_bbox:
                    _, src_bbox = parsed_bbox
                    bbox = src_bbox

            if not bbox or bbox.w <= 0 or bbox.h <= 0:
                continue

            bbox = _offset_bbox(bbox, crop)
            page_idx = crop.page_idx

            key = (
                title,
                page_idx,
                round(bbox.x, 1),
                round(bbox.y, 1),
                round(bbox.w, 1),
                round(bbox.h, 1),
            )
            if key in seen:
                continue
            seen.add(key)

            detected_parts.append(DetectedPart(title=title, bbox=bbox, page=page_idx))

    expanded = _expand_parts_by_grid(page_images, detected_parts, title_position=title_position)
    kept_parts, header_items = _split_header_items(page_images, expanded, header_position=header_position)

    header_field_items: list[HeaderFieldItem] = []
    resolved_header_analyzer_id = (cu_header_analyzer_id or "").strip()
    if resolved_header_analyzer_id:
        header_analyses: list[tuple[_PageCrop, dict]] = []
        for crop in header_crops:
            header_payload = _analyze_image(
                crop.image_path,
                analyzer_id=resolved_header_analyzer_id,
                api_version=cu_header_api_version,
            )
            header_analyses.append((crop, header_payload))
            header_field_items.extend(_extract_header_fields_from_crop(header_payload, crop))
        _write_analysis_artifact(header_raw_output_path, "header", header_analyses)
        header_field_items = _filter_header_field_items(
            page_images,
            header_field_items,
            header_position=header_position,
        )

    return kept_parts, header_items, header_field_items
