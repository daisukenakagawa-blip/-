# -*- coding: utf-8 -*-
"""
集めた記事を分析し、「売れる記事」の傾向を抽出する。

- 売れ筋ランキング(スキ数順)
- 価格帯の分布
- タイトルによく登場する単語・記号(【】や数字など)の傾向
- 著者のフォロワー規模との関係
"""
import re
from collections import Counter
from statistics import median
from typing import List

from .note_client import NoteItem

# タイトル分析で無視する一般的すぎる語(日本語の助詞・記号など)
STOPWORDS = {
    "の", "に", "は", "を", "が", "と", "で", "も", "や", "から", "まで",
    "する", "した", "して", "こと", "もの", "ため", "ない", "です", "ます",
    "note", "ノート", "について", "という", "ある", "いる", "なる", "私",
    "&", "-", "|", "/", "・", "！", "？", "。", "、", "…",
}

# 数字を含むタイトル(「3つの方法」など)を検出
NUM_RE = re.compile(r"\d+")
# 【】や「」などの装飾記号
BRACKET_RE = re.compile(r"[【】「」『』《》\[\]()]")


# アルファベット/数字混じりの語(ChatGPT, NISA, AI, iPhone など)
ALNUM_RE = re.compile(r"[A-Za-z][A-Za-z0-9\+\.]*")
# カタカナの連続(ブログ, ダイエット, ノウハウ など)
KATAKANA_RE = re.compile(r"[ァ-ヶー]{2,}")
# 漢字/ひらがなの連続(ここから 2〜3 文字の n-gram を作る)
JP_RUN_RE = re.compile(r"[一-龥々ぁ-ん]{2,}")


def _try_janome(title: str):
    """janome がインストールされていれば形態素解析で名詞を抽出。なければ None。"""
    global _JANOME
    try:
        if _JANOME is None:
            from janome.tokenizer import Tokenizer
            _JANOME = Tokenizer()
        words = []
        for tok in _JANOME.tokenize(title):
            pos = tok.part_of_speech.split(",")[0]
            if pos == "名詞" and len(tok.surface) >= 2:
                words.append(tok.surface)
        return words
    except Exception:
        return None


_JANOME = None  # 遅延初期化用キャッシュ


def _tokenize_title(title: str) -> List[str]:
    """タイトルから「売れるワード候補」を抽出する。

    形態素解析(janome)が使えればそれを優先。無ければ日本語向けの簡易抽出:
    - 英数字の語(ChatGPT 等)とカタカナ語(ブログ 等)はそのまま1語に
    - 漢字/ひらがなの連続からは 2〜3 文字の n-gram を生成して頻出句を拾う
    日本語はスペースで区切られないため、単純な空白分割では機能しないので
    この方式を採用しています。
    """
    janome_words = _try_janome(title)
    if janome_words is not None:
        return [w for w in janome_words if w.lower() not in STOPWORDS]

    tokens: List[str] = []
    # 英数字語・カタカナ語
    for m in ALNUM_RE.findall(title):
        if len(m) >= 2 and m.lower() not in STOPWORDS:
            tokens.append(m)
    for m in KATAKANA_RE.findall(title):
        if m not in STOPWORDS:
            tokens.append(m)
    # 漢字・ひらがな連続 -> n-gram
    for run in JP_RUN_RE.findall(title):
        for n in (3, 2):
            for i in range(len(run) - n + 1):
                gram = run[i:i + n]
                if gram not in STOPWORDS:
                    tokens.append(gram)
    return tokens


def analyze(items: List[NoteItem], top_n: int, min_like: int) -> dict:
    """記事リストから傾向レポート用のデータ(dict)を作る。"""
    # ノイズ除去
    filtered = [it for it in items if it.like_count >= min_like]
    paid = [it for it in filtered if it.is_paid]
    free = [it for it in filtered if not it.is_paid]

    # 売れ筋ランキング: 有料記事をスキ数順、同数なら価格順
    paid_ranked = sorted(paid, key=lambda x: (x.like_count, x.price), reverse=True)
    # 人気記事(無料含む)ランキング: タイトル傾向の参考
    all_ranked = sorted(filtered, key=lambda x: x.like_count, reverse=True)

    # 価格帯分布
    prices = [it.price for it in paid if it.price > 0]
    price_buckets = Counter()
    for p in prices:
        if p <= 300:
            price_buckets["¥1〜300"] += 1
        elif p <= 500:
            price_buckets["¥301〜500"] += 1
        elif p <= 1000:
            price_buckets["¥501〜1000"] += 1
        elif p <= 3000:
            price_buckets["¥1001〜3000"] += 1
        else:
            price_buckets["¥3001〜"] += 1

    # タイトル頻出ワード(人気記事から)
    word_counter = Counter()
    for it in all_ranked[: max(top_n, 50)]:
        # 同一タイトル内の重複は1回として数える(n-gram の二重計上を防ぐ)
        word_counter.update(set(_tokenize_title(it.title)))
    # 2回以上出現したワードのみ(ノイズ除去)。無ければ上位をそのまま。
    repeated = [(w, c) for w, c in word_counter.most_common(60) if c >= 2]
    top_words = (repeated or word_counter.most_common(25))[:25]

    # タイトルの型の傾向
    titles = [it.title for it in all_ranked[: max(top_n, 50)]] or [it.title for it in filtered]
    n_titles = len(titles) or 1
    num_ratio = sum(1 for t in titles if NUM_RE.search(t)) / n_titles
    bracket_ratio = sum(1 for t in titles if BRACKET_RE.search(t)) / n_titles
    avg_title_len = sum(len(t) for t in titles) / n_titles

    return {
        "total_collected": len(items),
        "analyzed": len(filtered),
        "paid_count": len(paid),
        "free_count": len(free),
        "paid_ranked": paid_ranked[:top_n],
        "all_ranked": all_ranked[:top_n],
        "price_stats": {
            "count": len(prices),
            "min": min(prices) if prices else 0,
            "median": int(median(prices)) if prices else 0,
            "max": max(prices) if prices else 0,
            "buckets": dict(price_buckets),
        },
        "top_words": top_words,
        "title_patterns": {
            "num_ratio": round(num_ratio, 2),
            "bracket_ratio": round(bracket_ratio, 2),
            "avg_len": round(avg_title_len, 1),
        },
    }
