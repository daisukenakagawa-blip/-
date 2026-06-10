#!/usr/bin/env python3
"""
手動実行用 データ取得スクリプト（CLI）
====================================================================
Streamlitを使わず、コマンドラインから1日1回のデータ取得を行います。
cron 等で1日1回呼び出すこともできますが、まずは手動実行を想定しています。

使い方:
    python collect.py                # 本日分を取得
    python collect.py 2026-06-09     # 指定日を取得
    python collect.py --force        # レート制限を無視（テスト用）
    python collect.py --demo-history 90   # デモ履歴を90日分まとめて生成
"""

import sys
from datetime import date, datetime

import storage as db
import scraper
import sample_data
import config


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]

    if "--demo-history" in argv:
        i = argv.index("--demo-history")
        days = int(argv[i + 1]) if i + 1 < len(argv) else 90
        hist = sample_data.generate_history(days=days)
        ins = skip = 0
        for d, recs in hist.items():
            a, b = db.save_records(recs, d)
            ins += a
            skip += b
        print(f"デモ履歴生成: 新規{ins}件 / 重複スキップ{skip}件")
        return 0

    # --require-real: 実サイト接続が無効ならスキップ（自動実行でデモデータを
    # 本番シートに書き込まないための安全弁）
    if "--require-real" in argv and not config.SCRAPER_ENABLED:
        print("[skip] 実サイト接続が無効のため自動収集をスキップしました。"
              "（デモデータは書き込みません）")
        return 0

    target = parse_date(args[0]) if args else date.today()
    print(f"対象: {config.STORE_NAME} / {config.MACHINE_NAME}")
    print(f"取得日: {target.isoformat()}  "
          f"モード: {'実サイト' if config.SCRAPER_ENABLED else 'デモ'}")
    print(f"保存先: {db.backend_label()}")

    try:
        records = scraper.fetch(target, force=force)
    except scraper.FetchBlocked as e:
        print(f"[中止] {e}")
        return 1

    ins, skip = db.save_records(records, target.isoformat())
    print(f"完了: 新規{ins}件 / 重複スキップ{skip}件")
    print(f"DB: {config.DB_PATH}  （総レコード {db.record_count()} 件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
