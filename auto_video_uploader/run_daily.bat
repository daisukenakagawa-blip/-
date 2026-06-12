@echo off
rem 毎日自動実行用(タスクスケジューラから呼ばれる)。直接使うのは④でOK。
cd /d "%~dp0"
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
if not exist logs mkdir logs
python main.py >> logs\cron.log 2>&1
