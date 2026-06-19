# -*- coding: utf-8 -*-
"""note 記事ジェネレーターの設定"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARTICLES_DIR = BASE_DIR / "articles"     # 手書き/完成済みの記事サンプル
OUTPUT_DIR = BASE_DIR / "output"          # 自動生成した記事の出力先
PLAN_FILE = BASE_DIR / "article_plan.csv"  # 量産する記事の計画(テーマ一覧)
LOG_DIR = BASE_DIR / "logs"

# リサーチ結果(note_research)の output から、最新の CSV を入力に使う
RESEARCH_OUTPUT_DIR = BASE_DIR.parent / "note_research" / "output"

# ── 生成設定 ────────────────────────────────────────────────
USE_AI = True                  # ANTHROPIC_API_KEY があれば AI 生成、無ければ雛形
AI_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4000

# 無料パートで全体の何割を見せるか(noteの定番は2〜3割)
FREE_RATIO_HINT = 0.3

# 既定の推奨価格(リサーチCSVに価格中央値があればそれを優先)
DEFAULT_PRICE = 500

# 有料ラインの区切り文字列(noteの有料エリア設定の目印)
PAYWALL_MARK = "━━ ここから先は有料パートです ━━"

# ── LINE 通知 ───────────────────────────────────────────────
# 記事生成が完了したら LINE に通知する。
# 送信には環境変数 LINE_CHANNEL_ACCESS_TOKEN が必要(.env.example 参照)。
# 未設定なら自動でスキップします。
NOTIFY_LINE = True
