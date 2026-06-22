"""実トレードの判定・発注ロジック (run_live.py と run_bot.py で共有)。

バックテスト(backtest.py)と完全に同じ戦略を、リアルタイムのデータで実行する。
"""
from datetime import datetime, timezone

from .config import Config
from .indicators import atr, ema, rsi
from .strategy import entry_signal, trend_direction


def log(msg: str):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z] {msg}", flush=True)


def evaluate_and_trade(client, cfg: Config, instrument: str, digits: int,
                       state: dict, dry: bool = False):
    """1サイクル: データ取得 → 判定 → 発注。

    新しいM15足が確定したときだけ判定する。1ポジション固定・固定リスクのため
    ナンピン/マーチンは構造的に発生しない。
    """
    m15 = client.candles(instrument, "M15", count=cfg.breakout_bars + 5)
    h1 = client.candles(instrument, "H1", count=cfg.rsi_period + 5)
    h4 = client.candles(instrument, "H4", count=cfg.ema_slow + 5)
    atr_src = h1 if cfg.atr_timeframe == "H1" else \
        client.candles(instrument, cfg.atr_timeframe, count=cfg.atr_period + 5)
    if len(h4) < cfg.ema_slow + 1 or len(h1) < cfg.rsi_period + 1 or len(m15) < cfg.breakout_bars + 2:
        log("データ不足。スキップ。")
        return

    last_m15_time = m15[-1].time
    if state.get("last_m15") == last_m15_time:
        return  # まだ同じ足
    state["last_m15"] = last_m15_time

    ef = ema([b.close for b in h4], cfg.ema_fast)[-1]
    es = ema([b.close for b in h4], cfg.ema_slow)[-1]
    rv = rsi([b.close for b in h1], cfg.rsi_period)[-1]
    av = atr([b.high for b in atr_src], [b.low for b in atr_src],
             [b.close for b in atr_src], cfg.atr_period)[-1]
    if None in (ef, es, rv, av) or av <= 0:
        log("指標計算待ち。スキップ。")
        return

    direction = trend_direction(ef, es)
    trend_txt = "買い環境" if direction == 1 else "売り環境" if direction == -1 else "中立"
    log(f"H4:{trend_txt} H1_RSI:{rv:.1f} ATR:{av/cfg.pip_size:.1f}pips")

    # 損失リミット (当日/当月の開始残高比)
    balance = client.balance()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if state.get("day") != today:
        state["day"], state["day_start"] = today, balance
    if state.get("month") != month:
        state["month"], state["month_start"] = month, balance
    if balance - state["day_start"] <= -state["day_start"] * cfg.max_daily_loss_pct / 100:
        log("日次損失リミット到達。本日は新規停止。")
        return
    if balance - state["month_start"] <= -state["month_start"] * cfg.max_monthly_loss_pct / 100:
        log("月次損失リミット到達。今月は新規停止。")
        return

    if client.open_positions(instrument) > 0:
        return  # ナンピン禁止: 既にポジションあり
    if cfg.use_news_filter and client.has_high_impact_news(cfg.news_stop_minutes):
        log("重要指標フィルターにより停止。")
        return

    closed = m15[-1]
    window = m15[-(cfg.breakout_bars + 1):-1]
    recent_high = max(b.high for b in window)
    recent_low = min(b.low for b in window)
    sig = entry_signal(direction, rv, closed.close, recent_high, recent_low, cfg)
    if sig == 0:
        return

    sl_dist = av * cfg.sl_atr_mult
    tp_dist = av * cfg.tp_atr_mult
    if sl_dist <= 0 or tp_dist / sl_dist < cfg.min_rr - 1e-9:
        log("RR不足のため見送り。")
        return

    mid = closed.close
    if sig == 1:
        sl, tp = mid - sl_dist, mid + tp_dist
        units = +int(balance * cfg.risk_percent / 100 / sl_dist)
    else:
        sl, tp = mid + sl_dist, mid - tp_dist
        units = -int(balance * cfg.risk_percent / 100 / sl_dist)
    if units == 0:
        log("計算ロットが0。残高またはリスク設定を確認。")
        return

    side = "BUY" if sig == 1 else "SELL"
    log(f"シグナル: {side} units={units} SL={sl:.{digits}f} TP={tp:.{digits}f}")
    if dry:
        log("(dry-run のため発注しません)")
        return
    res = client.market_order(instrument, units, sl, tp, digits)
    fill = res.get("orderFillTransaction")
    if fill:
        log(f"約定: {fill.get('price')} units={fill.get('units')}")
    else:
        log(f"発注応答: {res}")
