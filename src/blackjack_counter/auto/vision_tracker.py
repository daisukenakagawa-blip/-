"""画像認識での二重カウント防止トラッカー（純粋ロジック）。

画面上のカードはラウンド中ずっと映り続けるため、毎フレーム検出すると同じカードを
何度もカウントしてしまう。検出されたカードを「位置（中心座標）＋ランク」で同一視し、
新規に出現したカードだけを 1 回だけカウントする。

ラウンドが変わってカードが画面から消えると、一定フレーム見えなくなった確定カードは
忘れる（次ラウンドの同位置の新カードを数えられるように）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DetectedCard:
    """1 フレームで検出されたカード。"""

    rank: str
    cx: float  # 中心 x（0..1 正規化推奨）
    cy: float  # 中心 y
    confidence: float


@dataclass(slots=True)
class _Counted:
    rank: str
    cx: float
    cy: float
    misses: int = 0  # 連続で検出されなかったフレーム数


@dataclass(slots=True)
class VisionRoundTracker:
    """検出カード列から新規カードを抽出する。

    Args:
        dist_threshold: 同一カードとみなす中心間距離（正規化座標）。
        forget_after: この回数連続で見えなければ確定カードを忘れる。
    """

    dist_threshold: float = 0.05
    forget_after: int = 5
    _counted: list[_Counted] = field(default_factory=list)

    def update(self, detections: list[DetectedCard]) -> list[str]:
        """今回新たに出現したカードのランク列を返す。"""
        # 既存確定カードと突き合わせ、マッチしたものは miss をリセット
        matched_idx: set[int] = set()
        new_ranks: list[str] = []

        for det in detections:
            hit = self._find_match(det, matched_idx)
            if hit is None:
                # 新規カード
                self._counted.append(_Counted(det.rank, det.cx, det.cy))
                matched_idx.add(len(self._counted) - 1)
                new_ranks.append(det.rank)
            else:
                matched_idx.add(hit)
                self._counted[hit].misses = 0
                # 位置を緩やかに追従
                self._counted[hit].cx = det.cx
                self._counted[hit].cy = det.cy

        # 今回マッチしなかった確定カードは miss を加算し、一定で忘れる
        survivors: list[_Counted] = []
        for i, c in enumerate(self._counted):
            if i in matched_idx:
                survivors.append(c)
                continue
            c.misses += 1
            if c.misses < self.forget_after:
                survivors.append(c)
        self._counted = survivors

        return new_ranks

    def _find_match(self, det: DetectedCard, used: set[int]) -> int | None:
        best_i: int | None = None
        best_d = self.dist_threshold
        for i, c in enumerate(self._counted):
            if i in used or c.rank != det.rank:
                continue
            d = ((c.cx - det.cx) ** 2 + (c.cy - det.cy) ** 2) ** 0.5
            if d <= best_d:
                best_d = d
                best_i = i
        return best_i

    def reset(self) -> None:
        self._counted.clear()
