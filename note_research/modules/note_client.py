# -*- coding: utf-8 -*-
"""
note.com の公開 JSON API から記事を検索・取得するクライアント。

note には公式の検索 API(エンドポイント)が存在し、ブラウザの検索結果もこれを
利用しています。本ツールはこの公開エンドポイントを、人間の閲覧と同程度の
ゆるやかな間隔で叩いて記事メタデータ(タイトル・価格・スキ数など)を集めます。

※ 仕様変更でフィールド名が変わる可能性があるため、全て .get() で防御的に取得します。
"""
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import requests

SEARCH_ENDPOINT = "https://note.com/api/v3/searchnote"


@dataclass
class NoteItem:
    """1記事ぶんのメタデータ"""
    key: str = ""
    title: str = ""
    url: str = ""
    price: int = 0
    is_paid: bool = False
    like_count: int = 0
    comment_count: int = 0
    published_at: str = ""
    author_name: str = ""
    author_urlname: str = ""
    author_followers: int = 0
    keyword: str = ""          # どの検索キーワードでヒットしたか

    def as_dict(self) -> dict:
        return asdict(self)


class NoteClient:
    def __init__(self, user_agent: str, timeout: int, interval: float,
                 max_retries: int, logger):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Referer": "https://note.com/search",
        })
        self.timeout = timeout
        self.interval = interval
        self.max_retries = max_retries
        self.log = logger

    # ── 内部: 1ページぶん取得 ───────────────────────────────
    def _fetch_page(self, keyword: str, start: int, size: int) -> Optional[dict]:
        params = {
            "q": keyword,
            "size": size,
            "start": start,
            "context": "note",
            "mode": "search",
        }
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(
                    SEARCH_ENDPOINT, params=params, timeout=self.timeout
                )
                if resp.status_code == 200:
                    return resp.json()
                self.log.warn(
                    f"  HTTP {resp.status_code} (keyword='{keyword}', start={start}) "
                    f"retry {attempt}/{self.max_retries}"
                )
            except Exception as e:
                self.log.warn(
                    f"  通信エラー: {e} (keyword='{keyword}') "
                    f"retry {attempt}/{self.max_retries}"
                )
            time.sleep(self.interval * attempt)
        return None

    # ── 内部: API レスポンスから記事配列を取り出す ──────────
    @staticmethod
    def _extract_contents(data: dict) -> List[dict]:
        # 仕様揺れに備え、想定される複数の場所を順に探す
        try:
            notes = data.get("data", {}).get("notes", {})
            if isinstance(notes, dict) and "contents" in notes:
                return notes.get("contents", []) or []
            if isinstance(notes, list):
                return notes
        except AttributeError:
            pass
        # 念のため別パターン
        d = data.get("data", {})
        if isinstance(d, dict) and isinstance(d.get("contents"), list):
            return d["contents"]
        return []

    @staticmethod
    def _is_last(data: dict) -> bool:
        try:
            notes = data.get("data", {}).get("notes", {})
            if isinstance(notes, dict):
                return bool(notes.get("isLastPage", False))
        except AttributeError:
            pass
        return False

    # ── 内部: 生 JSON を NoteItem に変換 ───────────────────
    @staticmethod
    def _parse_item(raw: dict, keyword: str) -> NoteItem:
        price = int(raw.get("price") or 0)
        user = raw.get("user") or {}
        urlname = user.get("urlname", "")
        key = raw.get("key", "")
        url = raw.get("note_url") or (
            f"https://note.com/{urlname}/n/{key}" if urlname and key else ""
        )
        return NoteItem(
            key=key,
            title=raw.get("name", "") or "",
            url=url,
            price=price,
            is_paid=price > 0,
            like_count=int(raw.get("like_count") or 0),
            comment_count=int(raw.get("comment_count") or 0),
            published_at=str(raw.get("publish_at") or ""),
            author_name=user.get("nickname", "") or "",
            author_urlname=urlname,
            author_followers=int(user.get("follower_count") or 0),
            keyword=keyword,
        )

    # ── 公開: キーワードで記事を集める ──────────────────────
    def search(self, keyword: str, max_items: int, page_size: int) -> List[NoteItem]:
        items: List[NoteItem] = []
        seen = set()
        start = 0
        while len(items) < max_items:
            data = self._fetch_page(keyword, start, page_size)
            if not data:
                break
            contents = self._extract_contents(data)
            if not contents:
                break
            for raw in contents:
                if not isinstance(raw, dict):
                    continue
                item = self._parse_item(raw, keyword)
                if item.key and item.key not in seen:
                    seen.add(item.key)
                    items.append(item)
            if self._is_last(data) or len(contents) < page_size:
                break
            start += page_size
            time.sleep(self.interval)
        return items[:max_items]
