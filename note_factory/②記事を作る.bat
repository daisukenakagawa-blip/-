@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo plan.csv のテーマで、編集部が記事を作ります（リサーチ→執筆→部長の精査）。
python run.py
explorer "%~dp0output"
pause
