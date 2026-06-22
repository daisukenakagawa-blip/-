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

from fx_bot.config import Config
from fx_bot.live import evaluate_and_trade, log


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
