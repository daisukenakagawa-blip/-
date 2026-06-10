"""
データ取得層
====================================================================
- レート制限（1日1回）の強制
- robots.txt のチェック
- 実サイトからの取得（設定済みの場合）/ デモデータ（未設定の場合）

【設計方針】
本ツールは「正確にデータを蓄積する」ことを最優先にしています。
実サイト接続部分（HTML解析）は、対象サイトの利用規約と構造を
利用者が確認のうえで config.py に設定してから有効化してください。
未設定の場合はサンプルデータで全機能が動作します。
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import config
import sample_data


class FetchBlocked(Exception):
    """レート制限・robots.txt 等で取得が許可されない場合に送出。"""


# ------------------------------------------------------------------
# レート制限（1日1回）
# ------------------------------------------------------------------
def _read_last_fetch() -> dict:
    if config.LAST_FETCH_PATH.exists():
        try:
            return json.loads(config.LAST_FETCH_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_last_fetch(ts: float) -> None:
    config.LAST_FETCH_PATH.write_text(
        json.dumps({"last_fetch_ts": ts,
                    "last_fetch_iso": datetime.fromtimestamp(ts).isoformat()}),
        encoding="utf-8",
    )


def seconds_until_allowed() -> float:
    """次の取得が許可されるまでの残り秒数。0以下なら取得可能。"""
    last = _read_last_fetch().get("last_fetch_ts")
    if last is None:
        return 0.0
    elapsed = time.time() - last
    return config.MIN_FETCH_INTERVAL_SEC - elapsed


def can_fetch_now() -> bool:
    return seconds_until_allowed() <= 0


# ------------------------------------------------------------------
# robots.txt
# ------------------------------------------------------------------
def robots_allows(url: str) -> bool:
    if not config.RESPECT_ROBOTS_TXT:
        return True
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(config.USER_AGENT, url)
    except Exception:
        # robots.txt が取得できない場合は安全側に倒して False
        return False


# ------------------------------------------------------------------
# 実サイト取得（要設定）
# ------------------------------------------------------------------
def _fetch_real(target_date: date) -> list[dict]:
    import requests
    from bs4 import BeautifulSoup

    if not config.TARGET_URL_TEMPLATE or not config.TABLE_SELECTOR:
        raise FetchBlocked(
            "実サイト接続が有効ですが、TARGET_URL_TEMPLATE / TABLE_SELECTOR が "
            "未設定です。config.py を設定してください。"
        )

    url = config.TARGET_URL_TEMPLATE.format(
        date=target_date.strftime(config.URL_DATE_FORMAT)
    )

    if not robots_allows(url):
        raise FetchBlocked(
            f"robots.txt により {url} へのアクセスが許可されていません。"
        )

    resp = requests.get(
        url,
        headers={"User-Agent": config.USER_AGENT},
        timeout=config.REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.select_one(config.TABLE_SELECTOR)
    if table is None:
        raise FetchBlocked(
            f"セレクタ '{config.TABLE_SELECTOR}' に一致する表が見つかりません。"
        )

    return _parse_table(table)


def _parse_table(table) -> list[dict]:
    """
    HTMLテーブルを config.COLUMN_MAP に従って解析する。
    サイト構造に依存するため、必要に応じてこの関数を調整してください。
    """
    rows = table.find_all("tr")
    if not rows:
        return []

    # ヘッダ行から列見出し→列indexの対応を作る
    header_cells = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    header_index = {h: i for i, h in enumerate(header_cells)}

    def col_index(spec):
        if isinstance(spec, int):
            return spec
        return header_index.get(spec)

    idx = {k: col_index(v) for k, v in config.COLUMN_MAP.items()}

    def to_int(text: str) -> int:
        digits = "".join(ch for ch in text if ch.isdigit())
        return int(digits) if digits else 0

    records = []
    for tr in rows[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not cells or len(cells) < len(header_cells):
            continue
        try:
            records.append({
                "machine_no": to_int(cells[idx["machine_no"]]),
                "big": to_int(cells[idx["big"]]),
                "reg": to_int(cells[idx["reg"]]),
                "total_games": to_int(cells[idx["total_games"]]),
            })
        except (TypeError, IndexError):
            continue
    return records


# ------------------------------------------------------------------
# 公開API
# ------------------------------------------------------------------
def fetch(target_date: date | None = None, *, force: bool = False,
          use_demo: bool | None = None) -> list[dict]:
    """
    データを1回取得する。

    引数:
      target_date : 取得対象日（省略時は本日）
      force       : True でレート制限を無視（テスト用・非推奨）
      use_demo    : True を明示するとデモデータを返す。
                    None の場合は config.SCRAPER_ENABLED に従う。

    戻り値: 生レコードのリスト [{machine_no, big, reg, total_games}, ...]
    """
    target_date = target_date or date.today()

    if not force and not can_fetch_now():
        remaining = seconds_until_allowed()
        hrs = remaining / 3600
        raise FetchBlocked(
            f"1日1回の取得制限により、あと約 {hrs:.1f} 時間は取得できません。"
        )

    demo = (not config.SCRAPER_ENABLED) if use_demo is None else use_demo

    if demo:
        records = sample_data.generate_for_date(target_date)
    else:
        records = _fetch_real(target_date)

    _write_last_fetch(time.time())
    return records
