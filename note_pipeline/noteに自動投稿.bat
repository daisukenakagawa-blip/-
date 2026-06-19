@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  記事を作って、noteに「下書き」として自動投稿します
echo ============================================
echo  ※ 先に note_publisher の「ログイン」を済ませておいてください
echo.
python pipeline.py --publish draft
echo.
echo 完了。noteの「下書き一覧」を開いて、
echo  ・「（ここにあなたの実体験）」を1行うめる
echo  ・有料ラインと価格を設定
echo してから「公開」してください。
pause
