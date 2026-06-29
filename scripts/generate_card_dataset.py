"""合成トランプ画像データセットを生成する（YOLO 形式 / 学習用）。

外部データもアカウントも不要。カード面を描画し、ランダムな背景・位置・回転・
スケールで合成して物体検出用のラベル（クラス=ランク, bbox）を作る。

クラスは 13 ランク（A,2..10,J,Q,K）。カウントにはランクのみ必要なため。

使い方:
    python scripts/generate_card_dataset.py --out data/cards --train 400 --val 80
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]  # 黒: S,C / 赤: H,D
RED = (40, 40, 210)  # BGR
BLACK = (30, 30, 30)


def render_card(rank: str, suit: str, w: int = 140, h: int = 196) -> np.ndarray:
    """1 枚のカード面（BGR, 白背景の角丸風）を描画する。"""
    card = np.full((h, w, 3), 250, np.uint8)
    cv2.rectangle(card, (2, 2), (w - 3, h - 3), (210, 210, 210), 2)
    color = RED if suit in ("H", "D") else BLACK

    # 左上のランク＋スート
    cv2.putText(card, rank, (8, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
    cv2.putText(card, suit, (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    # 右下（180度回転風に下部へ）
    cv2.putText(card, rank, (w - 46, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 1.1, color, 3)
    # 中央に大きくランク
    scale = 2.4 if rank != "10" else 1.8
    (tw, th), _ = cv2.getTextSize(rank, cv2.FONT_HERSHEY_SIMPLEX, scale, 4)
    cv2.putText(card, rank, ((w - tw) // 2, (h + th) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, 4)
    return card


def random_background(w: int, h: int) -> np.ndarray:
    """フェルト地っぽいランダム背景。"""
    base = random.choice([(40, 90, 30), (30, 60, 25), (60, 60, 70), (20, 20, 20)])
    bg = np.full((h, w, 3), base, np.uint8)
    noise = np.random.randint(-12, 12, (h, w, 3), dtype=np.int16)
    return np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def paste_rotated(bg: np.ndarray, card: np.ndarray, cx: int, cy: int,
                  angle: float, scale: float) -> tuple[int, int, int, int]:
    """カードを回転・拡縮して bg に貼り、bbox(x1,y1,x2,y2) を返す。"""
    ch, cw = card.shape[:2]
    M = cv2.getRotationMatrix2D((cw / 2, ch / 2), angle, scale)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(cw * cos + ch * sin), int(cw * sin + ch * cos)
    M[0, 2] += nw / 2 - cw / 2
    M[1, 2] += nh / 2 - ch / 2
    rot = cv2.warpAffine(card, M, (nw, nh), borderValue=(0, 0, 0))
    mask = cv2.warpAffine(np.full((ch, cw), 255, np.uint8), M, (nw, nh))

    H, W = bg.shape[:2]
    x1, y1 = cx - nw // 2, cy - nh // 2
    x2, y2 = x1 + nw, y1 + nh
    # 画面内にクリップ
    bx1, by1, bx2, by2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
    if bx2 <= bx1 or by2 <= by1:
        return (0, 0, 0, 0)
    roi = bg[by1:by2, bx1:bx2]
    sub = rot[by1 - y1:by2 - y1, bx1 - x1:bx2 - x1]
    m = mask[by1 - y1:by2 - y1, bx1 - x1:bx2 - x1] > 0
    roi[m] = sub[m]
    return (bx1, by1, bx2, by2)


def make_image(w: int = 640, h: int = 480) -> tuple[np.ndarray, list[tuple[int, float, float, float, float]]]:
    """1 枚の合成画像と YOLO ラベル(class, xc, yc, bw, bh 正規化)を作る。"""
    bg = random_background(w, h)
    labels: list[tuple[int, float, float, float, float]] = []
    n = random.randint(1, 4)
    for _ in range(n):
        rank = random.choice(RANKS)
        suit = random.choice(SUITS)
        card = render_card(rank, suit)
        scale = random.uniform(0.6, 1.1)
        angle = random.uniform(-25, 25)
        cx = random.randint(int(w * 0.15), int(w * 0.85))
        cy = random.randint(int(h * 0.2), int(h * 0.85))
        x1, y1, x2, y2 = paste_rotated(bg, card, cx, cy, angle, scale)
        if x2 <= x1 or y2 <= y1:
            continue
        cls = RANKS.index(rank)
        xc = (x1 + x2) / 2 / w
        yc = (y1 + y2) / 2 / h
        bw = (x2 - x1) / w
        bh = (y2 - y1) / h
        labels.append((cls, xc, yc, bw, bh))
    return bg, labels


def write_split(out: Path, split: str, count: int) -> None:
    img_dir = out / "images" / split
    lbl_dir = out / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        img, labels = make_image()
        stem = f"{split}_{i:05d}"
        cv2.imwrite(str(img_dir / f"{stem}.jpg"), img)
        with open(lbl_dir / f"{stem}.txt", "w") as f:
            for cls, xc, yc, bw, bh in labels:
                f.write(f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")


def write_data_yaml(out: Path) -> Path:
    yaml_path = out / "cards.yaml"
    names = "\n".join(f"  {i}: '{r}'" for i, r in enumerate(RANKS))
    yaml_path.write_text(
        f"path: {out.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n{names}\n"
    )
    return yaml_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="合成トランプデータセット生成")
    ap.add_argument("--out", default="data/cards", help="出力ディレクトリ")
    ap.add_argument("--train", type=int, default=400)
    ap.add_argument("--val", type=int, default=80)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    random.seed(args.seed)
    np.random.seed(args.seed)
    out = Path(args.out)
    write_split(out, "train", args.train)
    write_split(out, "val", args.val)
    yaml_path = write_data_yaml(out)
    print(f"生成完了: {out} （train={args.train}, val={args.val}）")
    print(f"データ定義: {yaml_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
