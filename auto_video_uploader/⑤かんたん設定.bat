@echo off
chcp 65001 >nul
title ⑤かんたん設定(AI台本・スマホ連携)
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul

echo ============================================================
echo  かんたん設定
echo  ※入力せず Enter だけ押すとスキップできます
echo  ※貼り付けは「右クリック」でできます
echo ============================================================
echo.
echo 【1/2】Anthropic APIキー → 台本がAI生成になり品質が大幅UP
set "KEY="
set /p KEY=APIキーを貼り付けて Enter:
if "%KEY%"=="" goto :sheet
powershell -NoProfile -Command "$p='.env';(Get-Content $p) -replace '^ANTHROPIC_API_KEY=.*','ANTHROPIC_API_KEY=%KEY%' | Set-Content -Encoding UTF8 $p"
echo   設定しました!

:sheet
echo.
echo 【2/2】Googleスプレッドシートの公開URL → スマホからテーマ追加
set "URL="
set /p URL=URLを貼り付けて Enter:
if "%URL%"=="" goto :done
powershell -NoProfile -Command "$p='.env'; $c=Get-Content $p; if($c -match '^TOPICS_SHEET_URL='){$c -replace '^TOPICS_SHEET_URL=.*','TOPICS_SHEET_URL=%URL%' | Set-Content -Encoding UTF8 $p}else{Add-Content -Path $p -Value 'TOPICS_SHEET_URL=%URL%' -Encoding UTF8}"
echo   設定しました!

:done
echo.
echo ============================================================
echo  設定完了!次回の実行から反映されます。
echo ============================================================
pause
