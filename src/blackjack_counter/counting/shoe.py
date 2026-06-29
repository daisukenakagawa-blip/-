"""シュー（複数デッキ）の残枚数・消化率管理。"""

from __future__ import annotations

from dataclasses import dataclass

CARDS_PER_DECK = 52


@dataclass(slots=True)
class Shoe:
    """シューの状態。配られた枚数から残デッキ数・消化率を算出する。"""

    num_decks: int
    cards_dealt: int = 0

    def __post_init__(self) -> None:
        if self.num_decks < 1:
            raise ValueError("num_decks は 1 以上である必要があります")

    @property
    def total_cards(self) -> int:
        return self.num_decks * CARDS_PER_DECK

    @property
    def remaining_cards(self) -> int:
        return self.total_cards - self.cards_dealt

    @property
    def remaining_decks(self) -> float:
        """残デッキ数。ゼロ除算を避けるため下限を設ける。"""
        return max(self.remaining_cards / CARDS_PER_DECK, 1e-9)

    @property
    def penetration(self) -> float:
        """消化率（0.0〜1.0）。深いほどカウントが有効。"""
        return self.cards_dealt / self.total_cards

    def deal(self, n: int = 1) -> None:
        self.cards_dealt += n

    def undo(self, n: int = 1) -> None:
        self.cards_dealt = max(0, self.cards_dealt - n)

    def reset(self) -> None:
        self.cards_dealt = 0
