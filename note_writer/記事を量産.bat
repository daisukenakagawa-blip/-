@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  note 記事を量産します
echo ============================================
echo  article_plan.csv のテーマで記事を生成します。
echo.
python generator.py
echo.
echo 生成物は output フォルダに保存されました。
explorer "%~dp0output"
pause
