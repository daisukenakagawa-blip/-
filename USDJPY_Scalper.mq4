//+------------------------------------------------------------------+
//|                                              USDJPY_Scalper.mq4  |
//|                  USD/JPY スキャルピングEA for MT4 (M5専用)         |
//|                  戦略: ボリンジャーバンド+RSI レンジ逆張り          |
//|                  ※まずデモ口座で十分に検証してください              |
//+------------------------------------------------------------------+
#property copyright "Demo EA"
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
//| 基本設定                                                          |
//+------------------------------------------------------------------+
// ★★★ リアル口座で使う場合のみ false に変更 ★★★
extern bool    DemoOnly           = true;   // true=デモ口座のみ動作

extern string  _sec1_             = "=== トレード設定 ===";
extern double  LotSize            = 0.01;   // ロットサイズ (0.01=1000通貨)
extern double  MaxLotSize         = 0.1;    // 最大ロット
extern int     MaxPositions       = 1;      // 同時最大ポジション数
extern int     MagicNumber        = 20260612; // EA識別番号 (AutoTraderと別の番号)

extern string  _sec2_             = "=== 利確/損切り (スキャル設定) ===";
extern double  StopLossPips       = 10.0;   // 損切り (pips)
extern double  TakeProfitPips     = 6.0;    // 利確 (pips)
extern bool    UseMiddleBandExit  = true;   // BB中央線タッチで早期利確
extern int     MaxHoldMinutes     = 120;    // 最大保有時間 (分, 0=無制限)

extern string  _sec3_             = "=== リスク管理 (安全装置) ===";
extern double  MaxDailyLossPct    = 3.0;    // 1日の最大損失 (口座の%)
extern double  MaxDrawdownPct     = 10.0;   // 最大ドローダウン (口座の%)
extern int     MaxTradesPerDay    = 10;     // 1日の最大トレード数
extern int     MaxConsecLosses    = 3;      // 連敗したらその日は停止 (0=無効)

extern string  _sec4_             = "=== ボリンジャーバンド ===";
extern int     BB_Period          = 20;     // BB期間
extern double  BB_Deviation       = 2.0;    // BB偏差

extern string  _sec5_             = "=== RSIフィルター ===";
extern int     RSI_Period         = 9;      // RSI期間 (スキャル用に短め)
extern double  RSI_BuyLevel       = 30.0;   // これ以下で買い許可
extern double  RSI_SellLevel      = 70.0;   // これ以上で売り許可

extern string  _sec6_             = "=== レンジ判定 (ADX) ===";
extern bool    UseADXFilter       = true;   // ADXフィルター使用
extern int     ADX_Period         = 14;     // ADX期間
extern double  ADX_MaxLevel       = 25.0;   // この値以上(強トレンド)は見送り

extern string  _sec7_             = "=== 時間フィルター ===";
extern bool    UseTimeFilter      = true;   // 時間フィルター使用
extern int     TradeStartHour     = 2;      // 取引開始 (サーバー時間, 東京時間帯)
extern int     TradeEndHour       = 9;      // 取引終了 (サーバー時間)

extern string  _sec8_             = "=== スプレッドフィルター (重要) ===";
extern double  MaxSpreadPips      = 1.2;    // 最大許容スプレッド (pips)

extern string  _sec9_             = "=== スマホ通知 ===";
extern bool    UsePushNotify      = true;   // スマホMT4へプッシュ通知
extern bool    UseEmailNotify     = false;  // メール通知
extern bool    NotifyOnStart      = true;   // EA起動/停止を通知
extern bool    NotifyOnEntry      = true;   // 新規エントリーを通知
extern bool    NotifyOnClose      = true;   // 決済を通知

//+------------------------------------------------------------------+
//| グローバル変数                                                     |
//+------------------------------------------------------------------+
double g_startBalance;
int    g_todayTrades;
int    g_lastTradeDay;
double g_peakBalance;
double g_point;
int    g_digits;
int    g_lastHistoryTotal;  // 決済検出用
int    g_consecLosses;      // 連敗カウント
bool   g_pausedToday;       // 連敗による当日停止フラグ

//+------------------------------------------------------------------+
//| 初期化                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   // デモ口座チェック
   if(DemoOnly && !IsDemo())
   {
      Alert("★ このEAはデモ口座専用です。リアル口座では動作しません。");
      Alert("★ リアル口座で使用するには DemoOnly を false に変更してください。");
      return INIT_FAILED;
   }

   // 通貨ペアチェック
   if(StringFind(Symbol(), "USDJPY") != 0)
   {
      Alert("このEAは USD/JPY 専用です。USD/JPYのチャートに設置してください。");
      return INIT_FAILED;
   }

   // 時間足チェック (M5推奨)
   if(Period() != PERIOD_M5)
      Alert("※ このEAは5分足(M5)用に設計されています。現在: M", Period());

   // ポイント計算
   g_digits = (int)MarketInfo(Symbol(), MODE_DIGITS);
   if(g_digits == 3 || g_digits == 5)
      g_point = MarketInfo(Symbol(), MODE_POINT) * 10;
   else
      g_point = MarketInfo(Symbol(), MODE_POINT);

   g_startBalance     = AccountBalance();
   g_peakBalance      = AccountBalance();
   g_todayTrades      = 0;
   g_lastTradeDay     = DayOfYear();
   g_lastHistoryTotal = OrdersHistoryTotal();
   g_consecLosses     = 0;
   g_pausedToday      = false;

   Print("=== USDJPY Scalper 起動 ===");
   Print("口座: ", AccountNumber(), " (", IsDemo() ? "デモ" : "リアル", ")");
   Print("残高: ", AccountBalance(), " ", AccountCurrency());
   Print("ロット: ", LotSize, " SL: ", StopLossPips, "pips TP: ", TakeProfitPips, "pips");

   if(NotifyOnStart)
      Notify("EA起動 | 口座:" + IntegerToString(AccountNumber()) +
             (IsDemo() ? "(デモ)" : "(リアル)") +
             " 残高:" + DoubleToString(AccountBalance(), 0) + AccountCurrency());

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| 終了処理                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("=== USDJPY Scalper 停止 ===");
   if(NotifyOnStart && reason != REASON_PARAMETERS && reason != REASON_CHARTCHANGE && reason != REASON_RECOMPILE)
      Notify("EA停止 | 残高:" + DoubleToString(AccountBalance(), 0) + AccountCurrency());
}

//+------------------------------------------------------------------+
//| メインループ (Tickごとに実行)                                      |
//+------------------------------------------------------------------+
void OnTick()
{
   // 日付が変わったらカウントリセット
   if(DayOfYear() != g_lastTradeDay)
   {
      g_todayTrades  = 0;
      g_lastTradeDay = DayOfYear();
      g_consecLosses = 0;
      g_pausedToday  = false;
   }

   // ピーク残高更新
   if(AccountBalance() > g_peakBalance)
      g_peakBalance = AccountBalance();

   // ===== 決済検出 → 通知 + 連敗カウント =====
   CheckClosedPositions();

   // ===== ポジション管理 (早期利確/時間切れ決済) =====
   ManageOpenPositions();

   // ===== 画面表示 =====
   UpdateDisplay();

   // ===== 安全装置チェック =====
   if(!SafetyCheck()) return;

   // ===== 新規エントリー判断 =====
   if(CountPositions() < MaxPositions)
   {
      int signal = GetSignal();
      if(signal != 0)
         ExecuteTrade(signal);
   }
}

//+------------------------------------------------------------------+
//| 安全装置                                                          |
//+------------------------------------------------------------------+
bool SafetyCheck()
{
   // 連敗による当日停止
   if(g_pausedToday)
      return false;

   // 1日の最大トレード数
   if(g_todayTrades >= MaxTradesPerDay)
      return false;

   // 1日の最大損失チェック
   double dailyLoss = GetTodayPL();
   double maxLoss   = AccountBalance() * MaxDailyLossPct / 100.0;
   if(dailyLoss < -maxLoss)
   {
      CloseAllPositions("日次最大損失到達");
      g_pausedToday = true;
      return false;
   }

   // 最大ドローダウンチェック
   double drawdown = (g_peakBalance - AccountBalance()) / g_peakBalance * 100;
   if(drawdown >= MaxDrawdownPct)
   {
      CloseAllPositions("最大ドローダウン到達");
      g_pausedToday = true;
      return false;
   }

   // スプレッドチェック (スキャルでは最重要)
   if(GetSpreadPips() > MaxSpreadPips)
      return false;

   // 時間フィルター
   if(UseTimeFilter)
   {
      int hour = Hour();
      if(TradeStartHour < TradeEndHour)
      {
         if(hour < TradeStartHour || hour >= TradeEndHour) return false;
      }
      else // 日をまたぐ場合
      {
         if(hour < TradeStartHour && hour >= TradeEndHour) return false;
      }
   }

   return true;
}

//+------------------------------------------------------------------+
//| シグナル判定 (BB逆張り + RSI + レンジ判定)                          |
//+------------------------------------------------------------------+
int GetSignal()
{
   // 新しいバーが確定した時のみ判定
   static datetime lastBarTime = 0;
   if(Time[0] == lastBarTime) return 0;
   lastBarTime = Time[0];

   // === ボリンジャーバンド (直近確定足) ===
   double bbUpper = iBands(Symbol(), 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_UPPER, 1);
   double bbLower = iBands(Symbol(), 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_LOWER, 1);

   double closePrev = Close[1];

   int signal = 0;
   if(closePrev <= bbLower)      signal = 1;   // 下バンド割れ → 反発買い候補
   else if(closePrev >= bbUpper) signal = -1;  // 上バンド超え → 反落売り候補
   else return 0;

   // === RSI 確認 (行き過ぎの確認) ===
   double rsi = iRSI(Symbol(), 0, RSI_Period, PRICE_CLOSE, 1);
   if(signal == 1  && rsi > RSI_BuyLevel)  return 0; // 売られすぎでない → 見送り
   if(signal == -1 && rsi < RSI_SellLevel) return 0; // 買われすぎでない → 見送り

   // === ADXフィルター (強トレンド中の逆張りは危険 → 見送り) ===
   if(UseADXFilter)
   {
      double adx = iADX(Symbol(), 0, ADX_Period, PRICE_CLOSE, MODE_MAIN, 1);
      if(adx >= ADX_MaxLevel) return 0;
   }

   return signal;
}

//+------------------------------------------------------------------+
//| トレード実行                                                       |
//+------------------------------------------------------------------+
void ExecuteTrade(int signal)
{
   double price, sl, tp;
   int    cmd;

   // ロットサイズ検証
   double lot = LotSize;
   if(lot > MaxLotSize) lot = MaxLotSize;
   lot = NormalizeDouble(lot, 2);

   double minLot = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot = MarketInfo(Symbol(), MODE_MAXLOT);
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;

   // 証拠金チェック
   double margin = AccountFreeMarginCheck(Symbol(), signal == 1 ? OP_BUY : OP_SELL, lot);
   if(margin <= 0)
   {
      Print("証拠金不足: ", GetLastError());
      return;
   }

   if(signal == 1) // 買い
   {
      cmd   = OP_BUY;
      price = Ask;
      sl    = NormalizeDouble(price - StopLossPips * g_point, g_digits);
      tp    = NormalizeDouble(price + TakeProfitPips * g_point, g_digits);
   }
   else // 売り
   {
      cmd   = OP_SELL;
      price = Bid;
      sl    = NormalizeDouble(price + StopLossPips * g_point, g_digits);
      tp    = NormalizeDouble(price - TakeProfitPips * g_point, g_digits);
   }

   int ticket = OrderSend(Symbol(), cmd, lot, price, 2, sl, tp,
                           "USDJPY_Scalp", MagicNumber, 0,
                           signal == 1 ? clrBlue : clrRed);

   if(ticket > 0)
   {
      g_todayTrades++;
      Print(signal == 1 ? "BUY" : "SELL", " エントリー: ", price,
            " SL: ", sl, " TP: ", tp, " Lot: ", lot);
      if(NotifyOnEntry)
         Notify((signal == 1 ? "BUY" : "SELL") + " エントリー " +
                DoubleToString(price, g_digits) +
                " Lot:" + DoubleToString(lot, 2) +
                " SL:" + DoubleToString(sl, g_digits) +
                " TP:" + DoubleToString(tp, g_digits));
   }
   else
   {
      Print("注文エラー: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| ポジション管理 (BB中央線で早期利確 / 保有時間切れ決済)                |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   double bbMiddle = iBands(Symbol(), 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_MAIN, 0);

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;

      bool doClose = false;
      string reason = "";

      // 最大保有時間チェック (レンジ想定が外れたら撤退)
      if(MaxHoldMinutes > 0 && TimeCurrent() - OrderOpenTime() >= MaxHoldMinutes * 60)
      {
         doClose = true;
         reason  = "保有時間切れ";
      }

      // BB中央線タッチで早期利確 (利益が出ている場合のみ)
      if(!doClose && UseMiddleBandExit)
      {
         if(OrderType() == OP_BUY && Bid >= bbMiddle && Bid > OrderOpenPrice())
         {
            doClose = true;
            reason  = "BB中央線利確";
         }
         else if(OrderType() == OP_SELL && Ask <= bbMiddle && Ask < OrderOpenPrice())
         {
            doClose = true;
            reason  = "BB中央線利確";
         }
      }

      if(doClose)
      {
         double closePrice = (OrderType() == OP_BUY) ? Bid : Ask;
         if(OrderClose(OrderTicket(), OrderLots(), closePrice, 2, clrYellow))
            Print("決済(", reason, "): ", closePrice);
         else
            Print("決済エラー(", reason, "): ", GetLastError());
      }
   }
}

//+------------------------------------------------------------------+
//| 決済検出 (通知 + 連敗カウント)                                       |
//+------------------------------------------------------------------+
void CheckClosedPositions()
{
   int total = OrdersHistoryTotal();
   if(total <= g_lastHistoryTotal) { g_lastHistoryTotal = total; return; }

   for(int i = g_lastHistoryTotal; i < total; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL) continue;

      double pl = OrderProfit() + OrderSwap() + OrderCommission();

      // 連敗カウント
      if(pl < 0)
      {
         g_consecLosses++;
         if(MaxConsecLosses > 0 && g_consecLosses >= MaxConsecLosses && !g_pausedToday)
         {
            g_pausedToday = true;
            Print("★ ", g_consecLosses, "連敗のため本日の取引を停止します");
            Notify("★" + IntegerToString(g_consecLosses) + "連敗 → 本日の取引を停止 | 残高:" +
                   DoubleToString(AccountBalance(), 0) + AccountCurrency());
         }
      }
      else
         g_consecLosses = 0;

      if(NotifyOnClose)
         Notify((OrderType() == OP_BUY ? "BUY" : "SELL") + " 決済 " +
                DoubleToString(OrderClosePrice(), g_digits) +
                " 損益:" + (pl >= 0 ? "+" : "") + DoubleToString(pl, 0) + AccountCurrency() +
                " | 残高:" + DoubleToString(AccountBalance(), 0) + AccountCurrency());
   }
   g_lastHistoryTotal = total;
}

//+------------------------------------------------------------------+
//| 全ポジション決済                                                    |
//+------------------------------------------------------------------+
void CloseAllPositions(string reason)
{
   Print("★ 全ポジション決済: ", reason);
   Alert("★ ", reason, " - 全ポジション決済実行");
   Notify("★緊急決済: " + reason + " | 残高:" + DoubleToString(AccountBalance(), 0) + AccountCurrency());

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;

      double closePrice = (OrderType() == OP_BUY) ? Bid : Ask;
      if(!OrderClose(OrderTicket(), OrderLots(), closePrice, 3, clrYellow))
         Print("決済エラー: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| ポジション数取得                                                    |
//+------------------------------------------------------------------+
int CountPositions()
{
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() == Symbol() && OrderMagicNumber() == MagicNumber)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| 本日の損益取得                                                     |
//+------------------------------------------------------------------+
double GetTodayPL()
{
   double pl = 0;
   for(int i = OrdersHistoryTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;
      if(TimeDay(OrderCloseTime()) == Day() &&
         TimeMonth(OrderCloseTime()) == Month() &&
         TimeYear(OrderCloseTime()) == Year())
      {
         pl += OrderProfit() + OrderSwap() + OrderCommission();
      }
   }
   return pl;
}

//+------------------------------------------------------------------+
//| スプレッド取得 (pips)                                              |
//+------------------------------------------------------------------+
double GetSpreadPips()
{
   return MarketInfo(Symbol(), MODE_SPREAD) * MarketInfo(Symbol(), MODE_POINT) / g_point;
}

//+------------------------------------------------------------------+
//| 通知送信 (スマホMT4プッシュ + メール)                                |
//+------------------------------------------------------------------+
void Notify(string msg)
{
   string text = "[USDJPY Scalp] " + msg;
   if(UsePushNotify)
   {
      if(!SendNotification(text))
         Print("プッシュ通知エラー: ", GetLastError(), " (MetaQuotes IDの設定を確認してください)");
   }
   if(UseEmailNotify)
      SendMail("USDJPY Scalper", text);
}

//+------------------------------------------------------------------+
//| 画面表示                                                          |
//+------------------------------------------------------------------+
void UpdateDisplay()
{
   string info = "";
   info += "━━━ USDJPY Scalper (M5) ━━━\n";
   info += "口座: " + IntegerToString(AccountNumber());
   info += (IsDemo() ? " [デモ]" : " [リアル]") + "\n";
   info += "残高: " + DoubleToString(AccountBalance(), 0) + " " + AccountCurrency() + "\n";
   info += "有効証拠金: " + DoubleToString(AccountEquity(), 0) + "\n";
   info += "━━━━━━━━━━━━━━━━\n";

   double bbUpper  = iBands(Symbol(), 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_UPPER, 0);
   double bbMiddle = iBands(Symbol(), 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_MAIN, 0);
   double bbLower  = iBands(Symbol(), 0, BB_Period, BB_Deviation, 0, PRICE_CLOSE, MODE_LOWER, 0);
   double rsi      = iRSI(Symbol(), 0, RSI_Period, PRICE_CLOSE, 0);
   info += "BB上: " + DoubleToString(bbUpper, g_digits) + "\n";
   info += "BB中: " + DoubleToString(bbMiddle, g_digits) + "\n";
   info += "BB下: " + DoubleToString(bbLower, g_digits) + "\n";
   info += "RSI: " + DoubleToString(rsi, 1) + "\n";

   if(UseADXFilter)
   {
      double adx = iADX(Symbol(), 0, ADX_Period, PRICE_CLOSE, MODE_MAIN, 0);
      info += "ADX: " + DoubleToString(adx, 1) + (adx < ADX_MaxLevel ? " (レンジ:OK)" : " (トレンド:見送り)") + "\n";
   }

   info += "━━━━━━━━━━━━━━━━\n";
   info += "ポジション: " + IntegerToString(CountPositions()) + "/" + IntegerToString(MaxPositions) + "\n";
   info += "本日トレード: " + IntegerToString(g_todayTrades) + "/" + IntegerToString(MaxTradesPerDay) + "\n";
   info += "本日損益: " + DoubleToString(GetTodayPL(), 0) + " " + AccountCurrency() + "\n";
   info += "連敗: " + IntegerToString(g_consecLosses) + "/" + IntegerToString(MaxConsecLosses);
   info += (g_pausedToday ? " ★本日停止中" : "") + "\n";

   double dd = 0;
   if(g_peakBalance > 0)
      dd = (g_peakBalance - AccountBalance()) / g_peakBalance * 100;
   info += "DD: " + DoubleToString(dd, 1) + "% / " + DoubleToString(MaxDrawdownPct, 0) + "%\n";

   double spread = GetSpreadPips();
   info += "スプレッド: " + DoubleToString(spread, 1) + " pips";
   info += (spread > MaxSpreadPips ? " ★広すぎ(見送り中)" : " (OK)") + "\n";

   Comment(info);
}
//+------------------------------------------------------------------+
