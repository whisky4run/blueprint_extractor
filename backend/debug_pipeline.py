"""
パイプライン診断スクリプト
各ステップの結果を出力し、OpenCV中間画像を /tmp/bp_debug/ に保存する。

使い方（コンテナ内 or ローカル）:
    python debug_pipeline.py <PDFパス>

例:
    python debug_pipeline.py /app/test.pdf
"""
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

# ── 引数チェック ──────────────────────────────────────────────
if len(sys.argv) < 2:
    print("使い方: python debug_pipeline.py <PDFパス>")
    sys.exit(1)

pdf_path = Path(sys.argv[1])
if not pdf_path.exists():
    print(f"[ERROR] ファイルが見つかりません: {pdf_path}")
    sys.exit(1)

DEBUG_DIR = Path("/tmp/bp_debug")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)
print(f"\n中間画像の保存先: {DEBUG_DIR}\n")
print("=" * 60)

# ── Step 1: PDF → PNG 変換 ────────────────────────────────────
print("[Step 1] PDF → PNG 変換")
try:
    from app.pdf_converter import pdf_to_images
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pages = pdf_to_images(pdf_path, tmp_path)
        print(f"  変換成功: {len(pages)} ページ")

        if not pages:
            print("  [ERROR] ページ画像が1枚も生成されませんでした")
            sys.exit(1)

        # 診断用に1枚目を debug_dir にコピーして保存
        for i, p in enumerate(pages):
            img = cv2.imread(str(p))
            if img is None:
                print(f"  [ERROR] ページ{i}: cv2.imread が None を返しました（パス or フォーマット問題）")
                continue
            h, w = img.shape[:2]
            print(f"  ページ{i}: {w}×{h} px ({w/150*25.4:.0f}mm × {h/150*25.4:.0f}mm @ 150dpi)")
            out = DEBUG_DIR / f"page_{i:03d}.png"
            cv2.imwrite(str(out), img)
            print(f"    → 保存: {out}")

        # 以降の処理は1ページ目のみ対象
        first_page = DEBUG_DIR / "page_000.png"
        if not first_page.exists():
            print("[ERROR] ページ画像の保存に失敗しました")
            sys.exit(1)

except Exception as e:
    print(f"  [ERROR] PDF変換中に例外: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)

# ── Step 2: OpenCV 中間処理の可視化 ──────────────────────────
print("[Step 2] OpenCV 候補領域検出（中間画像を保存）")

from app.cv_detector import MIN_LINE_SPAN_RATIO, MIN_AREA_RATIO, MERGE_TOLERANCE
from app.models import BoundingBox

img_gray = cv2.imread(str(first_page), cv2.IMREAD_GRAYSCALE)
h, w = img_gray.shape
print(f"  グレースケール画像: {w}×{h}")

# 二値化
_, binary = cv2.threshold(img_gray, 200, 255, cv2.THRESH_BINARY_INV)
cv2.imwrite(str(DEBUG_DIR / "step2a_binary.png"), binary)
white_ratio = binary.sum() / 255 / (w * h) * 100
print(f"  二値化後の白画素率: {white_ratio:.2f}%  (0%=全黒→閾値問題, >20%=ノイズ過多)")

# 水平線検出
min_h_span = max(int(w * MIN_LINE_SPAN_RATIO), 20)
k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (min_h_span, 1))
horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_h)
cv2.imwrite(str(DEBUG_DIR / "step2b_horiz.png"), horiz)
h_white = horiz.sum() / 255
print(f"  水平線検出後の白画素数: {h_white:.0f}  (0=水平線なし→要確認)")
print(f"    ※最小スパン: {min_h_span}px ({MIN_LINE_SPAN_RATIO*100:.0f}% of 幅{w}px)")

# 垂直線検出
min_v_span = max(int(h * MIN_LINE_SPAN_RATIO), 20)
k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_v_span))
vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_v)
cv2.imwrite(str(DEBUG_DIR / "step2c_vert.png"), vert)
v_white = vert.sum() / 255
print(f"  垂直線検出後の白画素数: {v_white:.0f}  (0=垂直線なし→要確認)")
print(f"    ※最小スパン: {min_v_span}px ({MIN_LINE_SPAN_RATIO*100:.0f}% of 高さ{h}px)")

# 射影ピーク
from app.cv_detector import _projection_peaks, _ensure_boundaries

h_proj = horiz.sum(axis=1).astype(float)
h_thresh = w * 0.05
h_positions_raw = _projection_peaks(h_proj, h_thresh)
h_positions = _ensure_boundaries(h_positions_raw, h)
print(f"\n  水平線ピーク(境界補完前): {h_positions_raw}")
print(f"  水平線ピーク(境界補完後): {h_positions}")
print(f"    ※射影閾値: {h_thresh:.0f}")

v_proj = vert.sum(axis=0).astype(float)
v_thresh = h * 0.05
v_positions_raw = _projection_peaks(v_proj, v_thresh)
v_positions = _ensure_boundaries(v_positions_raw, w)
print(f"\n  垂直線ピーク(境界補完前): {v_positions_raw}")
print(f"  垂直線ピーク(境界補完後): {v_positions}")
print(f"    ※射影閾値: {v_thresh:.0f}")

# 候補矩形の生成
total_area = float(w * h)
candidates_all = []
candidates_ok = []
for i in range(len(h_positions) - 1):
    for j in range(len(v_positions) - 1):
        y1, y2 = h_positions[i], h_positions[i + 1]
        x1, x2 = v_positions[j], v_positions[j + 1]
        bw, bh = x2 - x1, y2 - y1
        ratio = (bw * bh) / total_area
        bb = BoundingBox(x=float(x1), y=float(y1), w=float(bw), h=float(bh))
        candidates_all.append((bb, ratio))
        if ratio >= MIN_AREA_RATIO:
            candidates_ok.append(bb)

print(f"\n  生成された矩形: {len(candidates_all)}件")
print(f"  面積フィルタ通過({MIN_AREA_RATIO*100:.1f}%以上): {len(candidates_ok)}件")
if candidates_all:
    print(f"\n  全矩形の面積比一覧:")
    for bb, ratio in sorted(candidates_all, key=lambda x: -x[1]):
        flag = "✓" if ratio >= MIN_AREA_RATIO else "✗"
        print(f"    {flag} x={bb.x:.0f} y={bb.y:.0f} w={bb.w:.0f} h={bb.h:.0f}  面積比={ratio*100:.2f}%")

# 候補矩形を元画像に描画して保存
vis = cv2.imread(str(first_page))
for bb, ratio in candidates_all:
    color = (0, 200, 0) if ratio >= MIN_AREA_RATIO else (0, 0, 200)  # 緑=通過, 赤=除外
    x, y, bw, bh = int(bb.x), int(bb.y), int(bb.w), int(bb.h)
    cv2.rectangle(vis, (x, y), (x + bw, y + bh), color, 3)
    label = f"{ratio*100:.1f}%"
    cv2.putText(vis, label, (x + 5, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
cv2.imwrite(str(DEBUG_DIR / "step2d_candidates.png"), vis)
print(f"\n  候補可視化画像 → {DEBUG_DIR}/step2d_candidates.png")
print(f"    緑枠=フィルタ通過  赤枠=面積不足で除外")

print()
print("=" * 60)

# ── Step 3: AI 分類 ───────────────────────────────────────────
print("[Step 3] AI 分類（Azure OpenAI）")

if not candidates_ok:
    print("  [SKIP] OpenCV候補が0件のため、AIは呼び出しません")
    print("         → Step2の結果を確認してください")
else:
    print(f"  {len(candidates_ok)}件の候補をAIに送信します...")
    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()

        from app.detector import _build_client, _annotate_and_encode, _build_prompt, detect_parts

        # AIへの入力（プロンプト）を表示
        prompt = _build_prompt(candidates_ok)
        print("\n  ── 送信プロンプト ──")
        print(prompt)
        print("  ────────────────────\n")

        # AIの生の応答を表示
        b64 = _annotate_and_encode(first_page, candidates_ok)
        client = _build_client()
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        response = client.chat.completions.create(
            model=deployment,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_completion_tokens=1024,
            temperature=0,
        )
        raw = (response.choices[0].message.content or "").strip()
        print(f"  ── AIの生の応答 ──")
        print(raw)
        print(f"  ────────────────────\n")

        # detect_parts 経由でパース結果も確認
        parts = detect_parts(first_page, page_num=0)
        print(f"  AI分類後のパーツ: {len(parts)}件")
        for p in parts:
            print(f"    title='{p.title}'  page={p.page}")
            print(f"      bbox: x={p.bbox.x:.0f} y={p.bbox.y:.0f} w={p.bbox.w:.0f} h={p.bbox.h:.0f}")
    except Exception as e:
        print(f"  [ERROR] AI呼び出し中に例外: {e}")
        import traceback; traceback.print_exc()

print()
print("=" * 60)
print("[完了] 診断終了")
print(f"中間画像はこちらで確認: {DEBUG_DIR}/")
print("""
ファイル一覧:
  page_000.png        : PDF変換後の画像
  step2a_binary.png   : 二値化後（白=検出対象）
  step2b_horiz.png    : 水平線のみ抽出後
  step2c_vert.png     : 垂直線のみ抽出後
  step2d_candidates.png: 候補矩形（緑=通過/赤=除外）
""")
