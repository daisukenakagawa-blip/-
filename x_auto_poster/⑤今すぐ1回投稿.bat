@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  今すぐ X に投稿します(本番)
echo ============================================
echo.
python main.py
echo.
echo 投稿が終わりました。結果は posted_log.csv に記録されています。
pause
