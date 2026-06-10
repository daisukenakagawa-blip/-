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

## ⚠️ 重要：公開後のデータ保存について

Streamlit Community Cloud は、**アプリが再起動するとSQLiteの中身（蓄積データ）が
リセットされます**（再デプロイ・一定時間アクセスなしでのスリープ復帰など）。

- **傾向の確認・デモ用途**：このままで問題ありません
- **毎日コツコツ蓄積したい**：保存先を「消えない場所」にする必要があります
  - 相性が良いのは **Googleスプレッドシート**（本ツールに出力機能あり）
  - この改修が必要になったら、お申し付けください（`database.py` の保存先を
    スプレッドシート/外部DBに切り替える対応をします）

当面は「PCの `collect.py` で毎日蓄積 → スプレッドシートに出力 → スマホで閲覧」
という運用でも実用になります。

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
