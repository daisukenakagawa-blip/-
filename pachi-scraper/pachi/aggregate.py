"""収集データの集計とCSV出力。

- daily_model_summary: 日別×機種別の合計・平均・合成確率
- unit_history: 台ごとの日別履歴（横持ちしやすい縦形式）
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def _bonus_total(row: dict) -> int:
    return sum(row.get(k) or 0 for k in ("bb", "rb", "art"))


def combined_probability(row: dict) -> float | None:
    """合成確率（1/n の n を返す）。総スタートとボーナス回数が揃っている場合のみ。"""
    start = row.get("start")
    bonus = _bonus_total(row)
    if not start or not bonus:
        return None
    return round(start / bonus, 1)


def daily_model_summary(readings: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in readings:
        groups[(r["date"], r["hall"], r["model"])].append(r)

    summary = []
    for (date, hall, model), rows in sorted(groups.items()):
        n = len(rows)
        total_start = sum(r.get("start") or 0 for r in rows)
        total_bb = sum(r.get("bb") or 0 for r in rows)
        total_rb = sum(r.get("rb") or 0 for r in rows)
        total_bonus = sum(_bonus_total(r) for r in rows)
        summary.append(
            {
                "date": date,
                "hall": hall,
                "model": model,
                "units": n,
                "total_start": total_start,
                "avg_start": round(total_start / n, 1) if n else 0,
                "total_bb": total_bb,
                "total_rb": total_rb,
                "combined_prob": (
                    round(total_start / total_bonus, 1) if total_start and total_bonus else None
                ),
            }
        )
    return summary


def unit_history(readings: list[dict]) -> list[dict]:
    history = []
    for r in sorted(readings, key=lambda x: (x["model"], x["unit_no"], x["date"])):
        history.append({**r, "combined_prob": combined_probability(r)})
    return history


def write_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # 全行のキーの和集合を列にする（機種によって項目が違っても欠けないように）
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # Excelで開ける BOM 付き
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
