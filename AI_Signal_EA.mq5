//+------------------------------------------------------------------+
//|  AI Signal EA v5.0                                               |
//|  - يرسل بيانات السوق الحقيقية من MT5 للبوت                      |
//|  - Partial TP 20% + Breakeven                                    |
//|  - Trailing Stop ATR x1.5                                        |
//+------------------------------------------------------------------+
#property copyright "AI Trading Bot"
#property version   "5.80"

#include <Trade\Trade.mqh>

// ==========================================
// إعدادات
// ==========================================
input string BotURL      = "https://worker-production-0bf8.up.railway.app";
input int    CheckEvery  = 10;
input bool   EnableXAU   = true;
input bool   EnableBTC   = true;
input int    MagicNumber = 20240101;

// ==========================================
// متغيرات داخلية
// ==========================================
CTrade   trade;
datetime lastCheck          = 0;
datetime lastBalanceSend    = 0;
datetime lastPositionSend   = 0;
datetime lastMarketDataSend = 0;
int      lastSignalXAU      = 0;
int      lastSignalBTC      = 0;

// Cooldown بين Partials — 30 دقيقة لكل زوج
#define PARTIAL_COOLDOWN 1800
datetime lastPartialXAU = 0;
datetime lastPartialBTC = 0;

// Handles للمؤشرات - تُنشأ مرة واحدة في OnInit
int h_xau_d1_ema21, h_xau_d1_ema50;
int h_xau_h1_rsi, h_xau_h1_atr, h_xau_h1_ema21, h_xau_h1_ema50;
int h_xau_m15_rsi, h_xau_m15_atr, h_xau_m15_ema9, h_xau_m15_ema21;
int h_xau_m5_rsi,  h_xau_m5_ema9, h_xau_m5_ema21;
int h_btc_d1_ema21, h_btc_d1_ema50;
int h_btc_h1_rsi, h_btc_h1_atr, h_btc_h1_ema21, h_btc_h1_ema50;
int h_btc_m15_rsi, h_btc_m15_atr, h_btc_m15_ema9, h_btc_m15_ema21;
int h_btc_m5_rsi,  h_btc_m5_ema9, h_btc_m5_ema21;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   EventSetTimer(10);

   // XAUUSD handles
   h_xau_d1_ema21  = iMA("XAUUSD",  PERIOD_D1,  21, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_d1_ema50  = iMA("XAUUSD",  PERIOD_D1,  50, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_h1_ema21  = iMA("XAUUSD",  PERIOD_H1,  21, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_h1_ema50  = iMA("XAUUSD",  PERIOD_H1,  50, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_h1_rsi    = iRSI("XAUUSD", PERIOD_H1,  14, PRICE_CLOSE);
   h_xau_h1_atr    = iATR("XAUUSD", PERIOD_H1,  14);
   h_xau_m15_ema9  = iMA("XAUUSD",  PERIOD_M15,  9, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_m15_ema21 = iMA("XAUUSD",  PERIOD_M15, 21, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_m15_rsi   = iRSI("XAUUSD", PERIOD_M15, 14, PRICE_CLOSE);
   h_xau_m15_atr   = iATR("XAUUSD", PERIOD_M15, 14);
   h_xau_m5_ema9   = iMA("XAUUSD",  PERIOD_M5,   9, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_m5_ema21  = iMA("XAUUSD",  PERIOD_M5,  21, 0, MODE_EMA, PRICE_CLOSE);
   h_xau_m5_rsi    = iRSI("XAUUSD", PERIOD_M5,  14, PRICE_CLOSE);

   // BTCUSD handles
   h_btc_d1_ema21  = iMA("BTCUSD",  PERIOD_D1,  21, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_d1_ema50  = iMA("BTCUSD",  PERIOD_D1,  50, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_h1_ema21  = iMA("BTCUSD",  PERIOD_H1,  21, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_h1_ema50  = iMA("BTCUSD",  PERIOD_H1,  50, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_h1_rsi    = iRSI("BTCUSD", PERIOD_H1,  14, PRICE_CLOSE);
   h_btc_h1_atr    = iATR("BTCUSD", PERIOD_H1,  14);
   h_btc_m15_ema9  = iMA("BTCUSD",  PERIOD_M15,  9, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_m15_ema21 = iMA("BTCUSD",  PERIOD_M15, 21, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_m15_rsi   = iRSI("BTCUSD", PERIOD_M15, 14, PRICE_CLOSE);
   h_btc_m15_atr   = iATR("BTCUSD", PERIOD_M15, 14);
   h_btc_m5_ema9   = iMA("BTCUSD",  PERIOD_M5,   9, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_m5_ema21  = iMA("BTCUSD",  PERIOD_M5,  21, 0, MODE_EMA, PRICE_CLOSE);
   h_btc_m5_rsi    = iRSI("BTCUSD", PERIOD_M5,  14, PRICE_CLOSE);

   Print("✅ AI Signal EA v5.8 started | Partial1@15% Partial2@35% Partial3@60%");
   Print("🌐 Bot URL: ", BotURL);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   IndicatorRelease(h_xau_h1_ema21); IndicatorRelease(h_xau_h1_ema50);
   IndicatorRelease(h_xau_h1_rsi);   IndicatorRelease(h_xau_h1_atr);
   IndicatorRelease(h_xau_m15_ema9); IndicatorRelease(h_xau_m15_ema21);
   IndicatorRelease(h_xau_m15_rsi);  IndicatorRelease(h_xau_m15_atr);
   IndicatorRelease(h_xau_m5_ema9);  IndicatorRelease(h_xau_m5_ema21);
   IndicatorRelease(h_xau_m5_rsi);
   IndicatorRelease(h_btc_h1_ema21); IndicatorRelease(h_btc_h1_ema50);
   IndicatorRelease(h_btc_h1_rsi);   IndicatorRelease(h_btc_h1_atr);
   IndicatorRelease(h_btc_m15_ema9); IndicatorRelease(h_btc_m15_ema21);
   IndicatorRelease(h_btc_m15_rsi);  IndicatorRelease(h_btc_m15_atr);
   IndicatorRelease(h_btc_m5_ema9);  IndicatorRelease(h_btc_m5_ema21);
   IndicatorRelease(h_btc_m5_rsi);
}

//+------------------------------------------------------------------+
void OnTimer() { Run(); }
void OnTick()  { Run(); }

//+------------------------------------------------------------------+
void Run()
{
   if(TimeCurrent() - lastCheck < CheckEvery) return;
   lastCheck = TimeCurrent();

   if(TimeCurrent() - lastBalanceSend >= 60)
      { SendBalance(); lastBalanceSend = TimeCurrent(); }

   if(TimeCurrent() - lastPositionSend >= 30)
      { SendPositions(); lastPositionSend = TimeCurrent(); }

   if(TimeCurrent() - lastMarketDataSend >= 60)
      { SendMarketData(); lastMarketDataSend = TimeCurrent(); }

   ManagePositions();
   if(EnableXAU) ProcessSignal("XAUUSD", lastSignalXAU);
   if(EnableBTC) ProcessSignal("BTCUSD", lastSignalBTC);
}

//+------------------------------------------------------------------+
double GetVal(int handle, int shift=1)
{
   double buf[];
   if(CopyBuffer(handle, 0, shift, 1, buf) > 0) return buf[0];
   return 0;
}

string GetLast5(string symbol)
{
   double c[];
   if(CopyClose(symbol, PERIOD_M5, 1, 5, c) < 5) return "[]";
   string s = "[";
   for(int i=4;i>=0;i--) s += DoubleToString(c[i],5) + (i>0?",":"");
   return s + "]";
}

double SwingHigh(string symbol)
{
   double h[]; CopyHigh(symbol, PERIOD_M5, 1, 10, h);
   double mx=h[0]; for(int i=1;i<10;i++) if(h[i]>mx) mx=h[i]; return mx;
}

double SwingLow(string symbol)
{
   double l[]; CopyLow(symbol, PERIOD_M5, 1, 10, l);
   double mn=l[0]; for(int i=1;i<10;i++) if(l[i]<mn) mn=l[i]; return mn;
}

//+------------------------------------------------------------------+
void SendMarketData()
{
   double xau_h1e21=GetVal(h_xau_h1_ema21), xau_h1e50=GetVal(h_xau_h1_ema50);
   double xau_h1r=GetVal(h_xau_h1_rsi),     xau_h1a=GetVal(h_xau_h1_atr);
   double xau_m15e9=GetVal(h_xau_m15_ema9), xau_m15e21=GetVal(h_xau_m15_ema21);
   double xau_m15r=GetVal(h_xau_m15_rsi),   xau_m15a=GetVal(h_xau_m15_atr);
   double xau_m5e9=GetVal(h_xau_m5_ema9),   xau_m5e21=GetVal(h_xau_m5_ema21);
   double xau_m5r=GetVal(h_xau_m5_rsi),     xau_p=SymbolInfoDouble("XAUUSD",SYMBOL_BID);

   double btc_h1e21=GetVal(h_btc_h1_ema21), btc_h1e50=GetVal(h_btc_h1_ema50);
   double btc_h1r=GetVal(h_btc_h1_rsi),     btc_h1a=GetVal(h_btc_h1_atr);
   double btc_m15e9=GetVal(h_btc_m15_ema9), btc_m15e21=GetVal(h_btc_m15_ema21);
   double btc_m15r=GetVal(h_btc_m15_rsi),   btc_m15a=GetVal(h_btc_m15_atr);
   double btc_m5e9=GetVal(h_btc_m5_ema9),   btc_m5e21=GetVal(h_btc_m5_ema21);
   double btc_m5r=GetVal(h_btc_m5_rsi),     btc_p=SymbolInfoDouble("BTCUSD",SYMBOL_BID);

   string body="{\"symbols\":["
      +"{\"symbol\":\"XAUUSD\","
      +"\"price\":"+DoubleToString(xau_p,5)+","
      +"\"d1_trend\":\""+(GetVal(h_xau_d1_ema21)>GetVal(h_xau_d1_ema50)?"UP":"DOWN")+"\","
      +"\"h1_trend\":\""+(xau_h1e21>xau_h1e50?"UP":"DOWN")+"\","
      +"\"h1_ema21\":"+DoubleToString(xau_h1e21,5)+","
      +"\"h1_ema50\":"+DoubleToString(xau_h1e50,5)+","
      +"\"h1_rsi\":"+DoubleToString(xau_h1r,1)+","
      +"\"h1_atr\":"+DoubleToString(xau_h1a,5)+","
      +"\"m15_trend\":\""+(xau_m15e9>xau_m15e21?"UP":"DOWN")+"\","
      +"\"m15_ema9\":"+DoubleToString(xau_m15e9,5)+","
      +"\"m15_ema21\":"+DoubleToString(xau_m15e21,5)+","
      +"\"m15_rsi\":"+DoubleToString(xau_m15r,1)+","
      +"\"m15_atr\":"+DoubleToString(xau_m15a,5)+","
      +"\"m5_ema9\":"+DoubleToString(xau_m5e9,5)+","
      +"\"m5_ema21\":"+DoubleToString(xau_m5e21,5)+","
      +"\"m5_rsi\":"+DoubleToString(xau_m5r,1)+","
      +"\"m5_last5\":"+GetLast5("XAUUSD")+","
      +"\"swing_high\":"+DoubleToString(SwingHigh("XAUUSD"),5)+","
      +"\"swing_low\":"+DoubleToString(SwingLow("XAUUSD"),5)+"},"
      +"{\"symbol\":\"BTCUSD\","
      +"\"price\":"+DoubleToString(btc_p,5)+","
      +"\"d1_trend\":\""+(GetVal(h_btc_d1_ema21)>GetVal(h_btc_d1_ema50)?"UP":"DOWN")+"\","
      +"\"h1_trend\":\""+(btc_h1e21>btc_h1e50?"UP":"DOWN")+"\","
      +"\"h1_ema21\":"+DoubleToString(btc_h1e21,5)+","
      +"\"h1_ema50\":"+DoubleToString(btc_h1e50,5)+","
      +"\"h1_rsi\":"+DoubleToString(btc_h1r,1)+","
      +"\"h1_atr\":"+DoubleToString(btc_h1a,5)+","
      +"\"m15_trend\":\""+(btc_m15e9>btc_m15e21?"UP":"DOWN")+"\","
      +"\"m15_ema9\":"+DoubleToString(btc_m15e9,5)+","
      +"\"m15_ema21\":"+DoubleToString(btc_m15e21,5)+","
      +"\"m15_rsi\":"+DoubleToString(btc_m15r,1)+","
      +"\"m15_atr\":"+DoubleToString(btc_m15a,5)+","
      +"\"m5_ema9\":"+DoubleToString(btc_m5e9,5)+","
      +"\"m5_ema21\":"+DoubleToString(btc_m5e21,5)+","
      +"\"m5_rsi\":"+DoubleToString(btc_m5r,1)+","
      +"\"m5_last5\":"+GetLast5("BTCUSD")+","
      +"\"swing_high\":"+DoubleToString(SwingHigh("BTCUSD"),5)+","
      +"\"swing_low\":"+DoubleToString(SwingLow("BTCUSD"),5)+"}"
      +"]}";

   char data[],result[];
   StringToCharArray(body,data,0,StringLen(body));
   string hdr="Content-Type: application/json\r\n", rHdr;
   int res=WebRequest("POST",BotURL+"/marketdata",hdr,5000,data,result,rHdr);
   if(res==200) Print("📊 Market data sent");
   else Print("⚠️ Market data failed: ",res);
}

//+------------------------------------------------------------------+
void SendPositions()
{
   string xau="false",btc="false";
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong t=PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      string s=PositionGetString(POSITION_SYMBOL);
      if(s=="XAUUSD") xau="true";
      if(s=="BTCUSD") btc="true";
   }
   string body="{\"positions\":{\"XAUUSD\":"+xau+",\"BTCUSD\":"+btc+"}}";
   char data[],result[]; StringToCharArray(body,data,0,StringLen(body));
   string hdr="Content-Type: application/json\r\n",rHdr;
   WebRequest("POST",BotURL+"/positions",hdr,5000,data,result,rHdr);
}

//+------------------------------------------------------------------+
void ManagePositions()
{
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;

      double price =PositionGetDouble(POSITION_PRICE_CURRENT);
      double sl    =PositionGetDouble(POSITION_SL);
      double tp    =PositionGetDouble(POSITION_TP);
      double open  =PositionGetDouble(POSITION_PRICE_OPEN);
      double volume=PositionGetDouble(POSITION_VOLUME);
      int    type  =(int)PositionGetInteger(POSITION_TYPE);
      string sym   =PositionGetString(POSITION_SYMBOL);
      int    digits=(int)SymbolInfoInteger(sym,SYMBOL_DIGITS);

      // ATR Trailing Stop
      int atrH=(sym=="XAUUSD")?h_xau_h1_atr:h_btc_h1_atr;
      double trail=GetVal(atrH)*1.5;
      if(trail<=0) trail=50*SymbolInfoDouble(sym,SYMBOL_POINT);

      // مسافة الـ TP الكاملة
      double tpDist = MathAbs(tp - open);
      if(tpDist <= 0) continue;

      // البريك إيفن فوق الدخول قليلاً لتغطية التكاليف
      double beCover = (sym=="XAUUSD") ? 1.5 : 15.0;

      // مستويات الإغلاق الجزئي
      double level1 = 0.15; // 15% من المسافة → Partial1
      double level2 = 0.35; // 35% من المسافة → Partial2
      double level3 = 0.60; // 60% من المسافة → Partial3

      // فلاغ Partial2 تم (بناءً على مستوى SL)
      bool p2Done = false;
      if(type==POSITION_TYPE_BUY)
         p2Done = (sl >= NormalizeDouble(open + tpDist * 0.20, digits));
      else
         p2Done = (sl <= NormalizeDouble(open - tpDist * 0.20, digits) && sl > 0);

      // فلاغات: هل تم الإغلاق الجزئي؟
      // نستخدم SL لمعرفة المرحلة الحالية
      bool beSet = false;
      if(type==POSITION_TYPE_BUY)
         beSet = (sl >= NormalizeDouble(open + beCover * 0.5, digits));
      else
         beSet = (sl <= NormalizeDouble(open - beCover * 0.5, digits) && sl > 0);

      // Cooldown check لكل زوج
      bool isXAU    = (sym == "XAUUSD");
      datetime lastP = isXAU ? lastPartialXAU : lastPartialBTC;
      bool cooldownOK = (TimeCurrent() - lastP >= PARTIAL_COOLDOWN);

      if(type==POSITION_TYPE_BUY)
      {
         double price1 = open + tpDist * level1;
         double price2 = open + tpDist * level2;
         double price3 = open + tpDist * level3;

         if(tp > 0 && !beSet && price >= price1 && volume >= 0.02 && cooldownOK)
         {
            // Partial1: أغلق 20% عند 15%
            double closeVol = NormalizeDouble(volume * 0.20, 2);
            if(closeVol < 0.01) closeVol = 0.01;
            trade.PositionClosePartial(ticket, closeVol);
            if(isXAU) lastPartialXAU = TimeCurrent(); else lastPartialBTC = TimeCurrent();
            Print("💰 Partial1 (15%) | ",sym," | Closed:",closeVol," lots");
            double beSL = NormalizeDouble(open + beCover, digits);
            if(beSL > sl) { trade.PositionModify(ticket, beSL, tp); Print("🛡️ BE+ | ",sym," → ",beSL); }
         }
         else if(beSet && !p2Done && price >= price2 && volume >= 0.02)
         {
            // Partial2: أغلق 25% عند 35% (بدون Cooldown)
            double closeVol = NormalizeDouble(volume * 0.25, 2);
            if(closeVol < 0.01) closeVol = 0.01;
            if(closeVol < volume - 0.01)
            {
               trade.PositionClosePartial(ticket, closeVol);
               Print("💰 Partial2 (35%) | ",sym," | Closed:",closeVol," lots");
            }
         }
         else if(beSet && p2Done && price >= price3 && volume >= 0.02)
         {
            // Partial3: أغلق 30% عند 60% (بدون Cooldown)
            double closeVol = NormalizeDouble(volume * 0.30, 2);
            if(closeVol < 0.01) closeVol = 0.01;
            if(closeVol < volume - 0.01)
            {
               trade.PositionClosePartial(ticket, closeVol);
               Print("💰 Partial3 (60%) | ",sym," | Closed:",closeVol," lots");
            }
         }
         else
         {
            double newSL=NormalizeDouble(price-trail,digits);
            if(newSL>sl && newSL>0) trade.PositionModify(ticket,newSL,tp);
         }
      }
      else if(type==POSITION_TYPE_SELL)
      {
         double price1 = open - tpDist * level1;
         double price2 = open - tpDist * level2;
         double price3 = open - tpDist * level3;

         if(tp > 0 && !beSet && price <= price1 && volume >= 0.02 && cooldownOK)
         {
            // Partial1: أغلق 20% عند 15%
            double closeVol = NormalizeDouble(volume * 0.20, 2);
            if(closeVol < 0.01) closeVol = 0.01;
            trade.PositionClosePartial(ticket, closeVol);
            if(isXAU) lastPartialXAU = TimeCurrent(); else lastPartialBTC = TimeCurrent();
            Print("💰 Partial1 (15%) | ",sym," | Closed:",closeVol," lots");
            double beSL = NormalizeDouble(open - beCover, digits);
            if(beSL < sl || sl == 0) { trade.PositionModify(ticket, beSL, tp); Print("🛡️ BE+ | ",sym," → ",beSL); }
         }
         else if(beSet && !p2Done && price <= price2 && volume >= 0.02)
         {
            // Partial2: أغلق 25% عند 35% (بدون Cooldown)
            double closeVol = NormalizeDouble(volume * 0.25, 2);
            if(closeVol < 0.01) closeVol = 0.01;
            if(closeVol < volume - 0.01)
            {
               trade.PositionClosePartial(ticket, closeVol);
               Print("💰 Partial2 (35%) | ",sym," | Closed:",closeVol," lots");
            }
         }
         else if(beSet && p2Done && price <= price3 && volume >= 0.02)
         {
            // Partial3: أغلق 30% عند 60% (بدون Cooldown)
            double closeVol = NormalizeDouble(volume * 0.30, 2);
            if(closeVol < 0.01) closeVol = 0.01;
            if(closeVol < volume - 0.01)
            {
               trade.PositionClosePartial(ticket, closeVol);
               Print("💰 Partial3 (60%) | ",sym," | Closed:",closeVol," lots");
            }
         }
         else
         {
            double newSL=NormalizeDouble(price+trail,digits);
            if((newSL<sl || sl==0) && newSL>0) trade.PositionModify(ticket,newSL,tp);
         }
      }
   }
}

//+------------------------------------------------------------------+
void ProcessSignal(string symbol,int &lastID)
{
   string resp=FetchURL(BotURL+"/signal/"+symbol);
   if(resp=="") return;
   int    sid=(int)GetJsonInt(resp,"id");
   string action=GetJsonString(resp,"action");
   double lot=GetJsonDouble(resp,"lot");
   double sl=GetJsonDouble(resp,"sl");
   double tp1=GetJsonDouble(resp,"tp1");
   if(sid==0||sid==lastID||action=="WAIT") return;
   if(symbol!=GetJsonString(resp,"symbol")) return;

   // تحقق من عدم وجود صفقة مفتوحة بنفس الاتجاه على نفس الزوج
   bool alreadyOpen = false;
   for(int i=0;i<PositionsTotal();i++)
   {
      if(PositionGetTicket(i)<=0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      int posType = (int)PositionGetInteger(POSITION_TYPE);
      if(action=="BUY"  && posType==POSITION_TYPE_BUY)  { alreadyOpen=true; break; }
      if(action=="SELL" && posType==POSITION_TYPE_SELL) { alreadyOpen=true; break; }
   }
   if(alreadyOpen)
   {
      lastID=sid; // احفظ الـ ID عشان ما يتكرر
      Print("⏭️ Skip | ",symbol," | Already open in same direction");
      return;
   }

   Print("📡 Signal | ",symbol," | ",action," | ID:",sid);
   bool ok=false;
   if(action=="BUY")  ok=OpenBuy(symbol,lot,sl,tp1);
   if(action=="SELL") ok=OpenSell(symbol,lot,sl,tp1);
   if(ok){ lastID=sid; Print("✅ Executed | ",symbol," | ",action); }
}

//+------------------------------------------------------------------+
bool OpenBuy(string symbol,double lot,double sl,double tp)
{
   CloseOrders(symbol,ORDER_TYPE_SELL);
   double ask=SymbolInfoDouble(symbol,SYMBOL_ASK);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);

   // حد أدنى للـ SL
   double minDist = (symbol == "XAUUSD") ? 15.0 : 400.0;
   if(ask - sl < minDist) sl = NormalizeDouble(ask - minDist, digits);

   if(sl>=ask) sl=NormalizeDouble(ask-(ask*0.003),digits);
   bool r=trade.Buy(lot,symbol,ask,NormalizeDouble(sl,digits),NormalizeDouble(tp,digits),"AI Signal BUY");
   if(!r) Print("❌ Buy failed: ",trade.ResultRetcodeDescription());
   return r;
}

bool OpenSell(string symbol,double lot,double sl,double tp)
{
   CloseOrders(symbol,ORDER_TYPE_BUY);
   double bid=SymbolInfoDouble(symbol,SYMBOL_BID);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);

   // حد أدنى للـ SL
   double minDist = (symbol == "XAUUSD") ? 15.0 : 400.0;
   if(sl - bid < minDist) sl = NormalizeDouble(bid + minDist, digits);

   if(sl<=bid) sl=NormalizeDouble(bid+(bid*0.003),digits);
   bool r=trade.Sell(lot,symbol,bid,NormalizeDouble(sl,digits),NormalizeDouble(tp,digits),"AI Signal SELL");
   if(!r) Print("❌ Sell failed: ",trade.ResultRetcodeDescription());
   return r;
}

void CloseOrders(string symbol,ENUM_ORDER_TYPE type)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i);
      if(PositionSelectByTicket(t))
         if(PositionGetString(POSITION_SYMBOL)==symbol &&
            PositionGetInteger(POSITION_MAGIC)==MagicNumber &&
            PositionGetInteger(POSITION_TYPE)==type)
            trade.PositionClose(t);
   }
}

//+------------------------------------------------------------------+
void SendBalance()
{
   string body="{\"balance\":"+DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2)+"}";
   char data[],result[]; StringToCharArray(body,data,0,StringLen(body));
   string hdr="Content-Type: application/json\r\n",rHdr;
   int res=WebRequest("POST",BotURL+"/balance",hdr,5000,data,result,rHdr);
   if(res==200) Print("💰 Balance sent: $",AccountInfoDouble(ACCOUNT_BALANCE));
}

string FetchURL(string url)
{
   char data[],result[];
   string hdr="Content-Type: application/json\r\n",rHdr;
   int res=WebRequest("GET",url,hdr,5000,data,result,rHdr);
   if(res==-1){ int e=GetLastError(); if(e==4060) Print("⚠️ Allow WebRequest in settings"); else Print("❌ WebRequest error: ",e); return ""; }
   return CharArrayToString(result);
}

string GetJsonString(string json,string key)
{
   string s="\""+key+"\":\""; int i=StringFind(json,s); if(i==-1) return "";
   i+=StringLen(s); int e=StringFind(json,"\"",i); if(e==-1) return "";
   return StringSubstr(json,i,e-i);
}

double GetJsonDouble(string json,string key)
{
   string s="\""+key+"\":"; int i=StringFind(json,s); if(i==-1) return 0;
   i+=StringLen(s);
   int e=StringFind(json,",",i), e2=StringFind(json,"}",i);
   if(e==-1||(e2!=-1&&e2<e)) e=e2; if(e==-1) return 0;
   return StringToDouble(StringSubstr(json,i,e-i));
}

long GetJsonInt(string json,string key){ return(long)GetJsonDouble(json,key); }
//+------------------------------------------------------------------+
