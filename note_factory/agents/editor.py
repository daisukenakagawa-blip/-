# -*- coding: utf-8 -*-
"""④ 部長（編集長）: 記事を精査し、合否と修正指示を出す。"""
import json
import re

from .prompts import EDITOR_SYSTEM


class Editor:
    def __init__(self, llm, logger=None):
        self.llm = llm
        self.log = logger

    def review(self, topic, draft) -> dict:
        if self.log:
            self.log.info("  [部長] 精査中…")
        user = (
            f"# テーマ\n{topic}\n\n"
            f"# 審査する記事\n{draft}\n\n"
            "この記事を採点し、指定のJSONだけを返してください。"
        )
        raw = self.llm.complete(EDITOR_SYSTEM, user, max_tokens=3000, effort="high")
        return parse_verdict(raw)

    def feedback_text(self, verdict: dict) -> str:
        """合否結果を、ライターへ渡す修正指示テキストに整形する。"""
        lines = []
        if verdict.get("ai_smell"):
            lines.append("【AI臭い箇所（人間が書いた文章に直す）】")
            lines += [f"- {x}" for x in verdict["ai_smell"]]
        if verdict.get("must_fix"):
            lines.append("【必ず直す】")
            lines += [f"- {x}" for x in verdict["must_fix"]]
        if verdict.get("nice_to_have"):
            lines.append("【できれば直す】")
            lines += [f"- {x}" for x in verdict["nice_to_have"]]
        return "\n".join(lines)


def parse_verdict(raw: str) -> dict:
    """LLM出力からJSONを取り出す。壊れていても落ちないよう防御的に処理。"""
    default = {
        "scores": {}, "overall": 0, "verdict": "revise",
        "ai_smell": [], "must_fix": [], "nice_to_have": [],
        "one_line": "", "_raw": raw,
    }
    if not raw:
        return default
    # ```json ... ``` を剥がす
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    text = m.group(1) if m else raw
    # 最初の { から最後の } までを抜く
    if not m:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            text = text[s:e + 1]
    try:
        data = json.loads(text)
    except Exception:
        return default
    out = dict(default)
    out.update({k: data.get(k, default[k]) for k in default if k != "_raw"})
    # verdict の正規化
    v = str(out.get("verdict", "")).lower()
    out["verdict"] = "pass" if "pass" in v else "revise"
    try:
        out["overall"] = int(out.get("overall") or 0)
    except (ValueError, TypeError):
        out["overall"] = 0
    return out


def is_pass(verdict: dict) -> bool:
    """部長の合格基準（プロンプトと一致させた安全側の判定）。"""
    s = verdict.get("scores") or {}

    def g(k):
        try:
            return int(s.get(k, 0))
        except (ValueError, TypeError):
            return 0
    return (
        verdict.get("verdict") == "pass"
        and verdict.get("overall", 0) >= 8
        and g("human") >= 4 and g("value") >= 4 and g("safety") >= 4
    )
