"""合成データからトランプ認識用 YOLO を学習する。

GPU があれば自動利用、無ければ CPU。学習後の重みは
runs/detect/<name>/weights/best.pt に出力される。

使い方:
    # 1) データ生成
    python scripts/generate_card_dataset.py --out data/cards --train 400 --val 80
    # 2) 学習
    python scripts/train_yolo_cards.py --data data/cards/cards.yaml --epochs 50
    # 3) 重みを配置
    cp runs/detect/cards/weights/best.pt models/cards_yolo.pt
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="トランプ認識 YOLO の学習")
    ap.add_argument("--data", default="data/cards/cards.yaml")
    ap.add_argument("--model", default="yolov8n.pt", help="ベース重み")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None, help="cpu / 0 など（省略で自動）")
    ap.add_argument("--name", default="cards")
    args = ap.parse_args(argv)

    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        name=args.name,
        seed=42,
    )
    print("学習完了。best.pt を models/ にコピーして使用してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
