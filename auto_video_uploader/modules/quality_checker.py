"""動画完成後の自動品質チェック。

6つの基準を 100 点満点で採点し、QUALITY_MIN_SCORE (既定 80) 未満なら
原因を logs/quality_log.txt に残して再生成の対象にする。

配点:
  冒頭2秒の強さ        20点
  テロップの見やすさ    20点
  情報の分かりやすさ    15点
  画面変化の多さ        15点
  音声の自然さ          15点
  サムネの強さ          15点
"""

import re
from datetime import datetime
from pathlib import Path

import config
from modules.logger import get_logger
from modules.video_editor import plan_line_schedule

_HOOK_PUNCH = re.compile(r"[0-9!?!?]")
_DIGIT = re.compile(r"[0-9]")
# フックの引きの強さ: 疑問 / 断言パンチ / 意外性ワードのいずれか
_HOOK_STRONG = re.compile(
    r"[0-9!?！？]|ない\?|よな|ません|ほぼ|実は|逆|闇|ヤバ|9割|知らな|気づ|"
    r"負け|勝て|嘘|間違|やりがち|やってる|大事|だけ"
)


def _score_hook(content: dict) -> tuple:
    """冒頭2秒の強さ (20点)。"""
    reasons = []
    score = 0
    lines = content.get("script_lines") or []
    first = lines[0] if lines else ""
    segs = content.get("segments") or []
    if segs and segs[0].get("role") == "hook":
        score += 8
    else:
        reasons.append("冒頭がフック構成になっていない")
    if first and len(first) <= 15:
        score += 6
    else:
        reasons.append(f"フックが長すぎる ({len(first)}文字 > 15文字)")
    if _HOOK_STRONG.search(first):
        score += 6
    else:
        reasons.append("フックの引きが弱い (疑問・断言・意外性を入れる)")
    return score, reasons


def _score_telop(content: dict) -> tuple:
    """テロップの見やすさ (20点)。短い行 = 大きく表示できる。"""
    reasons = []
    lines = content.get("script_lines") or []
    if not lines:
        return 0, ["テロップが存在しない"]
    max_len = max(len(l) for l in lines)
    avg_len = sum(len(l) for l in lines) / len(lines)
    score = 10
    if max_len > 15:
        over = max_len - 15
        score -= min(10, over * 2)
        reasons.append(f"長すぎるテロップがある (最長{max_len}文字 > 15)")
    if avg_len <= 12:
        score += 10
    elif avg_len <= 15:
        score += 6
        reasons.append(f"テロップの平均文字数が多め ({avg_len:.1f}文字)")
    else:
        reasons.append(f"テロップ全体が長文寄り (平均{avg_len:.1f}文字)")
    return max(0, score), reasons


_PROB_RE = re.compile(r"\d+\s*[/／]\s*\d+")
_RANK_RE = re.compile(r"第[0-9一二三]位|ランキング")
_COMMENT_RE = re.compile(r"コメント|どう思|賛成|反対|あなたは")


def _score_info(content: dict) -> tuple:
    """情報の分かりやすさ / 引き込み (15点)。構成ごとに評価軸を変える。"""
    reasons = []
    if content.get("format") == "monologue":
        segs = content.get("segments") or []
        text = " ".join(content.get("script_lines") or [])
        score = 9
        # 各話題が2行以上の中身を持つ (薄い展開を減点)
        thin = sum(1 for s in segs if len(s.get("lines") or []) < 2 and s.get("role") != "hook")
        if thin:
            score -= min(4, thin)
            reasons.append(f"中身の薄い展開が{thin}個ある")
        # 生の確率・ランキングが残っていたら大幅減点 (データ羅列禁止)
        if _PROB_RE.search(text):
            score -= 5
            reasons.append("テロップに生の確率がある。意味に翻訳すること")
        if _RANK_RE.search(text):
            score -= 5
            reasons.append("ランキング表現が残っている")
        # コメント誘導
        last = " ".join(segs[-1].get("lines") or []) if segs else text
        if _COMMENT_RE.search(last):
            score += 6
        else:
            reasons.append("まとめにコメント誘導が無い")
        return max(0, min(15, score)), reasons
    if content.get("format") == "ranking":
        data_segs = [s for s in content["segments"] if s["role"] in ("rank1", "rank2", "rank3", "caution")]
        if not data_segs:
            return 0, ["ランキングセグメントが無い"]
        filled = sum(
            1 for s in data_segs
            if s.get("machine_no") and s.get("reg") and s.get("total") and s.get("verdict")
        )
        ratio = filled / len(data_segs)
        if filled > 0:
            score = round(12 * ratio)
            if ratio < 1:
                reasons.append(f"台データ(台番/REG/合算/判定)が欠けている ({filled}/{len(data_segs)}件)")
        else:
            # あるある・診断・クイズ等のデータ無しジャンルは「なるほど密度」で評価:
            # 各セグメントに2行以上の説明(理由・オチ)があるか
            lines_ok = sum(1 for s in data_segs if len(s.get("lines") or []) >= 2)
            score = round(12 * lines_ok / len(data_segs))
            if lines_ok < len(data_segs):
                reasons.append("理由・オチの薄いセグメントがある (各2行以上が目安)")
        # コメント誘導 (まとめにコメントを促す一言があるか)
        summary = next((s for s in content["segments"] if s["role"] == "summary"), None)
        if summary and any("コメント" in l for l in summary["lines"]):
            score += 3
        else:
            reasons.append("まとめにコメント誘導が無い")
        return score, reasons
    lines = content.get("script_lines") or []
    digit_lines = sum(1 for l in lines if _DIGIT.search(l))
    ratio = digit_lines / len(lines) if lines else 0
    if ratio >= 0.3:
        return 15, reasons
    reasons.append(f"数字を含むテロップが少ない ({digit_lines}/{len(lines)}行)")
    return round(15 * ratio / 0.3), reasons


def _score_motion(content: dict, total_sec: float, segment_durations: list | None) -> tuple:
    """画面変化の多さ (15点)。テロップ・バナーの切り替え間隔で評価。"""
    reasons = []
    schedule = plan_line_schedule(content, total_sec, segment_durations)
    if not schedule:
        return 0, ["表示要素が無い"]
    changes = len(schedule) + (len(content.get("segments", [])) if content.get("format") == "ranking" else 0)
    interval = total_sec / max(1, changes)
    if interval <= 1.5:
        return 15, reasons
    if interval <= 2.0:
        reasons.append(f"画面変化がやや少ない (平均{interval:.1f}秒間隔)")
        return 12, reasons
    if interval <= 2.5:
        reasons.append(f"画面変化が少ない (平均{interval:.1f}秒間隔)")
        return 8, reasons
    reasons.append(f"画面変化が大幅に不足 (平均{interval:.1f}秒間隔)")
    return 4, reasons


def _score_voice(content: dict, audio_path: Path, total_sec: float) -> tuple:
    """音声の自然さ (15点)。エンジン品質と読み上げ速度で評価。"""
    reasons = []
    score = 0
    if Path(audio_path).suffix.lower() == ".wav":  # VOICEVOX
        score += 10
    else:
        score += 5
        reasons.append("gTTS音声のため自然さが劣る (VOICEVOXを推奨)")
    chars = sum(len(l) for l in content.get("script_lines") or [])
    speed = chars / total_sec if total_sec else 0
    if 5.0 <= speed <= 9.0:
        score += 5
    else:
        reasons.append(f"読み上げ速度が不自然 ({speed:.1f}文字/秒)")
        score += 2
    return score, reasons


def _score_thumbnail(content: dict, thumb_path: Path) -> tuple:
    """サムネの強さ (15点)。"""
    reasons = []
    score = 0
    title = content.get("title", "")
    if Path(thumb_path).exists() and Path(thumb_path).stat().st_size > 10_000:
        score += 5
    else:
        reasons.append("サムネイルが生成されていない")
    punch = (content.get("thumb_text") or "").strip()
    if punch and len(punch) <= 10:
        score += 5
    else:
        reasons.append("サムネ用パンチワード(10文字以内)が無い")
    if content.get("format") == "monologue":
        # ジャグラーマンは感情ワード重視。数字は必須にしない
        if len(title) <= 28:
            score += 5
        else:
            reasons.append(f"タイトルが長い ({len(title)}文字>28)")
    elif _DIGIT.search(title) and len(title) <= 28:
        score += 5
    else:
        reasons.append("タイトルが28文字超か数字を含まない")
    return score, reasons


def evaluate(
    content: dict,
    audio_path: Path,
    total_sec: float,
    thumb_path: Path,
    segment_durations: list | None = None,
) -> tuple:
    """品質を採点する。戻り値: (score, breakdown dict, reasons list)。"""
    checks = {
        "冒頭2秒の強さ": _score_hook(content),
        "テロップの見やすさ": _score_telop(content),
        "情報の分かりやすさ": _score_info(content),
        "画面変化の多さ": _score_motion(content, total_sec, segment_durations),
        "音声の自然さ": _score_voice(content, audio_path, total_sec),
        "サムネの強さ": _score_thumbnail(content, thumb_path),
    }
    breakdown = {name: s for name, (s, _) in checks.items()}
    reasons = [r for _, (_, rs) in checks.items() for r in rs]
    return sum(breakdown.values()), breakdown, reasons


def log_quality(stem: str, attempt: int, score: int, breakdown: dict, reasons: list) -> None:
    """品質チェック結果を logs/quality_log.txt に記録する。"""
    config.ensure_dirs()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"[{timestamp}] stem={stem} attempt={attempt} score={score} "
        + " ".join(f"{k}:{v}" for k, v in breakdown.items())
    ]
    for r in reasons:
        lines.append(f"  - {r}")
    with open(config.QUALITY_LOG_TXT, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    get_logger().info("品質スコア: %d点 (attempt=%d)", score, attempt)
