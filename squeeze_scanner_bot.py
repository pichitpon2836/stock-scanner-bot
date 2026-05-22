import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import pytz
import time
import os
from datetime import datetime
import curl_cffi.requests as cffi_requests

# ============================================================
# CONFIG — รับจาก GitHub Secrets เหมือน bot.py เดิม
# ============================================================
BOT_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN')
CHAT_ID   = os.environ.get('CHAT_ID',         'YOUR_CHAT_ID')
TIMEZONE  = 'Asia/Bangkok'

# Universe — เน้น High Short Interest stocks + momentum plays
# Short squeeze candidates: short float สูง + มี catalyst
WATCHLIST = [
    # Classic squeeze targets
    'GME','AMC','BBBY','SPCE','SNDL',
    # High short float mid-caps
    'BYND','NKLA','RIDE','WKHS','GOEV',
    # Biotech (squeeze prone)
    'SAVA','ACMR','PRAX','NVAX','SRPT',
    # Small-cap momentum
    'MARA','RIOT','CLSK','CIFR',
    # Speculative tech
    'IONQ','RXRX','RKLB','LUNR','ASTS',
    # Beaten-down with high short
    'LCID','RIVN','FFIE','MULN',
    # Energy plays
    'FCEL','PLUG','BE','BLDP','RUN',
    # Growth reversal
    'UPST','AFRM','HOOD','SOFI','OPEN',
    # Add any high-conviction tickers here
]

# ============================================================
# TELEGRAM — ใช้ฟังก์ชันเดียวกับ bot.py
# ============================================================
def send(text):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': CHAT_ID,
        'text':    text,
        'parse_mode': 'HTML'
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"[Send Error] {e}")
    time.sleep(0.5)

# ============================================================
# DATA FETCH — เหมือน bot.py + เพิ่ม short interest data
# ============================================================
def fetch_all(ticker):
    """ดึง price history + fundamentals รวม short interest"""
    try:
        session = cffi_requests.Session(impersonate="chrome110")
        tk  = yf.Ticker(ticker, session=session)
        info = tk.info

        price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not price:
            return None

        df_d = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df_d) < 50:
            return None

        # Short interest metrics
        short_float = info.get('shortPercentOfFloat', 0) or 0
        short_ratio = info.get('shortRatio', 0) or 0  # days to cover

        # Performance
        close = df_d['Close']
        perf_1d  = round((float(close.iloc[-1]) / float(close.iloc[-2])  - 1) * 100, 2) if len(close) >= 2  else 0
        perf_1w  = round((float(close.iloc[-1]) / float(close.iloc[-5])  - 1) * 100, 2) if len(close) >= 5  else 0
        perf_1m  = round((float(close.iloc[-1]) / float(close.iloc[-21]) - 1) * 100, 2) if len(close) >= 21 else 0

        return {
            'ticker':       ticker,
            'name':         info.get('shortName', ticker),
            'price':        float(price),
            'df_d':         df_d,
            # Short data
            'short_float':  round(float(short_float) * 100, 1),   # เปลี่ยนเป็น %
            'short_ratio':  round(float(short_ratio), 1),
            # Performance
            'change':       perf_1d,
            'perf_week':    perf_1w,
            'perf_month':   perf_1m,
            # Fundamentals
            'market_cap':   info.get('marketCap'),
            'volume':       info.get('volume', 0) or 0,
            'avg_volume':   info.get('averageVolume', 1) or 1,
            'float_shares': info.get('floatShares'),
            'week52_high':  info.get('fiftyTwoWeekHigh'),
            'week52_low':   info.get('fiftyTwoWeekLow'),
            'forward_pe':   info.get('forwardPE'),
            'sector':       info.get('sector', 'Unknown'),
        }
    except Exception as e:
        print(f"[{ticker}] fetch error: {e}")
        return None

# ============================================================
# MODULE 1: SHORT SQUEEZE SETUP
# เงื่อนไข: Short Float สูง + Price กำลังขึ้น = squeeze incoming
# ============================================================
def check_squeeze(d):
    """
    Classic squeeze setup:
    - Short Float >= 15% (shorts ติดกับดัก)
    - Price เป็นบวกวันนี้ >= 3% (shorts เริ่ม cover)
    - Volume surge >= 2x avg (แรงซื้อเข้า)
    - Days to cover >= 3 (shorts ออกยาก)
    """
    try:
        sf    = d['short_float']      # %
        chg   = d['change']           # % วันนี้
        vol   = d['volume']
        avg_v = d['avg_volume']
        ratio = d['short_ratio']      # days to cover

        vol_ratio = (vol / avg_v) if avg_v > 0 else 0

        # Squeeze score components
        is_high_short   = sf >= 15
        is_moving_up    = chg >= 3.0
        is_vol_surge    = vol_ratio >= 2.0
        is_hard_to_exit = ratio >= 3.0

        # Grade
        conditions_met = sum([is_high_short, is_moving_up, is_vol_surge, is_hard_to_exit])

        return {
            'pass':           conditions_met >= 3,       # ผ่านอย่างน้อย 3 จาก 4
            'alert':          conditions_met == 4,       # ครบทุกข้อ = FULL ALERT
            'short_float':    sf,
            'change':         chg,
            'vol_ratio':      round(vol_ratio, 1),
            'days_to_cover':  ratio,
            'high_short':     is_high_short,
            'moving_up':      is_moving_up,
            'vol_surge':      is_vol_surge,
            'hard_to_exit':   is_hard_to_exit,
            'conditions_met': conditions_met,
        }
    except Exception as e:
        print(f"[{d['ticker']}] Squeeze error: {e}")
        return {'pass': False, 'alert': False}

# ============================================================
# MODULE 2: TECHNICAL MOMENTUM
# RSI, MACD, Bollinger สำหรับ timing การเข้า
# ============================================================
def check_technical(d):
    try:
        df    = d['df_d']
        close = df['Close']
        price = d['price']

        rsi  = ta.rsi(close, length=14)
        macd = ta.macd(close)
        bb   = ta.bbands(close, length=20)

        rsi_val  = float(rsi.iloc[-1])
        macd_val = float(macd['MACD_12_26_9'].iloc[-1])
        macd_sig = float(macd['MACDs_12_26_9'].iloc[-1])
        bb_upper = float(bb['BBU_20_2.0'].iloc[-1])
        bb_lower = float(bb['BBL_20_2.0'].iloc[-1])
        bb_mid   = float(bb['BBM_20_2.0'].iloc[-1])

        # % position in BB band (0=lower, 100=upper)
        bb_pct = round((price - bb_lower) / (bb_upper - bb_lower) * 100, 0) if (bb_upper - bb_lower) > 0 else 50

        macd_cross_up = macd_val > macd_sig  # bullish crossover

        return {
            'rsi':          round(rsi_val, 1),
            'rsi_ok':       40 < rsi_val < 75,          # ไม่ overbought มากเกิน
            'macd_bull':    macd_cross_up,
            'bb_pct':       int(bb_pct),
            'breaking_out': bb_pct > 85,                 # กำลัง breakout BB
            'oversold':     rsi_val < 35,                # rebound play
        }
    except Exception as e:
        print(f"[{d['ticker']}] Technical error: {e}")
        return {'rsi': 0, 'rsi_ok': False, 'macd_bull': False, 'bb_pct': 50}

# ============================================================
# MODULE 3: ATR TRADE PLAN — เหมือน bot.py เดิม
# ============================================================
def calc_trade_plan(d):
    try:
        df    = d['df_d']
        price = d['price']

        atr     = ta.atr(df['High'], df['Low'], df['Close'], length=14).iloc[-1]
        atr_val = float(atr)
        atr_pct = round(atr_val / price * 100, 1)

        sl  = round(price - 1.5 * atr_val, 2)
        tp1 = round(price + 1.5 * atr_val, 2)
        tp2 = round(price + 3.0 * atr_val, 2)
        tp3 = round(price + 5.0 * atr_val, 2)   # squeeze TP3 ก้าวร้าวกว่า

        return {
            'atr_pct': atr_pct,
            'buy':  price,
            'sl':   sl,  'sl_pct':  round((sl  / price - 1) * 100, 1),
            'tp1':  tp1, 'tp1_pct': round((tp1 / price - 1) * 100, 1),
            'tp2':  tp2, 'tp2_pct': round((tp2 / price - 1) * 100, 1),
            'tp3':  tp3, 'tp3_pct': round((tp3 / price - 1) * 100, 1),
        }
    except Exception as e:
        print(f"[{d['ticker']}] ATR error: {e}")
        return None

# ============================================================
# MODULE 4: SQUEEZE SCORE (0-100)
# ============================================================
def calc_squeeze_score(sq, tech):
    score = 0

    # Short float tier
    sf = sq.get('short_float', 0)
    if sf >= 30:   score += 30
    elif sf >= 20: score += 22
    elif sf >= 15: score += 15

    # Price action today
    chg = sq.get('change', 0)
    if chg >= 10:  score += 25
    elif chg >= 5: score += 18
    elif chg >= 3: score += 10

    # Volume surge
    vr = sq.get('vol_ratio', 0)
    if vr >= 5:   score += 20
    elif vr >= 3: score += 14
    elif vr >= 2: score += 8

    # Days to cover
    dtc = sq.get('days_to_cover', 0)
    if dtc >= 7:  score += 15
    elif dtc >= 3: score += 8

    # Technical bonus
    if tech.get('macd_bull'):    score += 5
    if tech.get('breaking_out'): score += 5

    return min(score, 100)

# ============================================================
# FORMAT MESSAGE
# ============================================================
def format_squeeze_signal(d, sq, tech, plan, score):
    t    = d['ticker']
    p    = d['price']
    name = d['name']

    # Badge
    if sq.get('alert'):
        badge = "⚡⚡ FULL SQUEEZE ALERT"
    elif score >= 70:
        badge = "🔥🔥 HIGH PROBABILITY"
    elif score >= 50:
        badge = "🚀 SQUEEZE SETUP"
    else:
        badge = "👀 WATCH"

    chg_sign = "+" if d['change'] >= 0 else ""

    msg  = f"{'─'*28}\n"
    msg += f"{badge}\n"
    msg += f"<b>{t}</b> — {name}\n"
    msg += f"Score: <b>{score}/100</b>\n"
    msg += f"{'─'*28}\n"

    # Short data
    msg += f"📊 Short Float:  <b>{sq['short_float']}%</b>\n"
    msg += f"📅 Days to Cover: {sq['days_to_cover']}d\n"
    msg += f"📈 Today:        <b>{chg_sign}{d['change']}%</b>\n"
    msg += f"📆 1W / 1M:      {d['perf_week']:+.1f}% / {d['perf_month']:+.1f}%\n"
    msg += f"🔊 Volume:       {sq['vol_ratio']}x avg\n"
    msg += f"{'─'*28}\n"

    # Technical
    msg += f"RSI: {tech['rsi']} | BB: {tech['bb_pct']}%"
    if tech.get('breaking_out'):
        msg += " 💥BB Breakout"
    if tech.get('macd_bull'):
        msg += " | MACD ▲"
    msg += "\n"
    msg += f"{'─'*28}\n"

    # Trade plan
    if plan:
        msg += f"💰 Buy:  ${plan['buy']}\n"
        msg += f"🛑 SL:   ${plan['sl']} ({plan['sl_pct']}%)\n"
        msg += f"🎯 TP1:  ${plan['tp1']} (+{plan['tp1_pct']}%)\n"
        msg += f"🎯 TP2:  ${plan['tp2']} (+{plan['tp2_pct']}%)\n"
        msg += f"🎯 TP3:  ${plan['tp3']} (+{plan['tp3_pct']}%)\n"
        msg += f"⚡ ATR:  {plan['atr_pct']}%/day\n"

    # Squeeze flags
    flags = []
    if sq['high_short']:   flags.append(f"Short {sq['short_float']}% ✓")
    if sq['moving_up']:    flags.append(f"Up {d['change']}% ✓")
    if sq['vol_surge']:    flags.append(f"Vol {sq['vol_ratio']}x ✓")
    if sq['hard_to_exit']: flags.append(f"DTC {sq['days_to_cover']}d ✓")
    if flags:
        msg += f"\n🏷 {' | '.join(flags)}"

    return msg

# ============================================================
# STATS SUMMARY — ADV/DEC, Top Gainer, Alert count
# ============================================================
def build_summary(all_data, results):
    adv = sum(1 for d in all_data if d['change'] > 0)
    dec = sum(1 for d in all_data if d['change'] < 0)

    top_gainer = max(all_data, key=lambda x: x['change'], default=None)
    high_short  = max(all_data, key=lambda x: x['short_float'], default=None)
    alerts      = sum(1 for _, sq, _, _ in results if sq.get('alert'))

    msg  = f"<b>📊 Squeeze Scanner Stats</b>\n"
    msg += f"ADV / DEC: {adv} / {dec}\n"
    if top_gainer:
        msg += f"🏆 Top Gainer: {top_gainer['ticker']} ({top_gainer['change']:+.1f}%)\n"
    if high_short:
        msg += f"🎯 Highest Short: {high_short['ticker']} ({high_short['short_float']}%)\n"
    msg += f"⚡ Full Alerts: {alerts}\n"
    msg += f"✅ Total Signals: {len(results)}"
    return msg

# ============================================================
# MAIN
# ============================================================
def main():
    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    print(f'[{today}] Squeeze scan — {len(WATCHLIST)} stocks...')

    send(f"<b>⚡ Squeeze Hunter Scan</b>\n{today}\nScanning {len(WATCHLIST)} stocks for squeeze setups...\n")

    all_data = []
    results  = []   # (score, d, sq, tech, plan)

    for ticker in WATCHLIST:
        print(f"  {ticker}...")

        d = fetch_all(ticker)
        if not d:
            continue

        all_data.append(d)

        sq   = check_squeeze(d)
        tech = check_technical(d)
        plan = calc_trade_plan(d)

        # ต้องผ่าน squeeze check ก่อน
        if not sq.get('pass'):
            continue

        score = calc_squeeze_score(sq, tech)
        results.append((score, d, sq, tech, plan))

    # Sort by score
    results.sort(key=lambda x: x[0], reverse=True)

    # ส่ง Summary stats ก่อน
    if all_data:
        send(build_summary(all_data, results))

    # ส่ง Signals
    if results:
        send(f"\n<b>🔥 Squeeze Signals Found: {len(results)}</b>")
        for score, d, sq, tech, plan in results[:8]:   # max 8 ตัว
            msg = format_squeeze_signal(d, sq, tech, plan, score)
            send(msg)
    else:
        send("📊 No squeeze setups today. Market calm.")

    send(f"\n✅ Squeeze scan complete — {today}\n<i>Double-check short data before trading. DYOR.</i>")
    print("Done.")

if __name__ == '__main__':
    main()
