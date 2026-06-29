"""ブラックジャック カードカウンティング ライブラリ。

純粋なドメインロジック（カウント計算・戦略アドバイス）を提供する。
外部依存ゼロ（標準ライブラリのみ）で動作するため、すぐに利用できる。
"""

from blackjack_counter.domain.types import Card, GameState, Rank, Suit
from blackjack_counter.counting.engine import CountEngine
from blackjack_counter.counting.shoe import Shoe
from blackjack_counter.counting.strategies import (
    HiLo,
    KnockOut,
    OmegaII,
    CountingStrategy,
    get_strategy,
)
from blackjack_counter.advisor.advisor import BettingAdvisor

__version__ = "0.1.0"

__all__ = [
    "Card",
    "Rank",
    "Suit",
    "GameState",
    "CountEngine",
    "Shoe",
    "CountingStrategy",
    "HiLo",
    "KnockOut",
    "OmegaII",
    "get_strategy",
    "BettingAdvisor",
]
