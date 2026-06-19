# -*- coding: utf-8 -*-
"""
Anthropic Claude API のラッパー（編集部の全エージェントが共通で使う）。

設計（claude-api スキルの推奨に準拠）:
- モデルは既定で claude-opus-4-8（最も高性能）
- adaptive thinking + effort で深く考えさせる
- 大きな出力に備えてストリーミング（get_final_message でまとめて受け取る）
- システムプロンプトは prompt cache（cache_control: ephemeral）でコスト削減
- web_search はサーバーサイドツール。pause_turn を継続ループで処理
"""
import os


class LLM:
    def __init__(self, model: str, logger=None):
        # anthropic は requirements に含む。未インストールなら分かりやすく失敗させる。
        import anthropic
        self._anthropic = anthropic
        # ANTHROPIC_API_KEY を環境から解決
        self.client = anthropic.Anthropic()
        self.model = model
        self.log = logger

    # ── テキスト生成（任意で web_search 有効化）──────────────
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 8000,
        effort: str = "high",
        web_search: bool = False,
        max_web_uses: int = 6,
    ) -> str:
        system_blocks = [{
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},  # システムプロンプトをキャッシュ
        }]
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system_blocks,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
        )
        if web_search:
            # 最新版（動的フィルタリング対応）。Opus 4.8 で利用可能。
            kwargs["tools"] = [{
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": max_web_uses,
            }]

        messages = [{"role": "user", "content": user}]
        last = None
        for _ in range(10):  # pause_turn の継続上限
            with self.client.messages.stream(**kwargs, messages=messages) as stream:
                last = stream.get_final_message()
            if last.stop_reason == "pause_turn":
                # サーバーツールが途中で止まった → 続きを依頼
                messages = messages + [{"role": "assistant", "content": last.content}]
                continue
            break
        return self._text(last)

    @staticmethod
    def _text(message) -> str:
        if not message:
            return ""
        parts = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts).strip()
