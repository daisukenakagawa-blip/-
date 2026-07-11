"""コマンドラインエントリポイント。

使い方:
    python -m pachi collect --config config.yaml [--date 2026-07-11]
    python -m pachi report  --config config.yaml [--out reports/]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date as date_cls
from urllib.parse import urljoin

from .aggregate import daily_model_summary, unit_history, write_csv
from .config import load_config
from .http import Fetcher
from .parse import parse_unit_table
from .storage import connect, load_readings, save_readings


def cmd_collect(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    target_date = args.date or date_cls.today().isoformat()
    fetcher = Fetcher(
        user_agent=cfg.user_agent,
        rate_limit_seconds=cfg.rate_limit_seconds,
        respect_robots_txt=cfg.respect_robots_txt,
    )
    conn = connect(cfg.db_path)

    total = 0
    for page in cfg.pages:
        url = urljoin(cfg.base_url + "/", page.url)
        print(f"[collect] {page.name}: {url}")
        try:
            html = fetcher.fetch(url)
            units = parse_unit_table(html, cfg.table_selector, cfg.columns)
        except Exception as exc:  # 1機種の失敗で全体を止めない
            print(f"  !! 失敗: {exc}", file=sys.stderr)
            continue
        saved = save_readings(conn, target_date, cfg.hall_name, page.name, units)
        total += saved
        print(f"  -> {saved} 台分を保存")

    print(f"[collect] 完了: {target_date} / 合計 {total} 台分")
    return 0 if total > 0 else 1


def cmd_report(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    conn = connect(cfg.db_path)
    readings = load_readings(conn)
    if not readings:
        print("データがありません。先に collect を実行してください。", file=sys.stderr)
        return 1

    summary = daily_model_summary(readings)
    history = unit_history(readings)
    out = args.out
    write_csv(summary, f"{out}/daily_model_summary.csv")
    write_csv(history, f"{out}/unit_history.csv")

    print(f"[report] {out}/daily_model_summary.csv, {out}/unit_history.csv を出力")
    print()
    print(f"{'日付':<12}{'機種':<20}{'台数':>4}{'平均G数':>10}{'BB':>6}{'RB':>6}{'合成確率':>10}")
    for row in summary:
        prob = f"1/{row['combined_prob']}" if row["combined_prob"] else "-"
        print(
            f"{row['date']:<12}{row['model']:<20}{row['units']:>4}"
            f"{row['avg_start']:>10}{row['total_bb']:>6}{row['total_rb']:>6}{prob:>10}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pachi", description="台データ収集・集計ツール")
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="データを収集してDBへ保存")
    p_collect.add_argument("--config", required=True)
    p_collect.add_argument("--date", help="営業日 (YYYY-MM-DD)。省略時は今日")
    p_collect.set_defaults(func=cmd_collect)

    p_report = sub.add_parser("report", help="集計してCSVを出力")
    p_report.add_argument("--config", required=True)
    p_report.add_argument("--out", default="reports")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
