"""YOLO カード認識 → Hi-Lo → True Count → ベット助言 の自動パイプライン。

画面（または画像）からカードを YOLO で認識し、二重カウントを防ぎながら
カウントエンジンへ投入する。DOM が読めない canvas 描画ゲームに対応する。

使い方:
    # 画面領域を監視（mss が必要）
    python -m blackjack_counter.auto.yolo_counter \\
        --weights models/cards_yolo.pt --region 0 0 1280 720

    # 1 枚の画像で試す（動作確認）
    python -m blackjack_counter.auto.yolo_counter \\
        --weights models/cards_yolo.pt --image sample.jpg
"""

from __future__ import annotations

import argparse
import sys
import time

from blackjack_counter.advisor.advisor import BettingAdvisor
from blackjack_counter.adapters.yolo_detector import YoloCardRecognizer, YoloConfig
from blackjack_counter.auto.vision_tracker import VisionRoundTracker
from blackjack_counter.counting.engine import CountEngine
from blackjack_counter.counting.strategies import get_strategy
from blackjack_counter.domain.types import Rank


def _render(engine: CountEngine, advisor: BettingAdvisor) -> str:
    snap = engine.snapshot()
    advice = advisor.advise(snap)
    return (
        f"RC={snap.display_running:>5}  TC={snap.display_true:>5}  "
        f"残{snap.remaining_decks:4.1f}デッキ  見{snap.cards_seen:>3}枚  "
        f"| {advice.edge} → {advice.bet_label}"
    )


def _ingest(engine: CountEngine, new_ranks: list[str]) -> None:
    for r in new_ranks:
        try:
            engine.add_card(Rank.from_input(r))
        except ValueError:
            continue


def run_image(weights: str, image_path: str, strategy: str, decks: int,
              device: str) -> int:
    """画像 1 枚で認識→カウントを行い結果を表示（動作確認用）。"""
    import cv2

    recognizer = YoloCardRecognizer(
        YoloConfig(weights=weights, device=device)
    )
    engine = CountEngine(get_strategy(strategy), num_decks=decks)
    advisor = BettingAdvisor()
    tracker = VisionRoundTracker()

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"画像を読み込めません: {image_path}", file=sys.stderr)
        return 2
    cards = recognizer.recognize(frame)
    new = tracker.update(cards)
    _ingest(engine, new)
    print("検出カード:", [(c.rank, round(c.confidence, 2)) for c in cards])
    print(_render(engine, advisor))
    return 0


def run_screen(weights: str, region: tuple[int, int, int, int], strategy: str,
               decks: int, device: str, poll_ms: int) -> int:
    """画面領域を監視し続けて自動カウント。"""
    try:
        import mss
        import numpy as np
    except ImportError:
        print("mss/numpy が必要です: pip install mss numpy", file=sys.stderr)
        return 3

    recognizer = YoloCardRecognizer(YoloConfig(weights=weights, device=device))
    engine = CountEngine(get_strategy(strategy), num_decks=decks)
    advisor = BettingAdvisor()
    tracker = VisionRoundTracker()
    x, y, w, h = region
    monitor = {"left": x, "top": y, "width": w, "height": h}

    print(f"画面領域 {region} を監視中（Ctrl+C で終了）\n")
    with mss.mss() as sct:
        try:
            while True:
                shot = np.array(sct.grab(monitor))[:, :, :3]  # BGRA->BGR
                cards = recognizer.recognize(shot)
                new = tracker.update(cards)
                if new:
                    _ingest(engine, new)
                    print("\r" + _render(engine, advisor), flush=True)
                time.sleep(poll_ms / 1000)
        except KeyboardInterrupt:
            print("\n終了します。")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="blackjack-counter-yolo",
        description="YOLO カード認識による自動カウント",
    )
    ap.add_argument("--weights", required=True, help="学習済み YOLO 重み(.pt/.onnx)")
    ap.add_argument("--strategy", default="hi_lo")
    ap.add_argument("--decks", type=int, default=6)
    ap.add_argument("--device", default="cpu", help="cpu / cuda:0")
    ap.add_argument("--image", default=None, help="単一画像で動作確認")
    ap.add_argument("--region", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                    default=None, help="監視する画面領域")
    ap.add_argument("--poll-ms", type=int, default=300)
    args = ap.parse_args(argv)

    if args.image:
        return run_image(args.weights, args.image, args.strategy, args.decks,
                         args.device)
    if args.region:
        return run_screen(args.weights, tuple(args.region), args.strategy,
                          args.decks, args.device, args.poll_ms)
    ap.error("--image か --region のいずれかを指定してください")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
