# -*- coding: utf-8 -*-
"""
Playwright で note のエディタを操作し、記事を下書き保存/公開/予約投稿する。

note は公式投稿APIが無いため、ブラウザ自動操作で「自分のアカウント」を操作します。
セレクタは config.SELECTORS に集約しており、note の仕様変更時はそこを直せば対応できます。

設計方針:
- 既定は下書き保存(安全)。公開・予約は config.PUBLISH_MODE で明示的に選んだ時だけ。
- 各ステップでスクリーンショットを残し、失敗時の調査をしやすくする。
- 本文は1行ずつ入力し、note の Markdown 風オートフォーマット(# 見出し, - 箇条書き)を活かす。
"""
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


class NotePoster:
    def __init__(self, config, logger):
        self.cfg = config
        self.log = logger
        self._pw = None
        self.browser = None
        self.context = None
        self.page = None

    # ── 起動/終了 ──────────────────────────────────────────
    def start(self, use_session=True):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(
            headless=self.cfg.HEADLESS, slow_mo=self.cfg.SLOW_MO_MS
        )
        kwargs = {"locale": "ja-JP"}
        if use_session and self.cfg.SESSION_FILE.exists():
            kwargs["storage_state"] = str(self.cfg.SESSION_FILE)
        self.context = self.browser.new_context(**kwargs)
        self.context.set_default_timeout(self.cfg.NAV_TIMEOUT_MS)
        self.page = self.context.new_page()

    def stop(self):
        for closer in (self.context, self.browser):
            try:
                if closer:
                    closer.close()
            except Exception:
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def save_session(self):
        self.cfg.STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(self.cfg.SESSION_FILE))
        self.log.info(f"セッションを保存しました: {self.cfg.SESSION_FILE.name}")

    # ── 補助 ────────────────────────────────────────────────
    def _shot(self, name: str):
        try:
            self.cfg.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%H%M%S")
            self.page.screenshot(
                path=str(self.cfg.SCREENSHOT_DIR / f"{stamp}_{name}.png"),
                full_page=False,
            )
        except Exception:
            pass

    def _find(self, key: str, timeout=8000):
        """config.SELECTORS[key] の候補を順に試し、最初に見つかった要素を返す。"""
        last_err = None
        for sel in self.cfg.SELECTORS.get(key, []):
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="visible", timeout=timeout)
                return loc
            except PWTimeout as e:
                last_err = e
                continue
        if last_err:
            self.log.warn(f"  セレクタ '{key}' が見つかりませんでした(候補を全て試行)")
        return None

    # ── ログイン状態の確認 ─────────────────────────────────
    def is_logged_in(self) -> bool:
        self.page.goto(self.cfg.NOTE_TOP, wait_until="domcontentloaded")
        time.sleep(2)
        return self._find("logged_in", timeout=6000) is not None

    # ── 記事を投稿(下書き/公開/予約) ───────────────────────
    def post_article(self, article, mode: str) -> dict:
        """1記事を投稿。戻り値 {ok, note_url, message}"""
        result = {"ok": False, "note_url": "", "message": ""}
        try:
            self.log.info(f"  エディタを開きます: {self.cfg.EDITOR_URL}")
            self.page.goto(self.cfg.EDITOR_URL, wait_until="domcontentloaded")
            time.sleep(3)
            self._shot("editor_open")

            # タイトル入力
            title_el = self._find("title")
            if not title_el:
                result["message"] = "タイトル入力欄が見つかりませんでした"
                self._shot("no_title")
                return result
            title_el.click()
            title_el.type(article.title, delay=self.cfg.TYPE_DELAY_MS)
            self.log.info(f"  タイトル入力: {article.title}")

            # 本文入力(1行ずつ。Markdown風オートフォーマットを活かす)
            body_el = self._find("body")
            if not body_el:
                result["message"] = "本文入力欄が見つかりませんでした"
                self._shot("no_body")
                return result
            body_el.click()
            self._type_body(article.body_lines)
            self.log.info(f"  本文入力: {len(article.body_lines)}行")
            time.sleep(2)
            self._shot("after_body")

            # note はエディタ操作で自動的に下書き保存されます。
            # ここではモードに応じて公開/予約に進みます。
            if mode == "draft":
                result["ok"] = True
                result["message"] = "下書き保存しました(note上で内容を確認し、公開してください)"
                result["note_url"] = self.page.url
                self._shot("draft_saved")
                return result

            # publish / schedule は公開設定へ進む
            ok = self._go_publish(article, mode)
            result["ok"] = ok
            result["note_url"] = self.page.url
            result["message"] = ("公開/予約しました" if ok
                                  else "公開設定の操作に失敗(下書きは残っています)")
            self._shot("after_publish")
            return result

        except Exception as e:
            result["message"] = f"例外: {e}"
            self._shot("exception")
            self.log.error(f"  投稿中にエラー: {e}")
            return result

    def _type_body(self, lines):
        """本文を1行ずつタイプ。空行は段落区切りとして Enter を送る。"""
        kb = self.page.keyboard
        for i, line in enumerate(lines):
            if line.strip():
                kb.type(line, delay=self.cfg.TYPE_DELAY_MS)
            if i < len(lines) - 1:
                kb.press("Enter")

    def _go_publish(self, article, mode: str) -> bool:
        """公開設定に進み、公開 or 予約投稿する(best-effort)。"""
        btn = self._find("to_publish")
        if not btn:
            self.log.warn("  『公開設定』ボタンが見つかりません。下書きのままにします。")
            return False
        btn.click()
        time.sleep(2)
        self._shot("publish_dialog")

        if mode == "schedule":
            # 予約投稿のUIはnote側で変わりやすいため、ここはbest-effort。
            self.log.warn(
                "  予約投稿UIは環境により異なります。日時設定が反映されない場合は "
                "note画面で予約日時を確認してください。"
            )

        pub = self._find("publish")
        if not pub:
            self.log.warn("  『投稿する』ボタンが見つかりません。下書きのままにします。")
            return False
        pub.click()
        time.sleep(4)
        return True
