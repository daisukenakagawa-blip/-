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


def create_thumbnail(title: str, stem: str, badge: str = "狙い台TOP3",
                     punch: str = "") -> Path:
    """固定テンプレートのサムネイルを thumbnails/ に生成してパスを返す。

    テンプレート構成(毎回同じレイアウト・超高コントラスト):
      上: 赤帯 + チャンネルジャンル名 / 中: パンチワード(10文字以内・特大) /
      その下: タイトル(小さめ) / 左下: バッジ / 下: 黄帯
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

    # 中央のパンチワード (10文字以内・特大・超高コントラスト)
    punch = (punch or title)[:10]
    margin = 60
    font_size = 230
    while font_size >= 90:
        font = _load_font(font_size)
        lines = _wrap_text(draw, punch, font, THUMB_W - margin * 2)
        line_height = int(font_size * 1.2)
        if len(lines) * line_height <= 380:
            break
        font_size -= 16
    total_height = len(lines) * line_height
    y = 150 + (400 - total_height) // 2
    for line in lines:
        width = draw.textlength(line, font=font)
        x = (THUMB_W - width) // 2
        # 太い黒縁 + 赤の二重縁で視認性を最大化
        for dx in (-10, -6, 0, 6, 10):
            for dy in (-10, -6, 0, 6, 10):
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        for dx in (-3, 3):
            for dy in (-3, 3):
                draw.text((x + dx, y + dy), line, font=font, fill=(170, 20, 30))
        draw.text((x, y), line, font=font, fill=(255, 230, 60))
        y += line_height

    # パンチワードの下にタイトル (小さめ・白)
    tfont = _load_font(54)
    tlines = _wrap_text(draw, title, tfont, THUMB_W - margin * 2)[:2]
    ty = 575
    for line in tlines:
        width = draw.textlength(line, font=tfont)
        x = (THUMB_W - width) // 2
        for dx in (-3, 0, 3):
            for dy in (-3, 0, 3):
                draw.text((x + dx, ty + dy), line, font=tfont, fill=(0, 0, 0))
        draw.text((x, ty), line, font=tfont, fill=(255, 255, 255))
        ty += 64

    # YouTube サムネイルの上限 2MB に収まるよう品質を下げながら保存
    for quality in (90, 80, 70, 60):
        img.save(out_path, "JPEG", quality=quality)
        if out_path.stat().st_size < 2 * 1024 * 1024:
            break

    get_logger().info("サムネイルを生成しました: %s", out_path)
    return out_path
