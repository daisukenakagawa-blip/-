"""
保存先ルーター（SQLite ⇄ Googleスプレッドシート 自動切替）
====================================================================
アプリ(app.py)・CLI(collect.py) はこのモジュール経由でデータを保存/読込する。
保存先は config.STORAGE_BACKEND と、与えられた認証情報により自動で決まる。

- "sqlite" : ローカルPC向け（従来どおり data/jagler.db）
- "gsheet" : Googleスプレッドシートを本体に（クラウドでも消えない）
- "auto"   : 認証情報があれば gsheet、無ければ sqlite

【認証情報の渡し方（gsheet利用時）】
  1. Streamlitアプリ: st.secrets を app.py が set_gsheet_credentials() で注入
  2. CLI/ローカル    : 環境変数 GCP_SERVICE_ACCOUNT_JSON（JSON文字列）
                      もしくは config.GSHEET_CREDENTIALS_PATH のファイル
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

import config
import database  # SQLite バックエンド

# Streamlit から注入される認証情報・設定（任意）
_injected_credentials: dict | None = None
_injected_gs_config: dict = {}
_gsheet_store = None  # GSheetStore のキャッシュ


# ------------------------------------------------------------------
# Streamlit / 外部からの設定注入
# ------------------------------------------------------------------
def set_gsheet_credentials(cred: dict) -> None:
    global _injected_credentials, _gsheet_store
    _injected_credentials = dict(cred) if cred else None
    _gsheet_store = None  # 再生成させる


def set_gsheet_config(cfg: dict) -> None:
    global _injected_gs_config, _gsheet_store
    _injected_gs_config = dict(cfg) if cfg else {}
    _gsheet_store = None


# ------------------------------------------------------------------
# 認証情報の解決
# ------------------------------------------------------------------
def _resolve_credentials():
    """dict（推奨）またはファイルパスを返す。無ければ None。"""
    if _injected_credentials:
        return _injected_credentials
    env = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if env:
        try:
            return json.loads(env)
        except json.JSONDecodeError:
            pass
    path = Path(config.GSHEET_CREDENTIALS_PATH)
    if path.exists():
        return path
    return None


def _gsheet_available() -> bool:
    return _resolve_credentials() is not None


# ------------------------------------------------------------------
# バックエンド選択
# ------------------------------------------------------------------
def active_backend() -> str:
    backend = getattr(config, "STORAGE_BACKEND", "auto")
    if backend == "sqlite":
        return "sqlite"
    if backend == "gsheet":
        return "gsheet"
    # auto
    return "gsheet" if _gsheet_available() else "sqlite"


def backend_label() -> str:
    """画面表示用の説明（データが消えるか否かを明示）。"""
    if active_backend() == "gsheet":
        return "🟢 Googleスプレッドシート（蓄積OK・再起動でも消えません）"
    return "🟡 SQLite（このPC内・クラウドでは再起動で消えます）"


def _get_gsheet_store():
    global _gsheet_store
    if _gsheet_store is None:
        from gsheet_store import GSheetStore
        cred = _resolve_credentials()
        if cred is None:
            raise RuntimeError(
                "Googleスプレッドシートの認証情報が見つかりません。"
                "DEPLOY.md の手順で設定してください。"
            )
        name = _injected_gs_config.get("spreadsheet_name",
                                       config.GSHEET_SPREADSHEET_NAME)
        ws = _injected_gs_config.get("worksheet_name",
                                     config.GSHEET_WORKSHEET_NAME)
        key = _injected_gs_config.get("spreadsheet_key",
                                      getattr(config, "GSHEET_SPREADSHEET_KEY", None))
        _gsheet_store = GSheetStore(cred, name, ws, spreadsheet_key=key)
    return _gsheet_store


# ------------------------------------------------------------------
# 公開API（app.py / collect.py はこれだけ使う）
# ------------------------------------------------------------------
def save_records(raw_records: Iterable[dict], date_str: str, store: str,
                 machine_name: str | None = None) -> tuple[int, int]:
    if active_backend() == "gsheet":
        return _get_gsheet_store().save_records(
            raw_records, date_str, store, machine_name)
    return database.save_records(raw_records, date_str, store, machine_name)


def load_all() -> pd.DataFrame:
    if active_backend() == "gsheet":
        return _get_gsheet_store().load_all()
    return database.load_all()


def load_by_date(date_str: str, store: str | None = None) -> pd.DataFrame:
    if active_backend() == "gsheet":
        return _get_gsheet_store().load_by_date(date_str, store)
    return database.load_by_date(date_str, store)


def available_dates() -> list[str]:
    if active_backend() == "gsheet":
        return _get_gsheet_store().available_dates()
    return database.available_dates()


def available_stores() -> list[str]:
    if active_backend() == "gsheet":
        return _get_gsheet_store().available_stores()
    return database.available_stores()


def record_count() -> int:
    if active_backend() == "gsheet":
        return _get_gsheet_store().record_count()
    return database.record_count()
