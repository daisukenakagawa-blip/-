"""ベットアドバイザ。

true count に応じてベットユニットと有利不利の評価を返す。
プレイ（hit/stand 等）の基本戦略は将来追加（仕様書 §12 参照）。
"""

from __future__ import annotations

from dataclasses import dataclass

from blackjack_counter.counting.engine import CountSnapshot


@dataclass(frozen=True, slots=True)
class Advice:
    """ベットアドバイス（読み取り専用）。"""

    bet_units: int
    bet_label: str
    edge: str  # "プレイヤー有利" / "中立" / "ハウス有利"
    detail: str


# (true count の下限, ベットユニット) の昇順テーブル。
# 「その tc 以上ならこのユニット」を意味する。
_DEFAULT_SPREAD: tuple[tuple[float, int], ...] = (
    (float("-inf"), 1),
    (1.0, 1),
    (2.0, 2),
    (3.0, 4),
    (4.0, 6),
    (5.0, 8),
)


class BettingAdvisor:
    """true count からベット量を推奨する。"""

    def __init__(
        self, spread: tuple[tuple[float, int], ...] = _DEFAULT_SPREAD
    ) -> None:
        # 念のため下限昇順に整列
        self._spread = tuple(sorted(spread, key=lambda x: x[0]))

    def _units_for(self, tc: float) -> int:
        units = self._spread[0][1]
        for threshold, u in self._spread:
            if tc >= threshold:
                units = u
        return units

    def advise(self, count: CountSnapshot) -> Advice:
        tc = count.true_count
        units = self._units_for(tc)

        if tc >= 3:
            edge = "プレイヤー有利"
            detail = "ベットを上げる好機。高カードが多く残っています。"
        elif tc >= 1.5:
            edge = "ややプレイヤー有利"
            detail = "少しベットを上げてもOK。"
        elif tc >= -1:
            edge = "ほぼ中立"
            detail = "最小ベットで様子見。"
        else:
            edge = "ハウス有利"
            detail = "低カードが多く残存。ベットは最小限に。"

        return Advice(
            bet_units=units,
            bet_label=f"{units} ユニット",
            edge=edge,
            detail=detail,
        )
