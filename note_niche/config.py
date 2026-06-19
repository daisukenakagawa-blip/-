# -*- coding: utf-8 -*-
"""note 勝てるニッチ発掘ツールの設定"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
SEEDS_FILE = BASE_DIR / "seeds.csv"      # 出発点となる興味・ジャンル

# ── 収集設定 ────────────────────────────────────────────────
NOTES_PER_KEYWORD = 40       # 1キーワードあたり集めるnote記事数
REQUEST_INTERVAL = 1.0       # note へのリクエスト間隔（秒）

# ── 候補キーワード生成 ──────────────────────────────────────
# ANTHROPIC_API_KEY があれば、各シードからロングテール候補をAIが自動生成。
# 無ければ candidates.csv（あれば）や seeds をそのまま候補にする。
USE_AI_CANDIDATES = True
AI_MODEL = "claude-opus-4-8"
CANDIDATES_PER_SEED = 25     # 1シードから作る候補キーワード数

# ── スコア閾値（採点ロジックの調整つまみ）──────────────────
MIN_NOTES_FOR_DEMAND = 8     # これ未満の記事数なら「需要薄」
WEAK_PAID_LIKES = 50         # 最強有料記事のスキがこの未満なら「競合が弱い＝穴」
BIG_AUTHOR_FOLLOWERS = 10000 # 上位にこの規模の著者がいたら「大型支配」減点
SCORE_GOOD = 25              # これ以上で「狙い目」
SCORE_MAYBE = 10             # これ以上で「条件付き」

TOP_N_REPORT = 20            # レポートに載せる上位ニッチ数
USE_AI_ANALYSIS = True       # 上位ニッチにAIで「切り口・タイトル・価格」を付ける
