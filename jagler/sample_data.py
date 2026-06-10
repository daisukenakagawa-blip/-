"""
サンプル（デモ）データ生成
====================================================================
実サイトに接続せずに、ツールの全機能を試せるよう、
現実的なジャグラーの出方を模したダミーデータを生成します。

- 台ごとに「クセ（設定が入りやすい度合い）」を持たせ、
  末尾・曜日にも緩やかな傾向を付与しています。
- あくまで動作確認・デモ用であり、実際の店舗データではありません。
"""

from __future__ import annotations

import random
from datetime import date, timedelta

# マイジャグラーの設定別 おおよその合算確率（分母）イメージ
# 設定1:約1/146 設定2:約1/144 設定3:約1/138 設定4:約1/132 設定5:約1/126 設定6:約1/120
SETTING_COMBINED = {1: 146, 2: 144, 3: 138, 4: 132, 5: 126, 6: 120}
# REG確率（分母）。設定差が大きい。
SETTING_REG = {1: 410, 2: 380, 3: 345, 4: 315, 5: 290, 6: 273}

MACHINE_NUMBERS = list(range(1, 21))  # 1〜20番台を想定


def _pick_setting(machine_no: int, d: date) -> int:
    """台番号・末尾・曜日からそれっぽい設定を確率的に選ぶ（デモ用のクセ）。"""
    rng = random.Random(f"{machine_no}-{d.isoformat()}")
    tail = machine_no % 10

    weights = {1: 40, 2: 22, 3: 14, 4: 10, 5: 8, 6: 6}

    # 末尾7・末尾3を強めにするクセ
    if tail in (7,):
        weights[5] += 10
        weights[6] += 10
    if tail in (3,):
        weights[4] += 6
        weights[5] += 4

    # 角台（1, 20）にやや甘いクセ
    if machine_no in (1, 20):
        weights[5] += 6
        weights[6] += 4

    # 土日（5,6）は全体的に設定が入りやすい
    if d.weekday() in (5, 6):
        weights[5] += 6
        weights[6] += 6

    settings = list(weights.keys())
    w = list(weights.values())
    return rng.choices(settings, weights=w, k=1)[0]


def _simulate_day(machine_no: int, d: date) -> dict:
    rng = random.Random(f"sim-{machine_no}-{d.isoformat()}")
    setting = _pick_setting(machine_no, d)

    # その日の総回転数（営業時間ぶん）。3000〜9000ゲーム程度。
    total = rng.randint(3000, 9000)

    base_combined = SETTING_COMBINED[setting]
    base_reg = SETTING_REG[setting]
    # 1日の引きブレを ±15% 程度のせる
    combined_div = base_combined * rng.uniform(0.85, 1.15)
    reg_div = base_reg * rng.uniform(0.80, 1.20)

    bb_reg_total = max(1, round(total / combined_div))
    reg = max(0, round(total / reg_div))
    reg = min(reg, bb_reg_total)
    big = bb_reg_total - reg

    return {
        "machine_no": machine_no,
        "big": big,
        "reg": reg,
        "total_games": total,
    }


def generate_for_date(d: date) -> list[dict]:
    """指定日の全台ぶんのサンプルデータを返す。"""
    return [_simulate_day(m, d) for m in MACHINE_NUMBERS]


def generate_history(days: int = 120, end: date | None = None) -> dict[str, list[dict]]:
    """
    過去 days 日分の履歴をまとめて生成する。
    戻り値: {"YYYY-MM-DD": [生レコード, ...], ...}
    """
    end = end or date.today()
    out: dict[str, list[dict]] = {}
    for i in range(days):
        d = end - timedelta(days=i)
        out[d.isoformat()] = generate_for_date(d)
    return out
