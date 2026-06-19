# -*- coding: utf-8 -*-
"""
最初に1回だけ実行: ブラウザでnoteに手動ログインし、セッションを保存します。

この方式なら、メール/パスワード・Googleログイン・2段階認証のいずれでも対応でき、
パスワードをツールに保存する必要もありません(最も安全で壊れにくい)。

使い方:
    python login.py
ブラウザが開いたら、いつも通りnoteにログインしてください。
ログインが完了したら、ターミナルで Enter を押すとセッションが保存されます。
"""
import config
from modules.logger import Logger
from modules.note_poster import NotePoster


def main():
    log = Logger(config.LOG_DIR)
    poster = NotePoster(config, log)
    # ログイン作業は必ず画面表示で行う
    config.HEADLESS = False
    poster.start(use_session=False)
    try:
        log.info("noteのログインページを開きます。ブラウザでログインしてください。")
        poster.page.goto(config.NOTE_LOGIN, wait_until="domcontentloaded")
        input(
            "\n▶ ブラウザでnoteにログインを完了したら、ここで Enter を押してください...\n"
        )
        if poster.is_logged_in():
            poster.save_session()
            log.info("✅ ログイン状態を保存しました。次回からは publisher.py が使えます。")
        else:
            log.warn(
                "ログイン状態を確認できませんでした。ログイン後にもう一度お試しください。"
            )
            poster.save_session()  # 念のため保存(誤検知対策)
    finally:
        poster.stop()


if __name__ == "__main__":
    main()
