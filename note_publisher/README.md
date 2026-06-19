# note 自動投稿ツール(note_publisher)

`note_writer` で作った記事を、**note に自動で下書き保存/公開/予約投稿**するツールです。
自動記事量産ツールの**第3ステップ(投稿)**にあたります。

## ⚠️ 最初に必ずお読みください

- note には**公式の投稿API がありません**。本ツールは **Playwright(ブラウザ自動操作)**で
  **あなた自身のnoteアカウント**を操作します。
- **既定は「下書き保存」**です。いきなり公開はしません。note の画面で内容・有料設定を
  確認してから、あなたの手で公開する流れを推奨します(誤投稿・フォーマット崩れ防止)。
- note の**利用規約**を必ず確認し、**自分のアカウントの記事を、常識的な頻度で**投稿して
  ください。短時間の大量投稿・自動化が規約上問題になる可能性があります。本ツールは
  1回の実行本数(`MAX_POSTS_PER_RUN`)と投稿間隔(`INTERVAL_BETWEEN_POSTS`)を制限しています。
- パスワードはツールに保存しません。**手動ログイン → セッション保存方式**です
  (2段階認証・Googleログインにも対応)。

## セットアップと使い方

### Windows(ダブルクリック)

| 順番 | ファイル | やること |
|---|---|---|
| ① | `①セットアップ.bat` | Python部品＋ブラウザ(Chromium)を自動インストール |
| ② | `②ログイン.bat` | ブラウザでnoteに手動ログイン → セッション保存(最初に1回) |
| ③ | `③下書き投稿.bat` | 記事を「下書き」として自動投稿 |

### コマンド

```bash
pip install -r requirements.txt
python -m playwright install chromium    # 初回のみ

python login.py                          # 最初に1回ログイン(セッション保存)
python publisher.py                      # 既定モードで投稿(config.PUBLISH_MODE)
python publisher.py --mode draft         # 下書き保存(おすすめ)
python publisher.py --mode publish       # そのまま公開(自己責任)
python publisher.py --mode schedule      # 予約投稿
python publisher.py ../note_writer/articles/01_副業ロードマップ.md  # 1本だけ
```

## 動作の流れ

1. `note_writer/articles/*.md` を読み込み(front matter から価格・タグ、本文から
   タイトルと「無料/有料」の境界を解析)
2. `posted_log.csv` を見て**投稿済みはスキップ**(重複防止)
3. note のエディタにタイトル・本文を入力(本文は1行ずつ入力し、`#` 見出しや
   `-` 箇条書きなどの**Markdown風オートフォーマットを活かします**)
4. モードに応じて 下書き保存 / 公開 / 予約
5. 各ステップで `screenshots/` にスクショを保存(不具合調査用)

## 設定(`config.py`)

| 項目 | 説明 | 既定 |
|---|---|---|
| `PUBLISH_MODE` | draft / publish / schedule | `draft` |
| `MAX_POSTS_PER_RUN` | 1回の実行で投稿する最大本数 | 3 |
| `INTERVAL_BETWEEN_POSTS` | 投稿間隔(秒) | 30 |
| `HEADLESS` | False で画面を見ながら実行 | False |
| `ARTICLES_DIR` | 読み込む記事フォルダ | `../note_writer/articles` |
| `EDITOR_URL` | 新規記事エディタのURL | `https://note.com/notes/new` |
| `SELECTORS` | note の要素セレクタ(仕様変更時はここを修正) | — |

## 有料記事(paywall)について

- 記事の `推奨価格` が 0 より大きいと「有料記事」として扱い、`ここから先は有料です`
  の境界で本文を分割します。
- ただし **note 上での「有料エリアの設定・価格入力」は手動操作を推奨**します
  (自動化はnoteのUI変更で壊れやすく、価格ミスは事故につながるため)。
  下書き投稿後、note の編集画面で**有料ラインと価格を設定**してから公開してください。

## うまく動かないときは

- **入力欄が見つからない**: note の画面仕様が変わった可能性。`screenshots/` の画像を
  見て、`config.py` の `SELECTORS`(タイトル/本文/公開ボタン)を実際の要素に合わせて
  修正してください(候補を配列で複数指定できます)。
- **ログインが切れた**: もう一度 `python login.py` を実行してください。
- **エディタが開かない**: `config.EDITOR_URL` を、ブラウザで「投稿→テキスト」を押した
  ときのURLに合わせてください。

## ファイル構成

```
note_publisher/
├─ publisher.py          メイン(投稿実行)
├─ login.py              最初の手動ログイン(セッション保存)
├─ config.py             設定・セレクタ
├─ modules/
│  ├─ article_loader.py  Markdown→タイトル/本文/有料境界の解析
│  ├─ note_poster.py     Playwright によるエディタ操作
│  ├─ posted_log.py      重複投稿防止
│  └─ logger.py
├─ state/                ログインセッション(git管理外)
├─ screenshots/          各ステップのスクショ(git管理外)
└─ posted_log.csv        投稿済み記録(git管理外)
```
