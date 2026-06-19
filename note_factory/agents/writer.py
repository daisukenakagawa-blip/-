# -*- coding: utf-8 -*-
"""③ ライター: 材料をもとに、人間らしく価値ある記事を書く（必要なら書き直す）。"""
from .prompts import WRITER_SYSTEM


class Writer:
    def __init__(self, llm, logger=None):
        self.llm = llm
        self.log = logger

    def write(self, topic, trend_brief, research, price="", feedback=None) -> str:
        if self.log:
            self.log.info("  [ライター] 執筆中" + ("（修正反映）" if feedback else ""))
        parts = [
            f"# 執筆テーマ\n{topic}",
            f"# 推奨価格\n{price or '未指定（あなたが妥当な額を提案）'}",
            "# 戦略ブリーフ（話題スカウトより）\n" + (trend_brief or "（なし）"),
            "# リサーチ資料（Webリサーチャーより。具体・数字はここから使う）\n" + (research or "（なし）"),
        ]
        if feedback:
            parts.append(
                "# 編集長からの修正指示（必ず全て反映し、最初から書き直す）\n" + feedback
            )
        parts.append(
            "上記を踏まえ、note の有料記事を1本、完成稿で書いてください。"
            "本文（Markdown）のみを出力すること。"
        )
        user = "\n\n".join(parts)
        return self.llm.complete(WRITER_SYSTEM, user, max_tokens=9000, effort="high")
