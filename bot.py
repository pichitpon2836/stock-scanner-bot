import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import pytz
import time
from datetime import datetime
import curl_cffi.requests as cffi_requests

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID   = 'YOUR_CHAT_ID'
TIMEZONE  = 'Asia/Bangkok'

# Universe กว้างขึ้น — ครอบคลุม Large/Mid-cap Growth + AI/Tech + Energy
WATCHLIST = [
    # Mega-cap Tech & AI
    'AAPL','MSFT','GOOGL','AMZN','META','NVDA','TSM','AVGO','AMD','SMCI',
    # Growth Tech
    'ADBE','CRM','NFLX','TTD','SNOW','DDOG','NET','CRWD','PANW','ZS',
    # AI Infrastructure
    'VRT','DELL','ANET','MRVL','ARM',
    # Financials & Others
    'JPM','V','MA','GS','BLK',
    # Healthcare
    'LLY','TMO','ABBV','ISRG',
    # Consumer
    'HD','COST','MCD','NKE',
    # Clean Energy Momentum
    'FCEL','PLUG','BE','BLDP',
    # Momentum Specials
    'PLTR','RKLB','IONQ','RXRX',
    # Original list survivors
    'UNH','WMT','SCHW','MU','BULL'
]

# ============================================================
# TELEGRAM
# ============================================================
def send(text):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"[Send Error] {e}")
    time.sleep(0.5)

# ============================================================
# DATA FETCH — ดึงครั้งเดียว ใช้ทุก module
# ============================================================
def fetch_all(ticker):
    """ดึง price history + fundamentals ในครั้งเดียว"""
    try:
        session = cffi_requests.Session(impersonate="chrome110")
        tk = yf.Ticker(ticker, session=session)
        info = tk.info

        price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not price:
            return None

        # History: ดึง 5Y monthly + 2Y daily ในครั้งเดียว
        df_d = yf.download(ticker, period="2y", interval="1d", progress=False)
        df_m = yf.download(ticker, period="5y", interval="1mo", progress=False)

        if len(df_d) < 200 or len(df_m) < 10:
            return None

        return {
            'ticker':       ticker,
            'name':         info.get('shortName', ticker),
            'price':        float(price),
            'df_d':         df_d,
            'df_m':         df_m,
            # Fundamentals
            'eps_fwd':      info.get('forwardEps'),
            'growth':       info.get('earningsGrowth'),
            'rev_growth':   info.get('revenueGrowth'),
            'fcf':          info.get('freeCashflow'),
            'shares':       info.get('sharesOutstanding'),
            'roe':          info.get('returnOnEquity'),
            'net_margin':   info.get('profitMargins'),
            'gross_margin': info.get('grossMargins'),
            'peg':          info.get('pegRatio'),
            'forward_pe':   info.get('forwardPE'),
            'market_cap':   info.get('marketCap'),
            'short_float':  info.get('shortPercentOfFloat'),
            'week52_high':  info.get('fiftyTwoWeekHigh'),
            'week52_low':   info.get('fiftyTwoWeekLow'),
            'avg_volume':   info.get('averageVolume'),
            'volume':       info.get('volume'),
        }
    except Exception as e:
        print(f"[{ticker}] fetch error: {e}")
        return None

# ============================================================
# MODULE 1: WEINSTEIN STAGE 2
# Criteria: Price > EMA200d AND Price > EMA10M
# ============================================================
def check_weinstein(d):
    try:
        df_d = d['df_d']
        df_m = d['df_m']
        price = d['price']

        ema200_d = ta.ema(df_d['Close'], length=200).iloc[-1]
        ema10_m  = ta.ema(df_m['Close'], length=10).iloc[-1]

        above_ema200 = price > ema200_d
        above_ema10m = price > ema10_m

        return {
            'pass': above_ema200 and above_ema10m,
            'ema200d': round(float(ema200_d), 2),
            'ema10m':  round(float(ema10_m), 2),
            'pct_above_200': round((price / float(ema200_d) - 1) * 100, 1),
        }
    except Exception as e:
        print(f"[{d['ticker']}] Weinstein error: {e}")
        return {'pass': False}

# ============================================================
# MODULE 2: MINERVINI SEPA
# Criteria: Price > 50MA > 150MA > 200MA + RS + Volume surge
# ============================================================
def check_minervini(d):
    try:
        df   = d['df_d']
        price = d['price']

        sma50  = df['Close'].rolling(50).mean().iloc[-1]
        sma150 = df['Close'].rolling(150).mean().iloc[-1]
        sma200 = df['Close'].rolling(200).mean().iloc[-1]

        # MA Stack: Price > 50 > 150 > 200
        ma_stack = (price > sma50 > sma150 > sma200)

        # 200 SMA trending up (slope over last 20 days)
        sma200_20ago = df['Close'].rolling(200).mean().iloc[-20]
        ma200_trending_up = float(sma200) > float(sma200_20ago)

        # Price within 25% of 52W High
        w52h = d.get('week52_high')
        near_high = (price >= w52h * 0.75) if w52h else False

        # Volume surge: current vol > 1.5x avg
        vol = d.get('volume', 0)
        avg_vol = d.get('avg_volume', 1)
        vol_surge = (vol / avg_vol) >= 1.5 if avg_vol else False

        # RSI momentum check
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        rsi_ok = 50 < float(rsi) < 80

        passed = ma_stack and ma200_trending_up and near_high

        return {
            'pass':     passed,
            'ma_stack': ma_stack,
            'near_high': near_high,
            'vol_surge': vol_surge,
            'rsi':       round(float(rsi), 1),
            'rsi_ok':    rsi_ok,
            'sma50':     round(float(sma50), 2),
            'sma200':    round(float(sma200), 2),
        }
    except Exception as e:
        print(f"[{d['ticker']}] Minervini error: {e}")
        return {'pass': False}

# ============================================================
# MODULE 3: ATR-BASED TRADE PLAN
# Entry / SL / TP1 / TP2 / TP3
# ============================================================
def calc_trade_plan(d):
    try:
        df    = d['df_d']
        price = d['price']

        atr = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]
        atr_val = float(atr)
        atr_pct = round(atr_val / price * 100, 1)

        sl  = round(price - 1.5 * atr_val, 2)
        tp1 = round(price + 1.5 * atr_val, 2)
        tp2 = round(price + 3.0 * atr_val, 2)
        tp3 = round(price + 6.0 * atr_val, 2)

        sl_pct  = round((sl  / price - 1) * 100, 1)
        tp1_pct = round((tp1 / price - 1) * 100, 1)
        tp2_pct = round((tp2 / price - 1) * 100, 1)
        tp3_pct = round((tp3 / price - 1) * 100, 1)

        return {
            'atr_pct': atr_pct,
            'buy':  price,
            'sl':   sl,  'sl_pct':  sl_pct,
            'tp1':  tp1, 'tp1_pct': tp1_pct,
            'tp2':  tp2, 'tp2_pct': tp2_pct,
            'tp3':  tp3, 'tp3_pct': tp3_pct,
        }
    except Exception as e:
        print(f"[{d['ticker']}] ATR error: {e}")
        return None

# ============================================================
# MODULE 4: MOMENTUM SCORE
# Combines: RS proximity, volume, RSI, MA stack
# ============================================================
def calc_momentum_score(d, wei, mini):
    score = 0

    # Weinstein Stage 2 (+30)
    if wei.get('pass'):
        score += 30

    # Minervini MA Stack (+25)
    if mini.get('ma_stack'):
        score += 25

    # Near 52W High (+15)
    if mini.get('near_high'):
        score += 15

    # Volume Surge (+15)
    if mini.get('vol_surge'):
        score += 15

    # RSI in sweet zone (+10)
    if mini.get('rsi_ok'):
        score += 10

    # PEG < 2 (+5) — growth at reasonable price
    peg = d.get('peg')
    if peg and 0 < peg < 2:
        score += 5

    return score

# ============================================================
# MODULE 5: BUFFETT SCREEN (VI Layer)
# ============================================================
def check_buffett(d):
    eps = d.get('eps_fwd')
    if not eps or eps <= 0:
        return None
    fair = eps * 22
    buy  = fair * 0.85
    if d['price'] > buy * 1.1:
        return None
    status = 'BUY' if d['price'] <= buy else 'WATCH'
    return {'ticker': d['ticker'], 'status': status, 'fair': round(fair, 2)}

# ============================================================
# MODULE 6: LYNCH SCREEN (PEG-based)
# ============================================================
def check_lynch(d):
    peg = d.get('peg')
    growth = d.get('growth')
    eps = d.get('eps_fwd')
    if not all([peg, growth, eps]) or eps <= 0 or growth <= 0:
        return None
    # Lynch: PEG < 1 = undervalued growth
    if peg > 1.5:
        return None
    status = 'BUY' if peg < 1.0 else 'WATCH'
    return {'ticker': d['ticker'], 'status': status, 'peg': round(peg, 2)}

# ============================================================
# FORMAT MESSAGE
# ============================================================
def format_signal(d, wei, mini, plan, score):
    t = d['ticker']
    p = d['price']
    name = d['name']

    # Score emoji
    if score >= 80:
        badge = "🔥🔥🔥"
    elif score >= 60:
        badge = "🚀🚀"
    elif score >= 40:
        badge = "✅"
    else:
        badge = "👀"

    msg = f"{badge} <b>{t}</b> — {name}\n"
    msg += f"Score: <b>{score}/100</b> | Price: ${p}\n"
    msg += f"ATR: {plan['atr_pct']}%/day\n"
    msg += f"—\n"
    msg += f"Buy:  ${plan['buy']}\n"
    msg += f"SL:   ${plan['sl']} ({plan['sl_pct']}%)\n"
    msg += f"TP1:  ${plan['tp1']} (+{plan['tp1_pct']}%)\n"
    msg += f"TP2:  ${plan['tp2']} (+{plan['tp2_pct']}%)\n"
    msg += f"TP3:  ${plan['tp3']} (+{plan['tp3_pct']}%)\n"
    msg += f"—\n"

    flags = []
    if wei.get('pass'):
        flags.append(f"Stage2 ✓ (+{wei['pct_above_200']}% vs EMA200)")
    if mini.get('ma_stack'):
        flags.append("MA Stack ✓")
    if mini.get('vol_surge'):
        flags.append("Vol Surge ✓")
    if mini.get('rsi_ok'):
        flags.append(f"RSI {mini['rsi']} ✓")
    if mini.get('near_high'):
        flags.append("Near 52W High ✓")

    msg += " | ".join(flags) if flags else "No flags"
    return msg

# ============================================================
# POSITION SIZING GUIDE
# ============================================================
def position_sizing_guide(plan):
    atr = plan['atr_pct']
    if atr > 15:
        size = "⚠️ MAX 1% ของพอร์ต (ATR สูงมาก)"
    elif atr > 8:
        size = "🟡 MAX 3% ของพอร์ต"
    elif atr > 4:
        size = "🟢 MAX 5% ของพอร์ต"
    else:
        size = "🟢 MAX 8% ของพอร์ต (Core position)"
    return size

# ============================================================
# MAIN
# ============================================================
def main():
    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    print(f'[{today}] Scanning {len(WATCHLIST)} stocks...')

    # Header
    send(f"<b>🌅 Daily Stock Scan</b>\n{today}\nScanning {len(WATCHLIST)} stocks...\n")

    results      = []  # (score, msg, ticker)
    buffett_list = []
    lynch_list   = []

    for ticker in WATCHLIST:
        print(f"  Processing {ticker}...")

        d = fetch_all(ticker)
        if not d:
            continue

        # Run all modules
        wei   = check_weinstein(d)
        mini  = check_minervini(d)
        plan  = calc_trade_plan(d)
        score = calc_momentum_score(d, wei, mini)

        # Aggressive filter: ต้องผ่าน Weinstein หรือ Minervini อย่างน้อย 1 อัน
        if not (wei.get('pass') or mini.get('pass')):
            continue

        if plan:
            size_guide = position_sizing_guide(plan)
            msg = format_signal(d, wei, mini, plan, score)
            msg += f"\n📐 Size: {size_guide}"
            results.append((score, msg, ticker))

        # VI screens (separate)
        b = check_buffett(d)
        if b:
            buffett_list.append(f"{b['ticker']} [PEG fair=${b['fair']}] ({b['status']})")

        l = check_lynch(d)
        if l:
            lynch_list.append(f"{l['ticker']} [PEG={l['peg']}] ({l['status']})")

    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)

    # ส่ง Top signals
    if results:
        send(f"<b>🎯 Top Momentum Signals ({len(results)} passed)</b>")
        for score, msg, ticker in results[:10]:  # ส่งสูงสุด 10 ตัว
            send(msg)
    else:
        send("📊 No stocks passed momentum criteria today.")

    # ส่ง VI Summary
    vi_msg = f"\n<b>💎 Value Screens</b>\n"
    vi_msg += f"📌 Buffett: {', '.join(buffett_list) if buffett_list else 'None'}\n"
    vi_msg += f"🚀 Lynch:   {', '.join(lynch_list) if lynch_list else 'None'}"
    send(vi_msg)

    # Footer
    send(f"✅ Scan complete — {today}")
    print("Done.")

if __name__ == '__main__':
    main()
