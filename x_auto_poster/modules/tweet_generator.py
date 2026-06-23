"""テーマから X の投稿文(本文 + ハッシュタグ)を生成する。

ANTHROPIC_API_KEY が設定されていれば Claude API で生成し、
未設定または失敗時はテンプレート生成にフォールバックする。
"""

import json

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
#   "text": str,         # 投稿本文(ハッシュタグは含めない)
#   "hashtags": [str],   # "#ジャグラー" のような形式
# }
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "hashtags"],
    "additionalProperties": False,
}

PROMPT_TEMPLATE = """\
あなたは「{persona}」の中の人です。
次のテーマで X(旧Twitter)に投稿する文章を1つ作ってください。

テーマ: {topic}

条件:
- text: 投稿本文。全角{max_chars}文字以内。ハッシュタグは text には含めない。
  1行目に思わず読みたくなるフックを置き、読みやすいよう適度に改行する。
  煽りすぎず、フォロワーに語りかける自然な口調にする。
- hashtags: "#ジャグラー" の形式で3〜5個。テーマに関連するものにする。
- 断定や結果の保証はしない。あくまで予想・考察・情報共有の表現にする。
- 絵文字は1〜3個まで、入れすぎない。
"""


def _call_claude(prompt: str, schema: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude API がリクエストを拒否しました")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def _generate_with_claude(topic: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        persona=config.POST_PERSONA,
        topic=topic,
        max_chars=config.MAX_TWEET_CHARS,
    )
    return _call_claude(prompt, OUTPUT_SCHEMA)


def _generate_template(topic: str) -> dict:
    """API が無い / 失敗したときの簡易テンプレート。"""
    text = (
        f"【今日のひとこと】\n{topic}\n"
        "気になる方はぜひチェックしてみてください👀\n"
        "※あくまで予想・考察です。"
    )
    return {"text": text, "hashtags": ["#ジャグラー", "#スロット", "#パチスロ"]}


def _compose(parts: dict) -> str:
    """本文 + ハッシュタグを1つの投稿文に組み立て、文字数上限に収める。"""
    text = (parts.get("text") or "").strip()
    tags = [t.strip() for t in parts.get("hashtags", []) if t.strip()]
    tag_line = " ".join(t if t.startswith("#") else f"#{t}" for t in tags)

    # X は全角を2文字としてカウントするため、ここでは「全角換算の上限」を
    # config.MAX_TWEET_CHARS とみなして本文を安全に切り詰める。
    limit = config.MAX_TWEET_CHARS
    reserve = len(tag_line) + 2 if tag_line else 0
    body_limit = max(10, limit - reserve)
    if len(text) > body_limit:
        text = text[: body_limit - 1].rstrip() + "…"

    return f"{text}\n\n{tag_line}".strip() if tag_line else text


def generate_post(topic: str) -> str:
    """テーマから投稿文(完成形の文字列)を返す。"""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("テーマが空です")

    if config.ANTHROPIC_API_KEY:
        try:
            parts = _generate_with_claude(topic)
            _log().info("Claude API で投稿文を生成しました: %s", topic)
            return _compose(parts)
        except Exception as e:  # noqa: BLE001
            log_error(f"Claude API での生成に失敗。テンプレートに切替: {e}")
    else:
        _log().info("ANTHROPIC_API_KEY 未設定のためテンプレートで生成します")

    return _compose(_generate_template(topic))
