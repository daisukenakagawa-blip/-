"""テクニカル指標 (依存ライブラリなし・純Python)。

MT4/MT5の組み込み指標と同じ計算式 (EMA, Wilder's RSI, Wilder's ATR)。
いずれも「その足までの確定情報のみ」で計算し、未来を参照しない。
"""
from typing import List, Optional


def ema(values: List[float], period: int) -> List[Optional[float]]:
    """指数移動平均。最初の値はSMAでシード。"""
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    sma = sum(values[:period]) / period
    out[period - 1] = sma
    prev = sma
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: List[float], period: int) -> List[Optional[float]]:
    """Wilder方式のRSI (MT4/MT5の iRSI と同一)。"""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out
    gain = loss = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gain += ch if ch > 0 else 0.0
        loss += -ch if ch < 0 else 0.0
    avg_gain = gain / period
    avg_loss = loss / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, n):
        ch = closes[i] - closes[i - 1]
        g = ch if ch > 0 else 0.0
        l = -ch if ch < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        out[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1 + avg_gain / avg_loss)
    return out


def atr(highs: List[float], lows: List[float], closes: List[float],
        period: int) -> List[Optional[float]]:
    """Wilder方式のATR (MT4/MT5の iATR と同一)。"""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out
    tr = [0.0] * n
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]))
    first = sum(tr[1:period + 1]) / period
    out[period] = first
    prev = first
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out
