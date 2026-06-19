# -*- coding: utf-8 -*-
"""note編集部（note_factory）の設定"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"     # 完成記事
BRIEFS_DIR = BASE_DIR / "briefs"     # 中間生成物（ブリーフ/リサーチ/講評）
LOG_DIR = BASE_DIR / "logs"
PLAN_FILE = BASE_DIR / "plan.csv"    # 作るテーマ一覧

# ── モデル（claude-api スキル準拠。最高品質は claude-opus-4-8）──
MODEL_WRITER = "claude-opus-4-8"     # ライター（品質最優先）
MODEL_EDITOR = "claude-opus-4-8"     # 部長（精査）
MODEL_SCOUT = "claude-opus-4-8"      # 話題スカウト
MODEL_RESEARCH = "claude-opus-4-8"   # Webリサーチャー（web_search対応モデル）

# ── 編集フロー ──────────────────────────────────────────────
MAX_REVISION_ROUNDS = 3              # 部長NG時にライターが書き直す最大回数
NOTE_SCOUT_ITEMS = 40                # スカウトが集めるnote記事数（1テーマ）

# 中間生成物（ブリーフ・リサーチ・講評ログ）も保存するか
SAVE_BRIEFS = True
