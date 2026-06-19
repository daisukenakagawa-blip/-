# -*- coding: utf-8 -*-
"""
note 自動記事生産ライン ── オーケストレーター

niches.csv（作るニッチの待ち行列）から未生産のテーマを取り、
  ① note_factory で執筆（リサーチ→編集部AIの精査つき）
  ② 完成記事を produced/ に集約し、produced_log.csv に記録（重複防止）
  ③（任意）note_publisher で下書き投稿
を自動で回します。毎日自動実行（Windowsタスク）にも対応。

使い方:
  python pipeline.py                 # DAILY_COUNT 本を生産
  python pipeline.py --count 3       # 本数を指定
  python pipeline.py --dry-run       # 実行計画だけ表示（API呼び出しなし）
  python pipeline.py --publish draft # この実行だけ投稿モードを上書き
  python pipeline.py --discover      # note_niche を回して候補を提案（キュー補充の参考）
"""
import csv
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from logger import Logger


# ── キュー / 記録 ───────────────────────────────────────────
def load_queue():
    """niches.csv（列: theme, price, genre）を読む。"""
    rows = []
    if config.NICHES_FILE.exists():
        with open(config.NICHES_FILE, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                theme = (row.get("theme") or "").strip()
                if theme and not theme.startswith("#"):
                    rows.append({
                        "theme": theme,
                        "price": (row.get("price") or "").strip(),
                        "genre": (row.get("genre") or theme).strip(),
                    })
    return rows


def load_done():
    done = set()
    if config.PRODUCED_LOG.exists():
        with open(config.PRODUCED_LOG, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("theme"):
                    done.add(row["theme"])
    return done


def record_done(theme, status, files):
    exists = config.PRODUCED_LOG.exists()
    with open(config.PRODUCED_LOG, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["produced_at", "theme", "status", "files"])
        if not exists:
            w.writeheader()
        w.writerow({
            "produced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "theme": theme, "status": status,
            "files": " | ".join(Path(p).name for p in files),
        })


def pick_next(queue, done, n):
    return [q for q in queue if q["theme"] not in done][:n]


# ── サブプロセスでツールを実行 ─────────────────────────────
def _run(cmd, cwd, log):
    log.info(f"    $ {' '.join(cmd)}  (cwd={cwd.name})")
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            log.warn(f"    終了コード {proc.returncode}: {(proc.stderr or '').strip()[:300]}")
        return proc.returncode == 0
    except Exception as e:
        log.error(f"    実行失敗: {e}")
        return False


def factory_write(theme, price, log):
    """note_factory で1本書く。生成された新規ファイルのパス一覧を返す。"""
    out_dir = config.FACTORY_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.glob("*.md"))
    cmd = [config.PYTHON, "run.py", theme]
    if price:
        cmd += ["--price", price]
    _run(cmd, config.FACTORY_DIR, log)
    after = set(out_dir.glob("*.md"))
    return sorted(after - before)


def publish_drafts(files, mode, log):
    if mode not in ("draft", "publish") or not files:
        return
    if not (config.PUBLISHER_DIR / "state" / "note_session.json").exists():
        log.warn("    note未ログインのため投稿スキップ（note_publisher/login.py を先に実行）。")
        return
    cmd = [config.PYTHON, "publisher.py", "--mode", mode] + [str(p) for p in files]
    _run(cmd, config.PUBLISHER_DIR, log)


# ── メインの生産ループ ──────────────────────────────────────
def produce(count, publish_mode, dry_run, log):
    queue = load_queue()
    done = load_done()
    if not queue:
        log.error(f"キューが空です。{config.NICHES_FILE.name} にニッチを追加してください。")
        return
    todo = pick_next(queue, done, count)
    if not todo:
        log.info("未生産のニッチがありません。niches.csv を補充するか --discover を実行してください。")
        return

    log.info(f"本日の生産対象 {len(todo)}本 / 投稿モード: {publish_mode}"
             + ("（DRY-RUN）" if dry_run else ""))
    config.PRODUCED_DIR.mkdir(parents=True, exist_ok=True)

    for i, niche in enumerate(todo, 1):
        log.info(f"[{i}/{len(todo)}] ニッチ: {niche['theme']}  (¥{niche['price'] or '提案'})")
        if dry_run:
            log.info("    （DRY-RUN: note_factory で執筆 → produced/ へ集約 → 記録）")
            continue

        files = factory_write(niche["theme"], niche["price"], log)
        if not files:
            log.warn("    記事が生成されませんでした（APIキー/エラーの可能性）。スキップ。")
            record_done(niche["theme"], "failed", [])
            continue

        # produced/ に集約
        collected = []
        for src in files:
            dst = config.PRODUCED_DIR / src.name
            try:
                shutil.copy2(src, dst)
                collected.append(dst)
            except Exception as e:
                log.warn(f"    集約失敗 {src.name}: {e}")
        status = "要確認" if any("要確認" in p.name for p in collected) else "ok"
        log.info(f"    ✅ 生産: {[p.name for p in collected]}（{status}）")

        publish_drafts(collected, publish_mode, log)
        record_done(niche["theme"], status, collected)

        if i < len(todo):
            time.sleep(config.INTERVAL_BETWEEN)


def discover(log):
    """note_niche を実行して、狙い目ニッチの提案を出す（キュー補充の参考）。"""
    log.info("note_niche で狙い目ニッチを探索します…")
    _run([config.PYTHON, "find.py"], config.NICHE_DIR, log)
    log.info(f"結果は {config.NICHE_DIR / 'output'} を確認し、"
             f"良いものを {config.NICHES_FILE.name} に転記してください。")


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(config.FACTORY_DIR / ".env")   # APIキーは factory の .env を共用
        load_dotenv(config.BASE_DIR / ".env")
    except ImportError:
        pass

    args = sys.argv[1:]
    log = Logger(config.LOG_DIR)

    if "--discover" in args:
        discover(log)
        return

    count = config.DAILY_COUNT
    if "--count" in args:
        i = args.index("--count")
        if i + 1 < len(args):
            count = int(args[i + 1])
    publish_mode = config.PUBLISH_MODE
    if "--publish" in args:
        i = args.index("--publish")
        if i + 1 < len(args):
            publish_mode = args[i + 1]
    dry_run = "--dry-run" in args

    log.info("=" * 55)
    log.info("note 自動記事生産ライン 稼働")
    log.info("=" * 55)
    produce(count, publish_mode, dry_run, log)
    log.info("完了。produced/ と produced_log.csv を確認してください。")


if __name__ == "__main__":
    main()
