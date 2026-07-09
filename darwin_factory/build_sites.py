#!/usr/bin/env python3
"""LP を公開用ディレクトリにビルドする。

sites/ を出力先へコピーし、各 LP 内の __FORM_URL__ プレースホルダを
ventures.json の form_url に置換する。form_url が未設定の事業は
CTA が「準備中」表示になるよう "#" に置換する。

使い方: python build_sites.py <出力先ディレクトリ>
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("使い方: python build_sites.py <出力先ディレクトリ>")
    out = Path(sys.argv[1])
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "sites", out)

    ventures = json.loads((ROOT / "ventures.json").read_text(encoding="utf-8"))["ventures"]
    for v in ventures:
        if not v.get("site"):
            continue
        index = out / Path(v["site"]).name / "index.html"
        if not index.exists():
            continue
        html = index.read_text(encoding="utf-8")
        html = html.replace("__FORM_URL__", v.get("form_url") or "#")
        index.write_text(html, encoding="utf-8")
        print(f"built: {index} (form={'設定済み' if v.get('form_url') else '未設定'})")


if __name__ == "__main__":
    main()
