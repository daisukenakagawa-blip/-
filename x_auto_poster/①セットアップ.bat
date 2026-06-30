@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  X 自動投稿ツール セットアップ
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [情報] Python が見つかりません。インストールします...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Python をインストールしました。いったんこのウィンドウを閉じて、もう一度①を実行してください。
    pause
    exit /b
)

echo [1/2] 必要な部品をインストールしています...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.

echo [2/2] 設定ファイル (.env) を準備しています...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo .env を作成しました。
) else (
    echo .env は既にあります。
)
echo.
echo セットアップ完了です。
echo 次に「②かんたん設定.bat」でキーを貼り付けてください。
pause
