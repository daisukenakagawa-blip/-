"""
SQLite データベース層
====================================================================
- データの保存（重複防止つき）
- 読み出し（pandas DataFrame）
- 各種派生指標（確率・末尾など）の計算
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable

import pandas as pd

import config

# 日本語曜日
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

# テーブル定義。
# (日付, 台番号) を一意キーにして、同日・同台の重複登録を防ぐ。
SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,   -- YYYY-MM-DD
    weekday       TEXT    NOT NULL,   -- 月〜日
    machine_no    INTEGER NOT NULL,
    big           INTEGER NOT NULL,
    reg           INTEGER NOT NULL,
    total_games   INTEGER NOT NULL,
    big_prob      REAL,               -- 分母（1/big_prob）
    reg_prob      REAL,
    combined_prob REAL,
    bb_reg_total  INTEGER,
    reg_ratio     REAL,               -- REG / (BIG+REG)
    tail          INTEGER,            -- 台番号末尾
    created_at    TEXT,
    UNIQUE(date, machine_no)
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(SCHEMA)
        conn.commit()


# ------------------------------------------------------------------
# 派生指標の計算
# ------------------------------------------------------------------
def _safe_div(n: float, d: float) -> float | None:
    return (n / d) if d else None


def enrich_record(rec: dict, date_str: str) -> dict:
    """
    生データ（machine_no, big, reg, total_games, date）から
    確率・末尾・曜日などの派生項目を計算して返す。
    """
    big = int(rec["big"])
    reg = int(rec["reg"])
    total = int(rec["total_games"])
    machine_no = int(rec["machine_no"])

    bb_reg_total = big + reg
    # 確率は「1/N」の N（分母）として保存。N が大きいほど引きが悪い。
    big_prob = _safe_div(total, big)
    reg_prob = _safe_div(total, reg)
    combined_prob = _safe_div(total, bb_reg_total)
    reg_ratio = _safe_div(reg, bb_reg_total)

    d = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAY_JP[d.weekday()]

    return {
        "date": date_str,
        "weekday": weekday,
        "machine_no": machine_no,
        "big": big,
        "reg": reg,
        "total_games": total,
        "big_prob": round(big_prob, 2) if big_prob else None,
        "reg_prob": round(reg_prob, 2) if reg_prob else None,
        "combined_prob": round(combined_prob, 2) if combined_prob else None,
        "bb_reg_total": bb_reg_total,
        "reg_ratio": round(reg_ratio, 4) if reg_ratio else None,
        "tail": machine_no % 10,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


# ------------------------------------------------------------------
# 保存（重複防止）
# ------------------------------------------------------------------
def save_records(raw_records: Iterable[dict], date_str: str) -> tuple[int, int]:
    """
    生データのリストを保存する。
    戻り値: (新規登録件数, スキップした重複件数)
    """
    init_db()
    inserted = 0
    skipped = 0
    with get_connection() as conn:
        for raw in raw_records:
            rec = enrich_record(raw, date_str)
            try:
                conn.execute(
                    """
                    INSERT INTO records
                    (date, weekday, machine_no, big, reg, total_games,
                     big_prob, reg_prob, combined_prob, bb_reg_total,
                     reg_ratio, tail, created_at)
                    VALUES
                    (:date, :weekday, :machine_no, :big, :reg, :total_games,
                     :big_prob, :reg_prob, :combined_prob, :bb_reg_total,
                     :reg_ratio, :tail, :created_at)
                    """,
                    rec,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # UNIQUE(date, machine_no) 違反 = 同日・同台の重複
                skipped += 1
        conn.commit()
    return inserted, skipped


# ------------------------------------------------------------------
# 読み出し
# ------------------------------------------------------------------
def load_all() -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM records ORDER BY date DESC, machine_no ASC", conn
        )
    return df


def load_by_date(date_str: str) -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM records WHERE date = ? ORDER BY machine_no ASC",
            conn,
            params=(date_str,),
        )
    return df


def available_dates() -> list[str]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM records ORDER BY date DESC"
        ).fetchall()
    return [r["date"] for r in rows]


def record_count() -> int:
    init_db()
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
