"""テーマから タイトル / 台本 / 説明文 / ハッシュタグ を生成する。

ANTHROPIC_API_KEY が設定されていれば Claude API で生成し、
未設定または失敗時はテンプレート生成にフォールバックする。
"""

import json
import re

import config
from modules.logger import get_logger, log_error

logger_ = None


def _log():
    global logger_
    if logger_ is None:
        logger_ = get_logger()
    return logger_


# 生成結果のスキーマ:
# {
#   "title": str,            # 動画タイトル (100文字以内)
#   "script_lines": [str],   # ナレーション兼テロップ。1行 = 1テロップ
#   "description": str,      # YouTube 説明文
#   "hashtags": [str],       # "#ジャグラー" のような形式
# }

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "script_lines": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "script_lines", "description", "hashtags"],
    "additionalProperties": False,
}

PROMPT_TEMPLATE = """\
あなたはパチスロ・ジャグラー予想系YouTube Shortsの放送作家です。
次のテーマで30〜60秒の縦型ショート動画の台本を作ってください。

テーマ: {topic}

条件:
- title: 思わずタップしたくなる日本語タイトル。50文字以内。
- script_lines: ナレーション原稿。1要素 = 画面に出すテロップ1枚(20文字前後)。
  合計8〜14行。冒頭1行目は強いフック、最後はチャンネル登録を促す一言。
  読み上げ合計が30〜60秒(およそ200〜350文字)に収まること。
- description: YouTube説明文。テーマの要約 + 「※本動画は予想・考察であり、結果を保証するものではありません。」という免責を含める。
- hashtags: "#ジャグラー" のような形式で5〜8個。#Shorts を必ず含める。

注意: 店名・台番号などはテーマに含まれる範囲で扱い、断定ではなく予想・考察の表現を使うこと。
"""


def _generate_with_claude(topic: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(topic=topic)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude API がリクエストを拒否しました")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def _generate_with_template(topic: str) -> dict:
    """APIなしで動くテンプレート台本。"""
    short_topic = topic if len(topic) <= 40 else topic[:40] + "…"
    title = f"【ジャグラー予想】{short_topic}"[:100]
    script_lines = [
        f"今日のテーマは「{topic}」",
        "結論から言います",
        "狙うならこの条件です",
        "ポイント1 過去の出玉傾向をチェック",
        "ポイント2 末尾と角台の扱いに注目",
        "ポイント3 イベント日の翌日は据え置きに警戒",
        "高設定の可能性がある台は朝一の挙動で見極め",
        "ただしこれはあくまで予想です",
        "無理な深追いは禁物",
        "参考になったらチャンネル登録お願いします",
    ]
    description = (
        f"{topic} についてのショート解説です。\n"
        "狙い台の考え方・立ち回りのポイントをまとめました。\n\n"
        "※本動画は予想・考察であり、結果を保証するものではありません。\n"
        "※パチンコ・パチスロは適度に楽しみましょう。"
    )
    hashtags = ["#Shorts", "#ジャグラー", "#パチスロ", "#スロット", "#狙い台", "#設定判別"]
    return {
        "title": title,
        "script_lines": script_lines,
        "description": description,
        "hashtags": hashtags,
    }


def _validate(content: dict, topic: str) -> dict:
    """生成結果を整形・検証する。"""
    title = str(content.get("title") or "").strip() or f"【予想】{topic}"
    title = title[:100]

    lines = [str(l).strip() for l in (content.get("script_lines") or []) if str(l).strip()]
    if not lines:
        raise ValueError("script_lines が空です")

    description = str(content.get("description") or "").strip()
    if "保証するものではありません" not in description:
        description += "\n\n※本動画は予想・考察であり、結果を保証するものではありません。"

    hashtags = []
    for tag in content.get("hashtags") or []:
        tag = str(tag).strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        hashtags.append(tag)
    if "#Shorts" not in hashtags:
        hashtags.insert(0, "#Shorts")

    # 説明文の末尾にハッシュタグを付ける
    description = description + "\n\n" + " ".join(hashtags)

    # YouTube の tags は # なしの文字列リスト
    tags = [re.sub(r"^#", "", t) for t in hashtags]

    return {
        "topic": topic,
        "title": title,
        "script_lines": lines,
        "description": description,
        "hashtags": hashtags,
        "tags": tags,
    }


def generate(topic: str) -> dict:
    """テーマから台本一式を生成して dict で返す。"""
    if config.ANTHROPIC_API_KEY:
        try:
            _log().info("Claude API (%s) で台本を生成します", config.CLAUDE_MODEL)
            return _validate(_generate_with_claude(topic), topic)
        except Exception as e:  # API失敗時はテンプレートで継続
            log_error(f"Claude API での台本生成に失敗。テンプレートで継続します: {e}")
    else:
        _log().info("ANTHROPIC_API_KEY 未設定のためテンプレートで台本を生成します")
    return _validate(_generate_with_template(topic), topic)


def save_script(content: dict, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)


def load_script(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
