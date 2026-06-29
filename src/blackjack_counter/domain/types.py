"""ドメインの値オブジェクトと共通語彙（Ubiquitous Language）。

すべて不変（frozen）データ・列挙型として定義し、不正な状態を型で防ぐ。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Rank(str, Enum):
    """カードのランク。"""

    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"

    @property
    def base_value(self) -> int:
        """ブラックジャックの素点（Ace は 11。文脈により 1 に調整されうる）。"""
        if self in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING):
            return 10
        if self is Rank.ACE:
            return 11
        return int(self.value)

    @classmethod
    def from_input(cls, text: str) -> "Rank":
        """ユーザー入力（"k", "10", "J" など）から Rank を解決する。

        Raises:
            ValueError: 認識できない入力の場合。
        """
        key = text.strip().upper()
        aliases = {
            "1": "A",
            "T": "10",
            "10": "10",
            "0": "10",  # テンキーの 0 を 10 として扱う
        }
        key = aliases.get(key, key)
        for rank in cls:
            if rank.value == key:
                return rank
        raise ValueError(f"認識できないランク入力: {text!r}")


class Suit(str, Enum):
    """カードのスート（カウントには不要だが完全性のため定義）。"""

    SPADE = "S"
    HEART = "H"
    DIAMOND = "D"
    CLUB = "C"


@dataclass(frozen=True, slots=True)
class Card:
    """1 枚のカード。"""

    rank: Rank
    suit: Suit | None = None

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value if self.suit else ''}"


class GameState(str, Enum):
    """ゲームのフェーズ（将来の自動認識パイプラインで使用）。"""

    BETTING = "betting"
    DEALING = "dealing"
    PLAYER_TURN = "player_turn"
    DEALER_TURN = "dealer_turn"
    RESULT = "result"
    SHUFFLE = "shuffle"
    UNKNOWN = "unknown"


# カウント対象となる全ランク（テスト・初期化用）
ALL_RANKS: tuple[Rank, ...] = tuple(Rank)
