"""カウントエンジン・方式・差分検出のテスト。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from blackjack_counter.auto.card_diff import RoundTracker, diff_new_cards
from blackjack_counter.counting.engine import CountEngine
from blackjack_counter.counting.strategies import HiLo, KnockOut, get_strategy
from blackjack_counter.domain.types import ALL_RANKS, Rank


def test_hilo_values():
    s = HiLo()
    assert s.value(Rank.TWO) == 1
    assert s.value(Rank.SEVEN) == 0
    assert s.value(Rank.KING) == -1
    assert s.value(Rank.ACE) == -1


def test_hilo_running_count():
    eng = CountEngine(HiLo(), num_decks=6)
    for r in ["2", "3", "K", "A", "7"]:  # +1+1-1-1+0
        eng.add_card(Rank.from_input(r))
    assert eng.running_count == 0


def test_full_deck_returns_to_zero_balanced():
    """balanced 方式は 1 デッキ全消化で running count が 0 に戻る。"""
    eng = CountEngine(HiLo(), num_decks=1)
    for rank in ALL_RANKS:
        for _ in range(4):  # 各ランク 4 枚
            eng.add_card(rank)
    assert eng.running_count == 0
    assert eng.cards_seen == 52


def test_true_count():
    eng = CountEngine(HiLo(), num_decks=6)
    # 1 デッキ分（52枚）を low カードだけで消化すると RC=+? を作る代わりに直接検証
    for _ in range(52):
        eng.add_card(Rank.FIVE)  # +1 ずつ
    # 残り 5 デッキ、RC=52
    assert round(eng.true_count, 1) == round(52 / 5, 1)


def test_undo():
    eng = CountEngine(HiLo(), num_decks=6)
    eng.add_card(Rank.FIVE)  # +1
    eng.add_card(Rank.KING)  # -1
    assert eng.running_count == 0
    removed = eng.undo()
    assert removed == Rank.KING
    assert eng.running_count == 1
    assert eng.cards_seen == 1


def test_reset():
    eng = CountEngine(HiLo(), num_decks=6)
    for _ in range(10):
        eng.add_card(Rank.FIVE)
    eng.reset()
    assert eng.running_count == 0
    assert eng.cards_seen == 0


def test_ko_unbalanced_irc():
    """KO は IRC が -4*(decks-1)。balanced=False。"""
    eng = CountEngine(KnockOut(), num_decks=6)
    assert eng.running_count == -4 * 5
    # unbalanced は true_count = running_count
    assert eng.true_count == eng.running_count


def test_get_strategy():
    assert get_strategy("hi_lo").name == "Hi-Lo"
    assert get_strategy("ko").name == "KO"


def test_rank_from_input():
    assert Rank.from_input("k") == Rank.KING
    assert Rank.from_input("10") == Rank.TEN
    assert Rank.from_input("0") == Rank.TEN
    assert Rank.from_input("1") == Rank.ACE
    assert Rank.from_input(" a ") == Rank.ACE


# --- 差分検出（自動カウントの二重カウント防止） ---


def test_diff_extension():
    assert diff_new_cards(["K"], ["K", "7"]) == ["7"]
    assert diff_new_cards([], ["A", "5"]) == ["A", "5"]
    assert diff_new_cards(["K", "7"], ["K", "7"]) == []


def test_diff_new_round():
    # 食い違い = 新ラウンド → 全部新規
    assert diff_new_cards(["10", "7"], ["3", "9"]) == ["3", "9"]
    # 短縮も新ラウンド扱い
    assert diff_new_cards(["10", "7"], ["10"]) == ["10"]


def test_round_tracker_no_double_count():
    t = RoundTracker()
    new, _ = t.update(["A", "9"], ["4"], remaining=40)
    assert new == ["A", "9", "4"]
    # 同じ状態を再ポーリング → 新規なし（二重カウントしない）
    new, _ = t.update(["A", "9"], ["4"], remaining=40)
    assert new == []
    # ディーラーが穴を公開 → 公開分だけ新規
    new, _ = t.update(["A", "9"], ["4", "K"], remaining=40)
    assert new == ["K"]


def test_round_tracker_reshuffle():
    t = RoundTracker()
    t.update(["5"], ["6"], remaining=12)
    # 残デッキが増えた = リシャッフル
    new, reshuffled = t.update(["2"], ["3"], remaining=52)
    assert reshuffled is True
    assert set(new) == {"2", "3"}
