"""ユーザー提供の字幕入り画像/動画 + アフレコ で1本の縦動画を組み立てる。

各シーンは「画像」または「動画クリップ」。ナレーション(narration)があれば
その読み上げ長だけ表示し、無い動画シーンはクリップ自身の尺と音声を使う。
出力は 1080x1920。画像は背景ぼかしでフィット、動画は左右をトリムして全画面。

音声エンジン:
  - VOICEVOX が起動していれば config.VOICEVOX_SPEAKER を使う(本番・高品質)
  - 無ければ pyopenjtalk(オフライン)で生成(ローカル試聴用)。VOICE_STYLE で声色。
"""

import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import config

W, H, FPS = 1080, 1920, 30
STORY = os.getenv("STORY", "voiceover_story")
STORY_DIR = config.BASE_DIR / "drafts" / STORY
VOICE_STYLE = os.getenv("VOICE_STYLE", "female").lower()
# BGM の音量(ナレーション=1.0 に対する比)。env で調整可。
BGM_VOL = float(os.getenv("VO_BGM_VOLUME", "0.32"))
# アフレコの話速(早口目)。VOICEVOX の speedScale / pyopenjtalk の atempo に反映。
VO_SPEED = float(os.getenv("VO_SPEED", "1.3"))

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTS = (".mov", ".mp4", ".mkv", ".webm", ".m4v")


def _run(cmd: list) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg失敗: {' '.join(map(str, cmd[:6]))}…\n{p.stderr[-1200:]}")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(path)],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip() or 0)


def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return bool(out.stdout.strip())


# --- 音声合成 ---------------------------------------------------------------

def _voicevox_available() -> bool:
    try:
        import requests
        requests.get(f"{config.VOICEVOX_URL.rstrip('/')}/version", timeout=3)
        return True
    except Exception:
        return False


def _synth_voicevox(text: str, out_wav: Path) -> None:
    import requests
    base = config.VOICEVOX_URL.rstrip("/")
    spk = config.VOICEVOX_SPEAKER
    q = requests.post(f"{base}/audio_query", params={"text": text, "speaker": spk}, timeout=30)
    q.raise_for_status()
    payload = q.json()
    payload["speedScale"] = VO_SPEED
    s = requests.post(f"{base}/synthesis", params={"speaker": spk}, json=payload, timeout=300)
    s.raise_for_status()
    out_wav.write_bytes(s.content)


def _synth_openjtalk(text: str, out_wav: Path) -> None:
    import numpy as np
    import pyopenjtalk
    wav, sr = pyopenjtalk.tts(text)
    wav = wav / (np.abs(wav).max() + 1e-9) * 0.95
    pcm = (wav * 32767).astype(np.int16)
    raw = out_wav.with_suffix(".raw.wav")
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    rate, tempo = (0.82, 1.22) if VOICE_STYLE == "male" else (1.08, 0.926)
    tempo = max(0.5, min(2.0, tempo * VO_SPEED))  # 早口目を反映
    _run(["ffmpeg", "-y", "-i", str(raw), "-af",
          f"asetrate={sr}*{rate},aresample=44100,atempo={tempo},"
          "highpass=f=90,lowpass=f=11000,dynaudnorm", "-ar", "44100", "-ac", "1", str(out_wav)])
    raw.unlink(missing_ok=True)


def _synth(text: str, out_wav: Path, use_vv: bool) -> None:
    if use_vv:
        _synth_voicevox(text, out_wav)
    else:
        _synth_openjtalk(text, out_wav)


# --- シーンの正規化 (1080x1920 クリップ + Dぴったりの音声) -------------------

def _audio_exact(src: Path | None, D: float, out: Path) -> None:
    """src 音声を長さ D ぴったり(不足は無音パディング)で書き出す。src=None は無音。"""
    if src is None:
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
              "-t", f"{D:.2f}", "-ar", "44100", "-ac", "2", str(out)])
    else:
        _run(["ffmpeg", "-y", "-i", str(src), "-af", "aresample=44100,apad",
              "-t", f"{D:.2f}", "-ar", "44100", "-ac", "2", str(out)])


def _image_clip(img: Path, D: float, out: Path) -> None:
    fc = (
        f"[0:v]split=2[a][b];"
        f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2,setsar=1[bg];"
        f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p,fps={FPS}[v]"
    )
    _run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{D:.2f}",
          "-i", str(img), "-filter_complex", fc, "-map", "[v]",
          "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])


def _video_clip(vid: Path, D: float, out: Path) -> None:
    # 左右をトリムして縦全画面に(ピラーボックスの黒帯を除去)
    _run(["ffmpeg", "-y", "-t", f"{D:.2f}", "-i", str(vid), "-an",
          "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"setsar=1,fps={FPS},format=yuv420p",
          "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS), str(out)])


def main() -> int:
    manifest = json.loads((STORY_DIR / "manifest.json").read_text(encoding="utf-8"))
    scenes = manifest["scenes"]
    config.ensure_dirs()
    work = config.AUDIO_DIR
    use_vv = _voicevox_available()
    eng = f"VOICEVOX(speaker={config.VOICEVOX_SPEAKER})" if use_vv else f"pyopenjtalk({VOICE_STYLE})"
    print(f"ストーリー: {STORY} / 音声エンジン: {eng}")

    clip_paths, aud_paths, total = [], [], 0.0
    for i, sc in enumerate(scenes):
        media = STORY_DIR / sc["image"]
        is_video = media.suffix.lower() in VIDEO_EXTS
        narration = (sc.get("narration") or "").strip()
        min_sec = float(sc.get("min_sec") or 0)
        gap = 0.3

        narr_wav = None
        if narration:
            narr_wav = work / f"{STORY}_n{i}.wav"
            _synth(narration, narr_wav, use_vv)
            L = _wav_duration(narr_wav)
            D = max(L, min_sec) + gap
        elif is_video:
            D = max(_media_duration(media), min_sec or 0.5)
        else:
            D = max(min_sec, 3.0)

        # 映像クリップ
        clip = work / f"{STORY}_v{i}.mp4"
        if is_video:
            _video_clip(media, D, clip)
        else:
            _image_clip(media, D, clip)
        clip_paths.append(clip)

        # 音声(長さ D ぴったり)
        aud = work / f"{STORY}_a{i}.wav"
        if narr_wav is not None:
            _audio_exact(narr_wav, D, aud)
        elif is_video and sc.get("keep_audio") and _has_audio(media):
            tmp = work / f"{STORY}_va{i}.wav"
            _run(["ffmpeg", "-y", "-i", str(media), "-vn", "-ar", "44100", "-ac", "2", str(tmp)])
            _audio_exact(tmp, D, aud)
            tmp.unlink(missing_ok=True)
        else:
            _audio_exact(None, D, aud)
        aud_paths.append(aud)

        total += D
        label = narration or ("[動画]" if is_video else "[無音]")
        print(f"  シーン{sc.get('index', i+1)}: {D:.2f}秒  「{label}」")

    # 映像を連結 (同一設定なのでコピー連結)
    listf = work / f"{STORY}_list.txt"
    listf.write_text("".join(f"file '{p}'\n" for p in clip_paths), encoding="utf-8")
    video_only = work / f"{STORY}_video.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
          "-c", "copy", str(video_only)])

    # ナレーション/音声を連結
    voice = work / f"{STORY}_voice.wav"
    cmd = ["ffmpeg", "-y"]
    for p in aud_paths:
        cmd += ["-i", str(p)]
    n = len(aud_paths)
    cmd += ["-filter_complex",
            "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]",
            "-map", "[a]", "-ar", "44100", "-ac", "2", str(voice)]
    _run(cmd)

    # 最終合成 (映像 + 音声 + BGM)
    out = config.VIDEOS_DIR / f"{STORY}.mp4"
    bgm = Path(config.BGM_PATH)
    cmd = ["ffmpeg", "-y", "-i", str(video_only), "-i", str(voice)]
    if bgm.exists():
        cmd += ["-stream_loop", "-1", "-i", str(bgm),
                "-filter_complex",
                f"[1:a]volume=1.0[na];[2:a]volume={BGM_VOL}[bg];"
                "[na][bg]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(out)]
    _run(cmd)

    # 中間ファイル掃除
    for p in clip_paths + aud_paths + [video_only, voice, listf]:
        Path(p).unlink(missing_ok=True)
    for sc_i in range(len(scenes)):
        (work / f"{STORY}_n{sc_i}.wav").unlink(missing_ok=True)

    print(f"完成: {out}  (合計 {total:.1f}秒)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
