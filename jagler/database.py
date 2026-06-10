"""
SQLite データベース層（多店舗対応）
====================================================================
- データの保存（重複防止つき）
- 読み出し（pandas DataFrame）
- 各種派生指標（確率・末尾など）の計算

複数店舗のデータを扱えるよう store（店舗名）・machine_name（機種名）を持つ。
一意キーは (date, store, machine_no)。
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
# (日付, 店舗, 台番号) を一意キーにして、同日・同店・同台の重複登録を防ぐ。
SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,   -- YYYY-MM-DD
    weekday       TEXT    NOT NULL,   -- 月〜日
    store         TEXT    NOT NULL,   -- 店舗名
    machine_name  TEXT,               -- 機種名（ジャグラー系の種類）
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
    UNIQUE(date, store, machine_no)
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _needs_migration(conn) -> bool:
    """旧スキーマ（store 列なし）かどうかを判定。"""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='records'"
    ).fetchone()
    if not tables:
        return False
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(records)")]
    return "store" not in cols


def _migrate(conn) -> None:
    """旧テーブルを新スキーマへ移行（既存行は既定店舗名を補完）。"""
    conn.execute("ALTER TABLE records RENAME TO records_old")
    conn.execute(SCHEMA)
    old_cols = [r["name"] for r in conn.execute("PRAGMA table_info(records_old)")]
    common = [c for c in
              ["date", "weekday", "machine_no", "big", "reg", "total_games",
               "big_prob", "reg_prob", "combined_prob", "bb_reg_total",
               "reg_ratio", "tail", "created_at"] if c in old_cols]
    col_list = ", ".join(common)
    conn.execute(
        f"INSERT INTO records (store, machine_name, {col_list}) "
        f"SELECT ?, ?, {col_list} FROM records_old",
        (config.STORE_NAME, config.MACHINE_NAME),
    )
    conn.execute("DROP TABLE records_old")
    conn.commit()


def init_db() -> None:
    with get_connection() as conn:
        if _needs_migration(conn):
            _migrate(conn)
        conn.execute(SCHEMA)
        conn.commit()


# ------------------------------------------------------------------
# 派生指標の計算
# ------------------------------------------------------------------
def _safe_div(n: float, d: float) -> float | None:
    return (n / d) if d else None


def enrich_record(rec: dict, date_str: str, store: str,
                  machine_name: str | None = None) -> dict:
    """
    生データ（machine_no, big, reg, total_games）と店舗・日付から
    確率・末尾・曜日などの派生項目を計算して返す。
    """
    big = int(rec["big"])
    reg = int(rec["reg"])
    total = int(rec["total_games"])
    machine_no = int(rec["machine_no"])

    bb_reg_total = big + reg
    big_prob = _safe_div(total, big)
    reg_prob = _safe_div(total, reg)
    combined_prob = _safe_div(total, bb_reg_total)
    reg_ratio = _safe_div(reg, bb_reg_total)

    d = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = WEEKDAY_JP[d.weekday()]

    return {
        "date": date_str,
        "weekday": weekday,
        "store": store,
        "machine_name": machine_name or rec.get("machine_name") or config.MACHINE_NAME,
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
def save_records(raw_records: Iterable[dict], date_str: str, store: str,
                 machine_name: str | None = None) -> tuple[int, int]:
    """
    生データのリストを保存する。
    戻り値: (新規登録件数, スキップした重複件数)
    """
    init_db()
    inserted = 0
    skipped = 0
    with get_connection() as conn:
        for raw in raw_records:
            rec = enrich_record(raw, date_str, store, machine_name)
            try:
                conn.execute(
                    """
                    INSERT INTO records
                    (date, weekday, store, machine_name, machine_no, big, reg,
                     total_games, big_prob, reg_prob, combined_prob,
                     bb_reg_total, reg_ratio, tail, created_at)
                    VALUES
                    (:date, :weekday, :store, :machine_name, :machine_no, :big,
                     :reg, :total_games, :big_prob, :reg_prob, :combined_prob,
                     :bb_reg_total, :reg_ratio, :tail, :created_at)
                    """,
                    rec,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # UNIQUE(date, store, machine_no) 違反 = 重複
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
            "SELECT * FROM records ORDER BY date DESC, store ASC, machine_no ASC",
            conn,
        )
    return df


def load_by_date(date_str: str, store: str | None = None) -> pd.DataFrame:
    init_db()
    sql = "SELECT * FROM records WHERE date = ?"
    params: list = [date_str]
    if store:
        sql += " AND store = ?"
        params.append(store)
    sql += " ORDER BY store ASC, machine_no ASC"
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=tuple(params))


def available_dates() -> list[str]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM records ORDER BY date DESC"
        ).fetchall()
    return [r["date"] for r in rows]


def available_stores() -> list[str]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT store FROM records ORDER BY store ASC"
        ).fetchall()
    return [r["store"] for r in rows]


def record_count() -> int:
    init_db()
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
