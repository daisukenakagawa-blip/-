"""HTMLテーブルの汎用パーサ。

台データ公開サイトの多くは「台番号 / BB / RB / 総スタート …」のような
テーブル形式なので、見出しテキストとフィールドの対応を設定で与えれば
サイトごとの専用コードなしで取り込める。
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup

_NUMBER_RE = re.compile(r"-?\d+")


def normalize_number(text: str) -> int | None:
    """「１,２３４回」のような表記から整数を取り出す。数値が無ければ None。"""
    if text is None:
        return None
    normalized = unicodedata.normalize("NFKC", text).replace(",", "")
    match = _NUMBER_RE.search(normalized)
    return int(match.group()) if match else None


def _clean(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def parse_unit_table(
    html: str,
    table_selector: str,
    columns: dict[str, list[str]],
) -> list[dict]:
    """テーブルを解析し、1台 = 1dict のリストを返す。

    columns: フィールド名 -> 見出しテキスト候補のリスト。
    戻り値の各dictは {"unit_no": "1023", "metrics": {"bb": 20, ...}}。
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(table_selector)
    if table is None:
        raise ValueError(f"テーブルが見つかりません (selector={table_selector!r})")

    rows = table.find_all("tr")
    if not rows:
        return []

    header_cells = [_clean(c.get_text()) for c in rows[0].find_all(["th", "td"])]

    # 見出し -> 列インデックスの対応を作る（部分一致ではなく完全一致を優先）
    field_index: dict[str, int] = {}
    for field, candidates in columns.items():
        for cand in candidates:
            cand_norm = _clean(cand)
            if cand_norm in header_cells:
                field_index[field] = header_cells.index(cand_norm)
                break

    if "unit_no" not in field_index:
        raise ValueError(
            f"台番号の列が見つかりません。見出し: {header_cells}"
        )

    units: list[dict] = []
    for row in rows[1:]:
        cells = [_clean(c.get_text()) for c in row.find_all(["th", "td"])]
        if len(cells) < len(header_cells):
            continue  # 区切り行や広告行はスキップ
        unit_no_raw = cells[field_index["unit_no"]]
        unit_no = normalize_number(unit_no_raw)
        if unit_no is None:
            continue
        metrics = {
            field: normalize_number(cells[idx])
            for field, idx in field_index.items()
            if field != "unit_no"
        }
        units.append({"unit_no": str(unit_no), "metrics": metrics})
    return units
