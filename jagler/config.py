"""
設定ファイル
====================================================================
ジャグラーデータ収集ツールの全体設定をここで管理します。

【重要・利用規約について】
- 実サイトへの接続を有効化する前に、必ず対象サイトの利用規約と
  robots.txt を確認してください。
- スクレイピングが許可されているか不明な場合、または禁止されている
  場合は、SCRAPER_ENABLED = False のまま（デモデータ）で使用するか、
  公式に提供されているデータ（CSVダウンロード等）を利用してください。
- 本ツールはアクセス頻度を「1日1回」に制限しており、サーバへ過度な
  負荷をかけない設計になっていますが、最終的な順守責任は利用者にあります。
"""

import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


# ------------------------------------------------------------------
# 基本情報
# ------------------------------------------------------------------
STORE_NAME = "ビッグディッパー新橋1号店"
MACHINE_NAME = "マイジャグラー"

# ------------------------------------------------------------------
# 保存先（ストレージ）
# ------------------------------------------------------------------
# "auto"   : 認証情報があれば Googleスプレッドシート、無ければ SQLite（推奨）
# "sqlite" : 常にローカルの SQLite（このPC内に保存）
# "gsheet" : 常に Googleスプレッドシート（クラウドでも消えない蓄積先）
STORAGE_BACKEND = "auto"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "jagler.db"
CSV_EXPORT_PATH = DATA_DIR / "jagler_export.csv"
# レート制限の記録（最後に取得した時刻を保存）
LAST_FETCH_PATH = DATA_DIR / "last_fetch.json"

# ------------------------------------------------------------------
# スクレイピング設定
# ------------------------------------------------------------------
# 実サイト接続を有効にする場合は True にし、下の URL/セレクタを設定してください。
# False の場合はデモ（サンプル）データを生成します。
# 環境変数 JAG_SCRAPER_ENABLED でも上書き可能（GitHub Actions等で設定するため）。
SCRAPER_ENABLED = _env_bool("JAG_SCRAPER_ENABLED", False)

# 対象データページのURL（{date} に YYYYMMDD などが入る想定）
# 例: "https://example.com/hall/shinbashi1/data?date={date}"
# 環境変数 JAG_TARGET_URL_TEMPLATE で上書き可能。
TARGET_URL_TEMPLATE = _env_str("JAG_TARGET_URL_TEMPLATE", "")

# 取得対象の日付フォーマット（URL に埋め込む際の strftime）
URL_DATE_FORMAT = "%Y%m%d"

# HTMLテーブルを特定するためのCSSセレクタ。
# 対象サイトの構造に合わせて設定してください（BeautifulSoup で使用）。
# 例: "table.data-table"
# 環境変数 JAG_TABLE_SELECTOR で上書き可能。
TABLE_SELECTOR = _env_str("JAG_TABLE_SELECTOR", "")

# テーブルの各列が「取得したい項目」のどれに当たるかのマッピング。
# キー: 内部カラム名 / 値: そのサイトの列見出し（テキスト）または列インデックス(int)
# 列見出しで対応できない場合は parse 関数を scraper.py 側で調整してください。
COLUMN_MAP = {
    "machine_no": "台番号",
    "big": "BIG",
    "reg": "REG",
    "total_games": "総回転数",
    # 任意：機種名の列。設定すると MACHINE_KEYWORDS で行を絞り込める
    # （店ページに複数機種が混在する場合にジャグラー系だけを残す）。
    # "machine_name": "機種",
}

# ------------------------------------------------------------------
# 取得対象の店舗リスト（多店舗対応）
# ------------------------------------------------------------------
# 「東京都の公開店すべて」を対象にする場合、ここに店舗を追加します。
# 各店: name=店舗名 / url={date}を含むデータページURL / table_selector=表のCSSセレクタ
# ※ URL・セレクタは対象サイトの構造に合わせて設定。各サイトのToS確認は利用者が行うこと。
STORES = [
    {
        "name": STORE_NAME,            # ビッグディッパー新橋1号店
        "url": TARGET_URL_TEMPLATE,    # 既定は空（未設定）
        "table_selector": TABLE_SELECTOR,
        "area": "東京都",
    },
]

# 取得対象の機種名キーワード（ジャグラー系を広く拾う）。
# 例: アイムジャグラー / マイジャグラー / ファンキー / ゴーゴー など全ジャグラー系。
MACHINE_KEYWORDS = ["ジャグラー"]

# 多店舗を巡回するとき、1リクエストごとの待機秒数（サーバ負荷軽減・マナー）。
REQUEST_DELAY_SEC = 6

# ------------------------------------------------------------------
# 巡回方式（Pattern A / B）
# ------------------------------------------------------------------
# "A" : 1ページに東京都の全店データが並ぶサイト（STORES を手動設定）
# "B" : 店舗一覧ページ → 各店ページを巡回（東京都の公開店を自動で辿る）★今回これ
CRAWL_MODE = _env_str("JAG_CRAWL_MODE", "B")

# 【Pattern B】東京都の店舗一覧（インデックス）ページの設定
# - {page} : ページ番号（複数ページに分かれている場合）
# - {date} : 日付（必要な場合）
AREA_INDEX_URL = _env_str("JAG_AREA_INDEX_URL", "")
# 一覧が複数ページに分かれている場合の総ページ数
INDEX_PAGES = int(_env_str("JAG_INDEX_PAGES", "1") or "1")
# 一覧ページ内で「各店ページへのリンク <a>」を指すCSSセレクタ
STORE_LINK_SELECTOR = _env_str("JAG_STORE_LINK_SELECTOR", "")
# 相対リンクを絶対URLに変換する際の基準URL（空なら一覧ページのURLを基準にする）
STORE_BASE_URL = _env_str("JAG_STORE_BASE_URL", "")
# 各店ページのデータ表セレクタ（空なら TABLE_SELECTOR を使用）
STORE_PAGE_TABLE_SELECTOR = _env_str("JAG_STORE_PAGE_TABLE_SELECTOR", "")

# ------------------------------------------------------------------
# アクセスマナー設定
# ------------------------------------------------------------------
# 1日1回に制限（秒）。86400秒 = 24時間
MIN_FETCH_INTERVAL_SEC = 60 * 60 * 20  # 20時間（同日2回目を防ぐ安全マージン）

# robots.txt を尊重する
RESPECT_ROBOTS_TXT = True

# リクエストヘッダ（連絡先を入れておくとサイト運営者に親切です）
USER_AGENT = (
    "JagulerDataCollector/1.0 (personal research; "
    "respects robots.txt; 1 request/day)"
)
REQUEST_TIMEOUT_SEC = 20

# ------------------------------------------------------------------
# 分析・色分けのしきい値
# ------------------------------------------------------------------
# 合算確率の色分け（分母の値で判定。小さいほど良い＝高設定示唆）
# 1/140〜1/130 : 黄色 / 1/129〜1/110 : オレンジ / 1/109〜1/80 : 赤
COMBINED_COLOR_THRESHOLDS = [
    # (下限分母, 上限分母, 色名, 16進カラー)
    (80, 109, "赤", "#ff5b5b"),
    (110, 129, "オレンジ", "#ffae42"),
    (130, 140, "黄色", "#ffe066"),
]

# REG確率の色分け（マイジャグラーは REG が設定差の鍵。分母が小さいほど高設定示唆）
REG_COLOR_THRESHOLDS = [
    (200, 255, "赤", "#ff5b5b"),
    (256, 290, "オレンジ", "#ffae42"),
    (291, 330, "黄色", "#ffe066"),
]

# 分析の対象期間
RECENT_30 = 30
RECENT_90 = 90

# 狙い台ランキングの表示件数
RANKING_TOP_N = 20

# ------------------------------------------------------------------
# Googleスプレッドシート連携（任意）
# ------------------------------------------------------------------
# gspread + サービスアカウントを使用。利用する場合のみ設定してください。
GSHEET_ENABLED = False
GSHEET_CREDENTIALS_PATH = str(BASE_DIR / "service_account.json")
GSHEET_SPREADSHEET_NAME = "ジャグラーデータ"
GSHEET_WORKSHEET_NAME = "data"
# スプレッドシートをURL/キーで指定する場合（名前より確実。任意）
# 例: シートURL https://docs.google.com/spreadsheets/d/<ここがキー>/edit
# 環境変数 JAG_GSHEET_SPREADSHEET_KEY でも指定可能（GitHub Actions等）。
GSHEET_SPREADSHEET_KEY = _env_str("JAG_GSHEET_SPREADSHEET_KEY", "") or None
