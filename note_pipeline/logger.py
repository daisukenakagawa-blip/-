# -*- coding: utf-8 -*-
"""コンソール + ファイルロガー"""
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"pipeline_{stamp}.log"

    def _w(self, level, msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {level} {msg}"
        print(line, flush=True)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def info(self, m): self._w("INFO ", m)
    def warn(self, m): self._w("WARN ", m)
    def error(self, m): self._w("ERROR", m)
