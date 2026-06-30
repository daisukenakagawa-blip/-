@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  X との接続をテストします
echo ============================================
echo.
python main.py --test
echo.
pause
