@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo note_niche を回して、狙い目ニッチの候補を探します。
python pipeline.py --discover
pause
