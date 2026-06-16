"""ユーザー提供の字幕入り画像 + アフレコ で1本の縦動画を組み立てる。

各シーンは画像の字幕に合わせたナレーションを読み上げ、その音声の長さだけ
表示する。画像は 1080x1920 にフィットさせ、背景はぼかしで埋める(黒帯なし)。

音声エンジン:
  - VOICEVOX が起動していれば speaker 13 (青山龍星) を使う(本番・高品質)
  - 無ければ pyopenjtalk(オフライン)で生成し、男性寄りにピッチを下げる(試聴用)
"""

import json
import subprocess
import sys
import wave
from pathlib import Path

import config

W, H, FPS = 1080, 1920, 30
STORY_DIR = config.BASE_DIR / "drafts" / "voiceover_story"


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


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
    payload["speedScale"] = config.VOICEVOX_SPEED
    s = requests.post(f"{base}/synthesis", params={"speaker": spk}, json=payload, timeout=300)
    s.raise_for_status()
    out_wav.write_bytes(s.content)


def _synth_openjtalk(text: str, out_wav: Path) -> None:
    """pyopenjtalk で合成し、男性寄りにピッチを下げて保存する。"""
    import numpy as np
    import pyopenjtalk

    wav, sr = pyopenjtalk.tts(text)
    wav = wav / (np.abs(wav).max() + 1e-9) * 0.95
    pcm = (wav * 32767).astype(np.int16)
    raw = out_wav.with_suffix(".raw.wav")
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    # asetrate でピッチを下げ、atempo で長さを戻す(=低い男性声)。整音も少し。
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw), "-af",
         f"asetrate={sr}*0.82,aresample=44100,atempo=1.22,"
         "highpass=f=80,lowpass=f=9000,dynaudnorm",
         "-ar", "44100", "-ac", "1", str(out_wav)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    raw.unlink(missing_ok=True)


def synth_scene(text: str, out_wav: Path, use_vv: bool) -> None:
    if use_vv:
        _synth_voicevox(text, out_wav)
    else:
        _synth_openjtalk(text, out_wav)


def main() -> int:
    manifest = json.loads((STORY_DIR / "manifest.json").read_text(encoding="utf-8"))
    scenes = manifest["scenes"]
    config.ensure_dirs()
    work = config.AUDIO_DIR
    use_vv = _voicevox_available()
    print(f"音声エンジン: {'VOICEVOX(青山龍星)' if use_vv else 'pyopenjtalk(男性ピッチ)'}")

    seg_wavs, durations = [], []
    for sc in scenes:
        text = sc["narration"]
        wav = work / f"vo_seg{sc['index']}.wav"
        synth_scene(text, wav, use_vv)
        dur = _wav_duration(wav)
        min_sec = float(sc.get("min_sec") or 0)
        if min_sec > dur + 0.05:
            padded = work / f"vo_seg{sc['index']}_pad.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav), "-af",
                 f"apad=pad_dur={min_sec - dur:.2f}", "-t", f"{min_sec:.2f}",
                 "-ar", "44100", "-ac", "1", str(padded)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )
            wav, dur = padded, min_sec
        # 各シーン末尾に軽い間(0.35秒)
        gap = 0.35
        padded2 = work / f"vo_seg{sc['index']}_g.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav), "-af", f"apad=pad_dur={gap}",
             "-ar", "44100", "-ac", "2", str(padded2)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        seg_wavs.append(padded2)
        durations.append(dur + gap)
        print(f"  シーン{sc['index']}: {dur + gap:.2f}秒  「{text}」")

    # ナレーション結合
    voice = work / "voiceover_full.wav"
    cmd = ["ffmpeg", "-y"]
    for p in seg_wavs:
        cmd += ["-i", str(p)]
    n = len(seg_wavs)
    cmd += ["-filter_complex",
            "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]",
            "-map", "[a]", "-ar", "44100", "-ac", "2", str(voice)]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    total = sum(durations)

    # 各シーン画像を 1080x1920 にフィット(背景ぼかし)してクリップ化
    parts, filters = [], []
    cmd = ["ffmpeg", "-y"]
    for i, sc in enumerate(scenes):
        img = STORY_DIR / sc["image"]
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{durations[i]:.2f}", "-i", str(img)]
    for i in range(n):
        # bg: cover してぼかし / fg: contain / 重ねる
        filters.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},boxblur=24:2,setsar=1[bg{i}];"
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,setsar=1[fg{i}];"
            f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:format=auto,"
            f"format=yuv420p,fps={FPS}[v{i}]"
        )
    concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    filter_complex = ";".join(filters) + ";" + concat

    # BGM(任意)
    bgm = Path(config.BGM_PATH)
    voice_idx = n
    cmd += ["-i", str(voice)]
    if bgm.exists():
        cmd += ["-stream_loop", "-1", "-i", str(bgm)]
        bgm_idx = n + 1
        filter_complex += (
            f";[{voice_idx}:a]volume=1.0[na];"
            f"[{bgm_idx}:a]volume={min(config.BGM_VOLUME,0.18)}[bg];"
            f"[na][bg]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]"
        )
    else:
        filter_complex += f";[{voice_idx}:a]volume=1.0[a]"

    out = config.VIDEOS_DIR / "voiceover_story.mp4"
    cmd += ["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]",
            "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print(proc.stderr[-1500:])
        return 1
    print(f"完成: {out}  (合計 {total:.1f}秒)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
