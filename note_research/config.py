# -*- coding: utf-8 -*-
"""
設定ファイル
ここを書き換えるだけで、リサーチ対象や条件を変更できます。
"""
from pathlib import Path

# ── 基本パス ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"          # レポート・CSV の出力先
KEYWORDS_FILE = BASE_DIR / "keywords.csv"  # リサーチするキーワード一覧
LOG_DIR = BASE_DIR / "logs"

# ── リサーチ条件 ────────────────────────────────────────────
# 1キーワードあたり何件まで取得するか（API を複数回叩いてページング取得します）
MAX_ITEMS_PER_KEYWORD = 100

# note 検索 API の取得単位（1回のリクエストで取れる件数。最大 20 程度）
PAGE_SIZE = 20

# 「売れている記事」の判定条件
# price > 0（有料記事）を基本とし、無料でも人気な記事を参考に含めるかどうか
INCLUDE_FREE_NOTES = True       # 無料記事も分析対象に含める（人気タイトルの参考になる）
MIN_LIKE_COUNT = 10             # スキ数がこの数未満の記事は除外（ノイズ削減）

# レポートに載せる「売れ筋ランキング」の上位件数
TOP_N = 30

# ── 通信設定 ────────────────────────────────────────────────
REQUEST_TIMEOUT = 20            # 秒
REQUEST_INTERVAL = 1.0         # 連続リクエストの間隔（秒）。note に負荷をかけないため
MAX_RETRIES = 3                # 失敗時のリトライ回数
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# ── AI による考察生成(任意) ─────────────────────────────────
# .env に ANTHROPIC_API_KEY を設定すると、AI が「売れる理由・狙い目」を要約します。
# 設定しなくてもルールベースの分析レポートは出力されます。
USE_AI_INSIGHT = True
AI_MODEL = "claude-sonnet-4-6"
