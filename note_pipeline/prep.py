# -*- coding: utf-8 -*-
"""
完成記事（note_factory の出力）を、そのまま自動投稿できる「投稿用」へ整える。

- 先頭の HTMLコメント（<!-- 工程メモ等 -->）を除去
- 末尾の「出品前メモ／販売前メモ」「参照・出典リスト」を除去
- note_publisher が価格・タグを読めるよう、フロントマター（推奨価格・タグ）を付与
- 有料ライン「ここから先は有料パートです」はそのまま残す（投稿ツールが分割に使う）
"""
import re


def _genre_to_tags(genre: str, limit: int = 5) -> str:
    words = [w for w in re.split(r"[\s　]+", (genre or "").strip()) if w]
    return " ".join("#" + w for w in words[:limit])


def to_publishable(text: str, price: str = "", tags: str = "") -> str:
    lines = text.splitlines()

    # 1) 最初の "# 見出し" まで（HTMLコメント・空行）を捨てる
    start = 0
    for i, l in enumerate(lines):
        if l.strip().startswith("# "):
            start = i
            break
    body = lines[start:]

    # 2) 末尾の編集用フッター（出品前/販売前メモ・参照リスト）を切る
    cut = len(body)
    for i, l in enumerate(body):
        s = l.strip()
        if ("出品前" in s or "販売前" in s) and "メモ" in s:
            cut = i
            break
        if re.match(r"^#{0,3}\s*(参照|参考|出典|ソース|リンク)\b", s) or \
           re.match(r"^#{0,3}\s*(参照|参考|出典|ソース)（", s):
            cut = i
            break
    body = body[:cut]

    # 3) 末尾の区切り線・空行を整える
    while body and (not body[-1].strip() or re.fullmatch(r"[-―ー—─=]{3,}", body[-1].strip())):
        body.pop()

    article = "\n".join(body).strip()

    # 4) フロントマター付与
    fm = "---\n"
    if price:
        fm += f"推奨価格: ¥{price}\n"
    if tags:
        fm += f"タグ: {tags}\n"
    fm += "---\n\n"
    return fm + article + "\n"


def make_publishable_file(src_path, dst_path, price="", genre="", tags=""):
    """src の記事を投稿用に整えて dst に保存。dst のパスを返す。"""
    from pathlib import Path
    src_path, dst_path = Path(src_path), Path(dst_path)
    text = src_path.read_text(encoding="utf-8")
    out = to_publishable(text, price=price, tags=(tags or _genre_to_tags(genre)))
    dst_path.write_text(out, encoding="utf-8")
    return dst_path
