#!/usr/bin/env python3
"""
AI Trading Bot v2 - Multi-Timeframe Analysis
H1 Trend + M15 Confirmation + M5 Entry
"""

import os
import requests
import schedule
import time
import json
import threading
from datetime import datetime
from flask import Flask, jsonify, request
import pytz

# ==========================================
# الإعدادات
# ==========================================
BOT_TOKEN   = "8764834987:AAHZ_dC1TmEfTO-Pbmd1AyZQcuHsNFQZy64"
CHAT_ID     = "6652508619"
CLAUDE_API  = "https://api.anthropic.com/v1/messages"
CLAUDE_KEY  = os.environ.get("CLAUDE_KEY", "")
TIMEZONE    = "Asia/Kuwait"

RISK_PERCENT   = 1.0
MAX_DAILY_LOSS = 2.0

# ==========================================
# متغيرات
# ==========================================
real_balance   = 2000.0
day_start_real = 2000.0
daily_pnl      = 0.0
last_day       = datetime.now().date()
signal_counter = 0
current_news   = None
bot_enabled    = True  # تحكم يدوي بالبوت
stoppedToday   = False  # توقف بسبب الخسارة اليومية

open_positions = {s: False for s in SYMBOLS}
latest_signals = {s: {"action": "WAIT", "id": 0} for s in SYMBOLS}

# تخزين الأخبار
_news_cache     = []
_news_last_fetch = None

# ==========================================
# Flask
# ==========================================
app = Flask(__name__)

@app.route("/signal/<symbol>")
def get_signal(symbol):
    return jsonify(latest_signals.get(symbol.upper(), {"action": "WAIT", "id": 0}))

@app.route("/positions", methods=["POST"])
def update_positions():
    global open_positions
    data = request.get_json()
    if data and "positions" in data:
        open_positions = data["positions"]
    return jsonify({"status": "ok"})

@app.route("/balance", methods=["POST"])
def update_balance():
    global real_balance, daily_pnl, day_start_real
    data = request.get_json()
    if data and "balance" in data:
        real_balance = float(data["balance"])
        if day_start_real == 2000.0 and real_balance != 2000.0:
            day_start_real = real_balance
        if day_start_real > 0:
            daily_pnl = round(((real_balance - day_start_real) / day_start_real) * 100, 2)
        print(f"💰 Balance: ${real_balance} | P&L: {daily_pnl}%")
    return jsonify({"status": "ok"})

@app.route("/control/<action>")
def control_bot(action):
    global bot_enabled, stoppedToday, daily_pnl, day_start_real
    if action == "enable":
        bot_enabled = True
        stoppedToday = False
        # إعادة ضبط الـ P&L من الرصيد الحالي
        day_start_real = real_balance
        daily_pnl = 0.0
        print("✅ Bot manually ENABLED | P&L reset | New start: $" + str(real_balance))
        return jsonify({"status": "enabled", "balance": real_balance, "pnl_reset": True})
    elif action == "disable":
        bot_enabled = False
        print("🛑 Bot manually DISABLED")
        return jsonify({"status": "disabled"})
    return jsonify({"status": "unknown"})

@app.route("/")
def dashboard():
    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)

    news_banner = f'''<div style="background:#2a1a00;border:1px solid #ff8800;border-radius:8px;margin:15px 30px;padding:12px 20px;color:#ff8800;">
    ⚠️ التداول متوقف: {current_news}</div>''' if current_news else ""

    rows = ""
    for sym in SYMBOLS:
        is_open = open_positions.get(sym, False)
        sig = latest_signals.get(sym, {})
        action = sig.get("action", "WAIT")
        action_color = "#00ff88" if action == "BUY" else "#ff4444" if action == "SELL" else "#888"
        status = '<span style="color:#00ff88">● مفتوحة</span>' if is_open else '<span style="color:#555">○ لا يوجد</span>'
        rows += f"""<tr>
            <td>{sym}</td><td>{status}</td>
            <td style="color:{action_color}">{action}</td>
            <td>{sig.get("confidence","-")}/10</td>
            <td>{sig.get("entry","-")}</td>
            <td>{sig.get("sl","-")}</td>
            <td>{sig.get("tp1","-")}</td>
        </tr>"""

    pnl_color    = "#ff4444" if daily_pnl < 0 else "#00ff88"
    status_color = "#00ff88" if bot_enabled else "#ff4444"
    status_bg    = "#1a2a1a" if bot_enabled else "#2a1a1a"
    status_text  = "🟢 شغال" if bot_enabled else "🔴 متوقف"

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>AI Trading Bot v2</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a0f;color:#e0e0e0;font-family:'Segoe UI',sans-serif}}
.header{{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:18px 30px;border-bottom:1px solid #2a2a4a;display:flex;justify-content:space-between;align-items:center}}
.header h1{{color:#00ff88;font-size:1.3em}}
.time{{color:#888;font-size:0.82em}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;padding:18px 30px}}
.card{{background:#12122a;border:1px solid #2a2a4a;border-radius:10px;padding:18px}}
.card .label{{color:#888;font-size:0.78em;margin-bottom:6px}}
.card .value{{font-size:1.5em;font-weight:bold;color:#00ff88}}
.section{{padding:0 30px 20px}}
.section h2{{color:#666;font-size:0.85em;margin-bottom:10px;text-transform:uppercase;letter-spacing:1px}}
table{{width:100%;border-collapse:collapse;background:#12122a;border-radius:10px;overflow:hidden}}
th{{background:#1a1a3a;color:#888;font-size:0.78em;padding:10px 14px;text-align:right}}
td{{padding:10px 14px;border-top:1px solid #1a1a2e;font-size:0.88em}}
.dot{{display:inline-block;width:7px;height:7px;border-radius:50%;background:#00ff88;margin-left:7px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.3}}}}
.footer{{text-align:center;color:#333;font-size:0.72em;padding:16px}}
.badge{{background:#1a2a1a;border:1px solid #00ff88;color:#00ff88;padding:2px 8px;border-radius:4px;font-size:0.75em}}
</style>
</head>
<body>
<div class="header">
  <h1>🤖 AI Trading Bot v2 <span class="dot"></span></h1>
  <div style="display:flex;align-items:center;gap:15px">
    <span style="background:{status_bg};border:1px solid {status_color};color:{status_color};padding:4px 12px;border-radius:6px;font-size:0.85em">
      {status_text}
    </span>
    <div class="time">🕐 {now.strftime('%Y-%m-%d %H:%M')} Kuwait &nbsp;|&nbsp; <span class="badge">H1 + M15 + M5</span></div>
  </div>
</div>
{news_banner}
<div class="cards">
  <div class="card"><div class="label">💰 الرصيد</div><div class="value">${real_balance:,.2f}</div></div>
  <div class="card"><div class="label">📊 P&L اليوم</div><div class="value" style="color:{pnl_color}">{'+' if daily_pnl>0 else ''}{daily_pnl:.2f}%</div></div>
  <div class="card"><div class="label">📡 آخر Signal</div><div class="value" style="color:#fff">ID #{signal_counter}</div></div>
  <div class="card"><div class="label">🔄 الأزواج</div><div class="value" style="color:#fff">{len(SYMBOLS)}</div></div>
  <div class="card"><div class="label">⏱️ الفريم</div><div class="value" style="color:#fff;font-size:1em">H1+M15+M5</div></div>
  <div class="card"><div class="label">🛡️ حد الخسارة</div><div class="value" style="color:#fff">{MAX_DAILY_LOSS}%</div></div>
</div>
<div class="section">
  <h2>📋 الأزواج والإشارات</h2>
  <table>
    <thead><tr><th>الزوج</th><th>الصفقة</th><th>الإشارة</th><th>الثقة</th><th>الدخول</th><th>SL</th><th>TP1</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div style="text-align:center;padding:15px 30px">
  <a href="/control/enable" style="background:#1D9E75;color:#fff;padding:10px 25px;border-radius:8px;text-decoration:none;margin:5px;display:inline-block">✅ تشغيل البوت</a>
  <a href="/control/disable" style="background:#E24B4A;color:#fff;padding:10px 25px;border-radius:8px;text-decoration:none;margin:5px;display:inline-block">🛑 إيقاف البوت</a>
</div>
<div class="footer">AI Trading Bot v2 — Multi-Timeframe | Powered by Claude AI<br>
Status: {'🟢 Active' if bot_enabled else '🔴 Disabled'} | Daily Loss: {daily_pnl:.2f}%</div>
</body></html>"""

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

# ==========================================
# جلب البيانات - Multi-Timeframe
# ==========================================
def get_market_data(symbol):
    try:
        ticker_map = {
            "XAUUSD": "GC=F",
            "BTCUSD": "BTC-USD",
            "USDJPY": "JPY=X",
        }
        ticker = ticker_map.get(symbol, symbol)
        headers = {"User-Agent": "Mozilla/5.0"}

        def fetch(interval, period):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={period}"
            r = requests.get(url, headers=headers, timeout=10)
            data = r.json()
            result = data["chart"]["result"][0]
            closes = [x for x in result["indicators"]["quote"][0]["close"] if x]
            highs  = [x for x in result["indicators"]["quote"][0]["high"]  if x]
            lows   = [x for x in result["indicators"]["quote"][0]["low"]   if x]
            return closes, highs, lows

        # H1 - الاتجاه العام
        h1_closes, h1_highs, h1_lows = fetch("1h", "5d")
        # M15 - التأكيد
        m15_closes, m15_highs, m15_lows = fetch("15m", "5d")
        # M5 - الدخول
        m5_closes, m5_highs, m5_lows = fetch("5m", "1d")

        if len(h1_closes) < 21 or len(m15_closes) < 21 or len(m5_closes) < 10:
            return None

        price = m5_closes[-1]

        def ema(data, p):
            if len(data) < p: return data[-1]
            k = 2/(p+1); e = data[0]
            for x in data[1:]: e = x*k + e*(1-k)
            return round(e, 5)

        def rsi(data, p=14):
            if len(data) < p+1: return 50
            g = [max(data[i]-data[i-1],0) for i in range(1,len(data))]
            l = [max(data[i-1]-data[i],0) for i in range(1,len(data))]
            ag = sum(g[-p:])/p; al = sum(l[-p:])/p
            return round(100-(100/(1+ag/al)) if al else 100, 1)

        def atr(h, l, c, p=14):
            if len(h) < p+1: return h[-1]-l[-1]
            trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1,len(h))]
            return round(sum(trs[-p:])/p, 5)

        def swing_low(lows, n=10):
            return round(min(lows[-n:]), 5)

        def swing_high(highs, n=10):
            return round(max(highs[-n:]), 5)

        return {
            "symbol": symbol,
            "price":  round(price, 5),
            # H1
            "h1_ema21": ema(h1_closes, 21),
            "h1_ema50": ema(h1_closes, 50),
            "h1_rsi":   rsi(h1_closes),
            "h1_atr":   atr(h1_highs, h1_lows, h1_closes),
            "h1_trend": "UP" if ema(h1_closes, 21) > ema(h1_closes, 50) else "DOWN",
            # M15
            "m15_ema9":  ema(m15_closes, 9),
            "m15_ema21": ema(m15_closes, 21),
            "m15_rsi":   rsi(m15_closes),
            "m15_atr":   atr(m15_highs, m15_lows, m15_closes),
            "m15_trend": "UP" if ema(m15_closes, 9) > ema(m15_closes, 21) else "DOWN",
            # M5
            "m5_ema9":   ema(m5_closes, 9),
            "m5_ema21":  ema(m5_closes, 21),
            "m5_rsi":    rsi(m5_closes),
            "m5_atr":    atr(m5_highs, m5_lows, m5_closes),
            "m5_last5":  [round(x, 5) for x in m5_closes[-5:]],
            # Swing Points للـ SL
            "swing_low":  swing_low(m5_lows),
            "swing_high": swing_high(m5_highs),
        }
    except Exception as e:
        print(f"❌ Data error {symbol}: {e}")
        return None

# ==========================================
# الأخبار الحقيقية
# ==========================================
def fetch_news():
    global _news_cache, _news_last_fetch
    try:
        kuwait_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(kuwait_tz)
        if _news_last_fetch and (now - _news_last_fetch).seconds < 3600:
            return _news_cache
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            _news_cache = r.json()
            _news_last_fetch = now
            print(f"📰 News updated: {len(_news_cache)} events")
        return _news_cache
    except:
        return _news_cache

def get_news_warning():
    try:
        kuwait_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(kuwait_tz)
        for event in fetch_news():
            if event.get("impact","").lower() != "high": continue
            if event.get("currency","") not in ["USD","EUR","JPY","GBP"]: continue
            time_str = event.get("time","")
            if not time_str or time_str in ["All Day","Tentative"]: continue
            try:
                dt = datetime.strptime(f"{event['date']} {time_str}", "%Y-%m-%d %I:%M%p")
                dt = pytz.timezone("America/New_York").localize(dt).astimezone(kuwait_tz)
                diff = (dt - now).total_seconds() / 60
                if -10 <= diff <= 30:
                    return f"{event.get('title','')} ({event.get('currency','')}) @ {dt.strftime('%H:%M')}"
            except: continue
        return None
    except:
        return None

# ==========================================
# Claude AI - تحليل Multi-Timeframe
# ==========================================
def ask_claude(market_data_list):
    try:
        context = """You are a professional forex and crypto trader specializing in multi-timeframe analysis.

Analyze the following market data across 3 timeframes (H1, M15, M5) and make precise trading decisions.

ANALYSIS FRAMEWORK:
1. H1 = Overall trend direction (must align with trade direction)
2. M15 = Trend confirmation (must confirm H1 direction)  
3. M5 = Precise entry signal (pullback to EMA or breakout)

ENTRY RULES:
- BUY only when: H1 trend=UP AND M15 trend=UP AND M5 shows bullish signal (price above M5 EMA9, RSI 45-62)
- SELL only when: H1 trend=DOWN AND M15 trend=DOWN AND M5 shows bearish signal (price below M5 EMA9, RSI 38-55)
- WAIT if timeframes conflict or RSI is extreme (>70 or <30) or H1 RSI >68

RISK RULES:
- SL = swing_low for BUY, swing_high for SELL (already calculated)
- TP1 = 1.5x SL distance, TP2 = 2.5x, TP3 = 4x
- Minimum confidence 7/10 to trade

MARKET DATA:
"""
        for d in market_data_list:
            if not d: continue
            context += f"""
{d['symbol']} | Price: {d['price']}
H1:  Trend={d['h1_trend']} | EMA21={d['h1_ema21']} | EMA50={d['h1_ema50']} | RSI={d['h1_rsi']} | ATR={d['h1_atr']}
M15: Trend={d['m15_trend']} | EMA9={d['m15_ema9']} | EMA21={d['m15_ema21']} | RSI={d['m15_rsi']} | ATR={d['m15_atr']}
M5:  EMA9={d['m5_ema9']} | EMA21={d['m5_ema21']} | RSI={d['m5_rsi']} | ATR={d['m5_atr']} | Last5={d['m5_last5']}
SL_BUY={d['swing_low']} | SL_SELL={d['swing_high']}
---"""

        symbols_json = ",\n  ".join([
            f'{{"symbol":"{d["symbol"]}","action":"BUY or SELL or WAIT","reason":"brief reason","confidence":1-10,"entry":{d["price"]},"sl":price,"tp1":price,"tp2":price,"tp3":price}}'
            for d in market_data_list if d
        ])

        context += f"""
Account Balance: ${real_balance}
Risk per trade: {RISK_PERCENT}%

Respond ONLY with valid JSON array, no markdown:
[
  {symbols_json}
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
                if text.startswith("json"): text = text[4:]
            return json.loads(text.strip())
        else:
            print(f"❌ Claude Error: {response.status_code} | {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Claude Error: {e}")
        return None

# ==========================================
# حساب الـ Lot
# ==========================================
def calc_lot(balance, risk_pct, sl_distance, symbol):
    risk_amount = balance * (risk_pct / 100)
    if sl_distance <= 0: return 0.01

    # قيمة النقطة لكل زوج
    point_values = {
        "XAUUSD": 1.0,
        "BTCUSD": 0.001,
        "USDJPY": 10.0,
    }
    pv = point_values.get(symbol, 1.0)
    lot = risk_amount / (sl_distance * pv)

    # حد أقصى بناءً على الرصيد
    if balance < 500:
        max_lot = 0.05
    elif balance < 1000:
        max_lot = 0.1
    elif balance < 3000:
        max_lot = 0.2
    elif balance < 5000:
        max_lot = 0.5
    else:
        max_lot = 1.0

    # حد أدنى لكل زوج
    min_lot = 0.05

    # تأكد إن max_lot أكبر من min_lot
    max_lot = max(max_lot, min_lot)

    return round(max(0.05, min(lot, max_lot)), 2)

# ==========================================
# Telegram
# ==========================================
def send_telegram(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=15
        )
        if r.status_code == 200:
            print(f"✅ Telegram sent | {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Telegram: {e}")

# ==========================================
# الدورة الرئيسية - كل 5 دقائق
# ==========================================
def run_analysis():
    global daily_pnl, last_day, day_start_real, signal_counter, current_news, bot_enabled, stoppedToday

    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)

    print(f"\n{'='*50}")
    print(f"🔄 Analysis | {now.strftime('%Y-%m-%d %H:%M')} Kuwait")
    print(f"{'='*50}")

    # تحقق من التشغيل اليدوي
    if not bot_enabled:
        print("🛑 Bot is manually disabled")
        return

    # تصفير يوم جديد
    if now.date() != last_day:
        daily_pnl = 0.0
        day_start_real = real_balance
        last_day = now.date()
        print("📅 New day reset")

    # ويك اند - كريبتو فقط
    active_symbols = SYMBOLS
    if now.weekday() >= 5:
        active_symbols = ["BTCUSD"]
        print("📅 Weekend mode")

    # حد الخسارة اليومية
    if daily_pnl <= -MAX_DAILY_LOSS:
        stoppedToday = True
        print(f"🛑 Daily loss limit: {daily_pnl}%")
        return

    # الأخبار
    news = get_news_warning()
    if news:
        current_news = news
        print(f"⚠️ News: {news} - Skipping")
        return
    else:
        current_news = None

    # جلب البيانات
    market_data = []
    for symbol in active_symbols:
        data = get_market_data(symbol)
        if data:
            market_data.append(data)
            print(f"📊 {symbol}: ${data['price']} | H1:{data['h1_trend']} | M15:{data['m15_trend']} | M5 RSI:{data['m5_rsi']}")

    if not market_data:
        print("❌ No market data")
        return

    # Claude يحلل
    print("🤖 Asking Claude AI (H1+M15+M5)...")
    decisions = ask_claude(market_data)
    if not decisions:
        print("❌ No decision")
        return

    # تنفيذ القرارات
    for decision in decisions:
        symbol  = decision.get("symbol")
        action  = decision.get("action")
        reason  = decision.get("reason", "")
        conf    = decision.get("confidence", 0)

        print(f"📋 {symbol}: {action} | {conf}/10 | {reason}")

        if action == "WAIT": continue
        if conf < 7:
            print(f"⏳ Low confidence ({conf}/10) - Skip")
            continue
        if open_positions.get(symbol, False):
            print(f"⏭️ {symbol}: Already open - Skip")
            continue

        # حساب الـ Lot
        entry  = decision.get("entry", 0)
        sl     = decision.get("sl", 0)

        market = next((d for d in market_data if d["symbol"] == symbol), None)
        if market:
            # SL = H1 ATR × 1.5 مع حد أدنى ثابت لكل زوج
            min_sl_dists = {
                "XAUUSD": 2.0,
                "BTCUSD": 200.0,
                "USDJPY": 0.15,
            }
            atr_sl = market["h1_atr"] * 1.5
            fixed_sl = min_sl_dists.get(symbol, 0)
            sl_dist = max(atr_sl, fixed_sl)

            if action == "BUY":
                sl  = round(entry - sl_dist, 5)
                tp1 = round(entry + sl_dist * 1.5, 5)
                tp2 = round(entry + sl_dist * 2.5, 5)
                tp3 = round(entry + sl_dist * 4.0, 5)
            else:
                sl  = round(entry + sl_dist, 5)
                tp1 = round(entry - sl_dist * 1.5, 5)
                tp2 = round(entry - sl_dist * 2.5, 5)
                tp3 = round(entry - sl_dist * 4.0, 5)

            decision["sl"]  = sl
            decision["tp1"] = tp1
            decision["tp2"] = tp2
            decision["tp3"] = tp3
            print(f"📐 SL from H1 ATR×1.5 | {symbol} | dist: {sl_dist:.5f} | SL:{sl} | TP1:{tp1}")
        else:
            sl_dist = abs(entry - sl)

        lot = calc_lot(real_balance, RISK_PERCENT, sl_dist, symbol)

        # تحديث الـ Signal
        signal_counter += 1
        latest_signals[symbol] = {
            "id":         signal_counter,
            "symbol":     symbol,
            "action":     action,
            "lot":        lot,
            "entry":      entry,
            "sl":         sl,
            "tp1":        decision.get("tp1", 0),
            "tp2":        decision.get("tp2", 0),
            "tp3":        decision.get("tp3", 0),
            "reason":     reason,
            "confidence": conf,
            "time":       now.strftime("%Y.%m.%d %H:%M"),
        }
        print(f"📡 Signal updated | {symbol} | {action} | ID:{signal_counter}")

        # Telegram
        icon = "🟢" if action == "BUY" else "🔴"
        send_telegram(f"""{icon} AI Signal v2
Symbol: {symbol}
Action: {action}
Confidence: {conf}/10
Reason: {reason}
---
Lot: {lot}
Entry: {entry}
SL: {sl}
TP1: {decision.get('tp1')}
TP2: {decision.get('tp2')}
TP3: {decision.get('tp3')}
---
{now.strftime('%Y-%m-%d %H:%M')} Kuwait
[H1+M15+M5 Analysis]""")

# ==========================================
# تقرير يومي
# ==========================================
def daily_report():
    kuwait_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(kuwait_tz)
    if now.weekday() >= 5: return
    send_telegram(f"""📊 Daily Report v2
Date: {now.strftime('%Y-%m-%d')}
Balance: ${real_balance:,.2f}
P&L: {'+' if daily_pnl > 0 else ''}{daily_pnl:.2f}%
Status: {'🟢 Active' if daily_pnl > -MAX_DAILY_LOSS else '🛑 Stopped'}
Symbols: {len(SYMBOLS)}
Strategy: H1+M15+M5 Multi-Timeframe""")

# ==========================================
# تشغيل
# ==========================================
if __name__ == "__main__":
    import sys

    print("🤖 AI Trading Bot v2 - Multi-Timeframe")
    print(f"📊 Symbols: {', '.join(SYMBOLS)}")
    print(f"⏱️  Interval: Every 5 minutes")
    print(f"📈 Strategy: H1 Trend + M15 Confirm + M5 Entry")
    print("="*50)

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_analysis()
        sys.exit(0)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Signal server running on port 8080")

    schedule.every(5).minutes.do(run_analysis)
    schedule.every().day.at("20:00").do(daily_report)

    # انتظر دقيقة لاستلام الرصيد الحقيقي من MT5
    print("⏳ Waiting 60s for MT5 balance...")
    time.sleep(60)
    run_analysis()

    print("\n✅ Bot running...")
    while True:
        schedule.run_pending()
        time.sleep(30)
