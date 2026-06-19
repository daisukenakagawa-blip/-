@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo seeds.csv の興味から、勝てるニッチをnoteの実データで探します。
python find.py
explorer "%~dp0output"
pause
