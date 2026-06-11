"""FFmpeg による動画自動編集。

背景(画像 or 動画) + ナレーション + ASS テロップ + BGM を合成して
1080x1920 の縦動画 (YouTube Shorts 用) を生成する。
"""

import subprocess
from pathlib import Path

import config
from modules.logger import get_logger


def _run(cmd: list, cwd: Path | None = None) -> None:
    proc = subprocess.run(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        tail = proc.stderr[-2000:] if proc.stderr else ""
        raise RuntimeError(f"コマンド失敗: {' '.join(cmd[:2])} ...\n{tail}")


def get_audio_duration(path: Path) -> float:
    """ffprobe で音声の長さ(秒)を取得する。"""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(path),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe 失敗: {proc.stderr[-500:]}")
    return float(proc.stdout.strip())


# ---------------------------------------------------------------------------
# 背景
# ---------------------------------------------------------------------------

def _find_or_create_background() -> Path:
    """assets/ の背景素材を探し、無ければグラデーション画像を自動生成する。"""
    for name in config.BACKGROUND_CANDIDATES:
        p = config.ASSETS_DIR / name
        if p.exists():
            return p

    generated = config.ASSETS_DIR / "background_auto.png"
    if generated.exists():
        return generated

    from PIL import Image

    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    img = Image.new("RGB", (w, h))
    px = img.load()
    # 紺 → 紫の縦グラデーション
    top, bottom = (12, 16, 48), (72, 24, 96)
    for y in range(h):
        t = y / (h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = color
    img.save(generated)
    get_logger().info("背景素材が無いためグラデーション背景を生成しました: %s", generated)
    return generated


# ---------------------------------------------------------------------------
# ASS テロップ
# ---------------------------------------------------------------------------

def _ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass_subtitles(title: str, script_lines: list, total_sec: float, out_path: Path) -> Path:
    """タイトル(上部固定) + 台本行(下部・読み上げに同期)の ASS 字幕を作る。

    行ごとの表示時間は文字数に比例して配分する。
    """
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    font = config.FONT_NAME

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font},60,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,2,8,60,60,140,1
Style: Sub,{font},68,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,6,2,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    # タイトルは全編表示
    events.append(
        f"Dialogue: 0,{_ass_time(0)},{_ass_time(total_sec)},Title,,0,0,0,,{_escape_ass(title)}"
    )

    # 文字数比で各行に時間を配分(短い行が一瞬で消えないよう +4 の下駄)
    weights = [len(line) + 4 for line in script_lines]
    total_weight = sum(weights)
    cursor = 0.0
    for line, weight in zip(script_lines, weights):
        dur = total_sec * weight / total_weight
        start, end = cursor, min(cursor + dur, total_sec)
        events.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Sub,,0,0,0,,{_escape_ass(line)}"
        )
        cursor = end

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# 動画合成
# ---------------------------------------------------------------------------

def create_video(title: str, script_lines: list, audio_path: Path, stem: str) -> Path:
    """完成動画を videos/ に生成してパスを返す。"""
    logger = get_logger()
    config.ensure_dirs()

    out_path = config.VIDEOS_DIR / f"{stem}.mp4"
    audio_sec = get_audio_duration(audio_path)
    total_sec = audio_sec + 0.5
    logger.info("ナレーション %.1f 秒 / 動画 %.1f 秒で合成します", audio_sec, total_sec)

    ass_name = f"{stem}.ass"
    build_ass_subtitles(title, script_lines, audio_sec, config.VIDEOS_DIR / ass_name)

    background = _find_or_create_background()
    is_video_bg = background.suffix.lower() in (".mp4", ".mov", ".mkv")

    w, h, fps = config.VIDEO_WIDTH, config.VIDEO_HEIGHT, config.VIDEO_FPS

    cmd = ["ffmpeg", "-y"]
    if is_video_bg:
        cmd += ["-stream_loop", "-1", "-i", str(background)]
    else:
        cmd += ["-loop", "1", "-i", str(background)]
    cmd += ["-i", str(audio_path)]

    bgm = Path(config.BGM_PATH)
    use_bgm = bgm.exists()
    if use_bgm:
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]

    # 字幕ファイルはカレントディレクトリ相対で参照する(パスエスケープ問題の回避)
    ass_filter = f"ass={ass_name}"
    if Path(config.FONT_PATH).exists():
        fonts_dir = str(Path(config.FONT_PATH).parent).replace("\\", "/").replace(":", "\\:")
        ass_filter += f":fontsdir='{fonts_dir}'"

    vchain = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,fps={fps},{ass_filter}[v]"
    )

    if use_bgm:
        achain = (
            f"[1:a]volume=1.0[na];"
            f"[2:a]volume={config.BGM_VOLUME}[bgm];"
            f"[na][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
        )
    else:
        achain = "[1:a]volume=1.0[a]"

    cmd += [
        "-filter_complex", f"{vchain};{achain}",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{total_sec:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]

    logger.info("FFmpeg 実行中...")
    _run(cmd, cwd=config.VIDEOS_DIR)
    logger.info("動画を生成しました: %s", out_path)
    return out_path
