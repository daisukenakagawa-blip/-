@echo off
chcp 65001 >nul
title ①セットアップ(最初に1回だけ)
cd /d "%~dp0"

echo ============================================================
echo  自動セットアップを開始します(5〜10分かかります)
echo  途中で [Y] か「同意」を聞かれたら Y を押して Enter してください
echo ============================================================
echo.

rem ---- ZIPを展開せずに実行していないかチェック ----
if not exist requirements.txt (
    echo [エラー] 必要なファイルが見つかりません。
    echo.
    echo ZIP ファイルを「すべて展開」せずに、ZIP の中から直接
    echo ダブルクリックしている可能性があります。
    echo.
    echo 【直し方】
    echo  1. ダウンロードした ZIP ファイルを右クリック
    echo  2. 「すべて展開」をクリック
    echo  3. 展開してできたフォルダの中の auto_video_uploader を開く
    echo  4. その中の「①セットアップ.bat」をダブルクリック
    pause
    exit /b 1
)

rem ---- winget(Windows標準のインストーラー)の確認 ----
where winget >nul 2>&1
if errorlevel 1 (
    echo [エラー] winget が見つかりません。
    echo Microsoft Store を開いて「アプリ インストーラー」を更新してから、
    echo もう一度このファイルをダブルクリックしてください。
    pause
    exit /b 1
)

rem ---- インストール直後のソフトをこの画面でも使えるように場所を追加 ----
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

rem ---- [1/4] Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [1/4] Python をインストールしています...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
) else (
    echo [1/4] Python はすでに入っています
)

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python のインストールが終わりました。
    echo 一度この画面を閉じて、もう一度「①セットアップ.bat」をダブルクリックしてください。
    pause
    exit /b 0
)

rem ---- [2/4] FFmpeg(動画作成ソフト) ----
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [2/4] FFmpeg をインストールしています...
    winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
) else (
    echo [2/4] FFmpeg はすでに入っています
)

rem ---- [3/4] Python の部品 ----
echo [3/4] 必要な部品をインストールしています(数分かかります)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [エラー] 部品のインストールに失敗しました。
    echo すぐ上に表示されている赤い文字がエラーの内容です。
    echo その部分を 撮影(Windowsキー+Shift+S)して相談してください。
    pause
    exit /b 1
)

rem ---- [4/4] 設定ファイル(Windows用フォント設定込み) ----
echo [4/4] 設定ファイルを作成しています...
if not exist .env (
    powershell -NoProfile -Command "(Get-Content .env.example) -replace '^FONT_PATH=.*','FONT_PATH=C:/Windows/Fonts/meiryob.ttc' -replace '^FONT_NAME=.*','FONT_NAME=Meiryo' | Set-Content -Encoding UTF8 .env"
)

echo.
echo ============================================================
echo  セットアップ完了!
echo.
echo  次は「②動画を作る.bat」をダブルクリックしてください。
echo  動画が1本自動で作られます。
echo ============================================================
pause
