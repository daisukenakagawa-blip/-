@echo off
chcp 65001 >nul
title ⑥毎日自動投稿の設定
cd /d "%~dp0"

echo ============================================================
echo  毎日決まった時刻に自動で X に投稿する設定です
echo  ※その時刻にパソコンの電源が入っている必要があります
echo ============================================================
echo.
set "ST=08:00"
set /p ST=実行時刻を半角で入力 例 08:00 ※Enterだけなら08:00:
if "%ST%"=="" set "ST=08:00"

schtasks /create /f /tn XAutoPoster /sc daily /st %ST% /tr "\"%~dp0run_daily.bat\""
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo  設定完了!毎日 %ST% に自動で投稿されます。
echo  ネタはスマホのスプレッドシート、または topics.csv に
echo  足しておくだけでOK。
echo  やめたいときは「⑦毎日自動投稿を解除.bat」を実行してください。
echo ============================================================
pause
exit /b 0

:failed
echo.
echo [エラー] 設定に失敗しました。
echo 時刻が 08:00 のような半角の形式になっているか確認して、
echo もう一度ダブルクリックしてください。
pause
exit /b 1
