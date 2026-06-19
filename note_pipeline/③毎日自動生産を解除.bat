@echo off
chcp 65001 > nul
schtasks /Delete /TN "note_pipeline_daily" /F
echo 解除しました。
pause
