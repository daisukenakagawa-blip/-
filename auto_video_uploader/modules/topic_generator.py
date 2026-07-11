"""ネタ切れ防止の自動テーマ生成。

topics.csv / スプレッドシートに pending が無いときに、次に投稿するテーマを
自動で 1 件作る(完全放置運用のための機能)。

- ANTHROPIC_API_KEY があれば Claude API で新しいテーマを生成
  (過去に投稿したテーマ一覧を渡して重複を避ける)
- キーが無い・API失敗時は内蔵のネタ帳からまだ使っていないものを選ぶ
- ネタ帳も使い切ったら「【7月版】」のように月を付けて再利用する
"""

from datetime import date

import config
from modules.logger import get_logger, log_error

# CONTENT_STYLE=monologue (ジャグラーマンの一人語り) 前提のネタ帳。
# 実体験・オカルト・あるある系で、データが無くても台本にできるテーマのみ。
TOPIC_POOL = [
    "ジャグラーで一番ダメな台選びの話",
    "朝一のジャグラーで見るべきポイント",
    "ジャグラーのやめどきがわからない件",
    "隣の台がペカり続けた日の話",
    "ジャグラーで勝てる人と勝てない人の差",
    "閉店前のジャグラーは打つべきか",
    "ジャグラーの回転数は見るだけ損なのか",
    "ペカる直前に手が止まる現象",
    "ジャグラーで財布が空になる人の共通点",
    "低設定を高設定と思い込む瞬間",
    "ジャグラーの島で感じる謎の空気",
    "REGばかり引く日の正しい過ごし方",
    "ジャグラーをやめられない本当の理由",
    "設定6を捨てた日の話",
    "ジャグラーで隣に座ってほしくない人",
    "ガックンチェックは信じていいのか",
    "ジャグラー連チャンの正体を考える",
    "推し台ができてしまう心理",
    "ジャグラーで一番悔しい瞬間",
    "常連がこっそりやっている台選び",
    "ジャグラーのBGMが頭から離れない件",
    "沖ドキからジャグラーに戻ってきた理由",
    "ジャグラーで検証したいオカルトTOP3",
    "先ペカと後ペカどっちが嬉しいか問題",
    "ジャグラーの空き台に走る人々",
    "1000ハマりの台に座る勇気",
    "ジャグラーで勝った金の使い道あるある",
    "台パンしたくなる瞬間ランキング",
    "ジャグラーの設定判別は何回転から?",
    "並び席で友達がペカらせたときの顔",
]


TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
    "additionalProperties": False,
}

TOPIC_PROMPT = """あなたはパチスロ「ジャグラー」専門の YouTube Shorts チャンネルの企画担当です。
チャンネルの投稿キャラは「ジャグラーマン」(実体験ベースの一人語り・オカルト検証・あるある系)。

次に投稿する動画のテーマを1つだけ考えてください。

条件:
- 20文字前後の短いタイトル(Shorts 向け)
- 実体験・オカルト・あるある・検証ネタ(店名や実データが必要なネタは禁止)
- 視聴者がコメントしたくなる問いかけ・共感を含む切り口
- 以下の「過去に使ったテーマ」と内容が被らないこと

過去に使ったテーマ:
{used}
"""


def _normalize(topic: str) -> str:
    return "".join((topic or "").split()).lower()


def _generate_with_claude(used_topics: list) -> str:
    from modules.script_generator import _call_claude

    used = "\n".join(f"- {t}" for t in used_topics[-50:]) or "(なし)"
    result = _call_claude(TOPIC_PROMPT.format(used=used), TOPIC_SCHEMA)
    topic = (result.get("topic") or "").strip()
    if not topic:
        raise ValueError("Claude API が空のテーマを返しました")
    return topic


def _pick_from_pool(used_topics: list) -> str:
    used = {_normalize(t) for t in used_topics}
    for topic in TOPIC_POOL:
        if _normalize(topic) not in used:
            return topic
    # ネタ帳を使い切ったら月を付けて再利用 (重複投稿防止と両立させる)
    month = date.today().month
    for topic in TOPIC_POOL:
        candidate = f"【{month}月版】{topic}"
        if _normalize(candidate) not in used:
            return candidate
    # 同じ月に2周した場合の最終手段
    return f"【{date.today():%m月%d日}】{TOPIC_POOL[0]}"


def generate_topic(used_topics: list) -> str:
    """新しいテーマを1件返す。used_topics は過去に使ったテーマ名のリスト。"""
    logger = get_logger()
    if config.ANTHROPIC_API_KEY:
        try:
            topic = _generate_with_claude(used_topics)
            # AI が過去テーマと同じものを返した場合はネタ帳にフォールバック
            if _normalize(topic) not in {_normalize(t) for t in used_topics}:
                logger.info("Claude API で新テーマを自動生成しました: %s", topic)
                return topic
            logger.warning("AI生成テーマが過去と重複したためネタ帳から選びます: %s", topic)
        except Exception as e:
            log_error(f"テーマの AI 生成に失敗。内蔵ネタ帳から選びます: {e}")
    topic = _pick_from_pool(used_topics)
    logger.info("内蔵ネタ帳からテーマを選びました: %s", topic)
    return topic
