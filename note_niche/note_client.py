# -*- coding: utf-8 -*-
"""note の公開検索APIから、キーワードの上位記事メタデータを取得する。"""
import time

import requests

SEARCH_ENDPOINT = "https://note.com/api/v3/searchnote"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_top_notes(keyword, max_items=40, interval=1.0, logger=None):
    """キーワードでnoteを検索し、スキ数順の記事メタデータ（dictのリスト）を返す。"""
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json"})
    items, seen, start = [], set(), 0
    while len(items) < max_items:
        try:
            resp = session.get(
                SEARCH_ENDPOINT,
                params={"q": keyword, "size": 20, "start": start,
                        "context": "note", "mode": "search"},
                timeout=20,
            )
            if resp.status_code != 200:
                if logger:
                    logger.warn(f"  note検索 HTTP {resp.status_code} ('{keyword}')")
                break
            data = resp.json()
        except Exception as e:
            if logger:
                logger.warn(f"  note検索エラー '{keyword}': {e}")
            break

        notes = ((data.get("data") or {}).get("notes") or {})
        contents = notes.get("contents") or []
        if not contents:
            break
        for raw in contents:
            if not isinstance(raw, dict):
                continue
            key = raw.get("key", "")
            if not key or key in seen:
                continue
            seen.add(key)
            price = int(raw.get("price") or 0)
            user = raw.get("user") or {}
            items.append({
                "title": raw.get("name", "") or "",
                "price": price,
                "is_paid": price > 0,
                "like_count": int(raw.get("like_count") or 0),
                "author": user.get("nickname", "") or "",
                "followers": int(user.get("follower_count") or 0),
            })
        if notes.get("isLastPage"):
            break
        start += 20
        time.sleep(interval)
    items.sort(key=lambda x: x["like_count"], reverse=True)
    return items[:max_items]
