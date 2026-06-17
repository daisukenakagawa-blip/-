"""可愛い系の女性 VOICEVOX ボイスのサンプル音声を生成する。
GitHub Actions 上で VOICEVOX を起動して実行する想定。出力は voice_samples/ に保存。
"""

import subprocess
import sys
from pathlib import Path

import requests

import config

# 可愛い系の女性候補 (VOICEVOX の style id: 名前)
SPEAKERS = {
    0: "shikoku-metan-amaama",   # 四国めたん(あまあま) 甘くて可愛い
    1: "zundamon-amaama",        # ずんだもん(あまあま) マスコット系
    8: "kasukabe-tsumugi",       # 春日部つむぎ 明るい女の子
    14: "meimei-himari",         # 冥鳴ひまり 落ち着いた可愛さ
    20: "mochiko",               # もち子さん やわらかい
}

TEXT = "この台、最後どうなったと思う? 1083ゲームでビッグ1、バケ7。これは6あるぞ?"


def synth(text: str, speaker: int, out_wav: Path) -> None:
    base = config.VOICEVOX_URL.rstrip("/")
    q = requests.post(f"{base}/audio_query", params={"text": text, "speaker": speaker}, timeout=30)
    q.raise_for_status()
    payload = q.json()
    payload["speedScale"] = config.VOICEVOX_SPEED
    s = requests.post(f"{base}/synthesis", params={"speaker": speaker}, json=payload, timeout=300)
    s.raise_for_status()
    out_wav.write_bytes(s.content)


def main() -> int:
    outdir = config.BASE_DIR / "voice_samples"
    outdir.mkdir(exist_ok=True)
    for spk, name in SPEAKERS.items():
        wav = outdir / f"spk{spk}.wav"
        synth(TEXT, spk, wav)
        mp3 = outdir / f"spk{spk}_{name}.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav), "-b:a", "128k", str(mp3)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        wav.unlink(missing_ok=True)
        print(f"sample spk{spk} = {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
