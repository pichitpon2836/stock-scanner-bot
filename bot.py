import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import pytz
import time
from datetime import datetime
import curl_cffi.requests as cffi_requests

# --- CONFIGเดิมของคุณ ---
# BOT_TOKEN = '...'
# CHAT_ID = '...'
# TIMEZONE = 'Asia/Bangkok'

WATCHLIST = [
    'AAPL','MSFT','GOOGL','AMZN','META','NVDA',
    'JPM','V','MA','UNH','JNJ','PG','KO','WMT',
    'HD','COST','ADBE','CRM','NFLX','TSM','AVGO',
    'LLY','TMO','ABBV','MCD','NKE','SBUX','DIS',
    'SCHW','CI','TTD','FDS','KR','NOK','MU','BULL'
]

def send(text):
    # ฟังก์ชันส่ง Telegram เดิมของคุณ
    r = requests.post(
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
        timeout=15,
    )
    r.raise_for_status()
    time.sleep(0.5)

def fetch(ticker):
    # ฟังก์ชันดึงข้อมูลเดิมของคุณ (ใช้ curl_cffi เพื่อเลี่ยงการโดนบล็อก)
    try:
        session = cffi_requests.Session(impersonate="chrome110")
        info = yf.Ticker(ticker, session=session).info
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not price: return None
        return {
            'ticker': ticker,
            'name': info.get('shortName', ticker),
            'price': float(price),
            'eps_fwd': info.get('forwardEps'),
            'growth': info.get('earningsGrowth'),
            'rev_growth': info.get('revenueGrowth'),
            'fcf': info.get('freeCashflow'),
            'shares': info.get('sharesOutstanding'),
            'roe': info.get('returnOnEquity'),
            'net_margin': info.get('profitMargins'),
            'gross_margin': info.get('grossMargins'),
            'peg': info.get('pegRatio'),
            'forward_pe': info.get('forwardPE')
        }
    except Exception as e:
        print(f"{ticker} error: {str(e)}")
        return None

# --- ฟังก์ชันใหม่: เช็ค PHASE 2 (EMA 10 เดือน & EMA 200 วัน) ---
def check_phase2(ticker):
    try:
        df_d = yf.download(ticker, period="1y", interval="1d", progress=False)
        df_m = yf.download(ticker, period="5y", interval="1mo", progress=False)
        if len(df_d) < 200 or len(df_m) < 10: return False
        
        ema200 = ta.ema(df_d['Close'], length=200).iloc[-1]
        ema10m = ta.ema(df_m['Close'], length=10).iloc[-1]
        curr = df_d['Close'].iloc[-1]
        
        # เงื่อนไข: ราคายืนเหนือ EMA ทั้งสองเส้น (Validation Phase)
        return curr > ema200 and curr > ema10m
    except:
        return False

# --- ฟังก์ชันคำนวณสไตล์ต่างๆ (Logicเดิมของคุณ) ---
def buffett(d):
    eps = d['eps_fwd']
    if not eps or eps <= 0: return None
    fair = eps * 22
    buy = fair * 0.85
    if d['price'] > buy * 1.1: return None # WATCH ZONE
    return {'ticker': d['ticker'], 'status': 'BUY' if d['price'] <= buy else 'WATCH'}

def lynch(d):
    growth = d['growth']
    eps = d['eps_fwd']
    if not eps or eps <= 0 or not growth or growth <= 0: return None
    fair = eps * (growth * 100)
    buy = fair * 0.95
    if d['price'] > buy * 1.1: return None
    return {'ticker': d['ticker'], 'status': 'BUY' if d['price'] <= buy else 'WATCH'}

def main():
    print(f'Scanning {len(WATCHLIST)} stocks...')
    buf_list, lyn_list, phase2_list = [], [], []

    for ticker in WATCHLIST:
        # 1. เช็ค Phase 2 ก่อน (เน้นทรงกราฟ)
        if check_phase2(ticker):
            phase2_list.append(ticker)

        # 2. เช็คพื้นฐาน (Logic เดิม)
        d = fetch(ticker)
        if not d: continue
        
        b = buffett(d)
        if b: buf_list.append(f"{b['ticker']} ({b['status']})")
        
        l = lynch(d)
        if l: lyn_list.append(f"{l['ticker']} ({l['status']})")

    # --- ส่วนการส่งข้อความ ---
    today = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d')
    
    header = f"☀️ *Daily Stock Scan - {today}*\n"
    
    # 1. ส่งโซนสะสมพื้นฐาน (ของเดิม)
    vi_text = header + "\n📌 *Buffett Style:* " + (", ".join(buf_list) if buf_list else "None")
    vi_text += "\n🚀 *Lynch Style:* " + (", ".join(lyn_list) if lyn_list else "None")
    send(vi_text)

    # 2. ส่งโซน Momentum (Phase 2 ที่เพิ่มใหม่)
    if phase2_list:
        p2_text = "📈 *Phase 2 Validation (Trend follows Value)*\n"
        p2_text += "หุ้นที่ยืนเหนือ EMA 10 เดือน & 200 วัน:\n"
        p2_text += "`" + ", ".join(phase2_list) + "`"
        send(p2_text)

if __name__ == '__main__':
    main()
