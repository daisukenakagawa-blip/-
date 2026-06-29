# ブラックジャック カードカウンター（手動 + 自動）

カードカウンティングの**学習・練習用ツール**です。3 つの使い方があります。

> カードカウンティングは数学的な戦略であり違法行為ではありません。本ツールは
> **画面に表示された情報を読み取って人間に提示するだけ**で、自動ベット・自動プレイ・
> 送金・通信傍受などは一切行いません。対象は無料の練習用ブラックジャックです
> （オンラインカジノ＝実マネー賭博は対象外）。

---

## 1. すぐ使える（登録・追加インストール不要）— 手動カウンター

Python だけで動きます。カードが出るたびにキーを押すと、Running/True Count と
ベット助言を表示します。

```bash
cd /home/user/-
PYTHONPATH=src python3 -m blackjack_counter            # Hi-Lo, 6 デッキ
PYTHONPATH=src python3 -m blackjack_counter --strategy ko --decks 8
```

入力: `2`〜`9` / `0` または `t`=10 / `j q k a` / `u`=取消 / `r`=リセット /
`h`=ヘルプ / `quit`=終了。複数枚まとめ入力も可（例 `k 5 a`）。

---

## 2. 自動カウント（DOM 読取）— Web ブラックジャック向け ★おすすめ

ブラウザ上の HTML/JS 製ブラックジャックの**カードを自動で読み取り**、勝手に
カウントします。学習・GPU 不要。

### 準備（初回のみ）
```bash
pip install playwright
playwright install chromium      # ブラウザ本体を取得
```

### 実行
```bash
# このリポジトリの自作ゲームを自動カウント
PYTHONPATH=src python3 -m blackjack_counter.auto.browser_counter \
    --url file://$PWD/blackjack.html --decks 1

# 任意の練習サイト（カードを指す CSS セレクタを指定）
PYTHONPATH=src python3 -m blackjack_counter.auto.browser_counter \
    --url "https://example.com/blackjack" \
    --player-selector "#player-cards .card-rank" \
    --dealer-selector "#dealer-cards .card-rank"
```

ブラウザが開き、配られたカードに合わせてターミナルに次のように自動表示されます:
```
RC=  +2  TC= +0.3  残 5.9デッキ  見  6枚  | ほぼ中立 → 1 ユニット
```

**仕組み**: 表向きカードの DOM テキストをポーリングし、前回との差分で
「新たに公開されたカード」だけをカウント（二重カウント防止）。`deck` 変数が
読めるゲームでは残枚数の増加からリシャッフルを自動検知してリセットします。

**対応範囲**: カードが DOM 要素（テキスト）として描画されるゲーム。サイトごとに
`--player-selector` / `--dealer-selector` を調整してください。

---

## 3. 自動カウント（画像認識）— canvas 描画ゲーム向け（実験的・要校正）

DOM で取れない canvas 描画のゲーム向けに、OpenCV のテンプレート照合で画面から
カードを認識します（ディープラーニング不使用＝学習・GPU 不要）。

```bash
pip install opencv-python mss numpy
```

`blackjack_counter.auto.vision_counter` に、カード矩形検出（`find_card_regions`）と
ランク照合（`match_rank`）を実装。対象ゲームの見た目に合わせた**参照テンプレートの
校正**が必要です（精度は描画に依存）。高い汎用性が必要な場合は、設計仕様書
`docs/BLACKJACK_COUNTER_AI_SPEC.md` の YOLO/CNN 方式へ拡張してください。

---

## テスト

```bash
pip install pytest
python3 -m pytest tests/ -q
```

## 構成

```
src/blackjack_counter/
├── domain/types.py          # Rank/Suit/Card など値オブジェクト
├── counting/
│   ├── strategies.py        # Hi-Lo / KO / Omega II（方式追加が容易）
│   ├── shoe.py              # 残デッキ・消化率
│   └── engine.py            # カウントエンジン（純粋・テスト済）
├── advisor/advisor.py       # ベット助言
├── cli.py                   # 手動カウンター（対話型）
└── auto/
    ├── card_diff.py         # 差分検出（二重カウント防止・純粋）
    ├── browser_counter.py   # 自動カウント（DOM/Playwright）
    └── vision_counter.py    # 自動カウント（画像認識/OpenCV）
```

## 登録が必要なもの

| 使い方 | 登録/準備 |
|--------|-----------|
| 1. 手動カウンター | **不要**（Python のみ） |
| 2. 自動（DOM 読取） | `pip install playwright` + `playwright install chromium`。アカウント登録は**不要** |
| 3. 自動（画像認識） | `pip install opencv-python mss numpy`。アカウント登録は**不要** |

いずれも**アカウント登録・課金・APIキーは一切不要**です。
