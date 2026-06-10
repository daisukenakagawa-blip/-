"""
サンプル（デモ）データ生成（多店舗対応）
====================================================================
実サイトに接続せずにツールの全機能を試せるよう、複数店舗ぶんの
ジャグラーの出方を模したダミーデータを生成します。

- 店舗ごとに「設定の入りやすさ（クセ）」を変えてある
- 末尾・曜日・角台にも緩やかな傾向を付与
- あくまで動作確認・デモ用であり、実際の店舗データではありません。
"""

from __future__ import annotations

import random
from datetime import date, timedelta

# マイジャグラーの設定別 おおよその合算確率（分母）イメージ
SETTING_COMBINED = {1: 146, 2: 144, 3: 138, 4: 132, 5: 126, 6: 120}
SETTING_REG = {1: 410, 2: 380, 3: 345, 4: 315, 5: 290, 6: 273}

MACHINE_NUMBERS = list(range(1, 21))  # 1〜20番台を想定

# デモ用の店舗と機種（東京都の複数店をイメージ）。
# 末尾の "tightness" が大きいほど高設定が入りにくい店（デモ用のクセ）。
DEMO_STORES = [
    {"name": "ビッグディッパー新橋1号店", "machine": "マイジャグラーV", "tightness": 0.0},
    {"name": "デモホール渋谷",           "machine": "アイムジャグラーEX", "tightness": 0.6},
    {"name": "デモホール新宿東口",        "machine": "ファンキージャグラー2", "tightness": -0.4},
]


def _pick_setting(store: dict, machine_no: int, d: date) -> int:
    """店舗・台番号・末尾・曜日からそれっぽい設定を確率的に選ぶ（デモ用のクセ）。"""
    rng = random.Random(f"{store['name']}-{machine_no}-{d.isoformat()}")
    tail = machine_no % 10

    weights = {1: 40, 2: 22, 3: 14, 4: 10, 5: 8, 6: 6}

    # 末尾7・末尾3を強めにするクセ
    if tail == 7:
        weights[5] += 10
        weights[6] += 10
    if tail == 3:
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

    # 店舗ごとの渋さ（tightness>0 で高設定を減らす）
    t = store.get("tightness", 0.0)
    weights[5] = max(1, weights[5] - int(10 * t))
    weights[6] = max(1, weights[6] - int(10 * t))
    weights[1] = max(1, weights[1] + int(10 * t))

    settings = list(weights.keys())
    w = list(weights.values())
    return rng.choices(settings, weights=w, k=1)[0]


def _simulate_day(store: dict, machine_no: int, d: date) -> dict:
    rng = random.Random(f"sim-{store['name']}-{machine_no}-{d.isoformat()}")
    setting = _pick_setting(store, machine_no, d)

    total = rng.randint(3000, 9000)
    combined_div = SETTING_COMBINED[setting] * rng.uniform(0.85, 1.15)
    reg_div = SETTING_REG[setting] * rng.uniform(0.80, 1.20)

    bb_reg_total = max(1, round(total / combined_div))
    reg = max(0, round(total / reg_div))
    reg = min(reg, bb_reg_total)
    big = bb_reg_total - reg

    return {
        "machine_no": machine_no,
        "big": big,
        "reg": reg,
        "total_games": total,
        "machine_name": store["machine"],
    }


def generate_store_day(store: dict, d: date) -> list[dict]:
    """指定店舗・指定日の全台ぶんのサンプルデータを返す。"""
    return [_simulate_day(store, m, d) for m in MACHINE_NUMBERS]


# 後方互換：単一店舗（先頭のデモ店）の1日分
def generate_for_date(d: date) -> list[dict]:
    return generate_store_day(DEMO_STORES[0], d)


def generate_history(days: int = 120, end: date | None = None) -> list[dict]:
    """
    過去 days 日分 × 全デモ店舗の履歴を生成する。
    戻り値: [{"date","store","machine","records":[...]}, ...]
    """
    end = end or date.today()
    out: list[dict] = []
    for i in range(days):
        d = end - timedelta(days=i)
        for store in DEMO_STORES:
            out.append({
                "date": d.isoformat(),
                "store": store["name"],
                "machine": store["machine"],
                "records": generate_store_day(store, d),
            })
    return out
