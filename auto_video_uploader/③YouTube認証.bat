@echo off
chcp 65001 >nul
title ③YouTube認証(最初に1回だけ)
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

if not exist client_secret*.json (
    echo ============================================================
    echo  まだ「client_secret.json」がありません。
    echo.
    echo  これは Google からもらう鍵ファイルで、ここだけは
    echo  Google の決まりで手作業が必要です（1回だけ）。
    echo.
    echo  手順は README.md の「YouTube API 認証の手順」を見るか、
    echo  チャットで「認証の手順を教えて」と聞いてください。
    echo  ダウンロードした JSON を「client_secret.json」という名前で
    echo  このフォルダに置いたら、もう一度このファイルを
    echo  ダブルクリックしてください。
    echo ============================================================
    pause
    exit /b 1
)

echo ブラウザが開いたら、Google アカウントでログインして「許可」を押してください。
python main.py --auth-only
if errorlevel 1 (
    echo.
    echo [エラー] 認証に失敗しました。この画面の文字をコピーして相談してください。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  認証完了! 次からは「④アップロード実行.bat」で
echo  動画作成からYouTube投稿まで全自動で動きます。
echo ============================================================
pause
