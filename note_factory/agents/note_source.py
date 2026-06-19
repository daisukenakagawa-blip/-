# -*- coding: utf-8 -*-
"""
note の公開検索APIから、キーワードの売れ筋/人気記事メタデータを取得する。
（note_research の NoteClient を簡素化した自己完結版。話題スカウトの入力に使う）
"""
import time

import requests

SEARCH_ENDPOINT = "https://note.com/api/v3/searchnote"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_top_notes(keyword: str, max_items: int = 40, logger=None):
    """キーワードでnoteを検索し、スキ数順に並べた記事メタデータのリストを返す。"""
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
                    logger.warn(f"note検索 HTTP {resp.status_code} (start={start})")
                break
            data = resp.json()
        except Exception as e:
            if logger:
                logger.warn(f"note検索エラー: {e}")
            break

        contents = (((data.get("data") or {}).get("notes") or {}).get("contents")) or []
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
        if (((data.get("data") or {}).get("notes") or {}).get("isLastPage")):
            break
        start += 20
        time.sleep(1.0)

    items.sort(key=lambda x: x["like_count"], reverse=True)
    return items[:max_items]


def format_for_prompt(items) -> str:
    """記事リストを、LLMに渡しやすいテキストへ整形する。"""
    lines = []
    for i, it in enumerate(items, 1):
        price = f"¥{it['price']}" if it["is_paid"] else "無料"
        lines.append(
            f"{i}. 「{it['title']}」 / {price} / スキ{it['like_count']} / "
            f"著者フォロワー{it['followers']}"
        )
    return "\n".join(lines)
