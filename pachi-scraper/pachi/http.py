"""マナーを守った取得処理（robots.txt遵守・アクセス間隔・リトライ）。

ローカルファイルパス / file:// URL も受け付けるため、
ネットワーク無しのデモやテストにも同じ経路を使える。
"""

from __future__ import annotations

import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

import requests

RETRIES = 3
RETRY_WAIT = 5.0  # 秒


class RobotsDisallowedError(RuntimeError):
    pass


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        rate_limit_seconds: float = 3.0,
        respect_robots_txt: bool = True,
    ):
        self.user_agent = user_agent
        self.rate_limit_seconds = rate_limit_seconds
        self.respect_robots_txt = respect_robots_txt
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._last_request_at = 0.0
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def fetch(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme in ("", "file"):
            path = parsed.path if parsed.scheme == "file" else url
            return Path(path).read_text(encoding="utf-8")

        if self.respect_robots_txt and not self._robots_allows(url):
            raise RobotsDisallowedError(f"robots.txt がアクセスを許可していません: {url}")

        self._throttle()
        last_error: Exception | None = None
        for attempt in range(RETRIES):
            try:
                resp = self._session.get(url, timeout=30)
                resp.raise_for_status()
                # 文字化け対策: ヘッダに charset が無いサイトが多いので内容から推定
                if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                    resp.encoding = resp.apparent_encoding
                return resp.text
            except requests.RequestException as exc:
                last_error = exc
                if attempt < RETRIES - 1:
                    time.sleep(RETRY_WAIT * (attempt + 1))
        raise RuntimeError(f"取得に失敗しました: {url}") from last_error

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._robots_cache.get(origin)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{origin}/robots.txt")
            try:
                rp.read()
            except OSError:
                # robots.txt が取得できない場合は許可とみなす（一般的な慣行）
                rp.allow_all = True
            self._robots_cache[origin] = rp
        return rp.can_fetch(self.user_agent, url)
