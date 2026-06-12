"""Pillow によるサムネイル自動生成 (1280x720 JPEG)。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config
from modules.logger import get_logger

THUMB_W, THUMB_H = 1280, 720


def _load_font(size: int):
    font_path = Path(config.FONT_PATH)
    if font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception:
            pass
    get_logger().warning(
        "フォントが見つかりません (%s)。デフォルトフォントを使用します(日本語は崩れる可能性あり)",
        config.FONT_PATH,
    )
    try:
        return ImageFont.load_default(size)  # Pillow 10.1+ はサイズ指定可
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list:
    """ピクセル幅で日本語テキストを折り返す。"""
    lines, current = [], ""
    for ch in text:
        candidate = current + ch
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def create_thumbnail(title: str, stem: str, badge: str = "狙い台TOP3") -> Path:
    """固定テンプレートのサムネイルを thumbnails/ に生成してパスを返す。

    テンプレート構成(毎回同じレイアウト):
      上: 赤帯 + チャンネルジャンル名 / 中: タイトル(黄・黒縁) /
      左下: バッジ(TOP3 等) / 下: 黄帯
    """
    config.ensure_dirs()
    out_path = config.THUMBNAILS_DIR / f"{stem}.jpg"

    img = Image.new("RGB", (THUMB_W, THUMB_H), (10, 12, 34))
    draw = ImageDraw.Draw(img)

    # 固定テンプレート: 上の赤帯
    draw.rectangle([0, 0, THUMB_W, 110], fill=(200, 24, 36))
    band_font = _load_font(64)
    band_text = "ジャグラー予想"
    bw = draw.textlength(band_text, font=band_font)
    draw.text(((THUMB_W - bw) // 2, 18), band_text, font=band_font, fill=(255, 255, 255))

    # 下の黄帯
    draw.rectangle([0, THUMB_H - 84, THUMB_W, THUMB_H], fill=(255, 200, 0))
    foot_font = _load_font(44)
    foot_text = "毎日19時投稿 #Shorts"
    fw = draw.textlength(foot_text, font=foot_font)
    draw.text(((THUMB_W - fw) // 2, THUMB_H - 72), foot_text, font=foot_font, fill=(20, 20, 20))

    # 左下のバッジ
    if badge:
        badge_font = _load_font(58)
        bw2 = draw.textlength(badge, font=badge_font)
        bx, by = 36, THUMB_H - 190
        draw.rounded_rectangle(
            [bx - 16, by - 10, bx + bw2 + 16, by + 76], radius=14, fill=(200, 24, 36)
        )
        draw.text((bx, by), badge, font=badge_font, fill=(255, 230, 60))

    # 中央のタイトル
    font_size = 100
    margin = 70
    while font_size >= 44:
        font = _load_font(font_size)
        lines = _wrap_text(draw, title, font, THUMB_W - margin * 2)
        line_height = int(font_size * 1.25)
        if len(lines) * line_height <= THUMB_H - 420:
            break
        font_size -= 8
    else:
        font = _load_font(44)
        lines = _wrap_text(draw, title, font, THUMB_W - margin * 2)
        line_height = 56

    total_height = len(lines) * line_height
    y = 130 + (THUMB_H - 320 - total_height) // 2
    for line in lines:
        width = draw.textlength(line, font=font)
        x = (THUMB_W - width) // 2
        # 黒縁取り
        for dx in (-4, -2, 0, 2, 4):
            for dy in (-4, -2, 0, 2, 4):
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 230, 60))
        y += line_height

    # YouTube サムネイルの上限 2MB に収まるよう品質を下げながら保存
    for quality in (90, 80, 70, 60):
        img.save(out_path, "JPEG", quality=quality)
        if out_path.stat().st_size < 2 * 1024 * 1024:
            break

    get_logger().info("サムネイルを生成しました: %s", out_path)
    return out_path
