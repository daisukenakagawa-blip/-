@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  note リサーチツール セットアップ
echo ============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python が見つかりません。https://www.python.org/ からインストールしてください。
  echo     インストール時に「Add Python to PATH」に必ずチェックを入れてください。
  pause
  exit /b 1
)
echo 必要な部品をインストールします...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo 完了しました。次は「②リサーチ実行.bat」をダブルクリックしてください。
pause
