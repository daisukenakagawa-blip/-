# -*- coding: utf-8 -*-
"""② Webリサーチャー: web_search で一次情報・具体を集める。"""
from .prompts import WEB_RESEARCHER_SYSTEM


class WebResearcher:
    def __init__(self, llm, logger=None):
        self.llm = llm
        self.log = logger

    def research(self, topic: str, angle_hint: str = "") -> str:
        if self.log:
            self.log.info(f"  [Webリサーチ] 調査中: '{topic}'")
        user = (
            f"調査テーマ: {topic}\n"
            + (f"狙う切り口のヒント: {angle_hint}\n" if angle_hint else "")
            + "\n記事に具体性と信頼性を与える材料を、web_searchで集めてまとめてください。"
        )
        try:
            return self.llm.complete(
                WEB_RESEARCHER_SYSTEM, user,
                max_tokens=4000, effort="high", web_search=True,
            )
        except Exception as e:
            if self.log:
                self.log.warn(f"  Web検索に失敗（{e}）。検索なしで一般知識のリサーチに切替。")
            return self.llm.complete(
                WEB_RESEARCHER_SYSTEM + "\n（web_searchは使えません。一般知識の範囲で、"
                "確実なものだけ書いてください）",
                user, max_tokens=3000, effort="high", web_search=False,
            )
