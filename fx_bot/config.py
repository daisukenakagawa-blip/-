"""USD/JPY トレンドフォロー押し目ボット - 設定。

MT5版 USDJPY_TrendPullback と同一ロジックを、プラットフォーム非依存の
独自Pythonシステムとして実装したもの。
"""
from dataclasses import dataclass


@dataclass
class Config:
    # --- 銘柄 ---
    symbol: str = "USD_JPY"        # OANDA形式。バックテストでは表示のみ

    # --- 環境認識 (H4 EMA) ---
    ema_fast: int = 50
    ema_slow: int = 200

    # --- 押し目判定 (H1 RSI) ---
    rsi_period: int = 14
    rsi_buy_min: float = 35.0
    rsi_buy_max: float = 45.0
    rsi_sell_min: float = 55.0
    rsi_sell_max: float = 65.0

    # --- エントリー (M15 ブレイク) ---
    breakout_bars: int = 20        # 直近何本の高値/安値を参照するか

    # --- 損切り/利確 (ATR) ---
    atr_period: int = 14
    atr_timeframe: str = "H1"      # ATRを計算する時間足
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 3.0
    min_rr: float = 2.0            # 最低リスクリワード比 1:2

    # --- リスク管理 ---
    risk_percent: float = 1.0      # 1トレードのリスク = 口座資金の%
    max_daily_loss_pct: float = 3.0
    max_monthly_loss_pct: float = 10.0

    # --- 重要指標フィルター ---
    # バックテストでは外部カレンダーが無いため無視。実運用(live)でのみ使用。
    use_news_filter: bool = True
    news_stop_minutes: int = 60

    # --- 口座 (バックテスト用) ---
    # OANDA Japan口座はJPY建て前提。USDJPYの損益はそのまま円で計算できる。
    initial_balance: float = 1_000_000.0   # 円
    account_ccy: str = "JPY"

    # --- コスト (バックテスト用) ---
    spread_pips: float = 0.8       # 往復スプレッド(pips)を約定価格に上乗せ
    pip_size: float = 0.01         # USDJPYの1pip = 0.01

    # 1ポジション固定。ナンピン・マーチンは構造的に行わない。
