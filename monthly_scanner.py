import os
import requests
import pandas as pd
import yfinance as yf

# 1. ตั้งค่าดึงข้อมูลจาก GitHub Secrets (ปลอดภัยกว่าการใส่โค้ดตรงๆ)
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_msg(message):
    """ฟังก์ชันส่งข้อความเข้า Telegram"""
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: Telegram credentials not found.")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send message: {e}")

def get_ma10_monthly_signal(ticker):
    """เช็คสัญญาณ Break MA10 Months"""
    try:
        stock = yf.Ticker(ticker)
        # ดึงข้อมูลย้อนหลัง 2 ปี รายเดือน
        df = stock.history(period="2y", interval="1mo")
        
        if len(df) < 11: # ต้องมีข้อมูลพอคำนวณ MA10
            return None
            
        # คำนวณ MA 10 เดือน
        df['MA10'] = df['Close'].rolling(window=10).mean()
        
        curr_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        curr_ma10 = df['MA10'].iloc[-1]
        prev_ma10 = df['MA10'].iloc[-2]
        
        # เงื่อนไข: ราคาปิดก่อนหน้าอยู่ใต้เส้น แต่ราคาปัจจุบันทะลุขึ้นมา
        if prev_price <= prev_ma10 and curr_price > curr_ma10:
            change_pct = ((curr_price - prev_price) / prev_price) * 100
            return f"🚀 *{ticker}* Break MA10 Months!\nPrice: ${curr_price:.2f} ({change_pct:+.2f}%)"
            
        return None
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
        return None

def main():
    # รายชื่อหุ้นเป้าหมาย (คุณสามารถเพิ่ม/ลด ได้ตามต้องการ)
    watch_list = ["VRT", "NNE", "BE", "APLD", "COHR", "FCEL", "SMCI", "ACHR", "JOBY"]
    
    found_signals = []
    print("Starting scan...")
    
    for ticker in watch_list:
        signal = get_ma10_monthly_signal(ticker)
        if signal:
            found_signals.append(signal)
            
    if found_signals:
        header = "🔥 *Stock Breakout Alert (Monthly)*\n"
        full_msg = header + "\n" + "\n\n".join(found_signals)
        send_telegram_msg(full_msg)
        print("Signals sent to Telegram.")
    else:
        print("No breakout signals found.")

if __name__ == "__main__":
    main()
