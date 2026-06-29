"""カウントエンジン（純粋・決定論的）。

I/O・乱数・時刻に一切依存しないため、網羅的にテストできる。
"""

from __future__ import annotations

from dataclasses import dataclass

from blackjack_counter.counting.shoe import Shoe
from blackjack_counter.counting.strategies import CountingStrategy
from blackjack_counter.domain.types import Rank


@dataclass(frozen=True, slots=True)
class CountSnapshot:
    """ある時点のカウント状態（読み取り専用）。"""

    running_count: float
    true_count: float
    remaining_decks: float
    penetration: float
    cards_seen: int
    strategy: str

    @property
    def display_running(self) -> str:
        return f"{self.running_count:+g}"

    @property
    def display_true(self) -> str:
        return f"{self.true_count:+.1f}"


class CountEngine:
    """カウントの中核。カードを与えると running/true count を更新する。"""

    def __init__(self, strategy: CountingStrategy, num_decks: int = 6) -> None:
        self._strategy = strategy
        self._num_decks = num_decks
        self._shoe = Shoe(num_decks)
        self._running_count = strategy.initial_running_count(num_decks)
        self._history: list[Rank] = []

    # --- 更新操作 ---

    def add_card(self, rank: Rank) -> None:
        """カードを 1 枚カウントに反映する。"""
        self._running_count += self._strategy.value(rank)
        self._shoe.deal()
        self._history.append(rank)

    def undo(self) -> Rank | None:
        """直近のカードを取り消す。取り消したランクを返す。"""
        if not self._history:
            return None
        rank = self._history.pop()
        self._running_count -= self._strategy.value(rank)
        self._shoe.undo()
        return rank

    def reset(self) -> None:
        """シャッフル相当。カウントと履歴を初期化する。"""
        self._shoe.reset()
        self._running_count = self._strategy.initial_running_count(self._num_decks)
        self._history.clear()

    # --- 参照 ---

    @property
    def running_count(self) -> float:
        return self._running_count

    @property
    def true_count(self) -> float:
        """balanced 方式は running/残デッキ。unbalanced はそのまま。"""
        if not self._strategy.balanced:
            return self._running_count
        return self._running_count / self._shoe.remaining_decks

    @property
    def cards_seen(self) -> int:
        return len(self._history)

    @property
    def history(self) -> tuple[Rank, ...]:
        return tuple(self._history)

    @property
    def shoe(self) -> Shoe:
        return self._shoe

    @property
    def strategy(self) -> CountingStrategy:
        return self._strategy

    def snapshot(self) -> CountSnapshot:
        return CountSnapshot(
            running_count=self._running_count,
            true_count=self.true_count,
            remaining_decks=self._shoe.remaining_decks,
            penetration=self._shoe.penetration,
            cards_seen=self.cards_seen,
            strategy=self._strategy.name,
        )
