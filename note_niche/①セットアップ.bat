@echo off
chcp 65001 > nul
cd /d "%~dp0"
where python >nul 2>nul || (echo Pythonが必要です。https://www.python.org/ & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo 完了。seeds.csv に興味を書き、「②ニッチを探す.bat」を実行してください。
pause
