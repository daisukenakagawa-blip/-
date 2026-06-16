"""売買判定ロジック (MT5版 USDJPY_TrendPullback と同一)。

  環境認識 : H4 EMA50 vs EMA200      (50>200=買い環境 / 50<200=売り環境)
  押し目   : H1 RSI14                (買い:35-45 / 売り:55-65)
  エントリー: M15 直近高値/安値ブレイク
"""
from typing import Optional

from .config import Config


def trend_direction(ema_fast: Optional[float], ema_slow: Optional[float]) -> int:
    """H4トレンド方向。1=買い環境, -1=売り環境, 0=判定不能。"""
    if ema_fast is None or ema_slow is None:
        return 0
    if ema_fast > ema_slow:
        return 1
    if ema_fast < ema_slow:
        return -1
    return 0


def pullback_ok(direction: int, rsi_val: Optional[float], cfg: Config) -> bool:
    """H1 RSIが押し目/戻りのゾーンに入っているか。"""
    if rsi_val is None:
        return False
    if direction == 1:
        return cfg.rsi_buy_min <= rsi_val <= cfg.rsi_buy_max
    if direction == -1:
        return cfg.rsi_sell_min <= rsi_val <= cfg.rsi_sell_max
    return False


def entry_signal(direction: int, rsi_val: Optional[float],
                 m15_close: float, recent_high: float, recent_low: float,
                 cfg: Config) -> int:
    """全条件を満たしたとき 1(買い)/-1(売り)、それ以外 0 を返す。

    direction      : H4トレンド方向
    m15_close      : 直近確定M15足の終値
    recent_high/low: その前 breakout_bars 本のM15高値/安値
    """
    if direction == 0 or not pullback_ok(direction, rsi_val, cfg):
        return 0
    if direction == 1 and m15_close > recent_high:
        return 1
    if direction == -1 and m15_close < recent_low:
        return -1
    return 0
