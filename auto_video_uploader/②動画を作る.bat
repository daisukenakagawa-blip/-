@echo off
chcp 65001 >nul
title ②動画を作る(アップロードはしません)
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

python --version >nul 2>&1
if errorlevel 1 (
    echo 先に「①セットアップ.bat」をダブルクリックしてください。
    pause
    exit /b 1
)

echo ============================================================
echo  動画を作成しています(1〜3分かかります)
echo  topics.csv の一番上の「pending」のテーマで作ります
echo ============================================================
echo.

python main.py --no-upload
if errorlevel 1 (
    echo.
    echo [エラー] 動画の作成に失敗しました。
    echo この画面の文字をコピーして相談してください。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  完成! videos フォルダを開きます。
echo  mp4 ファイルをダブルクリックすると再生できます。
echo ============================================================
explorer videos
pause
