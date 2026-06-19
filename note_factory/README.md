# note編集部（note_factory）— 多段エージェントで“売れて・AIっぽくない”記事を作る

「リサーチ → 執筆 → 編集長の精査」を、役割の違う4つのAIエージェントが分担して回す
記事生成パイプラインです。1人のAIに丸投げするより、**実データから学び・ネットで裏取りし・
人間らしく書き・厳しく精査する**ことで、量産記事にありがちな“薄さ・AI臭”を減らします。

## 編集部の4人

| 役割 | やること |
|---|---|
| ① 話題スカウト | note の公開検索から、そのジャンルの**売れ筋・人気記事**を集め、「何が売れているか」を分析して戦略ブリーフにする |
| ② Webリサーチャー | **Web検索（Claudeのweb_searchツール）**で、具体的な手順・数字・相場・事例・最新事情を集める |
| ③ ライター | ①②を材料に、**人間らしく価値ある記事**を書く（AI臭を徹底的に避ける文体ルール付き） |
| ④ 部長（編集長） | 記事を**6軸で採点**し、合否判定。NGなら具体的な修正指示を返し、**ライターが書き直す**（最大3回） |

合格した記事だけが `output/` に保存されます（未達は `_要確認` 付きで保存）。

## 使うモデル

最高品質を出すため、既定で **Claude Opus 4.8（`claude-opus-4-8`）** を使用します
（`config.py` で変更可）。adaptive thinking + 高effortで深く考え、Web検索ツールで裏取りします。
※ Anthropic APIは**従量課金**です。4役 × 書き直しで1記事あたり相応のトークンを使います。

## セットアップ

### Windows（ダブルクリック）
| ファイル | やること |
|---|---|
| `①セットアップ.bat` | 必要な部品を自動インストール |
| `②記事を作る.bat` | plan.csv のテーマで記事を生成し output を開く |

### コマンド
```bash
pip install -r requirements.txt
cp .env.example .env        # .env に ANTHROPIC_API_KEY を貼る
python run.py               # plan.csv の全テーマ
python run.py "新NISAで失敗しない始め方" --price 680   # 1本だけ
```

## APIキーの設定（必須）

`.env` に Anthropic のキーを設定します（[console.anthropic.com](https://console.anthropic.com/) で発行）。
```
ANTHROPIC_API_KEY=sk-ant-...
```

## 作るテーマの指定（`plan.csv`）

| 列 | 意味 |
|---|---|
| `theme` | 記事のテーマ（タイトルの素） |
| `price` | 推奨価格（空欄ならAIが提案） |
| `genre` | note検索に使う語（空欄なら theme を使用） |

```csv
theme,price,genre
会社員が副業で月5万円を作る最短ルート,500,副業
新NISAで失敗しないための始め方,680,新NISA
```

## 部長の採点基準（品質の核）

各0〜5点：**value（独自性・価値）/ concrete（具体性）/ human（人間らしさ＝AI臭のなさ）/
structure（構成・読みやすさ）/ sellable（売れる設計）/ safety（誠実さ・法令）**。

合格条件は厳しめ：`overall ≥ 8` かつ `human ≥ 4` かつ `value ≥ 4` かつ `safety ≥ 4`。
満たすまでライターが書き直します（最大 `MAX_REVISION_ROUNDS` 回）。

## 出力

- `output/` … 完成記事（先頭コメントに部長評価・書き直し回数を記録）
- `briefs/` … 戦略ブリーフ・リサーチ資料・部長の講評（裏側の確認用）

完成した記事は、そのまま `note_publisher`（投稿ツール）に渡して下書き投稿できます。

## 仕組み・注意

- ② のWeb検索は Claude のサーバーサイド `web_search` ツールを使います（追加のAPI契約は不要、
  Anthropicの利用料に含まれます）。① のnote収集は公開検索を控えめな間隔で利用します。
- 体験談・実績の数字は**捏造しない**設計です。実体験が要る箇所は「（ここにあなたの実例）」と
  空欄になります。投資・健康・お金のテーマは断定/効果保証を避け、注意書きを入れます。
- 品質は上がりますが、1記事に4役＋書き直しが走るため**時間とAPIコスト**がかかります。
  まず1テーマで試し、`config.py` の `MODEL_*`（コスト重視なら一部 `claude-sonnet-4-6` 等）や
  `MAX_REVISION_ROUNDS` で調整してください。

## ファイル構成

```
note_factory/
├─ run.py                 オーケストレーター（4役を連携）
├─ config.py              モデル・ループ回数などの設定
├─ plan.csv              作るテーマ一覧
├─ agents/
│  ├─ llm.py              Claude API ラッパー（thinking/effort/web_search/キャッシュ）
│  ├─ prompts.py          各役のシステムプロンプト（品質の心臓部）
│  ├─ note_source.py      note 売れ筋の取得
│  ├─ trend_scout.py      ① 話題スカウト
│  ├─ web_researcher.py   ② Webリサーチャー
│  ├─ writer.py           ③ ライター
│  └─ editor.py           ④ 部長（採点・合否・修正指示）
├─ output/  briefs/  logs/
```
