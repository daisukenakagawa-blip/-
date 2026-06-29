# 学習済みモデル

## cards_yolo_synthetic.pt

トランプのランク認識用 YOLOv8n モデル（**合成データのみで学習**）。

| 項目 | 内容 |
|------|------|
| アーキテクチャ | YOLOv8n（Ultralytics） |
| クラス | 13 ランク（A,2,3,4,5,6,7,8,9,10,J,Q,K） |
| 学習データ | `scripts/generate_card_dataset.py` による合成画像のみ |
| 入力サイズ | 416 |
| 検証 mAP@0.5 | ≈ 0.91（合成 val） |
| 用途 | YOLO パイプラインの**動作確認・出発点** |

### 使い方
```bash
# 画像 1 枚で確認
python -m blackjack_counter.auto.yolo_counter \
    --weights models/cards_yolo_synthetic.pt --image hand.jpg
# 画面領域を監視
python -m blackjack_counter.auto.yolo_counter \
    --weights models/cards_yolo_synthetic.pt --region 0 0 1280 720
```

### 重要な注意（精度について）
このモデルは **合成カード画像のみ**で学習しているため、実際のゲーム画面の
カードデザイン・フォント・背景が合成と異なると精度が落ちます。実ゲームで
高精度を出すには、対象ゲームのスクリーンショットを少量（数百枚）アノテーション
して**ファインチューニング**してください。

```bash
# 対象ゲームの実データ(YOLO形式)で再学習
python scripts/train_yolo_cards.py --data your_data.yaml \
    --model models/cards_yolo_synthetic.pt --epochs 50
```

学習を一からやり直す場合:
```bash
python scripts/generate_card_dataset.py --out data/cards --train 600 --val 100
python scripts/train_yolo_cards.py --data data/cards/cards.yaml --epochs 80
```
