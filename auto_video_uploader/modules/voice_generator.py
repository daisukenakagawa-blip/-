"""台本からナレーション音声を生成する。

エンジン:
  - voicevox: ローカルの VOICEVOX エンジン (http://127.0.0.1:50021) を使用。高品質な日本語音声。
  - gtts:     Google Translate TTS。APIキー不要・ネット接続のみで動くフォールバック。
"""

from pathlib import Path

import requests

import config
from modules.logger import get_logger


def _narration_text(script_lines: list) -> str:
    # 行間に「。」を入れて読み上げの間を作る
    parts = []
    for line in script_lines:
        line = line.strip()
        if line and line[-1] not in "。!?!?":
            line += "。"
        parts.append(line)
    return "".join(parts)


def _generate_voicevox(text: str, out_path: Path) -> Path:
    """VOICEVOX エンジンで wav を生成する。"""
    base = config.VOICEVOX_URL.rstrip("/")
    speaker = config.VOICEVOX_SPEAKER

    query = requests.post(
        f"{base}/audio_query",
        params={"text": text, "speaker": speaker},
        timeout=30,
    )
    query.raise_for_status()

    synthesis = requests.post(
        f"{base}/synthesis",
        params={"speaker": speaker},
        json=query.json(),
        timeout=300,
    )
    synthesis.raise_for_status()

    out_path = out_path.with_suffix(".wav")
    out_path.write_bytes(synthesis.content)
    return out_path


def _generate_gtts(text: str, out_path: Path) -> Path:
    """gTTS で mp3 を生成する。"""
    from gtts import gTTS

    out_path = out_path.with_suffix(".mp3")
    gTTS(text=text, lang=config.GTTS_LANG).save(str(out_path))
    return out_path


def find_existing_audio(stem: str) -> Path | None:
    """同じ slug の生成済み音声があれば返す(再実行時のスキップ用)。"""
    for ext in (".wav", ".mp3"):
        p = config.AUDIO_DIR / f"{stem}{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def generate(script_lines: list, stem: str) -> Path:
    """ナレーション音声を生成し、ファイルパスを返す。"""
    logger = get_logger()
    text = _narration_text(script_lines)
    out_base = config.AUDIO_DIR / stem

    # auto: VOICEVOX が起動していれば自動で使い、無ければ gTTS にフォールバック
    if config.TTS_ENGINE in ("voicevox", "auto"):
        try:
            logger.info("VOICEVOX で音声を生成します (speaker=%s)", config.VOICEVOX_SPEAKER)
            return _generate_voicevox(text, out_base)
        except Exception as e:
            if config.TTS_ENGINE == "voicevox":
                logger.warning("VOICEVOX での生成に失敗 (%s)。gTTS にフォールバックします", e)
            else:
                logger.info("VOICEVOX が起動していないため gTTS を使用します")

    logger.info("gTTS で音声を生成します")
    return _generate_gtts(text, out_base)
