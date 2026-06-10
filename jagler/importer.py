"""
貼り付け / 手動入力 データ取り込み層
====================================================================
利用者が自分のブラウザで見た台データ表を「コピペ」または「手入力」で
取り込むためのパーサー。サイトを自動巡回せず、規約を守って蓄積するための入口。

- タブ区切り（表をコピーすると多くはTSV）/ カンマ / 連続スペース に対応
- 先頭行が見出しなら自動でカラムを対応づけ（台番号/BIG/REG/総回転数）
- 見出しが無ければ列の並び順（COLUMN_ORDER）で解釈
"""

from __future__ import annotations

import re

# 見出し語 → 内部カラムの対応（部分一致・小文字化して判定）
HEADER_KEYWORDS = {
    "machine_no": ["台番", "台番号", "台№", "台no", "no", "番号", "台"],
    "big": ["big", "bb", "ビッグ", "ボーナス回数"],
    "reg": ["reg", "rb", "レギュラー"],
    "total_games": ["総回転", "総ゲーム", "総g", "ゲーム数", "回転数", "回転", "スタート"],
}

# 見出しが無いときの既定の列順
DEFAULT_COLUMN_ORDER = ["machine_no", "big", "reg", "total_games"]


def _split_line(line: str) -> list[str]:
    """
    1行をセルに分割。ブラウザの表コピーはタブ区切りが多い。
    桁区切りカンマ（例 6,500）を列区切りと誤認しないよう判定順を工夫する。
    """
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    # 2つ以上連続する空白（全角含む）があれば、それを列区切りとみなす
    if re.search(r"[ 　]{2,}", line):
        return [c.strip() for c in re.split(r"[ 　]{2,}", line.strip()) if c.strip()]
    # カンマが3つ以上ならCSVの列区切りとみなす（桁区切りの1個だけとは区別）
    if line.count(",") >= 3:
        return [c.strip() for c in line.split(",")]
    # それ以外は単一空白区切り（桁区切りカンマは _to_int 側で除去）
    return [c for c in re.split(r"[ 　]+", line.strip()) if c != ""]


def _to_int(text: str) -> int | None:
    """文字列から数値（整数）を抽出。'1,234' や '6000G' にも対応。"""
    digits = re.sub(r"[^0-9]", "", text)
    return int(digits) if digits else None


def _looks_like_header(cells: list[str]) -> bool:
    joined = " ".join(cells).lower()
    hits = 0
    for kws in HEADER_KEYWORDS.values():
        if any(kw in joined for kw in kws):
            hits += 1
    return hits >= 2  # 2項目以上それっぽければ見出しとみなす


def _map_header(cells: list[str]) -> dict[str, int]:
    """見出しセルから {内部カラム: 列index} を作る。"""
    mapping: dict[str, int] = {}
    lowered = [c.lower() for c in cells]
    for col, kws in HEADER_KEYWORDS.items():
        for i, cell in enumerate(lowered):
            if i in mapping.values():
                continue
            if any(kw in cell for kw in kws):
                mapping[col] = i
                break
    return mapping


def parse_pasted_text(text: str,
                      column_order: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """
    貼り付けテキストを解析し、生レコードのリストを返す。

    戻り値: (records, warnings)
      records  : [{machine_no, big, reg, total_games}, ...]
      warnings : 解析時の注意メッセージ（スキップ行など）
    """
    warnings: list[str] = []
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return [], ["入力が空です。"]

    # 見出し行の検出
    first_cells = _split_line(lines[0])
    if _looks_like_header(first_cells):
        mapping = _map_header(first_cells)
        data_lines = lines[1:]
        missing = [c for c in DEFAULT_COLUMN_ORDER if c not in mapping]
        if missing:
            warnings.append(
                "見出しから一部の列を特定できませんでした: "
                + ", ".join(missing) + "（列の並び順で補完します）")
        # 見出しで取れなかった分は並び順で補完
        order = column_order or DEFAULT_COLUMN_ORDER
        for i, col in enumerate(order):
            mapping.setdefault(col, i)
    else:
        order = column_order or DEFAULT_COLUMN_ORDER
        mapping = {col: i for i, col in enumerate(order)}
        data_lines = lines

    records = []
    for ln in data_lines:
        cells = _split_line(ln)
        try:
            mno = _to_int(cells[mapping["machine_no"]])
            big = _to_int(cells[mapping["big"]])
            reg = _to_int(cells[mapping["reg"]])
            total = _to_int(cells[mapping["total_games"]])
        except (IndexError, KeyError):
            warnings.append(f"列数が足りずスキップ: {ln[:40]}")
            continue
        if mno is None or big is None or reg is None or total is None:
            warnings.append(f"数値を読めずスキップ: {ln[:40]}")
            continue
        records.append({
            "machine_no": mno, "big": big, "reg": reg, "total_games": total,
        })

    if not records:
        warnings.append("有効なデータ行が見つかりませんでした。"
                        "列の並び順の設定を確認してください。")
    return records, warnings
