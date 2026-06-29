"""連続したスナップショット間で「新たに出たカード」を検出する純粋ロジック。

DOM をポーリングすると、同じカードが何度も読み取られる。同一カードを二重に
カウントしないため、前回の見え方との差分から「今回新しく公開されたカード」のみ
を抽出する。

アルゴリズム（コンテナ単位、表向きカードのランク列を比較）:
- ``curr`` が ``prev`` の延長（prev が curr の先頭一致部分）なら、増えた末尾だけが新規。
  例: ["K"] -> ["K","7"]  => 新規 = ["7"]
- そうでなければ（途中で食い違う／短くなった = 新しいラウンド）、``curr`` 全体が
  新しく配られたカードとみなす。
  例: ["10","7"] -> ["3","9"]  => 新規 = ["3","9"]

この関数は副作用がなく、I/O にも依存しないため網羅的にテストできる。
"""

from __future__ import annotations


def diff_new_cards(prev: list[str], curr: list[str]) -> list[str]:
    """前回 ``prev`` に対し、今回 ``curr`` で新たに公開されたランク列を返す。"""
    if curr == prev:
        return []

    # prev が curr の先頭に完全一致するか（= 延長か）
    if len(curr) > len(prev) and curr[: len(prev)] == prev:
        return curr[len(prev) :]

    # 食い違い or 短縮 = 新しいラウンド。curr 全体が新規。
    return list(curr)


class RoundTracker:
    """player / dealer 2 コンテナの差分を管理し、新規カードを返す。

    リシャッフル（残デッキ数の増加）も検知できる。
    """

    def __init__(self) -> None:
        self._prev: dict[str, list[str]] = {"player": [], "dealer": []}
        self._last_remaining: int | None = None

    def update(
        self,
        player: list[str],
        dealer: list[str],
        remaining: int | None = None,
    ) -> tuple[list[str], bool]:
        """新規カードのランク列と「リシャッフル検知フラグ」を返す。

        Args:
            player: プレイヤーの表向きカードのランク列（出現順）。
            dealer: ディーラーの表向きカードのランク列（出現順）。
            remaining: 残デッキ枚数（取得できる場合）。増加でリシャッフル判定。
        """
        reshuffled = False
        if (
            remaining is not None
            and self._last_remaining is not None
            and remaining > self._last_remaining
        ):
            reshuffled = True
        self._last_remaining = remaining

        if reshuffled:
            # 山が作り直された。差分基準もクリアし、今見えているカードを基準にする。
            self._prev = {"player": list(player), "dealer": list(dealer)}
            return list(player) + list(dealer), True

        new_cards: list[str] = []
        new_cards += diff_new_cards(self._prev["player"], player)
        new_cards += diff_new_cards(self._prev["dealer"], dealer)
        self._prev["player"] = list(player)
        self._prev["dealer"] = list(dealer)
        return new_cards, False

    def reset(self) -> None:
        self._prev = {"player": [], "dealer": []}
        self._last_remaining = None
