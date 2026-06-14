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

# ---------------------------------------------------------------------------
# ランキング構成 (YouTube Shorts 向け)
#   0-2秒: フック / 3-8秒: 第3位 / 9-15秒: 第2位 / 16-25秒: 第1位 /
#   26-35秒: 注意台 / 36-45秒: まとめ
# ---------------------------------------------------------------------------

RANKING_ROLES = ["hook", "rank3", "rank2", "rank1", "caution", "summary"]

RANKING_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "thumb_text": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["hook", "rank3", "rank2", "rank1", "caution", "summary"],
                    },
                    "lines": {"type": "array", "items": {"type": "string"}},
                    "machine_no": {"type": "string"},
                    "big": {"type": "string"},
                    "reg": {"type": "string"},
                    "total": {"type": "string"},
                    "diff": {"type": "string"},
                    "verdict": {
                        "type": "string",
                        "enum": ["本命", "対抗", "見送り", "注意", ""],
                    },
                },
                "required": ["role", "lines", "machine_no", "big", "reg", "total", "diff", "verdict"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "thumb_text", "segments", "description", "hashtags"],
    "additionalProperties": False,
}

RANKING_PROMPT = """\
あなたは登録者10万人超えのパチスロ専門YouTubeショート動画クリエイターです。
次のテーマで、ランキング構成の縦型ショート動画(40〜45秒)の台本を作ってください。

テーマ: {topic}

【コンテンツポリシー(最優先で厳守)】
- 店舗依存コンテンツ禁止: 末尾・ゾロ目・特定日・地域イベント・店名は一切使わない
- 全国のジャグラーユーザーが楽しめる内容にする
- ジャンル優先順位: 1位 ジャグラーあるある / 2位 ジャグラー知識 /
  3位 ジャグラーマン診断 / 4位 クイズ / 5位 高設定の特徴
- 全体を「問題提起 → 理由 → 結論」の流れで構成する
  (hook=問題提起、rank3〜caution=理由・中身、summary=結論)
- データを並べるだけの内容は禁止。各セグメントに視聴者が
  「知らなかった」「なるほど」「そうだったのか」と思う一言を必ず入れる

動画構成(この順で segments を6個作る):
1. role=hook    (約3秒)  強烈な問題提起1行。14文字以内。
   例:「9割が勘違いしてる真実」「知らないと損する3選」「高設定ほど◯◯が出る!?」
2. role=rank3   (約6秒)  第3位。lines は2〜3行
3. role=rank2   (約7秒)  第2位。lines は2〜3行
4. role=rank1   (約9秒)  第1位。lines は3〜4行。一番熱く語る
5. role=caution (約9秒)  注意点・例外・ひっかけ。lines は2〜3行
6. role=summary (約9秒)  結論 + コメント誘導。lines は2〜3行。
   最後の1行は必ず「あなたはどう思う?コメントで」「共感したらコメントで」等の
   コメント誘導にすること(チャンネル登録のお願いではなくコメント誘導)

各 lines の条件(テロップ最適化・TikTokトップクリエイター水準):
- 1行 = 13文字以内。短く・大きく・数字中心に
- 「REG 1/240」「合算 1/114.6」のような数字を積極的に入れる
- 公表値を使う場合は小数第1位まで正確に (例 1/114.6。勝手に丸めない)

rank3/rank2/rank1/caution の台データは、テーマが設定狙い・台選び系のときのみ入れる
(あるある・診断・クイズ系では無理に数値を入れず、自然な場合だけ知識として使う):
- machine_no: 台番の予想 (例 "1038番台")
- big: BIG確率 (例 "1/230")
- reg: REG確率 (例 "1/240")
- total: 合算確率。**必ず 1/(1/BIG + 1/REG) を計算して一致させること** (例 BIG 1/230, REG 1/240 → 合算 1/117)
- diff: 想定差枚数 (例 "+2800枚" / "-1500枚")。高設定想定はプラス、低設定想定はマイナスにして判定と矛盾させない
- verdict: rank1=本命, rank2=対抗, rank3=対抗, caution=見送り
数値はジャグラー実機の設定別スペックとして現実的な範囲にすること
(BIG 1/210〜1/300, REG 1/230〜1/450, 合算 1/105〜1/180)。
hook と summary は machine_no/big/reg/total/diff/verdict をすべて空文字にする。

その他:
- title: タップしたくなるタイトル。数字を含める。28文字以内
- thumb_text: サムネイル用の感情ワード。10文字以内・超強い言葉
  (例「実は危険」「知らないと損」「設定6の癖」「9割が誤解」)
- description: 要約 + 「※本動画は予想・考察であり、結果を保証するものではありません。」を含める
- hashtags: #Shorts を必ず含む5〜8個
- 断定ではなく予想・考察の表現を使うこと
"""


def _call_claude(prompt: str, schema: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude API がリクエストを拒否しました")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def _generate_with_claude(topic: str) -> dict:
    return _call_claude(PROMPT_TEMPLATE.format(topic=topic), OUTPUT_SCHEMA)


def _generate_ranking_with_claude(topic: str, feedback: str = "") -> dict:
    from modules.juggler_knowledge import spec_prompt

    prompt = RANKING_PROMPT.format(topic=topic) + spec_prompt()
    if feedback:
        prompt += f"\n前回生成した台本の品質チェックで以下の課題が出ました。必ず改善してください:\n{feedback}\n"
    return _call_claude(prompt, RANKING_SCHEMA)


def _generate_ranking_template(topic: str) -> dict:
    """APIなしで動くランキング構成のテンプレート台本。"""
    short = topic if len(topic) <= 18 else topic[:14] + "…"
    return {
        "title": f"狙い台TOP3!{short}"[:28],
        "segments": [
            {"role": "hook", "lines": [f"狙い台TOP3発表!"],
             "machine_no": "", "big": "", "reg": "", "total": "", "diff": "", "verdict": ""},
            {"role": "rank3", "lines": ["第3位は角台", "出玉の波に注目"],
             "machine_no": "REG先行の台", "big": "1/258", "reg": "1/270",
             "total": "1/132", "diff": "+900枚", "verdict": "対抗"},
            {"role": "rank2", "lines": ["第2位はぶどう良好台", "前日高設定の可能性"],
             "machine_no": "ぶどう良好台", "big": "1/244", "reg": "1/250",
             "total": "1/123", "diff": "+1500枚", "verdict": "対抗"},
            {"role": "rank1", "lines": ["第1位はこれ", "REGが強い台", "朝一から狙う価値あり"],
             "machine_no": "角2の台", "big": "1/226", "reg": "1/230",
             "total": "1/114", "diff": "+2800枚", "verdict": "本命"},
            {"role": "caution", "lines": ["逆に危険な台", "前日大量出玉は", "リセット警戒"],
             "machine_no": "前日万枚の台", "big": "1/272", "reg": "1/388",
             "total": "1/160", "diff": "-2100枚", "verdict": "見送り"},
            {"role": "summary", "lines": ["あくまで予想です", "無理は禁物",
                                          "あなたの狙い目もコメントで!"],
             "machine_no": "", "big": "", "reg": "", "total": "", "diff": "", "verdict": ""},
        ],
        "thumb_text": "狙い台TOP3",
        "description": (
            f"{topic} の狙い台をランキング形式で紹介。\n\n"
            "※本動画は予想・考察であり、結果を保証するものではありません。"
        ),
        "hashtags": ["#Shorts", "#ジャグラー", "#パチスロ", "#狙い台", "#設定狙い"],
    }


def _validate_ranking(content: dict, topic: str) -> dict:
    """ランキング台本を整形・検証する。"""
    base = _validate(
        {
            "title": content.get("title"),
            "script_lines": ["dummy"],  # 後で差し替える
            "description": content.get("description"),
            "hashtags": content.get("hashtags"),
        },
        topic,
    )

    segments = []
    by_role = {s.get("role"): s for s in content.get("segments") or []}
    for role in RANKING_ROLES:
        seg = by_role.get(role)
        if not seg:
            continue
        lines = []
        for raw in seg.get("lines") or []:
            raw = str(raw).strip()
            if raw:
                lines.extend(_chunk_by_touten(raw, 13))
        if not lines:
            continue
        if role == "hook":
            lines = lines[:1]  # フックは1行・約2秒
        segments.append(
            {
                "role": role,
                "lines": lines,
                "machine_no": str(seg.get("machine_no") or "").strip(),
                "big": str(seg.get("big") or "").strip(),
                "reg": str(seg.get("reg") or "").strip(),
                "total": str(seg.get("total") or "").strip(),
                "diff": str(seg.get("diff") or "").strip(),
                "verdict": str(seg.get("verdict") or "").strip(),
            }
        )
    if len(segments) < 3:
        raise ValueError("ランキング構成のセグメントが不足しています")

    base["format"] = "ranking"
    base["segments"] = segments
    base["script_lines"] = [l for s in segments for l in s["lines"]]
    base["thumb_text"] = str(content.get("thumb_text") or "").strip()[:10]
    return base


# ---------------------------------------------------------------------------
# モノローグ型 (ジャグラーマン): 都市伝説・あるある・検証を語るキャラクター動画
#   ランキング/データカード禁止。3秒で強い疑問 → 仮説 → 検証 → 意外な事実 →
#   視聴者に問う → 結論。数字は「意味」で見せる(生の確率は出さない)。
# ---------------------------------------------------------------------------

MONOLOGUE_ROLES = ["hook", "setup", "build", "twist", "challenge", "conclusion"]

MONOLOGUE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "thumb_text": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["hook", "setup", "build", "twist", "challenge", "conclusion"],
                    },
                    "lines": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["role", "lines"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "thumb_text", "segments", "description", "hashtags"],
    "additionalProperties": False,
}

MONOLOGUE_PROMPT = """\
あなたは登録者50万人超えのパチスロ系YouTubeショート専門クリエイターです。
「ジャグラーマン」というキャラクターになりきって台本を書きます。

ジャグラーマンとは:
ジャグラー界の都市伝説や疑問を追求するキャラクター。
情報を読み上げる解説者ではない。仮説を立て、疑問を投げ、検証し、視聴者と議論する。

テーマ: {topic}

最優先事項: 情報量ではなく「視聴維持率・コメント率・保存率」を最大化すること。
視聴者が「だから何?」と思う動画は失敗。
視聴者が「知らなかった」「共感した」「反論したくなった」「試したくなった」と思う内容にする。

【絶対禁止】
- 第1位/第2位/第3位 などのランキング形式
- 回転数・合算・BIG確率・REG確率などのデータを並べるだけの構成
- スペック紹介、メーカーサイトのコピペ、数字の羅列

【数字は意味で見せる(超重要)】
- ✖「合算1/118.7」→ ○「高設定級の合算」
- ✖「REG1/240」→ ○「REGが異常に強い」
- 生の確率や台番は書かない。意味・体感・結論を言葉で伝える

【構成(segmentsを6個、この順で)】
1. role=hook       (約3秒) 最初の3秒で強烈な疑問。1行・14文字以内。
   例「高設定だけ先ペカ多くない?」「実はREGより大事な数字がある」
     「ジャグラーの闇に気づいた」「これやる人ほぼ負けます」「設定6でも普通に負ける」
   視聴者が『え?』と思う一文から始める
2. role=setup      (約7秒) 疑問の背景・あるある。共感を作る。lines 2〜3行
3. role=build      (約9秒) 仮説を立てる。「俺はこう思う」と語る。lines 2〜3行
4. role=twist      (約9秒) 意外な事実・ありがちな勘違いを暴く。「実は逆」。lines 2〜3行
5. role=challenge  (約8秒) 視聴者に問いを投げ、反論・議論を誘発。lines 2〜3行
6. role=conclusion (約8秒) 言い切りの結論 + コメント誘導。lines 2〜3行。
   最後の1行は必ず「あなたはどう思う?コメントで」「賛成?反対?コメントで」等

【テロップ条件】
- 1行15文字以内。1画面は最大2行のイメージで短く
- スマホ最優先。重要語は強い言葉で
- ジャグラーマンの一人称・話し言葉で(「〜だよな」「〜と思わない?」「断言する」)

その他:
- title: タップせずにいられないタイトル。28文字以内
- thumb_text: サムネ用の感情ワード。10文字以内・超強い言葉(例「実は逆」「9割が誤解」「闇」)
- description: 要約 + 「※本動画は予想・考察であり、結果を保証するものではありません。」を含める
- hashtags: #Shorts を必ず含む5〜8個
"""


def _generate_monologue_with_claude(topic: str, feedback: str = "") -> dict:
    from modules.juggler_knowledge import spec_prompt

    prompt = MONOLOGUE_PROMPT.format(topic=topic) + spec_prompt()
    prompt += (
        "\n(スペック表は背景知識として正確さの担保にのみ使い、"
        "テロップには生の数字を出さず『意味』に翻訳すること)\n"
    )
    if feedback:
        prompt += f"\nレビュー会議で以下の指摘が出ました。必ず直してください:\n{feedback}\n"
    return _call_claude(prompt, MONOLOGUE_SCHEMA)


# テーマ優先順位ごとのテンプレート(APIなしでも動く・ジャグラーマン voice)
_MONOLOGUE_TEMPLATES = {
    "urban": {  # 都市伝説
        "title": "ジャグラーの先ペカ伝説は本当か",
        "thumb_text": "先ペカの闇",
        "segments": [
            ("hook", ["高設定だけ先ペカ多くない?"]),
            ("setup", ["打ってる時こう思った事ない?", "「今日、先ペカ多いな」って", "勝ってる日ほどそう感じる"]),
            ("build", ["俺の仮説はこうだ", "高設定は当たりが軽いから", "結果的に先ペカも増えて見える"]),
            ("twist", ["でも実はここがミソ", "先告知の割合に設定差はない", "増えてるのは当たりの数なんだ"]),
            ("challenge", ["つまり先ペカ自体は無関係", "でも体感は嘘じゃない", "あなたはどっち派?"]),
            ("conclusion", ["先ペカは原因じゃなく結果だ", "それでもロマンは消えない", "賛成?反対?コメントで!"]),
        ],
        "hashtags": ["#Shorts", "#ジャグラー", "#都市伝説", "#先ペカ", "#オカルト"],
    },
    "aruaru": {  # あるある
        "title": "ジャグラーマンにしか分からない事",
        "thumb_text": "9割が共感",
        "segments": [
            ("hook", ["これ分かる人、相当ジャグ廃だ"]),
            ("setup", ["隣がペカった瞬間", "自分の台が急に重く感じる", "あの現象に名前を付けたい"]),
            ("build", ["でも冷静に考えてくれ", "抽選は毎ゲーム独立してる", "隣は1ミリも関係ない"]),
            ("twist", ["なのに席を立てない", "「次こそ来る」と思ってしまう", "これがジャグラーの魔力だ"]),
            ("challenge", ["分かってても抜けられない", "あなたにも経験あるよな?", "一番ヤバい瞬間は?"]),
            ("conclusion", ["共感したら立派なジャグラーマン", "今日も一緒にペカろう", "あなたのあるあるをコメントで!"]),
        ],
        "hashtags": ["#Shorts", "#ジャグラー", "#あるある", "#ジャグラーマン", "#共感"],
    },
    "begginer": {  # 初心者の勘違い
        "title": "初心者がやりがちな勘違い",
        "thumb_text": "9割が誤解",
        "segments": [
            ("hook", ["それ、ほぼ負ける打ち方です"]),
            ("setup", ["ハマってる台を見つけて", "「そろそろ来る」で座る", "やった事ある人、多いはず"]),
            ("build", ["気持ちは痛いほど分かる", "でもジャグラーに天井はない", "1000ハマりも次は同じ確率"]),
            ("twist", ["見るべきは過去じゃない", "REGが強いかどうか、それだけ", "そこに設定の本音が出る"]),
            ("challenge", ["ハマり狙いは卒業しよう", "でも夢を見たい日もある", "あなたは狙う?狙わない?"]),
            ("conclusion", ["過去のハマりは反発しない", "確率は冷たいけど正直だ", "あなたの意見をコメントで!"]),
        ],
        "hashtags": ["#Shorts", "#ジャグラー", "#初心者", "#立ち回り", "#勘違い"],
    },
}


def _pick_monologue_template(topic: str) -> dict:
    t = topic
    if any(k in t for k in ("初心者", "勘違い", "やりがち", "ハマり", "天井")):
        key = "begginer"
    elif any(k in t for k in ("あるある", "共感", "ジャグラーマン", "わかる")):
        key = "aruaru"
    else:
        key = "urban"
    tpl = _MONOLOGUE_TEMPLATES[key]
    return {
        "title": tpl["title"],
        "thumb_text": tpl["thumb_text"],
        "segments": [{"role": r, "lines": list(ls)} for r, ls in tpl["segments"]],
        "description": (
            f"{topic} をジャグラーマンが本気で考えてみた。\n\n"
            "※本動画は予想・考察であり、結果を保証するものではありません。"
        ),
        "hashtags": tpl["hashtags"],
    }


_PROB_RE = re.compile(r"\d+\s*[/／]\s*\d+")


def _validate_monologue(content: dict, topic: str) -> dict:
    """モノローグ台本を整形・検証する。生の確率はテロップから除外する。"""
    base = _validate(
        {
            "title": content.get("title"),
            "script_lines": ["dummy"],
            "description": content.get("description"),
            "hashtags": content.get("hashtags"),
        },
        topic,
    )

    segments = []
    by_role = {s.get("role"): s for s in content.get("segments") or []}
    for role in MONOLOGUE_ROLES:
        seg = by_role.get(role)
        if not seg:
            continue
        lines = []
        for raw in seg.get("lines") or []:
            raw = str(raw).strip()
            if not raw:
                continue
            lines.extend(_chunk_by_touten(raw, 15))
        if not lines:
            continue
        if role == "hook":
            lines = lines[:1]
        segments.append({"role": role, "lines": lines})
    if len(segments) < 4:
        raise ValueError("モノローグ構成のセグメントが不足しています")

    base["format"] = "monologue"
    base["segments"] = segments
    base["script_lines"] = [l for s in segments for l in s["lines"]]
    base["thumb_text"] = str(content.get("thumb_text") or "").strip()[:10]
    return base


def _generate_with_template(topic: str) -> dict:
    """APIなしで動くテンプレート台本。"""
    short_topic = topic if len(topic) <= 40 else topic[:40] + "…"
    title = f"【ジャグラー予想】{short_topic}"[:100]
    script_lines = [
        f"今日のテーマは「{topic}」",
        "結論から言います",
        "狙うならこの条件です",
        "ポイント1 過去の出玉傾向をチェック",
        "ポイント2 REGの出現率に注目",
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


def _split_script_text(text: str) -> list:
    """ユーザーが持ち込んだ台本テキストをテロップ単位の行に分割する。

    改行があれば改行単位、長い行は文(。!?)単位、それでも長ければ
    30文字前後で機械的に切る。
    """
    max_len = 30
    lines = []
    for raw in text.replace("\r", "").split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        for part in re.split(r"(?<=[。!?!?])", raw):
            part = part.strip().rstrip("。")
            if not part:
                continue
            lines.extend(_chunk_by_touten(part, max_len))
    return [l for l in lines if l]


def _chunk_by_touten(part: str, max_len: int) -> list:
    """長い文を読点(、)の位置を優先して max_len 以内に分割する。"""
    if len(part) <= max_len:
        return [part]
    out = []
    current = ""
    for seg in re.split(r"(?<=、)", part):
        while len(seg) > max_len:  # 読点が無い超長文は機械的に切る
            if current:
                out.append(current)
                current = ""
            out.append(seg[:max_len])
            seg = seg[max_len:]
        if len(current) + len(seg) <= max_len:
            current += seg
        else:
            out.append(current)
            current = seg
    if current:
        out.append(current)
    out = [l.strip().rstrip("、") for l in out if l.strip()]
    # 末尾に1〜2文字だけ取り残された行は前の行に結合する(「い」だけ等を防ぐ)
    merged = []
    for chunk in out:
        if merged and len(chunk) <= 2 and len(merged[-1]) + len(chunk) <= max_len + 3:
            merged[-1] += chunk
        else:
            merged.append(chunk)
    return merged


def build_from_user_script(topic: str, script_text: str) -> dict:
    """シートの script 列に貼られた台本をそのまま使う(生成はしない)。"""
    lines = _split_script_text(script_text)
    if not lines:
        raise ValueError("script 列の台本が空です")
    content = {
        "title": topic,
        "script_lines": lines,
        "description": (
            f"{topic}\n\n"
            "※本動画は予想・考察であり、結果を保証するものではありません。\n"
            "※パチンコ・パチスロは適度に楽しみましょう。"
        ),
        "hashtags": ["#Shorts", "#ジャグラー", "#パチスロ", "#スロット", "#狙い台"],
    }
    return _validate(content, topic)


def generate(topic: str, feedback: str = "") -> dict:
    """テーマから台本一式を生成して dict で返す。

    CONTENT_STYLE で構成を切り替える:
      monologue (既定) … ジャグラーマンの都市伝説・検証トーク (data/ランキング禁止)
      ranking          … 従来のランキング構成
    feedback には品質チェック/レビュー会議で出た課題を渡すと再生成時に反映される。
    """
    if config.CONTENT_STYLE == "monologue":
        if config.ANTHROPIC_API_KEY:
            try:
                _log().info("Claude API (%s) でジャグラーマン台本を生成します", config.CLAUDE_MODEL)
                return _validate_monologue(_generate_monologue_with_claude(topic, feedback), topic)
            except Exception as e:
                log_error(f"Claude API でのジャグラーマン台本生成に失敗。テンプレートで継続します: {e}")
        else:
            _log().info("ANTHROPIC_API_KEY 未設定のためテンプレートでジャグラーマン台本を生成します")
        return _validate_monologue(_pick_monologue_template(topic), topic)

    if config.CONTENT_STYLE == "ranking":
        if config.ANTHROPIC_API_KEY:
            try:
                _log().info("Claude API (%s) でランキング台本を生成します", config.CLAUDE_MODEL)
                return _validate_ranking(_generate_ranking_with_claude(topic, feedback), topic)
            except Exception as e:
                log_error(f"Claude API でのランキング台本生成に失敗。テンプレートで継続します: {e}")
        else:
            _log().info("ANTHROPIC_API_KEY 未設定のためテンプレートでランキング台本を生成します")
        return _validate_ranking(_generate_ranking_template(topic), topic)

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
