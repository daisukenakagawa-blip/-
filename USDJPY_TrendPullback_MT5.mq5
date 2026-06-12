//+------------------------------------------------------------------+
//|                                   USDJPY_TrendPullback_MT5.mq5   |
//|              USD/JPY 専用 トレンドフォロー押し目EA for MT5          |
//|                                                                   |
//| 戦略:                                                             |
//|   環境認識 : H4 EMA50/EMA200 (50>200=買い環境, 50<200=売り環境)    |
//|   押し目   : H1 RSI14 (買い:35-45 / 売り:55-65)                   |
//|   エントリー: M15 直近高値/安値ブレイク                             |
//|   損切り   : ATR14 x 1.5                                          |
//|   利確     : ATR14 x 3.0 (最低RR 1:2 を下回る場合は見送り)         |
//|   リスク   : 1トレード口座資金の1% (ロット自動計算)                 |
//|   停止     : 重要指標前後60分 / 日次-3% / 月次-10%                 |
//|   禁止     : ナンピン・マーチンゲール (常に最大1ポジション固定リスク) |
//|                                                                   |
//| 設置: USDJPY の M15 チャートに適用 (上位足は自動取得)               |
//| ※まずデモ口座・ストラテジーテスターで十分に検証してください          |
//+------------------------------------------------------------------+
#property copyright "Demo EA"
#property version   "1.00"

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| 入力パラメーター                                                   |
//+------------------------------------------------------------------+
// ★★★ リアル口座で使う場合のみ false に変更 ★★★
input bool   DemoOnly          = true;      // デモ口座のみ動作 (テスターは常に可)

input group "=== トレード設定 ==="
input long   MagicNumber       = 20260613;  // EA識別番号
input double RiskPercent       = 1.0;       // 1トレードのリスク (口座資金の%)
input double MaxLotCap         = 5.0;       // ロット上限 (安全弁)
input double MaxSpreadPips     = 2.5;       // 最大許容スプレッド (pips)

input group "=== 環境認識 (H4 EMA) ==="
input int    EMA_Fast_Period   = 50;        // 短期EMA期間
input int    EMA_Slow_Period   = 200;       // 長期EMA期間

input group "=== 押し目判定 (H1 RSI) ==="
input int    RSI_Period        = 14;        // RSI期間
input double RSI_BuyMin        = 35.0;      // 買い: RSI下限
input double RSI_BuyMax        = 45.0;      // 買い: RSI上限
input double RSI_SellMin       = 55.0;      // 売り: RSI下限
input double RSI_SellMax       = 65.0;      // 売り: RSI上限

input group "=== エントリー (M15ブレイク) ==="
input int    BreakoutBars      = 20;        // ブレイク判定の参照本数 (M15)

input group "=== 損切り/利確 (ATR) ==="
input int    ATR_Period        = 14;        // ATR期間
input ENUM_TIMEFRAMES ATR_TF   = PERIOD_H1; // ATR算出時間足
input double SL_ATR_Mult       = 1.5;       // 損切り = ATR x この値
input double TP_ATR_Mult       = 3.0;       // 利確   = ATR x この値
input double MinRR             = 2.0;       // 最低リスクリワード比 (1:2)

input group "=== 重要指標フィルター ==="
input bool   UseNewsFilter     = true;      // 重要指標前後は停止 (※テスターでは無効)
input int    NewsStopMinutes   = 60;        // 指標前後の停止時間 (分)

input group "=== 損失リミット ==="
input double MaxDailyLossPct   = 3.0;       // 日次損失でその日停止 (%)
input double MaxMonthlyLossPct = 10.0;      // 月次損失でその月停止 (%)

input group "=== スマホ通知 ==="
input bool   UsePushNotify     = true;      // プッシュ通知 (要MetaQuotes ID)
input bool   NotifyOnEntry     = true;      // エントリー通知
input bool   NotifyOnClose     = true;      // 決済通知

//+------------------------------------------------------------------+
//| グローバル変数                                                     |
//+------------------------------------------------------------------+
CTrade   trade;
int      g_hEmaFast = INVALID_HANDLE;   // H4 EMA50
int      g_hEmaSlow = INVALID_HANDLE;   // H4 EMA200
int      g_hRsi     = INVALID_HANDLE;   // H1 RSI14
int      g_hAtr     = INVALID_HANDLE;   // ATR14
double   g_pip;                          // 1pipの価格 (USDJPY=0.01)
int      g_digits;
bool     g_isTester;
double   g_dailyPL;                      // 本日の確定損益
double   g_monthlyPL;                    // 今月の確定損益
bool     g_pausedDay;                    // 日次損失による停止
bool     g_pausedMonth;                  // 月次損失による停止
int      g_curDayOfYear = -1;
int      g_curMonth     = -1;

//+------------------------------------------------------------------+
//| 初期化                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   g_isTester = (bool)MQLInfoInteger(MQL_TESTER);

   // デモ口座チェック (テスターでは常に許可)
   if(DemoOnly && !g_isTester &&
      AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Alert("★ このEAはデモ口座専用です。リアル口座で使うには DemoOnly=false に変更してください。");
      return INIT_FAILED;
   }

   // 通貨ペアチェック (USDJPY / USDJPYm 等のサフィックス付きも許可)
   if(StringFind(_Symbol, "USDJPY") != 0)
   {
      Alert("このEAは USD/JPY 専用です。USDJPYのチャートに設置してください。");
      return INIT_FAILED;
   }

   // インジケーターハンドル作成
   g_hEmaFast = iMA(_Symbol, PERIOD_H4, EMA_Fast_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaSlow = iMA(_Symbol, PERIOD_H4, EMA_Slow_Period, 0, MODE_EMA, PRICE_CLOSE);
   g_hRsi     = iRSI(_Symbol, PERIOD_H1, RSI_Period, PRICE_CLOSE);
   g_hAtr     = iATR(_Symbol, ATR_TF, ATR_Period);
   if(g_hEmaFast == INVALID_HANDLE || g_hEmaSlow == INVALID_HANDLE ||
      g_hRsi == INVALID_HANDLE || g_hAtr == INVALID_HANDLE)
   {
      Alert("インジケーターの初期化に失敗しました。");
      return INIT_FAILED;
   }

   // pip計算 (USDJPY: 3桁なら point*10 = 0.01)
   g_digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   g_pip = (g_digits == 3 || g_digits == 5) ? point * 10 : point;

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(20);
   trade.SetTypeFillingBySymbol(_Symbol);

   g_pausedDay   = false;
   g_pausedMonth = false;
   RefreshPL();

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   g_curDayOfYear = dt.day_of_year;
   g_curMonth     = dt.mon;

   Print("=== USDJPY TrendPullback (MT5) 起動 ===");
   Print("リスク/トレード: ", RiskPercent, "%  SL: ATRx", SL_ATR_Mult, "  TP: ATRx", TP_ATR_Mult);
   Notify("EA起動 | 残高:" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 0) +
          AccountInfoString(ACCOUNT_CURRENCY));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| 終了処理                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("=== USDJPY TrendPullback 停止 ===");
   if(reason != REASON_PARAMETERS && reason != REASON_CHARTCHANGE && reason != REASON_RECOMPILE)
      Notify("EA停止 | 残高:" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 0) +
             AccountInfoString(ACCOUNT_CURRENCY));
   Comment("");
}

//+------------------------------------------------------------------+
//| メインループ                                                       |
//+------------------------------------------------------------------+
void OnTick()
{
   // 日付・月の切り替わりで停止フラグ解除
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_year != g_curDayOfYear)
   {
      g_curDayOfYear = dt.day_of_year;
      g_pausedDay = false;
      RefreshPL();
   }
   if(dt.mon != g_curMonth)
   {
      g_curMonth = dt.mon;
      g_pausedMonth = false;
      RefreshPL();
   }

   // 新しいM15バー確定時のみ判定 (バックテストの再現性確保)
   static datetime lastM15 = 0;
   datetime curM15 = iTime(_Symbol, PERIOD_M15, 0);
   bool newBar = (curM15 != lastM15);
   if(newBar) lastM15 = curM15;

   // 画面表示 (テスター高速化のためビジュアルモード以外では省略)
   if(!g_isTester || (bool)MQLInfoInteger(MQL_VISUAL_MODE))
      if(newBar) UpdateDisplay();

   if(!newBar) return;

   RefreshPL();
   CheckLossLimits();

   // ===== エントリー条件チェック =====
   if(g_pausedDay || g_pausedMonth) return;          // 損失リミット停止中
   if(HasPosition()) return;                          // ナンピン・複数持ち禁止
   if(IsNewsTime()) return;                           // 重要指標前後60分

   // スプレッドチェック
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if((ask - bid) / g_pip > MaxSpreadPips) return;

   int signal = GetSignal();
   if(signal != 0)
      ExecuteTrade(signal);
}

//+------------------------------------------------------------------+
//| インジケーター値取得 (失敗時 EMPTY_VALUE)                           |
//+------------------------------------------------------------------+
double Ind(int handle, int shift)
{
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) != 1) return EMPTY_VALUE;
   return buf[0];
}

//+------------------------------------------------------------------+
//| シグナル判定: H4トレンド → H1押し目 → M15ブレイク                   |
//+------------------------------------------------------------------+
int GetSignal()
{
   // === 環境認識: H4 EMA50/EMA200 (直近確定足) ===
   double emaFast = Ind(g_hEmaFast, 1);
   double emaSlow = Ind(g_hEmaSlow, 1);
   if(emaFast == EMPTY_VALUE || emaSlow == EMPTY_VALUE) return 0;

   // === 押し目判定: H1 RSI14 (直近確定足) ===
   double rsi = Ind(g_hRsi, 1);
   if(rsi == EMPTY_VALUE) return 0;

   int dir = 0;
   if(emaFast > emaSlow && rsi >= RSI_BuyMin && rsi <= RSI_BuyMax)
      dir = 1;   // 上昇トレンド中の押し目
   else if(emaFast < emaSlow && rsi >= RSI_SellMin && rsi <= RSI_SellMax)
      dir = -1;  // 下降トレンド中の戻り
   else
      return 0;

   // === エントリー: M15 直近高値/安値ブレイク ===
   // 確定足(1本目)の終値が、その前 BreakoutBars 本の高値/安値を抜けたか
   int hiIdx = iHighest(_Symbol, PERIOD_M15, MODE_HIGH, BreakoutBars, 2);
   int loIdx = iLowest(_Symbol, PERIOD_M15, MODE_LOW, BreakoutBars, 2);
   if(hiIdx < 0 || loIdx < 0) return 0;
   double hh = iHigh(_Symbol, PERIOD_M15, hiIdx);
   double ll = iLow(_Symbol, PERIOD_M15, loIdx);
   double c1 = iClose(_Symbol, PERIOD_M15, 1);

   if(dir == 1 && c1 > hh)  return 1;
   if(dir == -1 && c1 < ll) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| トレード実行 (ATRベースSL/TP + 1%リスクロット)                       |
//+------------------------------------------------------------------+
void ExecuteTrade(int dir)
{
   double atr = Ind(g_hAtr, 1);
   if(atr == EMPTY_VALUE || atr <= 0) return;

   double slDist = atr * SL_ATR_Mult;
   double tpDist = atr * TP_ATR_Mult;

   // 最低RRチェック (1:2未満は見送り)
   if(slDist <= 0 || tpDist / slDist < MinRR - 0.0001)
   {
      Print("RR不足のため見送り: RR=", DoubleToString(tpDist / slDist, 2));
      return;
   }

   // ブローカーの最小ストップ距離チェック
   double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) *
                       SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(slDist < stopsLevel)
   {
      Print("SL距離が最小ストップ距離未満のため見送り");
      return;
   }

   // ロット計算 (口座資金の RiskPercent % をSL距離で割る)
   double lot = CalcLot(slDist, dir);
   if(lot <= 0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool ok;

   if(dir == 1)
   {
      double sl = NormalizeDouble(ask - slDist, g_digits);
      double tp = NormalizeDouble(ask + tpDist, g_digits);
      ok = trade.Buy(lot, _Symbol, 0, sl, tp, "USDJPY_TPB");
   }
   else
   {
      double sl = NormalizeDouble(bid + slDist, g_digits);
      double tp = NormalizeDouble(bid - tpDist, g_digits);
      ok = trade.Sell(lot, _Symbol, 0, sl, tp, "USDJPY_TPB");
   }

   if(ok && trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      Print(dir == 1 ? "BUY" : "SELL", " エントリー Lot:", lot,
            " SL距離:", DoubleToString(slDist / g_pip, 1), "pips",
            " TP距離:", DoubleToString(tpDist / g_pip, 1), "pips");
      if(NotifyOnEntry)
         Notify((dir == 1 ? "BUY" : "SELL") + " エントリー " +
                DoubleToString(trade.ResultPrice(), g_digits) +
                " Lot:" + DoubleToString(lot, 2) +
                " SL:" + DoubleToString(slDist / g_pip, 1) + "pips" +
                " TP:" + DoubleToString(tpDist / g_pip, 1) + "pips");
   }
   else
   {
      Print("注文エラー: ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| ロット計算: 損失額が口座資金の RiskPercent % になるように            |
//+------------------------------------------------------------------+
double CalcLot(double slDist, int dir)
{
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * RiskPercent / 100.0;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0) return 0;

   double lossPerLot = slDist / tickSize * tickValue; // 1ロットあたりのSL時損失額
   if(lossPerLot <= 0) return 0;

   double lot  = riskMoney / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   lot = MathFloor(lot / step) * step;
   if(lot < minL)
   {
      Print("※計算ロットが最小ロット未満のため最小ロットを使用 (リスクは1%を超えます)");
      lot = minL;
   }
   if(lot > MaxLotCap) lot = MaxLotCap;
   if(lot > maxL)      lot = maxL;
   lot = NormalizeDouble(lot, 2);

   // 証拠金チェック
   double price = (dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                             : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double margin = 0;
   if(!OrderCalcMargin(dir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL,
                       _Symbol, lot, price, margin))
      return 0;
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   {
      Print("証拠金不足のため見送り (必要:", margin, ")");
      return 0;
   }
   return lot;
}

//+------------------------------------------------------------------+
//| 重要指標フィルター (前後 NewsStopMinutes 分)                        |
//| ※経済カレンダーはストラテジーテスターでは利用不可のため、            |
//|   テスター実行時は自動的に無効になります。                          |
//+------------------------------------------------------------------+
bool IsNewsTime()
{
   if(!UseNewsFilter) return false;
   if(g_isTester)     return false;

   // 負荷軽減のため60秒キャッシュ
   static datetime lastCheck  = 0;
   static bool     lastResult = false;
   if(TimeCurrent() - lastCheck < 60) return lastResult;
   lastCheck = TimeCurrent();

   lastResult = HasHighImpactNews("USD") || HasHighImpactNews("JPY");
   if(lastResult) Print("重要指標の前後", NewsStopMinutes, "分のため取引停止中");
   return lastResult;
}

bool HasHighImpactNews(string currency)
{
   MqlCalendarValue values[];
   datetime from = TimeCurrent() - NewsStopMinutes * 60;
   datetime to   = TimeCurrent() + NewsStopMinutes * 60;
   if(CalendarValueHistory(values, from, to, NULL, currency) <= 0) return false;

   for(int i = 0; i < ArraySize(values); i++)
   {
      MqlCalendarEvent event;
      if(!CalendarEventById(values[i].event_id, event)) continue;
      if(event.importance == CALENDAR_IMPORTANCE_HIGH) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| 損失リミットチェック (日次-3% / 月次-10%)                           |
//+------------------------------------------------------------------+
void CheckLossLimits()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);

   // 日次: 当日開始時残高に対する損失率
   double dayStartBal = balance - g_dailyPL;
   if(!g_pausedDay && dayStartBal > 0 &&
      g_dailyPL <= -dayStartBal * MaxDailyLossPct / 100.0)
   {
      g_pausedDay = true;
      CloseAllPositions("日次損失 -" + DoubleToString(MaxDailyLossPct, 0) + "% 到達");
   }

   // 月次: 当月開始時残高に対する損失率
   double monStartBal = balance - g_monthlyPL;
   if(!g_pausedMonth && monStartBal > 0 &&
      g_monthlyPL <= -monStartBal * MaxMonthlyLossPct / 100.0)
   {
      g_pausedMonth = true;
      CloseAllPositions("月次損失 -" + DoubleToString(MaxMonthlyLossPct, 0) + "% 到達");
   }
}

//+------------------------------------------------------------------+
//| 確定損益の集計 (日次/月次)                                          |
//+------------------------------------------------------------------+
void RefreshPL()
{
   g_dailyPL   = RealizedPL(iTime(_Symbol, PERIOD_D1, 0));
   g_monthlyPL = RealizedPL(MonthStart());
}

datetime MonthStart()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.day  = 1;
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   return StructToTime(dt);
}

double RealizedPL(datetime from)
{
   double pl = 0;
   if(!HistorySelect(from, TimeCurrent() + 86400)) return 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC) != MagicNumber) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      pl += HistoryDealGetDouble(ticket, DEAL_PROFIT)
          + HistoryDealGetDouble(ticket, DEAL_SWAP)
          + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
   }
   return pl;
}

//+------------------------------------------------------------------+
//| ポジション保有チェック (最大1ポジション = ナンピン禁止)               |
//+------------------------------------------------------------------+
bool HasPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == MagicNumber)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| 全ポジション決済                                                    |
//+------------------------------------------------------------------+
void CloseAllPositions(string reason)
{
   Print("★ 全ポジション決済: ", reason);
   Notify("★緊急停止: " + reason + " | 残高:" +
          DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 0) +
          AccountInfoString(ACCOUNT_CURRENCY));

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(!trade.PositionClose(ticket))
         Print("決済エラー: ", trade.ResultRetcode());
   }
}

//+------------------------------------------------------------------+
//| 決済検出 → 通知 + 損失リミット即時チェック                           |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != MagicNumber) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;

   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) return;

   double pl = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
             + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
             + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);

   RefreshPL();
   CheckLossLimits();

   if(NotifyOnClose)
      Notify("決済 損益:" + (pl >= 0 ? "+" : "") + DoubleToString(pl, 0) +
             AccountInfoString(ACCOUNT_CURRENCY) +
             " | 本日:" + DoubleToString(g_dailyPL, 0) +
             " 今月:" + DoubleToString(g_monthlyPL, 0));
}

//+------------------------------------------------------------------+
//| 通知 (テスターでは送信しない)                                       |
//+------------------------------------------------------------------+
void Notify(string msg)
{
   if(g_isTester || !UsePushNotify) return;
   if(!SendNotification("[USDJPY MT5] " + msg))
      Print("プッシュ通知エラー: ", GetLastError(), " (MetaQuotes IDの設定を確認)");
}

//+------------------------------------------------------------------+
//| 画面表示                                                          |
//+------------------------------------------------------------------+
void UpdateDisplay()
{
   double emaFast = Ind(g_hEmaFast, 1);
   double emaSlow = Ind(g_hEmaSlow, 1);
   double rsi     = Ind(g_hRsi, 1);
   double atr     = Ind(g_hAtr, 1);

   string trend = "計算中";
   if(emaFast != EMPTY_VALUE && emaSlow != EMPTY_VALUE)
      trend = (emaFast > emaSlow) ? "↑ 買い環境" : "↓ 売り環境";

   string info = "";
   info += "━━ USDJPY TrendPullback (MT5) ━━\n";
   info += "H4環境: " + trend + "\n";
   info += "H1 RSI: " + (rsi == EMPTY_VALUE ? "計算中" : DoubleToString(rsi, 1));
   info += "  (買:" + DoubleToString(RSI_BuyMin, 0) + "-" + DoubleToString(RSI_BuyMax, 0);
   info += " 売:" + DoubleToString(RSI_SellMin, 0) + "-" + DoubleToString(RSI_SellMax, 0) + ")\n";
   info += "ATR: " + (atr == EMPTY_VALUE ? "計算中" :
                      DoubleToString(atr / g_pip, 1) + "pips") + "\n";
   info += "━━━━━━━━━━━━━━━━\n";
   info += "残高: " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 0) + "\n";
   info += "本日損益: " + DoubleToString(g_dailyPL, 0) +
           (g_pausedDay ? " ★日次停止中" : "") + "\n";
   info += "今月損益: " + DoubleToString(g_monthlyPL, 0) +
           (g_pausedMonth ? " ★月次停止中" : "") + "\n";
   info += "ポジション: " + (HasPosition() ? "あり" : "なし") + "\n";

   Comment(info);
}
//+------------------------------------------------------------------+
