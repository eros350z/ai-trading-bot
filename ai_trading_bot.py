#!/usr/bin/env python3
"""
AI Trading Bot - Claude Powered
يحلل الذهب والبيتكوين كل 15 دقيقة ويتداول تلقائياً
"""

import os
import requests
import schedule
import time
import json
import threading
from datetime import datetime
from flask import Flask, jsonify
import pytz

# ==========================================
# الإعدادات
# ==========================================
BOT_TOKEN    = "8764834987:AAHZ_dC1TmEfTO-Pbmd1AyZQcuHsNFQZy64"
CHAT_ID      = "6652508619"
CLAUDE_API   = "https://api.anthropic.com/v1/messages"
CLAUDE_KEY   = os.environ.get("CLAUDE_KEY", "")
print(f"🔑 CLAUDE_KEY length: {len(CLAUDE_KEY)} chars")
TIMEZONE     = "Asia/Kuwait"

ACCOUNT_BALANCE  = 2000.0
RISK_PERCENT     = 1.0
MAX_DAILY_LOSS   = 2.0
MAX_DRAWDOWN     = 10.0

SYMBOLS = ["XAUUSD", "BTCUSD", "USDJPY", "ETHUSD"]

daily_pnl     = 0.0
start_balance = ACCOUNT_BALANCE
day_start_bal = ACCOUNT_BALANCE
last_day      = datetime.now().date()

# ==========================================
# تخزين آخر Signal لكل رمز
# ==========================================
latest_signals = {
    "XAUUSD": {"action": "WAIT", "id": 0},
    "BTCUSD": {"action": "WAIT", "id": 0},
    "USDJPY": {"action": "WAIT", "id": 0},
    "ETHUSD": {"action": "WAIT", "id": 0},
}
signal_counter = 0

# ==========================================
# Flask Server
# ==========================================
app = Flask(__name__)

@app.route("/signal/<symbol>", methods=["GET"])
def get_signal(symbol):
    symbol = symbol.upper()
    if symbol in latest_signals:
        return jsonify(latest_signals[symbol])
    return jsonify({"action": "WAIT", "id": 0})

@app.route("/status", methods=["GET"])
def status():
    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)
    return jsonify({
        "status": "running",
        "time": now.strftime("%Y-%m-%d %H:%M"),
        "balance": ACCOUNT_BALANCE,
        "daily_pnl": round(daily_pnl, 2),
        "signals": latest_signals
    })

@app.route("/balance", methods=["POST"])
def update_balance():
    global real_balance
    from flask import request
    data = request.get_json()
    if data and "balance" in data:
        real_balance = float(data["balance"])
        print(f"💰 Balance updated from MT5: ${real_balance}")
    return jsonify({"status": "ok"})

@app.route("/", methods=["GET"])
def home():
    return jsonify({"bot": "AI Trading Bot", "status": "online", "balance": real_balance})

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ==========================================
# جلب السعر
# ==========================================
def get_market_data(symbol):
    try:
        ticker_map = {
            "XAUUSD": "GC=F",
            "BTCUSD": "BTC-USD",
            "USDJPY": "JPY=X",
            "ETHUSD": "ETH-USD",
        }
        ticker = ticker_map.get(symbol, symbol)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=30m&range=2d"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()

        result = data["chart"]["result"][0]
        meta   = result["meta"]
        closes = result["indicators"]["quote"][0]["close"]
        highs  = result["indicators"]["quote"][0]["high"]
        lows   = result["indicators"]["quote"][0]["low"]

        closes = [x for x in closes if x is not None]
        highs  = [x for x in highs  if x is not None]
        lows   = [x for x in lows   if x is not None]

        if len(closes) < 10:
            return None

        price = meta["regularMarketPrice"]
        prev  = meta["chartPreviousClose"]
        change = price - prev
        pct   = (change / prev) * 100

        ema8  = calc_ema(closes, 8)
        ema21 = calc_ema(closes, 21)
        rsi   = calc_rsi(closes, 14)
        atr   = calc_atr(highs, lows, closes, 14)
        last5 = [round(c, 2) for c in closes[-5:]]

        return {
            "symbol": symbol, "price": round(price, 2),
            "change": round(change, 2), "pct": round(pct, 2),
            "ema8": round(ema8, 2), "ema21": round(ema21, 2),
            "rsi": round(rsi, 1), "atr": round(atr, 2),
            "high24": round(max(highs[-48:]), 2) if len(highs) >= 48 else round(max(highs), 2),
            "low24":  round(min(lows[-48:]),  2) if len(lows)  >= 48 else round(min(lows),  2),
            "last5": last5,
        }
    except Exception as e:
        print(f"❌ Error getting {symbol} data: {e}")
        return None

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

def get_news_warning():
    try:
        kuwait_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(kuwait_tz)
        hour = now.hour
        high_impact_hours = {
            16: "NFP / CPI / Fed Decision",
            17: "US Economic Data",
            15: "US Market Open",
            21: "FOMC Minutes",
        }
        if hour in high_impact_hours:
            return f"High Impact News Expected: {high_impact_hours[hour]}"
        return None
    except:
        return None

def ask_gemini(market_data_list):
    try:
        context = "You are an expert forex and crypto trader. Analyze the following market data and make a trading decision.\n\n"
        for data in market_data_list:
            if data is None:
                continue
            context += f"{data['symbol']}|{data['price']}|RSI:{data['rsi']}|EMA8:{data['ema8']}|EMA21:{data['ema21']}|ATR:{data['atr']}|H:{data['high24']}|L:{data['low24']}\n"
        context += f"""
Balance:${ACCOUNT_BALANCE} Risk:{RISK_PERCENT}% DailyPnL:{round(daily_pnl,2)}%
Rules: EMA8>EMA21=uptrend, RSI buy:40-65 sell:35-60, avoid RSI>75 or <25
SL=1.5xATR, TP1=1.5xATR, TP2=2.5xATR, TP3=4xATR

Respond ONLY with a valid JSON array, no markdown, no explanation:
[
  {{"symbol": "XAUUSD", "action": "BUY or SELL or WAIT", "reason": "brief reason", "confidence": 1-10, "entry": price, "sl": price, "tp1": price, "tp2": price, "tp3": price}},
  {{"symbol": "BTCUSD", "action": "BUY or SELL or WAIT", "reason": "brief reason", "confidence": 1-10, "entry": price, "sl": price, "tp1": price, "tp2": price, "tp3": price}},
  {{"symbol": "USDJPY", "action": "BUY or SELL or WAIT", "reason": "brief reason", "confidence": 1-10, "entry": price, "sl": price, "tp1": price, "tp2": price, "tp3": price}},
  {{"symbol": "ETHUSD", "action": "BUY or SELL or WAIT", "reason": "brief reason", "confidence": 1-10, "entry": price, "sl": price, "tp1": price, "tp2": price, "tp3": price}}
]"""

        response = requests.post(
            CLAUDE_API,
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_KEY,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": context}]
            },
            timeout=30
        )
        if response.status_code == 200:
            text = response.json()["content"][0]["text"].strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        else:
            print(f"❌ Claude API Error: {response.status_code} | {response.text[:300]}")
            return None
    except Exception as e:
        print(f"❌ Claude Error: {e}")
        return None

def calc_lot(balance, risk_pct, sl_points, symbol):
    risk_amount = balance * (risk_pct / 100)

    # حد أقصى للـ lot بناءً على الرصيد الحقيقي
    if balance < 500:
        max_lot = 0.01
    elif balance < 1000:
        max_lot = 0.05
    elif balance < 3000:
        max_lot = 0.1
    elif balance < 5000:
        max_lot = 0.5
    else:
        max_lot = 1.0

    if symbol == "XAUUSD":
        lot = risk_amount / (sl_points * 1.0)
        min_lot = 0.01
    elif symbol == "USDJPY":
        lot = risk_amount / (sl_points * 10.0)
        min_lot = 0.01
    elif symbol == "ETHUSD":
        lot = risk_amount / (sl_points * 0.01)
        min_lot = 0.1
        max_lot = max(max_lot, 0.1)
    else:  # BTCUSD
        lot = risk_amount / (sl_points * 0.001)
        min_lot = 0.01

    return round(max(min_lot, min(lot, max_lot)), 2)

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=15)
        if r.status_code == 200:
            print(f"✅ Telegram sent | {datetime.now().strftime('%H:%M:%S')}")
        else:
            print(f"❌ Telegram error: {r.text}")
    except Exception as e:
        print(f"❌ Telegram exception: {e}")

def update_signal(decision, lot):
    global signal_counter
    signal_counter += 1
    symbol = decision["symbol"]
    latest_signals[symbol] = {
        "id":         signal_counter,
        "symbol":     symbol,
        "action":     decision["action"],
        "lot":        lot,
        "entry":      decision["entry"],
        "sl":         decision["sl"],
        "tp1":        decision["tp1"],
        "tp2":        decision["tp2"],
        "tp3":        decision["tp3"],
        "time":       datetime.now().strftime("%Y.%m.%d %H:%M"),
        "reason":     decision.get("reason", ""),
        "confidence": decision.get("confidence", 0)
    }
    print(f"📡 Signal updated | {symbol} | {decision['action']} | ID: {signal_counter}")

# ==========================================
# الدورة الرئيسية
# ==========================================
def run_analysis():
    global daily_pnl, day_start_bal, last_day

    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)
    print(f"\n{'='*50}")
    print(f"🔄 Analysis | {now.strftime('%Y-%m-%d %H:%M')} Kuwait")
    print(f"{'='*50}")

    if now.date() != last_day:
        daily_pnl = 0.0
        day_start_bal = ACCOUNT_BALANCE
        last_day = now.date()
        print("📅 New day reset")

    if now.weekday() >= 5:
        global SYMBOLS
        SYMBOLS = ["BTCUSD", "ETHUSD"]
        print("📅 Weekend - Gold stopped, BTC continues")
    else:
        SYMBOLS = ["XAUUSD", "BTCUSD", "USDJPY", "ETHUSD"]

    if daily_pnl <= -MAX_DAILY_LOSS:
        print(f"🛑 Daily loss limit reached: {daily_pnl}%")
        send_telegram(f"🛑 AI Bot: Daily loss limit {MAX_DAILY_LOSS}% reached. Stopped for today.")
        return

    news = get_news_warning()
    if news:
        print(f"⚠️ News warning: {news}")
        send_telegram(f"⚠️ AI Bot paused - {news}")
        return

    market_data = []
    for symbol in SYMBOLS:
        data = get_market_data(symbol)
        if data:
            market_data.append(data)
            print(f"📊 {symbol}: ${data['price']} | RSI: {data['rsi']} | EMA8: {data['ema8']} vs EMA21: {data['ema21']}")

    if not market_data:
        print("❌ No market data available")
        return

    print("🤖 Asking Claude AI...")
    decisions = ask_gemini(market_data)

    if not decisions:
        print("❌ No decision from Claude")
        return

    for decision in decisions:
        symbol = decision.get("symbol")
        action = decision.get("action")
        reason = decision.get("reason", "")
        conf   = decision.get("confidence", 0)

        print(f"\n📋 {symbol}: {action} | Confidence: {conf}/10 | {reason}")

        if action == "WAIT":
            continue

        if conf < 6:
            print(f"⏳ Confidence too low ({conf}/10) - Skip")
            continue

        sl_pts = abs(decision["entry"] - decision["sl"])
        lot = calc_lot(real_balance, RISK_PERCENT, sl_pts, symbol)

        # ✅ تحديث Signal للـ EA
        update_signal(decision, lot)

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

    # ✅ Flask في thread منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Signal server running on port 8080")

    schedule.every(15).minutes.do(run_analysis)
    schedule.every().day.at("20:00").do(daily_report)

    run_analysis()

    print("\n✅ Bot running... Press Ctrl+C to stop")
    while True:
        schedule.run_pending()
        time.sleep(30)
