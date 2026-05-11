import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import pytz
import time
from datetime import datetime
import curl_cffi.requests as cffi_requests

# --- CONFIG ---
BOT_TOKEN = 'YOUR_BOT_TOKEN'
CHAT_ID = 'YOUR_CHAT_ID'
TIMEZONE = 'Asia/Bangkok'

WATCHLIST = [
    'AAPL','MSFT','GOOGL','AMZN','META','NVDA',
    'JPM','V','MA','UNH','JNJ','PG','KO','WMT',
    'HD','COST','ADBE','CRM','NFLX','TSM','AVGO',
    'LLY','TMO','ABBV','MCD','NKE','SBUX','DIS',
    'SCHW','CI','TTD','FDS','KR','NOK','MU','BULL'
]

def send(text):
    # ปรับใช้ HTML parse_mode เพื่อให้รองรับ <b> <i> ตามที่คุณต้องการ
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
        print(f"Send Error: {e}")
    time.sleep(0.5)

def fetch(ticker):
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
        print(f"{ticker} fetch error: {str(e)}")
        return None

def check_phase2(ticker):
    try:
        # ดึงข้อมูลย้อนหลัง (เผื่อไว้คำนวณ EMA)
        df_d = yf.download(ticker, period="2y", interval="1d", progress=False)
        df_m = yf.download(ticker, period="5y", interval="1mo", progress=False)
        
        if len(df_d) < 200 or len(df_m) < 10: return False
        
        # คำนวณ EMA โดยใช้ pandas_ta
        ema200_d = ta.ema(df_d['Close'], length=200).iloc[-1]
        ema10_m = ta.ema(df_m['Close'], length=10).iloc[-1]
        current_price = df_d['Close'].iloc[-1]
        
        # เงื่อนไข Phase 2: ราคายืนเหนือ EMA ทั้งสองเส้น
        return current_price > ema200_d and current_price > ema10_m
    except Exception as e:
        print(f"{ticker} TA error: {e}")
        return False

def buffett(d):
    eps = d['eps_fwd']
    if not eps or eps <= 0: return None
    fair = eps * 22
    buy = fair * 0.85
    if d['price'] > buy * 1.1: return None 
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
        # 1. เช็ค Phase 2 (Technical)
        if check_phase2(ticker):
            phase2_list.append(ticker)

        # 2. เช็ค Fundamental
        d = fetch(ticker)
        if not d: continue
        
        b = buffett(d)
        if b: buf_list.append(f"{b['ticker']} ({b['status']})")
        
        l = lynch(d)
        if l: lyn_list.append(f"{l['ticker']} ({l['status']})")

    # --- ส่วนการส่งข้อความ ---
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime('%Y-%m-%d')
    
    # 1. ส่งผลลัพธ์สไตล์ VI
    vi_header = f"<b>☀️ Daily Stock Scan - {today}</b>\n"
    vi_body = vi_header + f"\n📌 <b>Buffett Style:</b> {', '.join(buf_list) if buf_list else 'None'}"
    vi_body += f"\n🚀 <b>Lynch Style:</b> {', '.join(lyn_list) if lyn_list else 'None'}"
    send(vi_body)

    # 2. ส่วนของ Phase 2 Validation (ตามที่คุณต้องการเพิ่ม)
    if phase2_list:
        p2_body = "\n\n🚀 <b>Phase 2 Validation List</b>\n"
        p2_body += "<i>Price > EMA200 & Price > EMA10M</i>\n"
        p2_body += "---------------------------\n"
        for ticker in phase2_list:
            p2_body += f"• {ticker}\n"
        send(p2_body)
    else:
        send("\n\n📊 <b>Phase 2 Style</b>\nNo stocks passing Phase 2 criteria today.")

if __name__ == '__main__':
    main()
