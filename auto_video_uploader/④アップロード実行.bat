@echo off
chcp 65001 >nul
title ④アップロード実行(動画作成 → YouTube投稿まで全自動)
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

python --version >nul 2>&1
if errorlevel 1 (
    echo 先に「①セットアップ.bat」をダブルクリックしてください。
    pause
    exit /b 1
)
if not exist token.json (
    echo 先に「③YouTube認証.bat」をダブルクリックしてください。
    pause
    exit /b 1
)

echo ============================================================
echo  topics.csv の一番上の「pending」のテーマで
echo  動画作成 → YouTube アップロードまで全自動で実行します
echo ============================================================
echo.

python main.py
if errorlevel 1 (
    echo.
    echo [エラー] 失敗しました。logs\error_log.txt に詳細があります。
    echo この画面の文字をコピーして相談してください。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  完了! 投稿結果は uploaded_log.csv に記録されています。
echo  （topics.csv の date が未来の日付なら 19:00 の予約投稿です）
echo ============================================================
pause
