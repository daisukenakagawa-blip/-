"""画面キャプチャ + OpenCV テンプレート照合によるカード認識（学習不要）。

DOM から読めない canvas 描画のゲーム向け。ディープラーニングを使わず、
カード隅のランク表記（A,2..,10,J,Q,K）をテンプレート照合で読み取るため、
GPU も学習も不要で動く。ただし**対象ゲームの見た目に合わせた校正**
（参照テンプレートの作成）が必要。

ワークフロー:
  1. ``calibrate`` で対象ゲームのランク画像（テンプレート）を保存。
  2. ``run`` で画面領域を監視し、出たカードを自動カウント。

注意: テンプレート照合は描画が大きく変わると精度が落ちる。高い汎用性が
必要な場合は仕様書(§5)記載の YOLO/CNN 方式へ拡張する。
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import cv2
    import numpy as np

    _HAS_CV = True
except ImportError:  # ライブラリ未導入でもインポート自体は失敗させない
    _HAS_CV = False


@dataclass(frozen=True, slots=True)
class TemplateMatch:
    rank: str
    score: float


def match_rank(
    card_gray: "np.ndarray",
    templates: dict[str, "np.ndarray"],
    *,
    threshold: float = 0.6,
) -> TemplateMatch | None:
    """グレースケールのカード隅画像を各テンプレートと照合し最良一致を返す。

    Args:
        card_gray: 認識対象（カード隅のランク領域）。グレースケール。
        templates: rank 文字列 -> テンプレート画像（グレースケール）。
        threshold: この相関スコア未満なら None（不確実として棄却）。

    Returns:
        最良一致（閾値以上）。なければ None。
    """
    if not _HAS_CV:
        raise RuntimeError("OpenCV/numpy が必要です: pip install opencv-python numpy")

    best: TemplateMatch | None = None
    for rank, tmpl in templates.items():
        # テンプレートを対象サイズへ合わせる
        h, w = card_gray.shape[:2]
        th, tw = tmpl.shape[:2]
        if th > h or tw > w:
            scale = min(h / th, w / tw)
            tmpl_r = cv2.resize(tmpl, (max(1, int(tw * scale)), max(1, int(th * scale))))
        else:
            tmpl_r = tmpl
        res = cv2.matchTemplate(card_gray, tmpl_r, cv2.TM_CCOEFF_NORMED)
        score = float(res.max())
        if best is None or score > best.score:
            best = TemplateMatch(rank=rank, score=score)

    if best is None or best.score < threshold:
        return None
    return best


def find_card_regions(
    frame_bgr: "np.ndarray",
    *,
    min_area_ratio: float = 0.002,
    max_area_ratio: float = 0.25,
) -> list[tuple[int, int, int, int]]:
    """フレームからカードらしい矩形領域 (x, y, w, h) を検出する。

    明るい矩形（カード面）を輪郭抽出で探す素朴な実装。背景とのコントラストが
    あるゲームで有効。精度が要る場合は YOLO 検出器へ差し替える。
    """
    if not _HAS_CV:
        raise RuntimeError("OpenCV/numpy が必要です: pip install opencv-python numpy")

    H, W = frame_bgr.shape[:2]
    total = H * W
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions: list[tuple[int, int, int, int]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if not (min_area_ratio * total <= area <= max_area_ratio * total):
            continue
        aspect = h / w if w else 0
        # トランプは縦長（おおむね 1.2〜1.6）
        if 1.1 <= aspect <= 1.8:
            regions.append((x, y, w, h))
    # 左上→右下の順に整列
    regions.sort(key=lambda r: (r[1], r[0]))
    return regions


# 実際の画面監視ループ（mss が必要）は、対象ゲームのテンプレート校正後に
# find_card_regions + match_rank を組み合わせて構築する。
# 校正補助は scripts/calibrate_vision.py（将来追加）を参照。
