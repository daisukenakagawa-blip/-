#!/usr/bin/env python3
"""
手動実行用 データ取得スクリプト（CLI・多店舗対応）
====================================================================
config.STORES に登録された全店舗を巡回して取得し、保存します。
多店舗巡回時は1リクエストごとに待機（REQUEST_DELAY_SEC）を入れ、
全体で1日1回に制限します（サーバ負荷軽減・マナー）。

使い方:
    python collect.py                # 全店舗・本日分を取得
    python collect.py 2026-06-09     # 全店舗・指定日を取得
    python collect.py --force        # 1日1回ゲートを無視（テスト用）
    python collect.py --require-real # 実サイト未設定なら何もせず終了（自動実行向け）
    python collect.py --demo-history 90  # 全デモ店舗の履歴を90日分生成
"""

import sys
import time
from datetime import date, datetime

import storage as db
import scraper
import sample_data
import config


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _run_demo_history(days: int) -> int:
    hist = sample_data.generate_history(days=days)
    ins = skip = 0
    for entry in hist:
        a, b = db.save_records(entry["records"], entry["date"],
                               entry["store"], entry["machine"])
        ins += a
        skip += b
    print(f"デモ履歴生成: {len(sample_data.DEMO_STORES)}店 × {days}日 "
          f"-> 新規{ins}件 / 重複スキップ{skip}件")
    return 0


def main(argv: list[str]) -> int:
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]

    if "--demo-history" in argv:
        i = argv.index("--demo-history")
        days = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 90
        return _run_demo_history(days)

    # 自動実行の安全弁：実サイト未設定ならデモを本番に書き込まずスキップ
    if "--require-real" in argv and not config.SCRAPER_ENABLED:
        print("[skip] 実サイト接続が無効のため自動収集をスキップしました。"
              "（デモデータは書き込みません）")
        return 0

    target = parse_date(args[0]) if args else date.today()

    # 1日1回ゲート（巡回全体に対して1回）
    if not force and not scraper.can_fetch_now():
        hrs = scraper.seconds_until_allowed() / 3600
        print(f"[中止] 1日1回の取得制限により、あと約 {hrs:.1f} 時間は取得できません。")
        return 1

    stores = config.STORES or [{"name": config.STORE_NAME}]
    print(f"取得日: {target.isoformat()}  "
          f"モード: {'実サイト' if config.SCRAPER_ENABLED else 'デモ'}  "
          f"対象店舗: {len(stores)}店")
    print(f"保存先: {db.backend_label()}")

    total_ins = total_skip = total_err = 0
    for n, store in enumerate(stores):
        name = store.get("name")
        try:
            records = scraper.fetch_store(store, target)
            machine = store.get("machine") or config.MACHINE_NAME
            ins, skip = db.save_records(records, target.isoformat(), name, machine)
            total_ins += ins
            total_skip += skip
            print(f"  ✓ {name}: 新規{ins} / 重複{skip}")
        except scraper.FetchBlocked as e:
            total_err += 1
            print(f"  ✗ {name}: {e}")
        except Exception as e:  # noqa: BLE001
            total_err += 1
            print(f"  ✗ {name}: 取得失敗 {e}")

        # マナー：最後の店以外はリクエスト間に待機
        if config.SCRAPER_ENABLED and n < len(stores) - 1:
            time.sleep(config.REQUEST_DELAY_SEC)

    scraper.mark_run()
    print(f"完了: 新規{total_ins}件 / 重複{total_skip}件 / 失敗{total_err}店")
    print(f"総レコード {db.record_count()} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
