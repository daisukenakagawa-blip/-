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


# inspect コマンドが列マッピングを提案するときに使う見出しキーワード
KNOWN_HEADER_FIELDS = {
    "unit_no": ["台番号", "台番", "No"],
    "bb": ["BB", "ビッグ", "BIG"],
    "rb": ["RB", "レギュラー", "REG", "バケ"],
    "start": ["総スタート", "スタート", "総回転", "G数", "ゲーム数", "総G数"],
    "diff_medals": ["差枚", "差メダル"],
    "max_medals": ["最大出メダル", "最大持ちメダル"],
}


def list_tables(html: str) -> list[dict]:
    """HTML内の全テーブルを列挙し、設定ファイル作成の材料を返す。

    各要素: {"selector": "table:nth-of-type(1)", "headers": [...],
             "rows": 行数, "sample": 最初のデータ行, "suggested_columns": {...}}
    """
    soup = BeautifulSoup(html, "lxml")
    tables = []
    for i, table in enumerate(soup.find_all("table"), start=1):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [_clean(c.get_text()) for c in rows[0].find_all(["th", "td"])]
        sample = (
            [_clean(c.get_text()) for c in rows[1].find_all(["th", "td"])]
            if len(rows) > 1
            else []
        )
        suggested: dict[str, str] = {}
        for field, keywords in KNOWN_HEADER_FIELDS.items():
            for header in headers:
                if any(kw.lower() in header.lower() for kw in keywords):
                    suggested[field] = header
                    break
        klass = table.get("class")
        selector = f"table.{klass[0]}" if klass else f"table:nth-of-type({i})"
        tables.append(
            {
                "selector": selector,
                "headers": headers,
                "rows": len(rows) - 1,
                "sample": sample,
                "suggested_columns": suggested,
            }
        )
    return tables


def _nearest_heading(table) -> str | None:
    """テーブルの直前にある見出し（h1〜h4 / caption）を機種名として拾う。"""
    caption = table.find("caption")
    if caption and _clean(caption.get_text()):
        return _clean(caption.get_text())
    node = table
    for _ in range(30):  # 無限ループ防止に上限を設ける
        node = node.find_previous(["h1", "h2", "h3", "h4", "caption"])
        if node is None:
            return None
        text = _clean(node.get_text())
        if text:
            return text
    return None


def extract_all_unit_tables(
    html: str,
    columns: dict[str, list[str]],
) -> list[dict]:
    """ページ内の「台番号列を持つテーブル」を全て抽出する。

    店舗ページのように機種ごとにテーブルが分かれているHTMLを、
    1回の保存でまとめて取り込むために使う。
    戻り値: [{"model": 見出し, "units": [...] }, ...]
    機種名が拾えなかったテーブルは "機種1" のような連番を付ける。
    """
    soup = BeautifulSoup(html, "lxml")
    unit_no_headers = [_clean(c) for c in columns.get("unit_no", ["台番号"])]

    results: list[dict] = []
    fallback_index = 0
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = [_clean(c.get_text()) for c in rows[0].find_all(["th", "td"])]
        if not any(h in header_cells for h in unit_no_headers):
            continue  # 台データ以外のテーブル（案内表など）は無視
        units = _parse_rows(rows, header_cells, columns)
        if not units:
            continue
        model = _nearest_heading(table)
        if not model:
            fallback_index += 1
            model = f"機種{fallback_index}"
        results.append({"model": model, "units": units})
    return results


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
    return _parse_rows(rows, header_cells, columns, strict=True)


def _parse_rows(
    rows,
    header_cells: list[str],
    columns: dict[str, list[str]],
    strict: bool = False,
) -> list[dict]:
    """見出し行 + データ行から 1台=1dict のリストを作る共通処理。

    strict=True なら台番号列が見つからないとき例外を投げる（単一テーブル取得用）。
    strict=False なら空リストを返す（複数テーブル走査で非該当を弾く用）。
    """
    # 見出し -> 列インデックスの対応を作る（部分一致ではなく完全一致を優先）
    field_index: dict[str, int] = {}
    for field, candidates in columns.items():
        for cand in candidates:
            cand_norm = _clean(cand)
            if cand_norm in header_cells:
                field_index[field] = header_cells.index(cand_norm)
                break

    if "unit_no" not in field_index:
        if strict:
            raise ValueError(f"台番号の列が見つかりません。見出し: {header_cells}")
        return []

    units: list[dict] = []
    for row in rows[1:]:
        cells = [_clean(c.get_text()) for c in row.find_all(["th", "td"])]
        if len(cells) < len(header_cells):
            continue  # 区切り行や広告行はスキップ
        unit_no = normalize_number(cells[field_index["unit_no"]])
        if unit_no is None:
            continue
        metrics = {
            field: normalize_number(cells[idx])
            for field, idx in field_index.items()
            if field != "unit_no"
        }
        units.append({"unit_no": str(unit_no), "metrics": metrics})
    return units
