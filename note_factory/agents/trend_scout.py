# -*- coding: utf-8 -*-
"""① 話題スカウト: noteの売れ筋を集め、戦略ブリーフに落とす。"""
from . import note_source
from .prompts import TREND_SCOUT_SYSTEM


class TrendScout:
    def __init__(self, llm, logger=None, max_items=40):
        self.llm = llm
        self.log = logger
        self.max_items = max_items

    def scout(self, genre: str) -> dict:
        """genre で note を調べ、{brief, raw_count, titles} を返す。"""
        if self.log:
            self.log.info(f"  [話題スカウト] note検索中: '{genre}'")
        items = note_source.fetch_top_notes(genre, self.max_items, self.log)
        if not items:
            if self.log:
                self.log.warn("  note からデータを取得できませんでした（ネット制限/仕様変更）。"
                              "ジャンル知識のみで進めます。")
            data_text = f"（noteの実データ取得に失敗。ジャンル『{genre}』の一般知識で推定してください）"
        else:
            data_text = note_source.format_for_prompt(items)

        user = (
            f"ジャンル/キーワード: {genre}\n\n"
            f"【実際に売れている/人気の note 記事リスト（スキ数順）】\n{data_text}\n\n"
            "このデータを分析し、戦略ブリーフを作ってください。"
        )
        brief = self.llm.complete(TREND_SCOUT_SYSTEM, user, max_tokens=3000, effort="high")
        return {
            "brief": brief,
            "raw_count": len(items),
            "titles": [it["title"] for it in items[:15]],
        }
