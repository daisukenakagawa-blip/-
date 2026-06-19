@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ============================================
echo  note 売れる記事リサーチを実行します
echo ============================================
echo  keywords.csv のキーワードで note を調べます。
echo.
python research.py
echo.
echo 結果は output フォルダの .md(レポート) と .csv に保存されました。
explorer "%~dp0output"
pause
