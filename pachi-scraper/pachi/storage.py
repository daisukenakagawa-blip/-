"""SQLiteへの保存。同じ日・同じ台のデータは上書き（当日中の再取得に対応）。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    date       TEXT NOT NULL,   -- 営業日 (YYYY-MM-DD)
    hall       TEXT NOT NULL,
    model      TEXT NOT NULL,   -- 機種名
    unit_no    TEXT NOT NULL,   -- 台番号
    metrics    TEXT NOT NULL,   -- JSON: {"bb": 20, "rb": 15, "start": 6800, ...}
    scraped_at TEXT NOT NULL,
    PRIMARY KEY (date, hall, model, unit_no)
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    return conn


def save_readings(
    conn: sqlite3.Connection,
    date: str,
    hall: str,
    model: str,
    units: list[dict],
) -> int:
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        """
        INSERT INTO readings (date, hall, model, unit_no, metrics, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (date, hall, model, unit_no)
        DO UPDATE SET metrics = excluded.metrics, scraped_at = excluded.scraped_at
        """,
        [
            (date, hall, model, u["unit_no"], json.dumps(u["metrics"]), scraped_at)
            for u in units
        ],
    )
    conn.commit()
    return len(units)


def load_readings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT date, hall, model, unit_no, metrics FROM readings ORDER BY date, model, unit_no"
    ).fetchall()
    return [
        {
            "date": r[0],
            "hall": r[1],
            "model": r[2],
            "unit_no": r[3],
            **json.loads(r[4]),
        }
        for r in rows
    ]
