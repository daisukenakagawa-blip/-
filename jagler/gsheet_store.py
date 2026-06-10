"""
Googleスプレッドシートを「データベース本体」として使う保存層
====================================================================
Streamlit Cloud は再起動でSQLiteが消えるため、消えない保存先として
Googleスプレッドシートに直接 読み書き（蓄積）する。

- 同日・同台の重複は (date, machine_no) で防止（SQLite版と同じ仕様）
- 派生指標の計算は database.enrich_record を再利用（ロジック重複なし）
- スマホのスプレッドシートアプリからも中身を直接確認できる

必要: pip install gspread
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from database import enrich_record

# スプレッドシートの列順（records テーブルの id を除いた並び）
HEADERS = [
    "date", "weekday", "machine_no", "big", "reg", "total_games",
    "big_prob", "reg_prob", "combined_prob", "bb_reg_total",
    "reg_ratio", "tail", "created_at",
]

# 数値として扱う列（読み出し時に型を揃える）
INT_COLS = ["machine_no", "big", "reg", "total_games", "bb_reg_total", "tail"]
FLOAT_COLS = ["big_prob", "reg_prob", "combined_prob", "reg_ratio"]


def _filter_new(existing_keys: set[tuple[str, int]],
                raw_records: Iterable[dict], date_str: str) -> list[dict]:
    """
    既存キー集合とバッチ内重複を考慮し、新規登録すべき行（enrich済み）だけを返す。
    ※ネットワークに依存しない純粋関数（テスト可能）。
    """
    new_rows: list[dict] = []
    seen = set(existing_keys)
    for raw in raw_records:
        rec = enrich_record(raw, date_str)
        key = (rec["date"], rec["machine_no"])
        if key in seen:
            continue
        seen.add(key)
        new_rows.append(rec)
    return new_rows


class GSheetStore:
    """storage.py から使われる、SQLite版と同じインターフェースの保存層。"""

    def __init__(self, credentials, spreadsheet_name: str,
                 worksheet_name: str, spreadsheet_key: str | None = None):
        import gspread

        if isinstance(credentials, dict):
            self._gc = gspread.service_account_from_dict(credentials)
        else:  # ファイルパス
            self._gc = gspread.service_account(filename=str(credentials))

        # スプレッドシートを開く（キー優先 → 名前。無ければ作成）
        if spreadsheet_key:
            sh = self._gc.open_by_key(spreadsheet_key)
        else:
            try:
                sh = self._gc.open(spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                sh = self._gc.create(spreadsheet_name)
        self._sh = sh

        # ワークシートを開く（無ければ作成し、ヘッダ行を用意）
        try:
            ws = sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=worksheet_name, rows=1000,
                                  cols=len(HEADERS))
        self._ws = ws
        self._ensure_header()

    # -- 内部 --------------------------------------------------------
    def _ensure_header(self) -> None:
        first_row = self._ws.row_values(1)
        if first_row != HEADERS:
            self._ws.update([HEADERS], "A1")

    def _existing_keys(self) -> set[tuple[str, int]]:
        df = self.load_all()
        if df.empty:
            return set()
        return {(str(r["date"]), int(r["machine_no"]))
                for _, r in df.iterrows()}

    # -- 公開インターフェース（SQLite版と同名・同戻り値） -----------
    def load_all(self) -> pd.DataFrame:
        records = self._ws.get_all_records(expected_headers=HEADERS)
        df = pd.DataFrame(records, columns=HEADERS)
        if df.empty:
            return df
        df = df[df["date"].astype(str).str.len() > 0]  # 空行除去
        for c in INT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
        for c in FLOAT_COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values(
            ["date", "machine_no"], ascending=[False, True]
        ).reset_index(drop=True)

    def save_records(self, raw_records: Iterable[dict],
                     date_str: str) -> tuple[int, int]:
        raw_list = list(raw_records)
        new_rows = _filter_new(self._existing_keys(), raw_list, date_str)
        inserted = len(new_rows)
        skipped = len(raw_list) - inserted
        if new_rows:
            values = [[r.get(h, "") for h in HEADERS] for r in new_rows]
            self._ws.append_rows(values, value_input_option="USER_ENTERED")
        return inserted, skipped

    def load_by_date(self, date_str: str) -> pd.DataFrame:
        df = self.load_all()
        if df.empty:
            return df
        return df[df["date"].astype(str) == date_str].sort_values("machine_no")

    def available_dates(self) -> list[str]:
        df = self.load_all()
        if df.empty:
            return []
        return sorted(df["date"].astype(str).unique(), reverse=True)

    def record_count(self) -> int:
        return len(self.load_all())
