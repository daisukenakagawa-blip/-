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
