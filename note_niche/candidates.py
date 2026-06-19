# -*- coding: utf-8 -*-
"""
候補キーワード（ロングテールのニッチ）を用意する。

優先順位:
  1) コマンドライン引数（直接指定）
  2) candidates.csv（手動で用意したリスト）
  3) AI生成（seeds.csv の各シードからロングテール候補を量産）
  4) seeds.csv をそのまま候補に
"""
import csv
import os

CANDIDATE_SYSTEM = """\
あなたは note の市場分析が得意な編集者です。
与えられた大ジャンルから、「無名の個人でも売れる可能性がある、具体的で尖ったロングテールの
ニッチ・キーワード」を考えます。

良いニッチの条件:
- 対象読者が絞られている（職業・状況・レベル・地域などで具体化）
- 悩みが深く、解決にお金を払う動機がある
- 「○○とは」のような一般情報ではなく、特定の人の特定の課題

出力は、検索キーワードとして使える短い語句のみ。1行に1つ、説明や記号を付けない。
例: 「経理 在宅 副業 簿記2級」「保育士 転職 失敗 体験」「ADHD 片付け 一人暮らし」
"""


def load_list_file(path):
    out = []
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                kw = row[0].strip()
                if kw and not kw.startswith("#") and kw.lower() not in ("keyword", "seed", "theme"):
                    out.append(kw)
    return out


def ai_expand(seed, n, model, logger=None):
    """1シードから n 個のロングテール候補をAIで生成。失敗時は空リスト。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return []
    try:
        import anthropic
    except ImportError:
        return []
    user = (f"大ジャンル: {seed}\n\nこのジャンルの中で、無名でも売れる可能性がある"
            f"ロングテールのニッチ・キーワードを{n}個、1行に1つ挙げてください。")
    try:
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=model, max_tokens=1500,
            system=[{"type": "text", "text": CANDIDATE_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            msg = stream.get_final_message()
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        cands = []
        for line in text.splitlines():
            kw = line.strip().lstrip("-・0123456789.　 ").strip()
            if kw and len(kw) >= 3:
                cands.append(kw)
        return cands[:n]
    except Exception as e:
        if logger:
            logger.warn(f"AI候補生成に失敗（{seed}）: {e}")
        return []


def build_candidates(args, cfg, logger=None):
    # 1) 引数
    direct = [a for a in args if not a.startswith("--")]
    if direct:
        return list(dict.fromkeys(direct))
    # 2) candidates.csv
    manual = load_list_file(cfg.BASE_DIR / "candidates.csv")
    if manual:
        return list(dict.fromkeys(manual))
    # 3) seeds + AI
    seeds = load_list_file(cfg.SEEDS_FILE)
    if not seeds:
        return []
    cands = []
    if cfg.USE_AI_CANDIDATES and os.environ.get("ANTHROPIC_API_KEY"):
        for seed in seeds:
            if logger:
                logger.info(f"  AI候補生成: '{seed}'")
            cands += ai_expand(seed, cfg.CANDIDATES_PER_SEED, cfg.AI_MODEL, logger)
    # 4) フォールバック: シードそのもの
    if not cands:
        if logger:
            logger.warn("AI候補が無いため、seeds をそのまま候補にします（candidates.csv 推奨）。")
        cands = seeds
    return list(dict.fromkeys(cands))
