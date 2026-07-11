# pachi-scraper

データを公開しているパチンコ・スロット店のサイトから台データ（BB/RB回数、総スタートなど）を自動収集し、SQLiteに蓄積して日別・機種別・台別に集計するツールです。

## 特徴

- **設定ファイルだけでサイトに対応**: 台データ公開サイトの多くは「台番号 / BB / RB / 総スタート」のようなテーブル形式なので、URLとテーブルの見出しをYAMLに書くだけで取り込めます。サイトごとの専用コードは不要です。
- **マナー重視の設計**: robots.txt の遵守、リクエスト間隔の強制（デフォルト3秒）、リトライ制御を組み込んでいます。
- **蓄積と集計**: SQLiteに日別で蓄積し、同じ日の再取得は上書き。日別×機種別サマリ（平均G数・合成確率）と台別履歴をCSV（Excel対応のBOM付きUTF-8）で出力します。

## セットアップ

```bash
cd pachi-scraper
pip install -r requirements.txt
```

## まず試す（ネットワーク不要のデモ）

同梱のサンプルHTMLを使ってすぐ動きを確認できます。

```bash
python -m pachi collect --config config.demo.yaml
python -m pachi report  --config config.demo.yaml
```

`reports/daily_model_summary.csv` と `reports/unit_history.csv` が生成され、ターミナルにもサマリが表示されます。

## 実際のサイトに対応させる

1. `config.example.yaml` をコピーして `config.yaml` を作る
2. ブラウザの開発者ツール（F12）で対象ページを確認し、以下を書き換える
   - `base_url`: 店舗の台データページのURL
   - `pages`: 機種ごとの一覧ページのURL
   - `table_selector`: データテーブルのCSSセレクタ（例: `table.unit_list`）
   - `columns`: テーブル見出しのテキスト（サイトの表記に合わせる）
3. 収集・集計を実行

```bash
python -m pachi collect --config config.yaml           # 今日の日付で保存
python -m pachi collect --config config.yaml --date 2026-07-10
python -m pachi report  --config config.yaml --out reports
```

## 毎日自動で収集する

cron（Linux/Mac）の例。閉店後の時間帯に1日1回:

```cron
30 23 * * * cd /path/to/pachi-scraper && python -m pachi collect --config config.yaml >> collect.log 2>&1
```

## 出力の見方

- `daily_model_summary.csv`: 日付×機種ごとの台数、総/平均スタート、BB・RB合計、**合成確率**（総スタート ÷ ボーナス合計。ジャグラー系の設定推測の目安になります）
- `unit_history.csv`: 台ごとの日別データ。特定の台番号の挙動を追うときに使います

## 注意事項（必ず読んでください）

- 収集前に**対象サイトの利用規約**を確認してください。スクレイピングを明示的に禁止しているサイトもあります。
- `rate_limit_seconds` は3秒以上を推奨します。サーバーに負荷をかける高頻度アクセスは絶対に避けてください。
- 収集したデータは私的利用の範囲にとどめ、無断で再配布・公開しないでください。
- JavaScriptで描画されるサイト（HTMLソースにテーブルが無いサイト）はこのツールでは取れません。その場合はPlaywright等のブラウザ自動化が必要です（対応は拡張として可能）。

## テスト

```bash
cd pachi-scraper
python -m pytest tests/ -v
```
