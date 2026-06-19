@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  note 自動投稿ツール セットアップ
echo ============================================
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python が見つかりません。https://www.python.org/ から入れてください。
  echo     インストール時「Add Python to PATH」に必ずチェックを。
  pause & exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo ブラウザ部品(Chromium)をインストールします...
python -m playwright install chromium
echo.
echo 完了。次に「②ログイン.bat」をダブルクリックしてください。
pause
