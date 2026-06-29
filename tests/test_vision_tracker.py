"""画像認識の二重カウント防止トラッカーのテスト。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blackjack_counter.auto.vision_tracker import DetectedCard, VisionRoundTracker


def test_new_cards_counted_once():
    t = VisionRoundTracker(dist_threshold=0.05, forget_after=3)
    frame1 = [
        DetectedCard("K", 0.2, 0.5, 0.9),
        DetectedCard("5", 0.4, 0.5, 0.9),
    ]
    assert sorted(t.update(frame1)) == ["5", "K"]
    # 同じカードが映り続けても再カウントしない
    assert t.update(frame1) == []
    # 新しいカードが 1 枚加わる（ヒット）
    frame2 = frame1 + [DetectedCard("A", 0.6, 0.5, 0.9)]
    assert t.update(frame2) == ["A"]


def test_same_rank_different_position_is_new():
    t = VisionRoundTracker(dist_threshold=0.05)
    t.update([DetectedCard("7", 0.2, 0.5, 0.9)])
    # 同じ 7 でも離れた位置なら別カード
    assert t.update([DetectedCard("7", 0.2, 0.5, 0.9),
                     DetectedCard("7", 0.7, 0.5, 0.9)]) == ["7"]


def test_forget_after_round():
    t = VisionRoundTracker(dist_threshold=0.05, forget_after=2)
    t.update([DetectedCard("K", 0.2, 0.5, 0.9)])
    # 見えないフレームが続くと忘れる
    t.update([])
    t.update([])
    # 同位置に再び K が出たら新規として数える
    assert t.update([DetectedCard("K", 0.2, 0.5, 0.9)]) == ["K"]


def test_reset():
    t = VisionRoundTracker()
    t.update([DetectedCard("K", 0.2, 0.5, 0.9)])
    t.reset()
    assert t.update([DetectedCard("K", 0.2, 0.5, 0.9)]) == ["K"]
