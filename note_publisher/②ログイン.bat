@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ブラウザが開いたら note にログインしてください。
echo ログイン後、この画面に戻って Enter を押すと保存されます。
python login.py
pause
