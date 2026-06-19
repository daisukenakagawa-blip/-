# -*- coding: utf-8 -*-
"""note 自動記事生産ライン（note_pipeline）の設定"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPO = BASE_DIR.parent

# ── 連結する各ツールの場所 ──────────────────────────────────
FACTORY_DIR = REPO / "note_factory"      # 執筆（編集部AI）
NICHE_DIR = REPO / "note_niche"          # ニッチ発掘
PUBLISHER_DIR = REPO / "note_publisher"  # 投稿（ブラウザ自動操作）

# ── 生産する記事のキュー（コンテンツカレンダー）─────────────
NICHES_FILE = BASE_DIR / "niches.csv"    # 作るニッチの待ち行列（theme,price,genre）
PRODUCED_LOG = BASE_DIR / "produced_log.csv"  # 生産済み記録（重複防止）
PRODUCED_DIR = BASE_DIR / "produced"     # 完成記事の集約先
LOG_DIR = BASE_DIR / "logs"

# ── 1回の実行で生産する本数（毎日自動なら「1日あたり」）──────
DAILY_COUNT = 1
# 連続生産の間隔（秒）。APIや負荷に配慮
INTERVAL_BETWEEN = 5

# ── 投稿の扱い ──────────────────────────────────────────────
# "none"  : 記事ファイルを作るだけ（既定・推奨）。あなたが実体験を足して手動投稿。
# "draft" : note_publisher で「下書き保存」まで自動（要・事前ログイン）。
# "publish": 公開まで自動（上級者向け・自己責任。実体験が入らない点に注意）
PUBLISH_MODE = "none"

# Python 実行コマンド（環境により "python3"）
PYTHON = "python"
