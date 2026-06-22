#!/data/data/com.termux/files/usr/bin/bash
# =====================================================================
#  USD/JPY 自動売買ボット - Android(Termux)用 かんたんセットアップ
# =====================================================================
#  これを実行すると、スマホ(Android)だけでボットを動かせます。PCは不要。
#
#  使い方:
#   1) Google Play ではなく F-Droid から「Termux」アプリをインストール
#      (Play版は古く動きません)
#   2) Termuxを開いて、次の1行を貼り付けて実行:
#        curl -fsSL https://raw.githubusercontent.com/daisukenakagawa-blip/-/claude/gracious-sagan-y604fg/setup_termux.sh | bash
#   3) 表示される手順に従って .env に OANDA の情報を入れて起動
# =====================================================================
set -e

REPO_URL="https://github.com/daisukenakagawa-blip/-.git"
BRANCH="claude/gracious-sagan-y604fg"
DIR="fxbot"

echo "==> 必要なパッケージをインストール中 (python, git)..."
pkg update -y >/dev/null 2>&1 || true
pkg install -y python git >/dev/null 2>&1

if [ -d "$DIR/.git" ]; then
  echo "==> 既存のリポジトリを更新..."
  git -C "$DIR" fetch origin "$BRANCH" -q
  git -C "$DIR" checkout "$BRANCH" -q
  git -C "$DIR" pull origin "$BRANCH" -q
else
  echo "==> リポジトリを取得..."
  git clone -b "$BRANCH" "$REPO_URL" "$DIR" -q
fi

cd "$DIR"

# .env テンプレートを用意 (まだ無ければ)
if [ ! -f ".env" ]; then
  cat > .env <<'EOF'
# OANDA の情報をここに入れて保存してください (= の右側を書き換える)
OANDA_TOKEN=ここにAPIトークン
OANDA_ACCOUNT=ここに口座ID
OANDA_ENV=practice
EOF
  echo "==> .env を作成しました。"
fi

# スリープ中もボットを止めないためのウェイクロック
termux-wake-lock 2>/dev/null || true

echo ""
echo "============================================================"
echo " セットアップ完了！ あと2ステップです。"
echo "============================================================"
echo " 1) OANDAの情報を入力する (テキストエディタ nano が開きます):"
echo "      nano .env"
echo "    OANDA_TOKEN と OANDA_ACCOUNT を書き換えて Ctrl+O→Enter→Ctrl+X で保存"
echo ""
echo " 2) ボットを起動する:"
echo "      python3 run_bot.py            # 売買 + スマホ画面"
echo "      python3 run_bot.py --monitor  # まず監視だけ試す"
echo ""
echo " 起動後、画面に出る http://localhost:8000/?token=... を"
echo " このスマホのブラウザ(Chrome等)で開けば操作画面が見られます。"
echo "============================================================"
echo " ※ Android設定 → アプリ → Termux → バッテリー → 「制限なし」に"
echo "    しておくと、画面を消してもボットが止まりにくくなります。"
echo "============================================================"
