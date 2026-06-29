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

## 3. 自動カウント（YOLO 画像認識）— canvas 描画ゲーム向け ★AI 物体検出

DOM で取れない canvas 描画のゲーム向けに、**YOLO（Ultralytics）の物体検出 AI** で
画面からカードを認識します。学習データは合成で自前生成するため、**外部データも
アカウントも不要**です（学習は CPU でも可、GPU 推奨）。

パイプライン: **YOLO カード認識 → Hi-Lo → True Count → ベット助言**

```bash
pip install ultralytics mss

# 1) 合成データ生成
python scripts/generate_card_dataset.py --out data/cards --train 600 --val 100
# 2) 学習（GPU があれば --device 0）
python scripts/train_yolo_cards.py --data data/cards/cards.yaml --epochs 80
cp runs/detect/cards/weights/best.pt models/cards_yolo.pt
# 3a) 画像 1 枚で動作確認
python -m blackjack_counter.auto.yolo_counter --weights models/cards_yolo.pt --image hand.jpg
# 3b) 画面領域を監視して自動カウント
python -m blackjack_counter.auto.yolo_counter \
    --weights models/cards_yolo.pt --region 0 0 1280 720
```

**仕組み**: 画面を YOLO で認識 → 位置ベースのトラッカーで二重カウントを防ぎながら
カウントエンジンへ投入。認識精度は学習量（エポック数・データ量・GPU）に比例します。
実ゲームで使う場合は、対象ゲームのスクリーンショットを少量アノテーションして
ファインチューニングすると精度が上がります（設計: `docs/BLACKJACK_COUNTER_AI_SPEC.md`）。

> 軽量な代替として、OpenCV テンプレート照合版（`auto/vision_counter.py`）も同梱。
> 学習不要だが対象ゲームごとの校正が必要です。

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
