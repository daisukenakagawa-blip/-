"""USD/JPY 独自自動売買ボット (プラットフォーム非依存)。

戦略は MT5版 USDJPY_TrendPullback と同一:
  H4 EMA50/200 環境認識 → H1 RSI14 押し目 → M15ブレイク
  SL=ATRx1.5 / TP=ATRx3 / リスク1% / 日次-3% / 月次-10% / ナンピン・マーチン無し
"""
from .config import Config

__all__ = ["Config"]
