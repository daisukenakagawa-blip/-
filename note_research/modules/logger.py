# -*- coding: utf-8 -*-
"""シンプルなロガー(コンソール + ファイル)"""
import sys
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"research_{stamp}.log"

    def _write(self, level: str, msg: str):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {level} {msg}"
        print(line, flush=True)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def info(self, msg: str):
        self._write("INFO ", msg)

    def warn(self, msg: str):
        self._write("WARN ", msg)

    def error(self, msg: str):
        self._write("ERROR", msg)
