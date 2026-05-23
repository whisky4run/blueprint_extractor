from pathlib import Path

import cv2
import numpy as np

from app.models import BoundingBox

# 罫線とみなす最小スパン（画像幅/高さに対する割合）
MIN_LINE_SPAN_RATIO = 0.45
# 候補領域の最小面積（画像全体に対する割合）
MIN_AREA_RATIO = 0.015
# 近傍の線をまとめるピクセル幅
MERGE_TOLERANCE = 12


def _extract_grid(image_path: Path) -> list[tuple[BoundingBox, float]]:
    """
    OpenCV で罫線を検出し、全グリッドセルを (BoundingBox, 面積比) のリストで返す。
    面積フィルタは適用しない。
    """
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    h, w = img.shape

    # 二値化（線は暗色、背景は明色を想定）
    _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)

    # 水平線の検出
    min_h_span = max(int(w * MIN_LINE_SPAN_RATIO), 20)
    k_h = cv2.getStructuringElement(cv2.MORPH_RECT, (min_h_span, 1))
    horiz = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_h)

    # 垂直線の検出
    min_v_span = max(int(h * MIN_LINE_SPAN_RATIO), 20)
    k_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_v_span))
    vert = cv2.morphologyEx(binary, cv2.MORPH_OPEN, k_v)

    # 射影で線の座標を取得
    h_positions = _projection_peaks(horiz.sum(axis=1).astype(float), w * 0.05)
    v_positions = _projection_peaks(vert.sum(axis=0).astype(float), h * 0.05)

    # 画像端を境界として追加
    h_positions = _ensure_boundaries(h_positions, h)
    v_positions = _ensure_boundaries(v_positions, w)

    total_area = float(w * h)
    cells: list[tuple[BoundingBox, float]] = []
    for i in range(len(h_positions) - 1):
        for j in range(len(v_positions) - 1):
            y1, y2 = h_positions[i], h_positions[i + 1]
            x1, x2 = v_positions[j], v_positions[j + 1]
            bw, bh = x2 - x1, y2 - y1
            ratio = (bw * bh) / total_area
            cells.append((
                BoundingBox(x=float(x1), y=float(y1), w=float(bw), h=float(bh)),
                ratio,
            ))

    return cells


def detect_candidate_regions(image_path: Path) -> list[BoundingBox]:
    """
    面積フィルタを通過した大セルのみを返す（AI 分類用）。
    座標は画像のピクセル値（左上原点）。
    """
    return [bb for bb, ratio in _extract_grid(image_path) if ratio >= MIN_AREA_RATIO]


def detect_small_cells(image_path: Path) -> list[BoundingBox]:
    """
    面積フィルタを通過しなかった小セル（タイトル行・区切り行）を返す。
    bbox を上方向に拡張してタイトル行を含めるために使用する。
    """
    return [bb for bb, ratio in _extract_grid(image_path) if ratio < MIN_AREA_RATIO]


def _projection_peaks(proj: np.ndarray, threshold: float) -> list[int]:
    """1次元射影プロファイルからピーク（線の中心位置）を返す。"""
    n = len(proj)
    positions: list[int] = []
    in_peak = False
    peak_start = 0

    for i in range(n):
        val = float(proj[i])
        if val >= threshold:
            if not in_peak:
                peak_start = i
                in_peak = True
        else:
            if in_peak:
                center = (peak_start + i) // 2
                if positions and (center - positions[-1]) < MERGE_TOLERANCE:
                    positions[-1] = (positions[-1] + center) // 2
                else:
                    positions.append(center)
                in_peak = False

    if in_peak:
        positions.append((peak_start + n) // 2)

    return positions


def _ensure_boundaries(positions: list[int], size: int) -> list[int]:
    """先頭と末尾に画像端（0 と size）が含まれるよう補完する。"""
    result = list(positions)
    if not result or result[0] > size * 0.05:
        result.insert(0, 0)
    if not result or result[-1] < size * 0.95:
        result.append(size)
    return result
