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


def create_thumbnail(title: str, stem: str) -> Path:
    """タイトル入りサムネイルを thumbnails/ に生成してパスを返す。"""
    config.ensure_dirs()
    out_path = config.THUMBNAILS_DIR / f"{stem}.jpg"

    img = Image.new("RGB", (THUMB_W, THUMB_H))
    px = img.load()
    top, bottom = (12, 16, 48), (120, 28, 40)
    for y in range(THUMB_H):
        t = y / (THUMB_H - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(THUMB_W):
            px[x, y] = color

    draw = ImageDraw.Draw(img)

    # 上下の帯
    draw.rectangle([0, 0, THUMB_W, 14], fill=(255, 200, 0))
    draw.rectangle([0, THUMB_H - 14, THUMB_W, THUMB_H], fill=(255, 200, 0))

    font_size = 96
    margin = 70
    while font_size >= 40:
        font = _load_font(font_size)
        lines = _wrap_text(draw, title, font, THUMB_W - margin * 2)
        line_height = int(font_size * 1.25)
        if len(lines) * line_height <= THUMB_H - 200:
            break
        font_size -= 8
    else:
        font = _load_font(40)
        lines = _wrap_text(draw, title, font, THUMB_W - margin * 2)
        line_height = 50

    total_height = len(lines) * line_height
    y = (THUMB_H - total_height) // 2
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
