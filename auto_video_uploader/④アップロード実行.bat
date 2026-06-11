@echo off
chcp 65001 >nul
title ④アップロード実行（動画作成 → YouTube投稿まで全自動）
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

python --version >nul 2>&1
if errorlevel 1 goto :need_setup
if not exist token.json goto :need_auth

echo ============================================================
echo  動画作成 → YouTube アップロードまで全自動で実行します
echo ============================================================
echo.

python main.py
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo  完了! 投稿結果は uploaded_log.csv に記録されています。
echo ============================================================
pause
exit /b 0

:need_setup
echo 先に「①セットアップ.bat」をダブルクリックしてください。
pause
exit /b 1

:need_auth
echo 先に「③YouTube認証.bat」をダブルクリックしてください。
pause
exit /b 1

:failed
echo.
echo [エラー] 失敗しました。エラー記録をメモ帳で開きます。
echo メモ帳の中身を全部コピーして、チャットに貼り付けてください。
if exist logs\error_log.txt start notepad logs\error_log.txt
pause
exit /b 1
