"""
出力・色分け層
====================================================================
- CSV出力
- Googleスプレッドシート出力（任意・gspread使用）
- 合算確率 / REG確率の色分け
"""

from __future__ import annotations

import pandas as pd

import config


# ------------------------------------------------------------------
# 色分け
# ------------------------------------------------------------------
def combined_color(div: float | None) -> str | None:
    """合算確率の分母から色（16進）を返す。範囲外は None。"""
    if div is None or pd.isna(div):
        return None
    for lo, hi, _name, hexc in config.COMBINED_COLOR_THRESHOLDS:
        if lo <= div <= hi:
            return hexc
    return None


def reg_color(div: float | None) -> str | None:
    if div is None or pd.isna(div):
        return None
    for lo, hi, _name, hexc in config.REG_COLOR_THRESHOLDS:
        if lo <= div <= hi:
            return hexc
    return None


def style_dataframe(df: pd.DataFrame):
    """
    Streamlit / pandas Styler 用。合算・REGの列を色分けして返す。
    対象列名: combined_prob, reg_prob（無ければ無視）
    """
    def _bg(col_name, fn):
        def inner(val):
            c = fn(val)
            return f"background-color: {c}" if c else ""
        return inner

    styler = df.style
    if "combined_prob" in df.columns:
        styler = styler.map(_bg("combined_prob", combined_color),
                            subset=["combined_prob"])
    if "reg_prob" in df.columns:
        styler = styler.map(_bg("reg_prob", reg_color), subset=["reg_prob"])
    return styler


# ------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Excelでも文字化けしないよう BOM 付き UTF-8 で返す。"""
    return df.to_csv(index=False).encode("utf-8-sig")


def save_csv(df: pd.DataFrame, path=None) -> str:
    path = path or config.CSV_EXPORT_PATH
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


# ------------------------------------------------------------------
# Googleスプレッドシート
# ------------------------------------------------------------------
def export_to_gsheet(df: pd.DataFrame) -> str:
    """
    Googleスプレッドシートへ出力する。
    事前準備:
      1) Google Cloud でサービスアカウントを作成し JSON キーを取得
      2) 対象スプレッドシートをそのサービスアカウントのメールと共有
      3) config.GSHEET_* を設定し GSHEET_ENABLED=True
      4) pip install gspread
    """
    if not config.GSHEET_ENABLED:
        raise RuntimeError("config.GSHEET_ENABLED が False です。")

    import gspread  # 遅延import（未使用時に依存を要求しない）

    gc = gspread.service_account(filename=config.GSHEET_CREDENTIALS_PATH)
    try:
        sh = gc.open(config.GSHEET_SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(config.GSHEET_SPREADSHEET_NAME)

    try:
        ws = sh.worksheet(config.GSHEET_WORKSHEET_NAME)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(
            title=config.GSHEET_WORKSHEET_NAME,
            rows=max(100, len(df) + 10), cols=max(20, len(df.columns) + 2),
        )

    values = [list(df.columns)] + df.astype(object).where(
        pd.notna(df), "").values.tolist()
    ws.update(values)
    return sh.url
