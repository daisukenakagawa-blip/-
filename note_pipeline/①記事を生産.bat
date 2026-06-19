@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo niches.csv のニッチから、本日分の記事を自動生産します。
python pipeline.py
explorer "%~dp0produced"
pause
