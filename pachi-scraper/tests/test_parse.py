from pathlib import Path

from pachi.parse import normalize_number, parse_unit_table

FIXTURES = Path(__file__).parent / "fixtures"

COLUMNS = {
    "unit_no": ["台番号"],
    "bb": ["BB"],
    "rb": ["RB"],
    "start": ["総スタート"],
    "max_medals": ["最大出メダル"],
}


def test_normalize_number():
    assert normalize_number("１,２３４回") == 1234
    assert normalize_number("4,120回") == 4120
    assert normalize_number("0枚") == 0
    assert normalize_number("データなし") is None
    assert normalize_number("") is None


def test_parse_unit_table():
    html = (FIXTURES / "im_juggler.html").read_text(encoding="utf-8")
    units = parse_unit_table(html, "table.unit_list", COLUMNS)

    # 広告行はスキップされ、データ4台分だけが取れる
    assert len(units) == 4

    first = units[0]
    assert first["unit_no"] == "1001"  # 全角 -> 半角
    assert first["metrics"] == {"bb": 25, "rb": 18, "start": 7234, "max_medals": 3560}


def test_list_tables():
    from pachi.parse import list_tables

    html = (FIXTURES / "im_juggler.html").read_text(encoding="utf-8")
    tables = list_tables(html)

    assert len(tables) == 1
    t = tables[0]
    assert t["selector"] == "table.unit_list"
    assert t["headers"] == ["台番号", "BB", "RB", "総スタート", "最大出メダル"]
    assert t["rows"] == 5  # 広告行込みの生の行数
    assert t["suggested_columns"]["unit_no"] == "台番号"
    assert t["suggested_columns"]["bb"] == "BB"
    assert t["suggested_columns"]["start"] == "総スタート"


def test_extract_all_unit_tables():
    from pachi.parse import extract_all_unit_tables

    columns = {
        "unit_no": ["台番号"],
        "bb": ["BB"],
        "rb": ["RB"],
        "start": ["総回転数"],
        "diff_medals": ["差枚"],
    }
    html = (FIXTURES / "store_page.html").read_text(encoding="utf-8")
    tables = extract_all_unit_tables(html, columns)

    # 機種ごとに見出しが拾えて、2つのテーブルに分かれる
    assert [t["model"] for t in tables] == ["マイジャグラーV", "アイムジャグラーEX"]
    assert len(tables[0]["units"]) == 3
    assert len(tables[1]["units"]) == 2

    # 差枚の符号（+/-）も正しく取れる
    myjug = tables[0]["units"]
    assert myjug[0]["metrics"]["diff_medals"] == 1240
    assert myjug[1]["metrics"]["diff_medals"] == -820


def test_parse_missing_table():
    import pytest

    with pytest.raises(ValueError):
        parse_unit_table("<html><body>no table</body></html>", "table.unit_list", COLUMNS)
