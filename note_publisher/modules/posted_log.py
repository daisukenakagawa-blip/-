# -*- coding: utf-8 -*-
"""投稿済み記録による重複投稿防止(auto_video_uploader と同じ思想)。"""
import csv
from datetime import datetime
from pathlib import Path

FIELDS = ["posted_at", "file", "title", "mode", "note_url"]


def load_posted_files(path: Path) -> set:
    done = set()
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("file"):
                    done.add(row["file"])
    return done


def record(path: Path, file_name: str, title: str, mode: str, note_url: str = ""):
    exists = path.exists()
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow({
            "posted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file": file_name,
            "title": title,
            "mode": mode,
            "note_url": note_url,
        })
