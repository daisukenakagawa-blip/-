"""YAML設定ファイルの読み込み。"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml


@dataclasses.dataclass
class PageConfig:
    name: str  # 機種名（集計時のラベルになる）
    url: str   # base_url からの相対URL、または絶対URL/ローカルパス


@dataclasses.dataclass
class Config:
    hall_name: str
    base_url: str
    pages: list[PageConfig]
    columns: dict[str, list[str]]  # フィールド名 -> 見出し候補
    table_selector: str = "table"
    user_agent: str = "pachi-scraper/0.1"
    rate_limit_seconds: float = 3.0
    respect_robots_txt: bool = True
    db_path: str = "data/pachi.db"


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    pages = [PageConfig(name=p["name"], url=p["url"]) for p in raw["pages"]]

    # columns は "bb: BB" のような単一文字列も許容し、常にリストへ正規化する
    columns: dict[str, list[str]] = {}
    for field, headers in raw["columns"].items():
        columns[field] = [headers] if isinstance(headers, str) else list(headers)

    return Config(
        hall_name=raw["hall_name"],
        base_url=raw["base_url"],
        pages=pages,
        columns=columns,
        table_selector=raw.get("table_selector", "table"),
        user_agent=raw.get("user_agent", "pachi-scraper/0.1"),
        rate_limit_seconds=float(raw.get("rate_limit_seconds", 3.0)),
        respect_robots_txt=bool(raw.get("respect_robots_txt", True)),
        db_path=raw.get("db_path", "data/pachi.db"),
    )
