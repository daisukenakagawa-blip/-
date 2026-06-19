# -*- coding: utf-8 -*-
"""
note_writer が作った Markdown 記事を読み込み、投稿に使える形に変換する。

- front matter(--- で囲まれた部分)から 推奨価格 / タグ / 予約日時 を取得
- 本文の最初の "# 見出し" を記事タイトルとして抽出
- "ここから先は有料パートです" の行で 無料パート / 有料パート に分割
- 投稿時に不要な装飾行(front matter, 区切り線, 販売前メモ)は除去
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


PAYWALL_KEYWORD = "ここから先は有料パートです"


@dataclass
class Article:
    path: Path
    title: str = ""
    price: int = 0
    tags: List[str] = field(default_factory=list)
    schedule_at: str = ""
    free_lines: List[str] = field(default_factory=list)   # 無料パートの本文行
    paid_lines: List[str] = field(default_factory=list)   # 有料パートの本文行
    is_paid: bool = False

    @property
    def body_lines(self) -> List[str]:
        """無料 + 有料 を結合した全文(投稿エディタに入力する内容)"""
        if self.is_paid and self.paid_lines:
            return self.free_lines + [""] + self.paid_lines
        return self.free_lines

    @property
    def free_line_count(self) -> int:
        return len(self.free_lines)


def _parse_front_matter(text: str):
    """先頭の --- ... --- を dict にして返し、本文と分離する。"""
    meta = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if m:
        block = m.group(1)
        body = text[m.end():]
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta, body


def _extract_price(meta: dict) -> int:
    raw = meta.get("推奨価格", "") or meta.get("price", "")
    m = re.search(r"\d[\d,]*", raw.replace(",", ""))
    return int(m.group()) if m else 0


def _extract_tags(meta: dict) -> List[str]:
    raw = meta.get("タグ", "") or meta.get("tags", "")
    return re.findall(r"#\S+", raw)


def _is_skippable(line: str) -> bool:
    """投稿本文に含めたくない行か判定する。"""
    s = line.strip()
    if not s:
        return False  # 空行は段落区切りとして残す
    # 区切り線(―や─の連続、--- )
    if re.fullmatch(r"[―ー—\-－─=━]{3,}", s):
        return True
    # 「販売前メモ」以降の出品者向けノート
    if "販売前" in s and ("メモ" in s or "チェック" in s):
        return True
    return False


def load_article(path: Path) -> Article:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_front_matter(text)

    art = Article(
        path=path,
        price=_extract_price(meta),
        tags=_extract_tags(meta),
        schedule_at=meta.get("予約日時", "") or meta.get("schedule_at", ""),
    )
    art.is_paid = art.price > 0

    lines = body.splitlines()

    # タイトル抽出: 最初の "# 見出し"
    title_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            art.title = line.strip()[2:].strip()
            title_idx = i
            break
    content_lines = lines[title_idx + 1:] if title_idx is not None else lines

    # 「販売前メモ」以降を丸ごと落とす
    cut = len(content_lines)
    for i, line in enumerate(content_lines):
        if "販売前" in line and ("メモ" in line or "チェック" in line):
            cut = i
            break
    content_lines = content_lines[:cut]

    # 有料ラインで分割
    in_paid = False
    for line in content_lines:
        if PAYWALL_KEYWORD in line:
            in_paid = True
            continue
        if _is_skippable(line):
            continue
        target = art.paid_lines if in_paid else art.free_lines
        target.append(line.rstrip())

    # 先頭・末尾の空行を整える
    art.free_lines = _trim_blank(art.free_lines)
    art.paid_lines = _trim_blank(art.paid_lines)
    return art


def _trim_blank(lines: List[str]) -> List[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def load_all(articles_dir: Path) -> List[Article]:
    files = sorted(articles_dir.glob("*.md"))
    return [load_article(p) for p in files]
