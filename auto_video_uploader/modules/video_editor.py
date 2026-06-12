"""FFmpeg による動画自動編集。

背景(画像 or 動画) + ナレーション + ASS テロップ + BGM を合成して
1080x1920 の縦動画 (YouTube Shorts 用) を生成する。
"""

import re
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
    """背景素材を決める。優先順: assets/ の手動素材 → Pexels 自動取得 → 自動生成。"""
    for name in config.BACKGROUND_CANDIDATES:
        p = config.ASSETS_DIR / name
        if p.exists():
            return p

    from modules.background_fetcher import fetch_background

    fetched = fetch_background()
    if fetched:
        return fetched

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


def _wrap_jp(text: str, chars_per_line: int) -> str:
    """日本語は自動折り返しが効かないことがあるため文字数で強制改行する。"""
    escaped = _escape_ass(text)
    lines = [
        escaped[i : i + chars_per_line]
        for i in range(0, len(escaped), chars_per_line)
    ]
    return r"\N".join(lines)


# ランキングのセグメント表示定義: (バナー文言, ASS色 &HAABBGGRR)
ROLE_META = {
    "hook":    ("",       "&H000000FF"),
    "rank3":   ("第3位",  "&H00327FCD"),  # ブロンズ
    "rank2":   ("第2位",  "&H00C0C0C0"),  # シルバー
    "rank1":   ("第1位",  "&H0000D7FF"),  # ゴールド
    "caution": ("注意台", "&H003333FF"),  # 赤
    "summary": ("まとめ", "&H0066CC33"),  # 緑
}

VERDICT_COLOR = {
    "本命": "&H0000D7FF",  # 金
    "対抗": "&H00FFD0A0",  # 水色寄り
    "見送り": "&H003333FF",
    "注意": "&H003333FF",
}


def _emphasize_numbers(text: str, base_color: str) -> str:
    """テロップ内の数字を黄色・大きめに強調する (ASS インライン装飾)。"""
    def repl(m):
        return (
            r"{\c&H0000E5FF&\fscx118\fscy118}" + m.group(0)
            + r"{\c" + base_color.replace("&H00", "&H") + r"&\fscx100\fscy100}"
        )

    return re.sub(r"[0-9]+(?:[./][0-9]+)*", repl, text)


def plan_line_schedule(content: dict, total_sec: float, segment_durations: list | None = None) -> list:
    """ナレーション行ごとの表示スケジュールを計算する。

    戻り値: [{"start","end","text","role"}] 。品質チェック(画面変化の頻度)でも使う。
    """
    schedule = []
    if content.get("format") == "ranking" and segment_durations:
        cursor = 0.0
        for seg, dur in zip(content["segments"], segment_durations):
            weights = [len(l) + 4 for l in seg["lines"]]
            total_w = sum(weights) or 1
            inner = cursor
            for line, w in zip(seg["lines"], weights):
                d = dur * w / total_w
                schedule.append(
                    {"start": inner, "end": min(inner + d, cursor + dur),
                     "text": line, "role": seg["role"]}
                )
                inner += d
            cursor += dur
    else:
        lines = content["script_lines"]
        weights = [len(l) + 4 for l in lines]
        total_w = sum(weights) or 1
        cursor = 0.0
        for i, (line, w) in enumerate(zip(lines, weights)):
            d = total_sec * w / total_w
            schedule.append(
                {"start": cursor, "end": min(cursor + d, total_sec),
                 "text": line, "role": "hook" if i == 0 else "body"}
            )
            cursor += d
    return schedule


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
Style: Title,{font},58,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,3,8,60,60,140,1
Style: Hook,{font},84,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Sub,{font},74,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,3,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    # タイトルは全編表示(文字数で強制改行して画面内に収める)
    events.append(
        f"Dialogue: 0,{_ass_time(0)},{_ass_time(total_sec)},Title,,0,0,0,,{_wrap_jp(title, 15)}"
    )

    # 文字数比で各行に時間を配分(短い行が一瞬で消えないよう +4 の下駄)
    weights = [len(line) + 4 for line in script_lines]
    total_weight = sum(weights)
    cursor = 0.0
    for i, (line, weight) in enumerate(zip(script_lines, weights)):
        dur = total_sec * weight / total_weight
        start, end = cursor, min(cursor + dur, total_sec)
        # 1行目はフック: 画面中央に大きく表示。以降は下部に表示
        style = "Hook" if i == 0 else "Sub"
        wrapped = _wrap_jp(line, 10 if style == "Hook" else 12)
        # フェードイン/アウトと軽いポップ演出で見栄えを上げる
        fx = r"{\fad(150,100)\t(0,120,\fscx108\fscy108)\t(120,240,\fscx100\fscy100)}"
        events.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{fx}{wrapped}"
        )
        cursor = end

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


def build_ranking_ass(content: dict, segment_durations: list, out_path: Path) -> Path:
    """ランキング構成用の ASS 字幕を作る。

    - 上部: タイトル(全編) + セグメントバナー(第3位/第2位/第1位/注意台/まとめ)
    - 中段: 台データカード(台番・REG・合算・判定を強調表示)
    - 下部: ナレーション同期テロップ(短く・大きく・数字強調)
    """
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    font = config.FONT_NAME
    total_sec = sum(segment_durations)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,{font},52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,8,60,60,90,1
Style: Banner,{font},100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,4,8,60,60,250,1
Style: Data,{font},66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,8,0,8,90,90,470,1
Style: Hook,{font},92,&H0000E5FF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Sub,{font},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,7,3,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = [
        f"Dialogue: 0,{_ass_time(0)},{_ass_time(total_sec)},Title,,0,0,0,,{_wrap_jp(content['title'], 18)}"
    ]

    cursor = 0.0
    for seg, dur in zip(content["segments"], segment_durations):
        start, end = cursor, cursor + dur
        label, color = ROLE_META.get(seg["role"], ("", "&H00FFFFFF"))

        # セグメントバナー (ドンと出るポップ演出)
        if label:
            fx = (r"{\c" + color.replace("&H00", "&H") + r"&"
                  r"\fad(120,80)\t(0,140,\fscx126\fscy126)\t(140,260,\fscx100\fscy100)}")
            events.append(
                f"Dialogue: 1,{_ass_time(start)},{_ass_time(end)},Banner,,0,0,0,,{fx}{label}"
            )

        # 台データカード (台番 / REG / 合算 / 判定)
        if seg.get("machine_no") or seg.get("verdict"):
            card_lines = []
            if seg.get("machine_no"):
                card_lines.append(_emphasize_numbers(_escape_ass(seg["machine_no"]), "&H00FFFFFF"))
            nums = []
            if seg.get("reg"):
                nums.append("REG " + seg["reg"])
            if seg.get("total"):
                nums.append("合算 " + seg["total"])
            if nums:
                card_lines.append(_emphasize_numbers(_escape_ass("  ".join(nums)), "&H00FFFFFF"))
            if seg.get("verdict"):
                vcolor = VERDICT_COLOR.get(seg["verdict"], "&H00FFFFFF")
                card_lines.append(
                    r"{\c" + vcolor.replace("&H00", "&H") + r"&\fscx135\fscy135}"
                    + _escape_ass("◆" + seg["verdict"] + "◆")
                )
            if card_lines:
                events.append(
                    f"Dialogue: 1,{_ass_time(start + 0.2)},{_ass_time(end)},Data,,0,0,0,,"
                    + r"{\fad(140,80)}" + r"\N".join(card_lines)
                )
        cursor = end

    # ナレーション同期テロップ
    for item in plan_line_schedule(content, total_sec, segment_durations):
        style = "Hook" if item["role"] == "hook" else "Sub"
        wrapped = _wrap_jp(item["text"], 9 if style == "Hook" else 11)
        base = "&H0000E5FF" if style == "Hook" else "&H00FFFFFF"
        emphasized = _emphasize_numbers(wrapped, base)
        fx = r"{\fad(120,80)\t(0,120,\fscx110\fscy110)\t(120,240,\fscx100\fscy100)}"
        events.append(
            f"Dialogue: 2,{_ass_time(item['start'])},{_ass_time(item['end'])},{style},,0,0,0,,{fx}{emphasized}"
        )

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# 動画合成
# ---------------------------------------------------------------------------

def create_video(
    content: dict,
    audio_path: Path,
    stem: str,
    background_url: str = "",
    segment_durations: list | None = None,
) -> Path:
    """完成動画を videos/ に生成してパスを返す。

    content が format=ranking かつ segment_durations 付きの場合は、
    バナー・台データカード・効果音入りのランキング演出でレンダリングする。
    background_url が指定されていれば、その動画/写真を背景に使う。
    """
    logger = get_logger()
    config.ensure_dirs()

    out_path = config.VIDEOS_DIR / f"{stem}.mp4"
    # ffmpeg は字幕パス対策で videos/ をカレントにして実行するため絶対パスに揃える
    audio_path = Path(audio_path).resolve()
    audio_sec = get_audio_duration(audio_path)
    total_sec = audio_sec + 0.5
    is_ranking = content.get("format") == "ranking" and segment_durations
    logger.info(
        "ナレーション %.1f 秒 / 動画 %.1f 秒で合成します (%s構成)",
        audio_sec, total_sec, "ランキング" if is_ranking else "通常",
    )

    ass_name = f"{stem}.ass"
    if is_ranking:
        build_ranking_ass(content, segment_durations, config.VIDEOS_DIR / ass_name)
    else:
        build_ass_subtitles(
            content["title"], content["script_lines"], audio_sec, config.VIDEOS_DIR / ass_name
        )

    background = None
    if background_url:
        from modules.background_fetcher import download_custom

        background = download_custom(background_url)
    if background is None:
        background = _find_or_create_background()
    is_video_bg = background.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")

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

    # ランキング切り替え時の効果音。assets/se.mp3 があればそれを、
    # 無ければ ffmpeg で短い電子音を合成して使う
    se_times = []
    if is_ranking:
        cum = 0.0
        for d in segment_durations[:-1]:
            cum += d
            se_times.append(cum)
    se_file = Path(config.SE_PATH)
    se_first_index = 3 if use_bgm else 2
    for _ in se_times:
        if se_file.exists():
            cmd += ["-t", "1.2", "-i", str(se_file)]
        else:
            cmd += ["-f", "lavfi", "-t", "0.25", "-i", "sine=frequency=1480"]

    # 字幕ファイルはカレントディレクトリ相対で参照する(パスエスケープ問題の回避)
    ass_filter = f"ass={ass_name}"
    if Path(config.FONT_PATH).exists():
        fonts_dir = str(Path(config.FONT_PATH).parent).replace("\\", "/").replace(":", "\\:")
        ass_filter += f":fontsdir='{fonts_dir}'"

    if is_video_bg:
        vsrc = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,fps={fps}"
        )
    else:
        # 静止画背景はゆっくりズームイン(Ken Burns 効果)で単調さを軽減
        frames = int(total_sec * fps) + fps
        vsrc = (
            f"[0:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
            f"crop={w * 2}:{h * 2},"
            f"zoompan=z='1+0.12*on/{frames}':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},setsar=1"
        )
    vchain = f"{vsrc},{ass_filter}[v]"

    # 音声ミックス: ナレーションを主役に、BGM は必ず小さく、SE は切替時のみ
    bgm_volume = min(config.BGM_VOLUME, 0.35)  # ナレーションより必ず小さく
    parts = ["[1:a]volume=1.0[na]"]
    mix_labels = ["[na]"]
    if use_bgm:
        parts.append(f"[2:a]volume={bgm_volume}[bgm]")
        mix_labels.append("[bgm]")
    for k, t in enumerate(se_times):
        ms = int(t * 1000)
        parts.append(
            f"[{se_first_index + k}:a]volume={config.SE_VOLUME},"
            f"afade=t=out:st=0.12:d=0.12,adelay={ms}|{ms}[se{k}]"
        )
        mix_labels.append(f"[se{k}]")
    if len(mix_labels) == 1:
        achain = "[1:a]volume=1.0[a]"
    else:
        achain = (
            ";".join(parts) + ";" + "".join(mix_labels)
            + f"amix=inputs={len(mix_labels)}:duration=first:"
              f"dropout_transition=2:normalize=0[a]"
        )

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
