@echo off
chcp 65001 >nul
title ②かんたん設定(X認証・AI投稿文・スマホ連携)
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul

echo ============================================================
echo  かんたん設定
echo  ※入力せず Enter だけ押すとスキップできます
echo  ※貼り付けは「右クリック」でできます
echo ============================================================
echo.
echo 【1/6】X の API Key (API Key / Consumer Key)
set "V="
set /p V=貼り付けて Enter:
if not "%V%"=="" powershell -NoProfile -Command "$p='.env';(Get-Content $p) -replace '^X_API_KEY=.*','X_API_KEY=%V%' | Set-Content -Encoding UTF8 $p"

echo.
echo 【2/6】X の API Secret (API Key Secret / Consumer Secret)
set "V="
set /p V=貼り付けて Enter:
if not "%V%"=="" powershell -NoProfile -Command "$p='.env';(Get-Content $p) -replace '^X_API_SECRET=.*','X_API_SECRET=%V%' | Set-Content -Encoding UTF8 $p"

echo.
echo 【3/6】X の Access Token
set "V="
set /p V=貼り付けて Enter:
if not "%V%"=="" powershell -NoProfile -Command "$p='.env';(Get-Content $p) -replace '^X_ACCESS_TOKEN=.*','X_ACCESS_TOKEN=%V%' | Set-Content -Encoding UTF8 $p"

echo.
echo 【4/6】X の Access Token Secret
set "V="
set /p V=貼り付けて Enter:
if not "%V%"=="" powershell -NoProfile -Command "$p='.env';(Get-Content $p) -replace '^X_ACCESS_TOKEN_SECRET=.*','X_ACCESS_TOKEN_SECRET=%V%' | Set-Content -Encoding UTF8 $p"

echo.
echo 【5/6】Anthropic APIキー → 投稿文がAI生成になり品質UP(任意)
set "V="
set /p V=貼り付けて Enter:
if not "%V%"=="" powershell -NoProfile -Command "$p='.env';(Get-Content $p) -replace '^ANTHROPIC_API_KEY=.*','ANTHROPIC_API_KEY=%V%' | Set-Content -Encoding UTF8 $p"

echo.
echo 【6/6】Googleスプレッドシートの公開URL → スマホからテーマ追加(任意)
set "V="
set /p V=貼り付けて Enter:
if not "%V%"=="" powershell -NoProfile -Command "$p='.env'; $c=Get-Content $p; if($c -match '^TOPICS_SHEET_URL='){$c -replace '^TOPICS_SHEET_URL=.*','TOPICS_SHEET_URL=%V%' | Set-Content -Encoding UTF8 $p}else{Add-Content -Path $p -Value 'TOPICS_SHEET_URL=%V%' -Encoding UTF8}"

echo.
echo ============================================================
echo  設定完了!「③X接続テスト.bat」で接続を確認してください。
echo ============================================================
pause
