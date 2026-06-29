"""カードカウンティング方式（Strategy パターン）。

新しい方式を追加するときは ``CountingStrategy`` を継承して ``_STRATEGIES`` に
登録するだけでよい。エンジン本体は一切変更しない（拡張性）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from blackjack_counter.domain.types import Rank


class CountingStrategy(ABC):
    """カウント方式の抽象基底。"""

    #: 表示名
    name: str = "abstract"
    #: balanced 方式（全カードの合計が 0 になる）なら True。
    #: True の場合 true count（= running count / 残デッキ数）を使う。
    #: False（unbalanced, 例: KO）の場合は running count をそのまま判断に使う。
    balanced: bool = True

    @abstractmethod
    def value(self, rank: Rank) -> float:
        """指定ランクのカウント値を返す。"""

    def initial_running_count(self, num_decks: int) -> float:
        """開始時の running count（unbalanced 方式の IRC 補正）。

        balanced 方式は 0。
        """
        return 0.0


class HiLo(CountingStrategy):
    """Hi-Lo 方式（最も普及した balanced 方式）。"""

    name = "Hi-Lo"
    balanced = True

    _MAP = {
        Rank.TWO: 1,
        Rank.THREE: 1,
        Rank.FOUR: 1,
        Rank.FIVE: 1,
        Rank.SIX: 1,
        Rank.SEVEN: 0,
        Rank.EIGHT: 0,
        Rank.NINE: 0,
        Rank.TEN: -1,
        Rank.JACK: -1,
        Rank.QUEEN: -1,
        Rank.KING: -1,
        Rank.ACE: -1,
    }

    def value(self, rank: Rank) -> float:
        return self._MAP[rank]


class KnockOut(CountingStrategy):
    """KO (Knock-Out) 方式（unbalanced。7 も +1）。

    true count 変換が不要で初心者向け。IRC は ``-4 * (num_decks - 1)``。
    """

    name = "KO"
    balanced = False

    _MAP = {
        Rank.TWO: 1,
        Rank.THREE: 1,
        Rank.FOUR: 1,
        Rank.FIVE: 1,
        Rank.SIX: 1,
        Rank.SEVEN: 1,
        Rank.EIGHT: 0,
        Rank.NINE: 0,
        Rank.TEN: -1,
        Rank.JACK: -1,
        Rank.QUEEN: -1,
        Rank.KING: -1,
        Rank.ACE: -1,
    }

    def value(self, rank: Rank) -> float:
        return self._MAP[rank]

    def initial_running_count(self, num_decks: int) -> float:
        return -4.0 * (num_decks - 1)


class OmegaII(CountingStrategy):
    """Omega II 方式（多レベル balanced。精度が高いが計算負荷大）。"""

    name = "Omega II"
    balanced = True

    _MAP = {
        Rank.TWO: 1,
        Rank.THREE: 1,
        Rank.FOUR: 2,
        Rank.FIVE: 2,
        Rank.SIX: 2,
        Rank.SEVEN: 1,
        Rank.EIGHT: 0,
        Rank.NINE: -1,
        Rank.TEN: -2,
        Rank.JACK: -2,
        Rank.QUEEN: -2,
        Rank.KING: -2,
        Rank.ACE: 0,  # Omega II では Ace は 0（別途サイドカウント推奨）
    }

    def value(self, rank: Rank) -> float:
        return self._MAP[rank]


# 文字列キー → 方式（設定や CLI から解決するためのレジストリ）
_STRATEGIES: dict[str, type[CountingStrategy]] = {
    "hi_lo": HiLo,
    "ko": KnockOut,
    "omega_ii": OmegaII,
}


def get_strategy(name: str) -> CountingStrategy:
    """方式名からインスタンスを生成する。

    Raises:
        KeyError: 未知の方式名の場合。
    """
    key = name.strip().lower()
    if key not in _STRATEGIES:
        available = ", ".join(sorted(_STRATEGIES))
        raise KeyError(f"未知のカウント方式: {name!r}（利用可能: {available}）")
    return _STRATEGIES[key]()


def available_strategies() -> list[str]:
    """利用可能な方式名の一覧。"""
    return sorted(_STRATEGIES)
