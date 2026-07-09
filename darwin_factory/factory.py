#!/usr/bin/env python3
"""ダーウィン工場: 事業ポートフォリオの観測・淘汰を自動化する CLI。

使い方:
    python factory.py report            # 全事業の成績表を reports/ に生成
    python factory.py launch <id>      # 事業の観測開始日を今日に設定
    python factory.py cull <id> --reason "理由"   # 事業を撤退状態にする
    python factory.py promote <id>     # 生存確定(倍賭け対象)にする

標準ライブラリのみで動く。登録数は Google フォームの回答シートを
「ウェブに公開(CSV)」した URL (signup_csv_url) から取得する。
"""

import argparse
import csv
import io
import json
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENTURES_FILE = ROOT / "ventures.json"
REPORTS_DIR = ROOT / "reports"

STATUS_LABELS = {
    "incubating": "観測中",
    "alive": "生存(倍賭け対象)",
    "culled": "撤退済み",
    "paused": "待機中",
}


def load() -> dict:
    return json.loads(VENTURES_FILE.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    VENTURES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_timestamp(value: str):
    value = value.strip()
    formats = (
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y/%m/%d",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fetch_signups(csv_url: str) -> list:
    """公開CSVから回答タイムスタンプ一覧を返す。1行目はヘッダとして捨てる。"""
    with urllib.request.urlopen(csv_url, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    stamps = []
    for row in rows[1:]:
        if row and row[0].strip():
            stamps.append(parse_timestamp(row[0]))
    return stamps


def judge(venture: dict, today: date) -> tuple:
    """(判定ラベル, 詳細文) を返す。レポート専用で状態は書き換えない。"""
    status = venture["status"]
    if status == "culled":
        return "撤退済み", "淘汰済み。対応不要。"
    if venture["type"] == "internal":
        return "対象外", venture.get("notes", "内部事業のため観測対象外。")
    if not venture.get("signup_csv_url"):
        return "未着工", "Google フォームと回答CSVのURLが未設定。README の手順①〜③を実施すると観測が始まる。"
    if not venture.get("launched"):
        return "未着工", "signup_csv_url は設定済み。`python factory.py launch " + venture["id"] + "` で観測開始日を記録すること。"

    launched = date.fromisoformat(venture["launched"])
    days = (today - launched).days
    observe_days = venture["criteria"].get("observe_days", 30)
    min_signups = venture["criteria"].get("min_signups", 10)

    try:
        stamps = fetch_signups(venture["signup_csv_url"])
    except Exception as exc:  # ネットワーク・URL不備はレポートに残す
        return "取得失敗", f"登録データの取得に失敗: {exc}"

    total = len(stamps)
    detail = f"観測 {min(days, observe_days)}/{observe_days} 日目、累計登録 {total} 件(基準 {min_signups} 件)。"

    if status == "alive":
        return "生存", detail + " 倍賭けフェーズ。"
    if days < observe_days:
        pace = "基準を上回るペース。" if total >= min_signups * days / observe_days else "このペースだと基準未達。"
        return "観測中", detail + " " + pace
    if total >= min_signups:
        return "生存判定", detail + f" 基準クリア。`python factory.py promote {venture['id']}` で倍賭け対象に昇格させること。"
    return "撤退勧告", detail + f" 観測期間満了・基準未達。`python factory.py cull {venture['id']} --reason \"30日で{total}件\"` で店じまいを推奨。"


def cmd_report(args) -> None:
    data = load()
    today = date.today()
    lines = [
        f"# ダーウィン工場 成績表 {today.isoformat()}",
        "",
        "| 事業 | 状態 | 判定 | 詳細 |",
        "|---|---|---|---|",
    ]
    summary = []
    for v in data["ventures"]:
        verdict, detail = judge(v, today)
        lines.append(
            f"| {v['name']} | {STATUS_LABELS.get(v['status'], v['status'])} | **{verdict}** | {detail} |"
        )
        summary.append((v["id"], verdict))

    lines += [
        "",
        "## 工場の掟",
        "",
        "- 撤退勧告が出た事業は感情を挟まず店じまいする(それが人間に対する構造的優位)。",
        "- 生存判定が出た事業だけに、翌月リソースを倍投入する。",
        "- 空いた枠には次の種(新事業)をまく。",
        "",
    ]

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"report-{today.isoformat()}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"レポート生成: {report_path}")
    for vid, verdict in summary:
        print(f"  {vid}: {verdict}")


def find(data: dict, venture_id: str) -> dict:
    for v in data["ventures"]:
        if v["id"] == venture_id:
            return v
    sys.exit(f"事業が見つからない: {venture_id}")


def cmd_launch(args) -> None:
    data = load()
    v = find(data, args.id)
    v["launched"] = date.today().isoformat()
    v["status"] = "incubating"
    save(data)
    print(f"{v['name']} の観測を開始した (launched={v['launched']})")


def cmd_cull(args) -> None:
    data = load()
    v = find(data, args.id)
    v["status"] = "culled"
    v["notes"] = f"撤退 ({date.today().isoformat()}): {args.reason}"
    save(data)
    print(f"{v['name']} を淘汰した。空いた枠に次の種をまくこと。")


def cmd_promote(args) -> None:
    data = load()
    v = find(data, args.id)
    v["status"] = "alive"
    save(data)
    print(f"{v['name']} を生存(倍賭け対象)に昇格した。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("report", help="成績表を生成").set_defaults(func=cmd_report)

    p = sub.add_parser("launch", help="観測開始日を今日に設定")
    p.add_argument("id")
    p.set_defaults(func=cmd_launch)

    p = sub.add_parser("cull", help="事業を撤退状態にする")
    p.add_argument("id")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_cull)

    p = sub.add_parser("promote", help="事業を生存状態にする")
    p.add_argument("id")
    p.set_defaults(func=cmd_promote)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
