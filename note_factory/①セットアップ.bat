@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  note編集部 セットアップ
echo ============================================
where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python が必要です。https://www.python.org/ から導入してください。
  pause & exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo 次に .env に ANTHROPIC_API_KEY を設定し、「②記事を作る.bat」を実行してください。
pause
