@echo off
chcp 65001 >nul
title ⑦毎日自動実行の解除
cd /d "%~dp0"

schtasks /delete /f /tn AutoVideoUploader
if errorlevel 1 goto :notfound

echo.
echo 毎日自動実行を解除しました。
pause
exit /b 0

:notfound
echo.
echo 自動実行は設定されていないようです。何もしませんでした。
pause
exit /b 0
