#!/usr/bin/env python3
"""
AI Trading Bot - Claude Powered
يحلل الذهب والبيتكوين كل 30 دقيقة ويتداول تلقائياً
"""

import requests
import schedule
import time
import json
from datetime import datetime
import pytz

# ==========================================
# الإعدادات
# ==========================================
BOT_TOKEN    = "8764834987:AAHZ_dC1TmEfTO-Pbmd1AyZQcuHsNFQZy64"
CHAT_ID      = "6652508619"
GEMINI_API   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GEMINI_KEY   = "AIzaSyA_0Pv9QdxyIcGdCXjVqWFf2IXlu2qBVsE"
TIMEZONE     = "Asia/Kuwait"

# إعدادات المخاطرة
ACCOUNT_BALANCE  = 2000.0   # رأس المال
RISK_PERCENT     = 1.0      # نسبة المخاطرة لكل صفقة
MAX_DAILY_LOSS   = 2.0      # أقصى خسارة يومية %
MAX_DRAWDOWN     = 10.0     # أقصى drawdown %

# الرموز
SYMBOLS = ["XAUUSD", "BTCUSD"]

# تتبع الخسائر
daily_pnl     = 0.0
start_balance = ACCOUNT_BALANCE
day_start_bal = ACCOUNT_BALANCE
last_day      = datetime.now().date()

# ==========================================
# جلب السعر والبيانات
# ==========================================
def get_market_data(symbol):
    try:
        ticker = "GC=F" if symbol == "XAUUSD" else "BTC-USD"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=30m&range=2d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        result = data["chart"]["result"][0]
        meta   = result["meta"]
        closes = result["indicators"]["quote"][0]["close"]
        highs  = result["indicators"]["quote"][0]["high"]
        lows   = result["indicators"]["quote"][0]["low"]
        volumes= result["indicators"]["quote"][0]["volume"]

        # تنظيف القيم None
        closes  = [x for x in closes  if x is not None]
        highs   = [x for x in highs   if x is not None]
        lows    = [x for x in lows    if x is not None]

        if len(closes) < 10:
            return None

        price   = meta["regularMarketPrice"]
        prev    = meta["chartPreviousClose"]
        change  = price - prev
        pct     = (change / prev) * 100

        # حساب المؤشرات
        ema8  = calc_ema(closes, 8)
        ema21 = calc_ema(closes, 21)
        rsi   = calc_rsi(closes, 14)
        atr   = calc_atr(highs, lows, closes, 14)

        # آخر 5 شموع للتحليل
        last5 = [round(c, 2) for c in closes[-5:]]

        return {
            "symbol":  symbol,
            "price":   round(price, 2),
            "change":  round(change, 2),
            "pct":     round(pct, 2),
            "ema8":    round(ema8, 2),
            "ema21":   round(ema21, 2),
            "rsi":     round(rsi, 1),
            "atr":     round(atr, 2),
            "high24":  round(max(highs[-48:]), 2) if len(highs) >= 48 else round(max(highs), 2),
            "low24":   round(min(lows[-48:]), 2)  if len(lows)  >= 48 else round(min(lows),  2),
            "last5":   last5,
        }
    except Exception as e:
        print(f"❌ Error getting {symbol} data: {e}")
        return None

# ==========================================
# حساب المؤشرات
# ==========================================
def calc_ema(data, period):
    if len(data) < period:
        return data[-1]
    k = 2 / (period + 1)
    ema = data[0]
    for price in data[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def calc_rsi(data, period=14):
    if len(data) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(data)):
        diff = data[i] - data[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def calc_atr(highs, lows, closes, period=14):
    if len(highs) < period + 1:
        return highs[-1] - lows[-1]
    trs = []
    for i in range(1, len(highs)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i-1]),
                 abs(lows[i]  - closes[i-1]))
        trs.append(tr)
    return sum(trs[-period:]) / period

# ==========================================
# جلب الأخبار المهمة
# ==========================================
def get_news_warning():
    try:
        kuwait_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(kuwait_tz)
        hour = now.hour

        # أوقات الأخبار المهمة (بتوقيت الكويت)
        high_impact_hours = {
            16: "NFP / CPI / Fed Decision",
            17: "US Economic Data",
            15: "US Market Open",
            21: "FOMC Minutes",
        }

        if hour in high_impact_hours:
            return f"⚠️ High Impact News Expected: {high_impact_hours[hour]}"
        return None
    except:
        return None

# ==========================================
# Gemini AI - قرار التداول
# ==========================================
def ask_gemini(market_data_list):
    try:
        context = "You are an expert forex and crypto trader. Analyze the following market data and make a trading decision.\n\n"

        for data in market_data_list:
            if data is None:
                continue
            context += f"""SYMBOL: {data['symbol']}
Price: {data['price']} | Change: {data['change']} ({data['pct']}%)
EMA8: {data['ema8']} | EMA21: {data['ema21']}
RSI: {data['rsi']} | ATR: {data['atr']}
24h High: {data['high24']} | 24h Low: {data['low24']}
Last 5 closes: {data['last5']}
---
"""

        context += f"""
Account Balance: ${ACCOUNT_BALANCE}
Risk per trade: {RISK_PERCENT}%
Max daily loss: {MAX_DAILY_LOSS}%
Daily P&L so far: {round(daily_pnl, 2)}%

Rules:
- Only trade with clear trend (EMA8 > EMA21 = uptrend, EMA8 < EMA21 = downtrend)
- RSI: Buy only 40-65, Sell only 35-60
- Avoid trading if RSI > 75 or < 25
- SL = 1.5 x ATR, TP1 = 1.5 x ATR, TP2 = 2.5 x ATR, TP3 = 4 x ATR

Respond ONLY with a valid JSON array, no markdown, no explanation:
[
  {{"symbol": "XAUUSD", "action": "BUY or SELL or WAIT", "reason": "brief reason", "confidence": 1-10, "entry": price, "sl": price, "tp1": price, "tp2": price, "tp3": price}},
  {{"symbol": "BTCUSD", "action": "BUY or SELL or WAIT", "reason": "brief reason", "confidence": 1-10, "entry": price, "sl": price, "tp1": price, "tp2": price, "tp3": price}}
]"""

        response = requests.post(
            f"{GEMINI_API}?key={GEMINI_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": context}]}]},
            timeout=30
        )

        if response.status_code == 200:
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            decisions = json.loads(text.strip())
            return decisions
        else:
            print(f"❌ Gemini API Error: {response.status_code} | {response.text}")
            return None

    except Exception as e:
        print(f"❌ Gemini Error: {e}")
        return None

# ==========================================
# حساب حجم اللوت
# ==========================================
def calc_lot(balance, risk_pct, sl_points, symbol):
    risk_amount = balance * (risk_pct / 100)
    if symbol == "XAUUSD":
        # XAUUSD: $1 per 0.01 lot per point
        lot = risk_amount / (sl_points * 1.0)
    else:
        # BTCUSD: approximate
        lot = risk_amount / (sl_points * 0.001)

    lot = round(max(0.01, min(lot, 2.0)), 2)
    return lot

# ==========================================
# إرسال تيليغرام
# ==========================================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            print(f"✅ Telegram sent | {datetime.now().strftime('%H:%M:%S')}")
        else:
            print(f"❌ Telegram error: {r.text}")
    except Exception as e:
        print(f"❌ Telegram exception: {e}")

# ==========================================
# إرسال أمر للـ EA على MT5
# ==========================================
def send_order_to_mt5(decision, lot):
    """
    يكتب الأمر في ملف يقرأه الـ EA على MT5
    الـ EA راح يتحقق من الملف كل 5 ثواني
    """
    order = {
        "symbol":  decision["symbol"],
        "action":  decision["action"],
        "lot":     lot,
        "entry":   decision["entry"],
        "sl":      decision["sl"],
        "tp1":     decision["tp1"],
        "tp2":     decision["tp2"],
        "tp3":     decision["tp3"],
        "time":    datetime.now().strftime("%Y.%m.%d %H:%M")
    }
    # سيتم ربطه مع الـ EA لاحقاً
    print(f"📤 Order: {json.dumps(order, indent=2)}")
    return order

# ==========================================
# الدورة الرئيسية - كل 30 دقيقة
# ==========================================
def run_analysis():
    global daily_pnl, day_start_bal, last_day

    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)
    print(f"\n{'='*50}")
    print(f"🔄 Analysis | {now.strftime('%Y-%m-%d %H:%M')} Kuwait")
    print(f"{'='*50}")

    # تصفير اليوم الجديد
    if now.date() != last_day:
        daily_pnl   = 0.0
        day_start_bal = ACCOUNT_BALANCE
        last_day    = now.date()
        print("📅 New day reset")

    # ويك اند - الذهب يوقف، البيتكوين يكمل
    if now.weekday() >= 5:
        global SYMBOLS
        SYMBOLS = ["BTCUSD"]  # فقط البيتكوين في الويك اند
        print("📅 Weekend - Gold stopped, BTC continues")
    else:
        SYMBOLS = ["XAUUSD", "BTCUSD"]

    # تحقق من الخسارة اليومية
    if daily_pnl <= -MAX_DAILY_LOSS:
        print(f"🛑 Daily loss limit reached: {daily_pnl}%")
        send_telegram(f"🛑 AI Bot: Daily loss limit {MAX_DAILY_LOSS}% reached. Stopped for today.")
        return

    # تحقق من الأخبار
    news = get_news_warning()
    if news:
        print(f"⚠️ News warning: {news}")
        send_telegram(f"⚠️ AI Bot paused - {news}")
        return

    # جلب البيانات
    market_data = []
    for symbol in SYMBOLS:
        data = get_market_data(symbol)
        if data:
            market_data.append(data)
            print(f"📊 {symbol}: ${data['price']} | RSI: {data['rsi']} | EMA8: {data['ema8']} vs EMA21: {data['ema21']}")

    if not market_data:
        print("❌ No market data available")
        return

    # سؤال Claude
    print("🤖 Asking Claude AI...")
    decisions = ask_gemini(market_data)

    if not decisions:
        print("❌ No decision from Claude")
        return

    # تنفيذ القرارات
    for decision in decisions:
        symbol  = decision.get("symbol")
        action  = decision.get("action")
        reason  = decision.get("reason", "")
        conf    = decision.get("confidence", 0)

        print(f"\n📋 {symbol}: {action} | Confidence: {conf}/10 | {reason}")

        if action == "WAIT":
            continue

        # تحقق من الثقة - مو أقل من 7
        if conf < 7:
            print(f"⏳ Confidence too low ({conf}/10) - Skip")
            continue

        # حساب الـ Lot
        sl_pts = abs(decision["entry"] - decision["sl"])
        lot = calc_lot(ACCOUNT_BALANCE, RISK_PERCENT, sl_pts, symbol)

        # إرسال الأمر
        order = send_order_to_mt5(decision, lot)

        # إرسال تيليغرام
        icon = "🟢" if action == "BUY" else "🔴"
        msg = f"""{icon} AI Trading Signal
Symbol: {symbol}
Action: {action}
Confidence: {conf}/10
Reason: {reason}
---
Lot: {lot}
Entry: {decision['entry']}
SL: {decision['sl']}
---
TP1: {decision['tp1']}
TP2: {decision['tp2']}
TP3: {decision['tp3']}
---
{now.strftime('%Y-%m-%d %H:%M')} Kuwait"""

        send_telegram(msg)

# ==========================================
# تقرير يومي
# ==========================================
def daily_report():
    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)
    if now.weekday() >= 5:
        return

    msg = f"""📊 Daily AI Trading Report
Date: {now.strftime('%Y-%m-%d')}
---
Balance: ${ACCOUNT_BALANCE}
Daily P&L: {round(daily_pnl, 2)}%
Status: {'🟢 Active' if daily_pnl > -MAX_DAILY_LOSS else '🛑 Stopped'}
---
Symbols: {', '.join(SYMBOLS)}
Interval: Every 15 minutes
Risk per trade: {RISK_PERCENT}%"""

    send_telegram(msg)

# ==========================================
# تشغيل البوت
# ==========================================
if __name__ == "__main__":
    import sys

    print("🤖 AI Trading Bot - Claude Powered")
    print(f"📊 Symbols: {', '.join(SYMBOLS)}")
    print(f"⏱️  Interval: Every 15 minutes")
    print(f"💰 Balance: ${ACCOUNT_BALANCE} | Risk: {RISK_PERCENT}%")
    print(f"🛡️  Max Daily Loss: {MAX_DAILY_LOSS}% | Max DD: {MAX_DRAWDOWN}%")
    print("="*50)

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🧪 Test mode - Running analysis now...")
        run_analysis()
        sys.exit(0)

    # جدولة
    schedule.every(15).minutes.do(run_analysis)
    schedule.every().day.at("20:00").do(daily_report)  # UTC = 11 PM Kuwait

    # تشغيل فوري عند البداية
    run_analysis()

    print("\n✅ Bot running... Press Ctrl+C to stop")
    while True:
        schedule.run_pending()
        time.sleep(30)
