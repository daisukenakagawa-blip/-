//+------------------------------------------------------------------+
//|                                          USDJPY_AutoTrader.mq4   |
//|                          USD/JPY 自動売買 EA for MT4              |
//|                          ※まずデモ口座で十分に検証してください      |
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
extern int     MagicNumber        = 20240401; // EA識別番号

extern string  _sec2_             = "=== リスク管理 ===";
extern double  StopLossPips       = 30.0;   // 損切り (pips)
extern double  TakeProfitPips     = 60.0;   // 利確 (pips)
extern double  TrailingStopPips   = 20.0;   // トレーリングストップ (0=無効)
extern double  MaxDailyLossPct    = 5.0;    // 1日の最大損失 (口座の%)
extern double  MaxDrawdownPct     = 15.0;   // 最大ドローダウン (口座の%)
extern int     MaxTradesPerDay    = 5;      // 1日の最大トレード数

extern string  _sec3_             = "=== MA クロス戦略 ===";
extern int     FastMA_Period      = 20;     // 短期EMA期間
extern int     SlowMA_Period      = 75;     // 長期EMA期間
extern ENUM_MA_METHOD MA_Method   = MODE_EMA; // MA種別

extern string  _sec4_             = "=== RSIフィルター ===";
extern bool    UseRSIFilter       = true;   // RSIフィルター使用
extern int     RSI_Period         = 14;     // RSI期間
extern double  RSI_OverboughtLv   = 70.0;   // 買われすぎ
extern double  RSI_OversoldLv     = 30.0;   // 売られすぎ

extern string  _sec5_             = "=== ADXフィルター ===";
extern bool    UseADXFilter       = true;   // ADXフィルター使用
extern int     ADX_Period         = 14;     // ADX期間
extern double  ADX_MinLevel       = 20.0;   // 最低ADX値 (トレンド強度)

extern string  _sec6_             = "=== 時間フィルター ===";
extern bool    UseTimeFilter      = true;   // 時間フィルター使用
extern int     TradeStartHour     = 16;     // 取引開始時刻 (サーバー時間)
extern int     TradeEndHour       = 23;     // 取引終了時刻

extern string  _sec7_             = "=== スプレッドフィルター ===";
extern double  MaxSpreadPips      = 3.0;    // 最大許容スプレッド (pips)

extern string  _sec8_             = "=== スマホ通知 ===";
extern bool    UsePushNotify      = true;   // スマホMT4へプッシュ通知 (要MetaQuotes ID設定)
extern bool    UseEmailNotify     = false;  // メール通知 (要MT4メール設定)
extern bool    NotifyOnStart      = true;   // EA起動/停止を通知
extern bool    NotifyOnEntry      = true;   // 新規エントリーを通知
extern bool    NotifyOnClose      = true;   // 決済(SL/TP含む)を通知

//+------------------------------------------------------------------+
//| グローバル変数                                                     |
//+------------------------------------------------------------------+
double g_startBalance;
int    g_todayTrades;
double g_todayPL;
int    g_lastTradeDay;
double g_peakBalance;
double g_point;
int    g_digits;
int    g_lastHistoryTotal;  // 決済検出用

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
   if(Symbol() != "USDJPY" && Symbol() != "USDJPYm" && Symbol() != "USDJPYmicro")
   {
      Alert("このEAは USD/JPY 専用です。USD/JPYのチャートに設置してください。");
      return INIT_FAILED;
   }
   
   // ポイント計算
   g_digits = (int)MarketInfo(Symbol(), MODE_DIGITS);
   if(g_digits == 3 || g_digits == 5)
      g_point = MarketInfo(Symbol(), MODE_POINT) * 10;
   else
      g_point = MarketInfo(Symbol(), MODE_POINT);
   
   g_startBalance   = AccountBalance();
   g_peakBalance    = AccountBalance();
   g_todayTrades    = 0;
   g_todayPL        = 0;
   g_lastTradeDay   = DayOfYear();
   g_lastHistoryTotal = OrdersHistoryTotal();

   Print("=== USDJPY AutoTrader 起動 ===");
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
   Print("=== USDJPY AutoTrader 停止 ===");
   // パラメーター変更や時間足切替による再起動では通知しない
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
      g_todayTrades = 0;
      g_todayPL     = 0;
      g_lastTradeDay = DayOfYear();
   }
   
   // ピーク残高更新
   if(AccountBalance() > g_peakBalance)
      g_peakBalance = AccountBalance();
   
   // ===== 決済検出 → スマホ通知 =====
   if(NotifyOnClose)
      CheckClosedPositions();

   // ===== 安全装置チェック =====
   if(!SafetyCheck()) return;

   // ===== トレーリングストップ =====
   if(TrailingStopPips > 0)
      ManageTrailingStop();
   
   // ===== 新規エントリー判断 =====
   if(CountPositions() < MaxPositions)
   {
      int signal = GetSignal();
      if(signal != 0)
         ExecuteTrade(signal);
   }
   
   // ===== 画面表示 =====
   UpdateDisplay();
}

//+------------------------------------------------------------------+
//| 安全装置                                                          |
//+------------------------------------------------------------------+
bool SafetyCheck()
{
   // 1日の最大トレード数
   if(g_todayTrades >= MaxTradesPerDay)
      return false;
   
   // 1日の最大損失チェック
   double dailyLoss = GetTodayPL();
   double maxLoss   = AccountBalance() * MaxDailyLossPct / 100.0;
   if(dailyLoss < -maxLoss)
   {
      // 全ポジション決済
      CloseAllPositions("日次最大損失到達");
      return false;
   }
   
   // 最大ドローダウンチェック
   double drawdown = (g_peakBalance - AccountBalance()) / g_peakBalance * 100;
   if(drawdown >= MaxDrawdownPct)
   {
      CloseAllPositions("最大ドローダウン到達");
      return false;
   }
   
   // スプレッドチェック
   double spread = MarketInfo(Symbol(), MODE_SPREAD) * MarketInfo(Symbol(), MODE_POINT) / g_point;
   if(spread > MaxSpreadPips)
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
//| シグナル判定                                                       |
//+------------------------------------------------------------------+
int GetSignal()
{
   // 新しいバーが確定した時のみ判定 (毎Tickでの売買を防止)
   static datetime lastBarTime = 0;
   if(Time[0] == lastBarTime) return 0;
   lastBarTime = Time[0];
   
   // === MAクロス ===
   double fastMA_curr = iMA(Symbol(), 0, FastMA_Period, 0, MA_Method, PRICE_CLOSE, 1);
   double fastMA_prev = iMA(Symbol(), 0, FastMA_Period, 0, MA_Method, PRICE_CLOSE, 2);
   double slowMA_curr = iMA(Symbol(), 0, SlowMA_Period, 0, MA_Method, PRICE_CLOSE, 1);
   double slowMA_prev = iMA(Symbol(), 0, SlowMA_Period, 0, MA_Method, PRICE_CLOSE, 2);
   
   int maSignal = 0;
   // ゴールデンクロス (短期MAが長期MAを上抜け)
   if(fastMA_prev <= slowMA_prev && fastMA_curr > slowMA_curr)
      maSignal = 1;  // 買い
   // デッドクロス (短期MAが長期MAを下抜け)
   else if(fastMA_prev >= slowMA_prev && fastMA_curr < slowMA_curr)
      maSignal = -1; // 売り
   else
      return 0; // クロスなし
   
   // === RSIフィルター ===
   if(UseRSIFilter)
   {
      double rsi = iRSI(Symbol(), 0, RSI_Period, PRICE_CLOSE, 1);
      // 買いシグナルなのにRSIが買われすぎ → 見送り
      if(maSignal == 1 && rsi > RSI_OverboughtLv) return 0;
      // 売りシグナルなのにRSIが売られすぎ → 見送り
      if(maSignal == -1 && rsi < RSI_OversoldLv) return 0;
   }
   
   // === ADXフィルター ===
   if(UseADXFilter)
   {
      double adx = iADX(Symbol(), 0, ADX_Period, PRICE_CLOSE, MODE_MAIN, 1);
      if(adx < ADX_MinLevel) return 0; // トレンドが弱い → 見送り
   }
   
   return maSignal;
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
   
   int ticket = OrderSend(Symbol(), cmd, lot, price, 3, sl, tp, 
                           "USDJPY_Auto", MagicNumber, 0, 
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
//| トレーリングストップ管理                                            |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;
      
      double trailDist = TrailingStopPips * g_point;
      
      if(OrderType() == OP_BUY)
      {
         double newSL = NormalizeDouble(Bid - trailDist, g_digits);
         if(Bid - OrderOpenPrice() > trailDist && newSL > OrderStopLoss())
         {
            if(!OrderModify(OrderTicket(), OrderOpenPrice(), newSL, OrderTakeProfit(), 0, clrBlue))
               Print("トレーリングSL変更エラー: ", GetLastError());
         }
      }
      else if(OrderType() == OP_SELL)
      {
         double newSL = NormalizeDouble(Ask + trailDist, g_digits);
         if(OrderOpenPrice() - Ask > trailDist && (newSL < OrderStopLoss() || OrderStopLoss() == 0))
         {
            if(!OrderModify(OrderTicket(), OrderOpenPrice(), newSL, OrderTakeProfit(), 0, clrRed))
               Print("トレーリングSL変更エラー: ", GetLastError());
         }
      }
   }
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
//| 決済検出 (SL/TP/手動決済をスマホに通知)                              |
//+------------------------------------------------------------------+
void CheckClosedPositions()
{
   int total = OrdersHistoryTotal();
   if(total <= g_lastHistoryTotal) { g_lastHistoryTotal = total; return; }

   // 新たに履歴入りした注文のうち、このEAの決済を通知
   for(int i = g_lastHistoryTotal; i < total; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != MagicNumber) continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL) continue;

      double pl = OrderProfit() + OrderSwap() + OrderCommission();
      Notify((OrderType() == OP_BUY ? "BUY" : "SELL") + " 決済 " +
             DoubleToString(OrderClosePrice(), g_digits) +
             " 損益:" + (pl >= 0 ? "+" : "") + DoubleToString(pl, 0) + AccountCurrency() +
             " | 残高:" + DoubleToString(AccountBalance(), 0) + AccountCurrency());
   }
   g_lastHistoryTotal = total;
}

//+------------------------------------------------------------------+
//| 通知送信 (スマホMT4プッシュ + メール)                                |
//+------------------------------------------------------------------+
void Notify(string msg)
{
   string text = "[USDJPY EA] " + msg;
   if(UsePushNotify)
   {
      if(!SendNotification(text))
         Print("プッシュ通知エラー: ", GetLastError(), " (MetaQuotes IDの設定を確認してください)");
   }
   if(UseEmailNotify)
      SendMail("USDJPY AutoTrader", text);
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
//| 画面表示                                                          |
//+------------------------------------------------------------------+
void UpdateDisplay()
{
   string info = "";
   info += "━━━ USDJPY AutoTrader ━━━\n";
   info += "口座: " + IntegerToString(AccountNumber());
   info += (IsDemo() ? " [デモ]" : " [リアル]") + "\n";
   info += "残高: " + DoubleToString(AccountBalance(), 0) + " " + AccountCurrency() + "\n";
   info += "有効証拠金: " + DoubleToString(AccountEquity(), 0) + "\n";
   info += "━━━━━━━━━━━━━━━━\n";
   
   // MA値
   double fastMA = iMA(Symbol(), 0, FastMA_Period, 0, MA_Method, PRICE_CLOSE, 0);
   double slowMA = iMA(Symbol(), 0, SlowMA_Period, 0, MA_Method, PRICE_CLOSE, 0);
   info += "EMA" + IntegerToString(FastMA_Period) + ": " + DoubleToString(fastMA, g_digits) + "\n";
   info += "EMA" + IntegerToString(SlowMA_Period) + ": " + DoubleToString(slowMA, g_digits) + "\n";
   info += "トレンド: " + (fastMA > slowMA ? "↑ 上昇" : "↓ 下降") + "\n";
   
   if(UseRSIFilter)
   {
      double rsi = iRSI(Symbol(), 0, RSI_Period, PRICE_CLOSE, 0);
      info += "RSI: " + DoubleToString(rsi, 1) + "\n";
   }
   if(UseADXFilter)
   {
      double adx = iADX(Symbol(), 0, ADX_Period, PRICE_CLOSE, MODE_MAIN, 0);
      info += "ADX: " + DoubleToString(adx, 1) + (adx >= ADX_MinLevel ? " (トレンドあり)" : " (レンジ)") + "\n";
   }
   
   info += "━━━━━━━━━━━━━━━━\n";
   info += "ポジション: " + IntegerToString(CountPositions()) + "/" + IntegerToString(MaxPositions) + "\n";
   info += "本日トレード: " + IntegerToString(g_todayTrades) + "/" + IntegerToString(MaxTradesPerDay) + "\n";
   info += "本日損益: " + DoubleToString(GetTodayPL(), 0) + " " + AccountCurrency() + "\n";
   
   double dd = 0;
   if(g_peakBalance > 0)
      dd = (g_peakBalance - AccountBalance()) / g_peakBalance * 100;
   info += "DD: " + DoubleToString(dd, 1) + "% / " + DoubleToString(MaxDrawdownPct, 0) + "%\n";
   
   double spread = MarketInfo(Symbol(), MODE_SPREAD) * MarketInfo(Symbol(), MODE_POINT) / g_point;
   info += "スプレッド: " + DoubleToString(spread, 1) + " pips\n";
   
   Comment(info);
}
//+------------------------------------------------------------------+
