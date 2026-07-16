@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================
echo  パチンコ情報スクレイパー 実行
echo ================================
python scraper.py
echo.
echo 完了しました。結果は data\articles.csv にあります。
pause
