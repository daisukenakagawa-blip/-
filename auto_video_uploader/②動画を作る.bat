@echo off
chcp 65001 >nul
title ②動画を作る（アップロードはしません）
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

python --version >nul 2>&1
if errorlevel 1 goto :need_setup

echo ============================================================
echo  動画を作成しています（1〜3分かかります）
echo  topics.csv の一番上の「pending」のテーマで作ります
echo ============================================================
echo.

python main.py --no-upload
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo  完成! videos フォルダを開きます。
echo  mp4 ファイルをダブルクリックすると再生できます。
echo ============================================================
explorer videos
pause
exit /b 0

:need_setup
echo 先に「①セットアップ.bat」をダブルクリックしてください。
pause
exit /b 1

:failed
echo.
echo [エラー] 失敗しました。エラー記録をメモ帳で開きます。
echo メモ帳の中身を全部コピーして、チャットに貼り付けてください。
if exist logs\error_log.txt start notepad logs\error_log.txt
pause
exit /b 1
