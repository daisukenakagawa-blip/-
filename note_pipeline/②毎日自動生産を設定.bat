@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo 毎日 朝9時に自動で記事を生産するよう、Windowsタスクに登録します。
schtasks /Create /SC DAILY /ST 09:00 /TN "note_pipeline_daily" /TR "cmd /c cd /d \"%~dp0\" && python pipeline.py" /F
echo 登録しました（毎日09:00）。時刻を変えたい場合はタスクスケジューラで編集してください。
pause
