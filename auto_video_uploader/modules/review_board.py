"""完成前レビュー会議。

4人のレビュアー(ジャグラー上級者 / ショート動画専門家 /
YouTubeアルゴリズム分析担当 / ジャグラーマン本人)が台本を採点する。
全員が合格 (REVIEW_PASS_SCORE 以上) のときだけ「最後まで見てしまう」と判定する。

API なしのヒューリスティック採点。各レビュアー5点満点。
"""

import re

import config

_PROB_RE = re.compile(r"\d+\s*[/／]\s*\d+")
_RANK_RE = re.compile(r"第[0-9一二三]位|ランキング|TOP\s?\d")
# 仮説・問い・断言など「引き」のある語(発注書のフック例に合わせて広め)
_QUESTION_RE = re.compile(
    r"[?？]|ない\?|よな|ません|ほぼ|と思わ|どう思|本当|なぜ|なのか|疑問|断言|"
    r"実は|気づ|逆|闇|ヤバ|9割|知らな|負け|勝て|嘘|間違|やりがち|大事|だけ"
)
_COMMENT_RE = re.compile(r"コメント|どう思|賛成|反対|あなたは|教えて|派\?")
_EMPATHY_RE = re.compile(
    r"分かる|あるある|経験|やった事|思った事|魔力|抜けられ|共感|やりがち|"
    r"俺|思わない|よな|座れ|やってしまう|気持ち"
)


def _all_lines(content: dict) -> list:
    return content.get("script_lines") or []


def _hook(content: dict) -> str:
    segs = content.get("segments") or []
    if segs:
        return " ".join(segs[0].get("lines") or [])
    lines = _all_lines(content)
    return lines[0] if lines else ""


def review_expert(content: dict) -> tuple:
    """ジャグラー上級者: 仮説・検証があり、データ羅列でないか。"""
    text = " ".join(_all_lines(content))
    score, notes = 5, []
    if _RANK_RE.search(text) or _RANK_RE.search(content.get("title", "")):
        score -= 3
        notes.append("ランキング要素が残っている")
    prob_hits = len(_PROB_RE.findall(text))
    if prob_hits:
        score -= min(3, prob_hits)
        notes.append(f"生の確率がテロップに出ている ({prob_hits}箇所)。意味に翻訳を")
    if not _QUESTION_RE.search(text):
        score -= 1
        notes.append("仮説・問いかけの要素が弱い")
    return max(0, score), notes


def review_shorts(content: dict) -> tuple:
    """ショート動画専門家: フックの強さ・テロップの短さ。"""
    score, notes = 5, []
    hook = _hook(content)
    if len(hook) > 15:
        score -= 2
        notes.append(f"フックが長い ({len(hook)}文字>15)。3秒で刺さらない")
    if not _QUESTION_RE.search(hook):
        score -= 2
        notes.append("フックが『え?』と思わせる引きになっていない")
    long_lines = [l for l in _all_lines(content) if len(l) > 15]
    if long_lines:
        score -= min(2, len(long_lines))
        notes.append(f"15文字超のテロップが{len(long_lines)}行ある")
    return max(0, score), notes


def review_algorithm(content: dict) -> tuple:
    """YouTubeアルゴリズム分析担当: コメント誘導・維持率(展開数)。"""
    score, notes = 5, []
    segs = content.get("segments") or []
    text = " ".join(_all_lines(content))
    last = " ".join(segs[-1].get("lines") or []) if segs else text
    if not _COMMENT_RE.search(last):
        score -= 2
        notes.append("最後にコメント誘導が無い (コメント率が伸びない)")
    if len(segs) < 5:
        score -= 1
        notes.append("展開が少なく中だるみしやすい (6展開推奨)")
    total_chars = sum(len(l) for l in _all_lines(content))
    if total_chars < 80:
        score -= 1
        notes.append("内容が薄く保存・維持につながりにくい")
    return max(0, score), notes


def review_jugglerman(content: dict) -> tuple:
    """ジャグラーマン本人: キャラの一人称・議論トーンか。"""
    score, notes = 5, []
    text = " ".join(_all_lines(content))
    if not _EMPATHY_RE.search(text) and not _QUESTION_RE.search(text):
        score -= 2
        notes.append("解説調で、ジャグラーマンの語り(共感・問い)になっていない")
    if _PROB_RE.search(text) or _RANK_RE.search(text):
        score -= 2
        notes.append("キャラが台無し。数字読み上げ・ランキングはやらない")
    if not _COMMENT_RE.search(text):
        score -= 1
        notes.append("視聴者に議論をふっていない")
    return max(0, score), notes


REVIEWERS = [
    ("ジャグラー上級者", review_expert),
    ("ショート動画専門家", review_shorts),
    ("アルゴリズム分析", review_algorithm),
    ("ジャグラーマン本人", review_jugglerman),
]


def review(content: dict) -> tuple:
    """レビュー会議を実施。戻り値: (全員合格か, 合計説明文字列, 指摘リスト)。"""
    passed = True
    parts = []
    all_notes = []
    for name, fn in REVIEWERS:
        score, notes = fn(content)
        ok = score >= config.REVIEW_PASS_SCORE
        passed = passed and ok
        parts.append(f"{name}:{score}/5{'' if ok else '✗'}")
        for n in notes:
            all_notes.append(f"[{name}] {n}")
    return passed, " ".join(parts), all_notes
