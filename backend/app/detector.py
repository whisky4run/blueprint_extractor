import base64
import json
import os
from io import BytesIO
from pathlib import Path

from openai import AzureOpenAI
from PIL import Image, ImageDraw

from app.cv_detector import detect_candidate_regions, detect_small_cells
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
    n = len(candidates)
    cands_lines = "\n".join(
        f"  [{i}]: x={int(c.x)}, y={int(c.y)}, 幅={int(c.w)}px, 高さ={int(c.h)}px"
        for i, c in enumerate(candidates)
    )
    all_indices = ", ".join(str(i) for i in range(n))
    return f"""\
画像内に赤枠と番号で示した {n} 個の候補領域があります。

候補一覧:
{cands_lines}

【重要】候補番号 {all_indices} の **全 {n} 件** について、必ずいずれかのエントリに含めてください。
1件でも漏れた場合、出力は不完全とみなします。

各候補を次のルールで判断してください:

■ 図面パーツである場合（平面図・断面図・立面図・詳細図などタイトル付きの図面ビュー）
  → {{"indices": [N], "title": "図面タイトル文字列"}}

■ 複数の候補が1つのパーツを構成する場合（同一列の連続した図面など）
  → {{"indices": [N, M, ...], "title": "図面タイトル文字列"}}
  まとめてよい条件: ある列の複数セルが1つの連続した図面を形成している場合。
  ※ 列タイトルセル（最上部セル）も必ず indices に含めること。
  まとめてはいけない条件: 各セルが異なるスケール（S:1/10、S:1/5 等）または
  異なる製品サイズ（450、600 等）を持ち、独立した図面である場合。

■ 図面パーツでない場合（表題欄・空白領域・凡例・注記のみの欄）
  → {{"indices": [N], "title": "exclude"}}

出力形式: 以下のJSON配列のみ。他のテキストは不要。
[{{"indices": [0], "title": "..."}}、{{"indices": [1], "title": "exclude"}}, ...]

全 {n} 件のすべての番号がいずれかのエントリの indices に含まれていることを確認してから出力してください。"""


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

    # Phase 1: AIレスポンスをパースして (インデックスリスト, タイトル) のグループ一覧に変換
    # "exclude" タイトルは図面パーツでない（表題欄・空白等）として除外する
    groups: list[tuple[list[int], str]] = []
    for item in items:
        # 旧形式 {"index": N} と新形式 {"indices": [...]} の両方に対応
        raw_indices = item.get("indices", item.get("index"))
        title = item.get("title", "").strip()
        if not title or raw_indices is None:
            continue

        # "exclude" はパーツでないと判断されたもの → スキップ
        if title.lower() == "exclude":
            continue

        if isinstance(raw_indices, int):
            idx_list = [raw_indices]
        else:
            idx_list = [i for i in raw_indices if isinstance(i, int)]

        idx_list = [i for i in idx_list if 0 <= i < len(candidates)]
        if idx_list:
            groups.append((idx_list, title))

    # Phase 2: AIが割り当てなかった候補を補完する
    # 同じ列（x・w が一致）かつグループの「上」に隣接する場合のみ追加する。
    # ※ 上方向のみ許可：下方向への拡張は異なるパーツの誤マージを招くため禁止。
    assigned: set[int] = {i for idxs, _ in groups for i in idxs}
    unassigned = [i for i in range(len(candidates)) if i not in assigned]

    _COL_TOL = 5    # 同一列と判定するx/w の許容誤差（px）
    _ADJ_GAP = 100  # 隣接と判定するy方向の最大ギャップ（px）

    for ui in unassigned:
        uc = candidates[ui]
        uc_y2 = uc.y + uc.h
        for idxs, _ in groups:
            # 同一列チェック
            if not all(
                abs(candidates[i].x - uc.x) < _COL_TOL
                and abs(candidates[i].w - uc.w) < _COL_TOL
                for i in idxs
            ):
                continue
            # 上方向のみ：uc がグループより上にあり、かつ隣接している
            g_y1 = min(candidates[i].y for i in idxs)
            if uc.y < g_y1 and uc_y2 >= g_y1 - _ADJ_GAP:
                idxs.append(ui)
                break  # 1グループにのみ追加

    # Phase 2b: 同列の単一セルグループ群をタイトル類似度でまとめる
    # 同列に2個以上の単一セルグループが上下に連続し、タイトルの共通プレフィックス比率が
    # 閾値以上なら1つのグループに統合する。
    # 例: [外枠・内枠断面詳細図 NHEⅡ SP] + [外枠・内枠断面詳細図 NHEⅡ SG] → LCP 81% → まとめる
    #     [NHEⅡ-450 SPOK] + [NHEⅡ-600 SPOK] → LCP 43% → まとめない
    _LCP_MERGE_RATIO = 0.80  # 共通プレフィックス比率の閾値

    def _lcp(*strings: str) -> str:
        """複数文字列の最長共通プレフィックス。"""
        if not strings:
            return ""
        prefix = strings[0]
        for s in strings[1:]:
            i = 0
            while i < len(prefix) and i < len(s) and prefix[i] == s[i]:
                i += 1
            prefix = prefix[:i]
            if not prefix:
                return ""
        return prefix

    # 列キー (x を _COL_TOL 単位で丸めたもの) → 単一セルグループのインデックス
    from collections import defaultdict as _defaultdict
    col_singles: dict[int, list[int]] = _defaultdict(list)
    for gi, (idxs, _) in enumerate(groups):
        if len(idxs) == 1:
            c = candidates[idxs[0]]
            col_key = round(c.x / (_COL_TOL * 2)) * (_COL_TOL * 2)
            col_singles[col_key].append(gi)

    to_remove: set[int] = set()
    for col_key, gis in col_singles.items():
        if len(gis) < 2:
            continue

        # y 順にソート
        gis_sorted = sorted(gis, key=lambda gi: candidates[groups[gi][0][0]].y)

        # 全グループが上から下へ連続しているか確認（各隣接ペアが _ADJ_GAP 以内）
        is_chain = True
        for k in range(len(gis_sorted) - 1):
            ca = candidates[groups[gis_sorted[k]][0][0]]
            cb = candidates[groups[gis_sorted[k + 1]][0][0]]
            if not (ca.y < cb.y and ca.y + ca.h >= cb.y - _ADJ_GAP):
                is_chain = False
                break
        if not is_chain:
            continue

        # タイトルの共通プレフィックス比率を確認
        titles = [groups[gi][1] for gi in gis_sorted]
        common = _lcp(*titles)
        min_len = min(len(t) for t in titles)
        ratio = len(common) / min_len if min_len > 0 else 0.0
        if ratio < _LCP_MERGE_RATIO:
            continue

        # 先頭グループに残りを統合（先頭のタイトルを採用）
        base_gi = gis_sorted[0]
        base_idxs, base_title = groups[base_gi]
        for gi in gis_sorted[1:]:
            base_idxs.extend(groups[gi][0])
            to_remove.add(gi)

    # マージ済みグループを除去
    if to_remove:
        groups = [g for i, g in enumerate(groups) if i not in to_remove]

    # Phase 3: グループごとにBBoxをマージして DetectedPart を生成
    parts: list[DetectedPart] = []
    for idxs, title in groups:
        if len(idxs) == 1:
            bbox = candidates[idxs[0]]
        else:
            x1 = min(candidates[i].x for i in idxs)
            y1 = min(candidates[i].y for i in idxs)
            x2 = max(candidates[i].x + candidates[i].w for i in idxs)
            y2 = max(candidates[i].y + candidates[i].h for i in idxs)
            bbox = BoundingBox(x=x1, y=y1, w=x2 - x1, h=y2 - y1)

        parts.append(DetectedPart(title=title, bbox=bbox, page=page_num))

    # Phase 4: bbox 上端をタイトル行まで拡張する
    # 面積フィルタ不合格の小セル（タイトル行・区切り行）を取得し、
    # 各パーツの上に隣接するものがあれば bbox を上方向へ伸ばす。
    small_cells = detect_small_cells(image_path)

    _TITLE_COL_TOL = 5   # 同一列判定の x/w 許容誤差（px）
    _TITLE_ADJ_TOL = 5   # 隣接判定の y 方向許容誤差（px）

    extended_parts: list[DetectedPart] = []
    for part in parts:
        part_x = part.bbox.x
        part_w = part.bbox.w
        current_top = part.bbox.y

        # 同一列の小セルを上方向に辿る（連鎖的に拡張）
        changed = True
        while changed:
            changed = False
            for sc in small_cells:
                sc_bottom = sc.y + sc.h
                if (
                    abs(sc.x - part_x) < _TITLE_COL_TOL
                    and abs(sc.w - part_w) < _TITLE_COL_TOL
                    and abs(sc_bottom - current_top) <= _TITLE_ADJ_TOL
                    and sc.y < current_top
                ):
                    current_top = sc.y
                    changed = True
                    break  # 1つ見つかったら top を更新して再スキャン

        if current_top < part.bbox.y:
            new_bbox = BoundingBox(
                x=part.bbox.x,
                y=current_top,
                w=part.bbox.w,
                h=part.bbox.y + part.bbox.h - current_top,
            )
            extended_parts.append(DetectedPart(title=part.title, bbox=new_bbox, page=part.page))
        else:
            extended_parts.append(part)

    return extended_parts
