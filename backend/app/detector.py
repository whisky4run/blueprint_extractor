import base64
import json
import os
from io import BytesIO
from pathlib import Path

from openai import AzureOpenAI
from PIL import Image, ImageDraw

from app.cv_detector import detect_candidate_regions
from app.models import BoundingBox, DetectedPart

# 番号ラベルの描画設定
_BOX_COLOR = (220, 30, 30)
_BOX_WIDTH = 3
_LABEL_FONT_SIZE = 24


def _build_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    )


def _annotate_and_encode(image_path: Path, candidates: list[BoundingBox]) -> str:
    """候補BBoxを番号付き赤枠で描画し、base64 PNGを返す。"""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    for i, bb in enumerate(candidates):
        x, y, w, h = int(bb.x), int(bb.y), int(bb.w), int(bb.h)
        draw.rectangle([x, y, x + w, y + h], outline=_BOX_COLOR, width=_BOX_WIDTH)
        # 番号ラベルを左上に描画
        lx, ly = x + 4, y + 4
        draw.rectangle([lx - 2, ly - 2, lx + _LABEL_FONT_SIZE, ly + _LABEL_FONT_SIZE],
                       fill=_BOX_COLOR)
        draw.text((lx, ly), str(i), fill=(255, 255, 255))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _build_prompt(candidates: list[BoundingBox]) -> str:
    cands_lines = "\n".join(
        f"  [{i}]: x={int(c.x)}, y={int(c.y)}, 幅={int(c.w)}px, 高さ={int(c.h)}px"
        for i, c in enumerate(candidates)
    )
    return f"""\
画像内に赤枠と番号で示した候補領域があります。

候補一覧:
{cands_lines}

各候補について、建築図面のパーツ（平面図・断面図・立面図・詳細図など、\
タイトルが付いた図面ビュー）に該当するか判断し、該当するもののタイトル文字列を返してください。

除外する領域:
- 表題欄（会社名・設計者・スタンプ・図面番号のみの欄）
- タイトルのない空白領域
- 凡例・注記のみの小さな欄

出力形式: 以下のJSON配列のみ。他のテキストは不要。
[{{"index": 0, "title": "タイトル文字列"}}, ...]

パーツが1つもなければ [] を返してください。"""


def detect_parts(image_path: Path, page_num: int) -> list[DetectedPart]:
    """
    1. OpenCVで候補領域を検出（精密なBBox）
    2. AIに「どの候補がパーツか＋タイトル」を問い合わせ
    3. AIのインデックス応答とCVのBBoxを組み合わせてDetectedPartを返す
    """
    candidates = detect_candidate_regions(image_path)
    if not candidates:
        return []

    b64 = _annotate_and_encode(image_path, candidates)
    prompt = _build_prompt(candidates)

    client = _build_client()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_completion_tokens=1024,
        temperature=0,
    )

    raw = (response.choices[0].message.content or "[]").strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.split("```")[0].strip()

    items: list[dict] = json.loads(raw)

    parts: list[DetectedPart] = []
    for item in items:
        idx = item.get("index")
        title = item.get("title", "").strip()
        if isinstance(idx, int) and 0 <= idx < len(candidates) and title:
            parts.append(DetectedPart(title=title, bbox=candidates[idx], page=page_num))

    return parts
