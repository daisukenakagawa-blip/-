#!/usr/bin/env python3
"""USD/JPY 独自ボット - 実トレード実行 (OANDA v20)。

MT4/MT5を使わず、このスクリプト自身が証券会社APIに接続して売買する。
バックテスト(run_backtest.py)と完全に同じ戦略ロジックを使用。

事前準備 (環境変数):
  export OANDA_TOKEN=...        # v20 APIトークン
  export OANDA_ACCOUNT=...      # 口座ID
  export OANDA_ENV=practice     # practice(デモ) / live(本番)

実行:
  python3 run_live.py                  # デモで常時稼働
  python3 run_live.py --once           # 1回だけ判定して終了 (動作確認)

★ OANDA_ENV=live は実資金が動く。必ず practice で数ヶ月検証してから。
"""
import argparse
import sys
import time
from datetime import datetime, timezone

from fx_bot.config import Config
from fx_bot.indicators import atr, ema, rsi
from fx_bot.strategy import entry_signal, trend_direction


def log(msg: str):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z] {msg}", flush=True)


def evaluate_and_trade(client, cfg: Config, instrument: str, digits: int,
                       state: dict, dry: bool = False):
    """1サイクル: データ取得 → 判定 → 発注。"""
    # --- データ取得 ---
    m15 = client.candles(instrument, "M15", count=cfg.breakout_bars + 5)
    h1 = client.candles(instrument, "H1", count=cfg.rsi_period + 5)
    h4 = client.candles(instrument, "H4", count=cfg.ema_slow + 5)
    atr_src = h1 if cfg.atr_timeframe == "H1" else \
        client.candles(instrument, cfg.atr_timeframe, count=cfg.atr_period + 5)
    if len(h4) < cfg.ema_slow + 1 or len(h1) < cfg.rsi_period + 1 or len(m15) < cfg.breakout_bars + 2:
        log("データ不足。スキップ。")
        return

    # --- 新しいM15足の確定を検出 ---
    last_m15_time = m15[-1].time
    if state.get("last_m15") == last_m15_time:
        return  # まだ同じ足
    state["last_m15"] = last_m15_time

    # --- 指標 (すべて確定足) ---
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

    # --- 損失リミット (当日/当月の開始残高比) ---
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

    # --- フィルター ---
    if client.open_positions(instrument) > 0:
        return  # ナンピン禁止: 既にポジションあり
    if cfg.use_news_filter and client.has_high_impact_news(cfg.news_stop_minutes):
        log("重要指標フィルターにより停止。")
        return

    # --- エントリー判定 (確定足ベース) ---
    closed = m15[-1]                       # 直近確定M15足
    window = m15[-(cfg.breakout_bars + 1):-1]  # その前 n 本
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
        sl, tp, units = mid - sl_dist, mid + tp_dist, +int(balance * cfg.risk_percent / 100 / sl_dist)
    else:
        sl, tp, units = mid + sl_dist, mid - tp_dist, -int(balance * cfg.risk_percent / 100 / sl_dist)
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


def main() -> int:
    p = argparse.ArgumentParser(description="USD/JPY 独自ボット 実トレード (OANDA)")
    p.add_argument("--once", action="store_true", help="1回だけ判定して終了")
    p.add_argument("--dry", action="store_true", help="発注せず判定のみ (新規足ごとにログ)")
    p.add_argument("--interval", type=int, default=30, help="ポーリング間隔(秒)")
    args = p.parse_args()

    from fx_bot.oanda import OandaClient, OandaError
    try:
        client = OandaClient()
    except OandaError as e:
        log(f"設定エラー: {e}")
        return 1

    cfg = Config()
    instrument = cfg.symbol  # "USD_JPY"
    digits = 3
    log(f"接続先: {client.env}  口座: {client.account}  銘柄: {instrument}")
    log(f"残高: {client.balance():,.0f} {client.account_summary().get('currency','')}")
    if client.env == "live":
        log("★★★ 本番(live)口座です。実資金が動きます。★★★")

    state: dict = {}
    if args.once:
        # 強制的に新規足扱いにして1回評価
        evaluate_and_trade(client, cfg, instrument, digits, state, dry=True)
        return 0

    log("常時稼働を開始します (Ctrl+Cで停止)。")
    try:
        while True:
            try:
                evaluate_and_trade(client, cfg, instrument, digits, state, dry=args.dry)
            except Exception as e:  # ネットワーク等で落ちないよう継続
                log(f"エラー(継続): {e}")
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        log("停止しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
