#!/usr/bin/env python3
"""USD/JPY 独自ボットのバックテスト実行スクリプト。

使い方:
  # 実データが無くてもすぐ試せる合成データで実行
  python3 run_backtest.py --synth

  # 実データ(M15のCSV)で実行  列: time,open,high,low,close
  python3 run_backtest.py --csv path/to/usdjpy_m15.csv

  # パラメーター上書きの例
  python3 run_backtest.py --synth --risk 1.0 --balance 1000000
"""
import argparse
import sys

from fx_bot.backtest import run
from fx_bot.config import Config
from fx_bot.data import generate_synthetic, load_csv


def main() -> int:
    p = argparse.ArgumentParser(description="USD/JPY トレンド押し目ボット バックテスト")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="M15のCSV (time,open,high,low,close)")
    src.add_argument("--synth", action="store_true", help="合成データで実行 (動作確認用)")
    p.add_argument("--months", type=int, default=6, help="合成データの月数 (--synth時)")
    p.add_argument("--seed", type=int, default=7, help="合成データのシード")
    p.add_argument("--risk", type=float, help="1トレードのリスク%% (既定1.0)")
    p.add_argument("--balance", type=float, help="初期資金 円 (既定1,000,000)")
    p.add_argument("--spread", type=float, help="スプレッド pips (既定0.8)")
    p.add_argument("--breakout", type=int, help="M15ブレイク参照本数 (既定20)")
    p.add_argument("--trades", action="store_true", help="個別トレード明細も表示")
    args = p.parse_args()

    cfg = Config()
    if args.risk is not None:
        cfg.risk_percent = args.risk
    if args.balance is not None:
        cfg.initial_balance = args.balance
    if args.spread is not None:
        cfg.spread_pips = args.spread
    if args.breakout is not None:
        cfg.breakout_bars = args.breakout

    if args.synth:
        print(f"合成データ生成中 ({args.months}ヶ月, seed={args.seed}) ...")
        m15 = generate_synthetic(months=args.months, seed=args.seed)
    else:
        print(f"CSV読み込み中: {args.csv}")
        m15 = load_csv(args.csv)
    print(f"M15足: {len(m15)} 本")

    res = run(m15, cfg)
    print()
    print(res.report())

    if args.trades:
        print("\n--- トレード明細 ---")
        from datetime import datetime, timezone
        for i, t in enumerate(res.trades, 1):
            et = datetime.fromtimestamp(t.entry_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            side = "BUY " if t.direction == 1 else "SELL"
            print(f"{i:3d} {et} {side} 数量{t.units:8.0f} "
                  f"約定{t.entry:.3f} → {t.exit:.3f} [{t.reason}] {t.pnl:+,.0f}円")
    return 0


if __name__ == "__main__":
    sys.exit(main())
