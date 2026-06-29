"""YOLO（Ultralytics）によるトランプ認識アダプタ。

画像（BGR）を入力に、検出されたカードのランク・中心座標・信頼度を返す。
カウントにはランクのみ必要なため、モデルのクラスはランク（A,2..10,J,Q,K）を想定。

学習済み重み（.pt / .onnx）が必要。重みは scripts/train_yolo_cards.py で
合成データから自前学習できる（外部データ・アカウント不要）。
"""

from __future__ import annotations

from dataclasses import dataclass

from blackjack_counter.auto.vision_tracker import DetectedCard


@dataclass(frozen=True, slots=True)
class YoloConfig:
    weights: str
    conf_threshold: float = 0.45
    iou_threshold: float = 0.5
    imgsz: int = 640
    device: str = "cpu"  # "cpu" / "cuda:0"


class YoloCardRecognizer:
    """YOLO でカードを検出し、ランク付きで返す（検出＋認識を 1 モデルで実施）。"""

    def __init__(self, config: YoloConfig) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ultralytics が必要です: pip install ultralytics"
            ) from exc
        self._cfg = config
        self._model = YOLO(config.weights)
        # クラス id -> ランク文字列
        self._names: dict[int, str] = dict(self._model.names)

    @property
    def class_names(self) -> dict[int, str]:
        return self._names

    def recognize(self, frame_bgr) -> list[DetectedCard]:
        """1 フレームを認識し、検出カード（中心は 0..1 正規化）を返す。"""
        h, w = frame_bgr.shape[:2]
        results = self._model.predict(
            source=frame_bgr,
            conf=self._cfg.conf_threshold,
            iou=self._cfg.iou_threshold,
            imgsz=self._cfg.imgsz,
            device=self._cfg.device,
            verbose=False,
        )
        cards: list[DetectedCard] = []
        for res in results:
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                rank = self._names.get(cls_id, str(cls_id))
                cards.append(
                    DetectedCard(
                        rank=rank,
                        cx=(x1 + x2) / 2 / w,
                        cy=(y1 + y2) / 2 / h,
                        confidence=conf,
                    )
                )
        return cards
