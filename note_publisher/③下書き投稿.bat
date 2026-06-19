@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo note_writer/articles の記事を「下書き」として投稿します(安全)。
python publisher.py --mode draft
echo.
echo note の「下書き一覧」で内容と有料設定を確認し、公開してください。
pause
