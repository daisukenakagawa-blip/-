@echo off
chcp 65001 > nul
cd /d "%~dp0"
rem タスクスケジューラから毎日呼ばれる本体。画面は出さず投稿だけ行う。
python main.py >> "logs\daily.log" 2>&1
