# 📱 スマホから使う：クラウド公開ガイド（Streamlit Community Cloud）

このツールを無料でWeb公開し、**スマホのブラウザからURLで開けるように**する手順です。
コードはすでにGitHubにあるので、画面操作だけで公開できます。

---

## 手順（5分ほど）

### 1. Streamlit Community Cloud にログイン
- https://share.streamlit.io にアクセス
- 「Continue with GitHub」で、このリポジトリを持つGitHubアカウントでログイン
- 初回はGitHubへのアクセス許可を求められるので承認

### 2. 新規アプリを作成
- 右上の **「Create app」** →「Deploy a public app from GitHub」を選択
- 次のように指定します：

| 項目 | 入力する値 |
|------|-----------|
| Repository | `daisukenakagawa-blip/-` |
| Branch | `claude/zealous-allen-w3gc7r` |
| Main file path | `jagler/app.py` |

### 3. Deploy
- **「Deploy」** を押す
- 1〜3分でビルドが終わり、`https://〇〇.streamlit.app` のURLが発行されます

### 4. スマホで開く
- 発行されたURLをスマホのブラウザで開く（ブックマーク推奨）
- 画面が出たら、左上の「>」からサイドバーを開き
  **「🧪 デモ履歴をまとめて生成」** を押すと表示を確認できます

> 💡 ホーム画面に追加：iPhoneなら共有→「ホーム画面に追加」、
> Androidなら︙→「ホーム画面に追加」で、アプリのように起動できます。

---

## ⭐ データを消さずに毎日蓄積する（Googleスプレッドシート保存）

Streamlit Cloud は再起動でSQLiteが消えますが、**保存先をGoogleスプレッドシートに
すると消えません**。本ツールは保存先を自動切替できるようになっており、認証情報を
設定するだけで「スプレッドシートをデータベース本体」として読み書きします
（スマホのスプレッドシートアプリから中身を直接見ることもできます）。

### 設定手順

#### A. Google側（サービスアカウントの用意）
1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→ **Google Sheets API** と **Google Drive API** を有効化
3. 「認証情報」→「サービスアカウント」を作成
4. 作成したサービスアカウントの **キー（JSON）** をダウンロード
5. Googleスプレッドシートを新規作成し、**サービスアカウントのメールアドレス**
   （`xxxx@xxxx.iam.gserviceaccount.com`）に**編集権限で共有**
6. そのシートのURL `https://docs.google.com/spreadsheets/d/<キー>/edit` の
   `<キー>` 部分を控える

#### B. Streamlit Cloud側（Secrets に貼り付け）
アプリ管理画面 → **Settings → Secrets** に、ダウンロードしたJSONの中身を
次の形式で貼り付けます（TOML形式）。

```toml
[gcp_service_account]
type = "service_account"
project_id = "xxxx"
private_key_id = "xxxx"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "xxxx@xxxx.iam.gserviceaccount.com"
client_id = "xxxx"
token_uri = "https://oauth2.googleapis.com/token"

[gsheet]
spreadsheet_key = "ここに手順A-6で控えたキー"
worksheet_name = "data"
```

保存して再デプロイすると、画面サイドバーの保存先表示が
**「🟢 Googleスプレッドシート（蓄積OK）」** に変わります。これで再起動しても
データが消えず、毎日蓄積されていきます。

> `secrets.toml` の雛形は `jagler/.streamlit/secrets.toml.example` にあります。

### ローカルPCでスプレッドシート蓄積を使う場合
- JSONキーを `jagler/service_account.json` に置く（または環境変数
  `GCP_SERVICE_ACCOUNT_JSON` にJSON文字列をセット）
- `config.py` の `GSHEET_SPREADSHEET_KEY` にシートのキーを設定
- `pip install gspread` 済みであれば `python collect.py` で自動的にシートへ蓄積

### 補足
- 認証情報を設定しなければ従来どおり SQLite（このPC内）で動きます
- どちらの保存先でも、同日・同台の重複は自動でスキップされます

---

## 🤖 毎日「完全自動」で取得・書き込みする（GitHub Actions）

Streamlit Cloud は画面を開いた時しか動かないため、**誰も操作しなくても毎日自動で
取得→シートに書き込む**には定期実行（スケジューラ）が必要です。本リポジトリには
GitHub Actions のワークフロー `.github/workflows/jagler-daily-collect.yml` を同梱
しており、**無料・PC不要**で毎日1回 自動実行できます。

> 補足：取得したデータの「シートへの書き込み」自体は元々自動です（手で貼り付け
> 不要）。下の設定は「取得作業そのもの」を毎日自動で走らせるためのものです。

### 設定（GitHubのリポジトリ画面で）
**Settings → Secrets and variables → Actions** を開き、以下を登録します。

**Secrets（秘密情報）**
| 名前 | 値 |
|------|-----|
| `GCP_SERVICE_ACCOUNT_JSON` | サービスアカウントJSONの**中身そのまま**（1行でも可） |
| `JAG_GSHEET_SPREADSHEET_KEY` | 蓄積先シートのキー（URLの `/d/<ここ>/edit`） |
| `JAG_TARGET_URL_TEMPLATE` | 対象データページのURL（`{date}` を含む）※ToS確認後 |
| `JAG_TABLE_SELECTOR` | データ表のCSSセレクタ ※ToS確認後 |

**Variables（変数）**
| 名前 | 値 |
|------|-----|
| `JAG_SCRAPER_ENABLED` | `true`（実サイト取得を有効化するとき）|

### 動作
- 毎日 **日本時間 1:00**（UTC 16:00）に自動実行（時刻は yml の `cron` で変更可）
- `Actions` タブの **Run workflow** から手動実行も可能（動作確認用）
- **`JAG_SCRAPER_ENABLED` が `true` でない間は、何も書き込まずスキップ**します
  （デモデータで本番シートを汚さないための安全弁）

### ⚠️ 自動取得とToSについて
GitHub Actions による定期取得は「自動アクセス」にあたります。対象サイトの利用規約・
`robots.txt` で許可されていることを必ず確認し、許可される場合のみ
`JAG_SCRAPER_ENABLED=true` と URL/セレクタを設定してください。本ツールは1日1回に
制限していますが、最終的な順守責任は利用者にあります。確認できるまでは未設定（スキップ）
のままにしておけば、誤って取得が走ることはありません。

---

## トラブル時のチェック

- **ビルドが失敗する**：Main file path が `jagler/app.py` になっているか確認
- **パッケージエラー**：リポジトリ直下の `requirements.txt` が反映されます
- **画面が真っ白**：サイドバー（左上の「>」）からデータ生成・取得を実行
- **非公開にしたい**：Streamlit Cloud のアプリ設定から削除/再デプロイ可能

---

## 補足：自分のPCだけで使う場合（公開しない）

```bash
cd jagler
streamlit run app.py --server.address 0.0.0.0
```
起動時に表示される `Network URL: http://192.168.x.x:8501` を、
**同じWiFiに繋いだスマホ**のブラウザで開けばアクセスできます
（PCを起動している間のみ・外出先からは不可）。
