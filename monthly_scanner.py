import os
import requests
import pandas as pd
import yfinance as yf

# ดึงค่าจาก GitHub Secrets (ต้องไปตั้งค่าใน GitHub Settings ก่อน)
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: Token หรือ Chat ID ไม่ถูกต้อง")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"ส่งข้อความไม่สำเร็จ: {e}")

def run_scan():
    # รายชื่อหุ้นที่ต้องการเฝ้าระวัง
    tickers = ["NNE", "ACHR", "JOBY", "SMCI", "MVST", "COHR", "BLDP", "FCEL", "BE", "APLD"]
    hit_list = []

    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            # ดึงข้อมูลย้อนหลัง 2 ปี รายเดือน
            df = stock.history(period="2y", interval="1mo")
            
            if len(df) < 10: continue
            
            # คำนวณ MA 10 เดือน
            df['MA10'] = df['Close'].rolling(window=10).mean()
            
            curr_price = df['Close'].iloc[-1]
            curr_ma10 = df['MA10'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            prev_ma10 = df['MA10'].iloc[-2]

            # เงื่อนไข: ราคาปิดแท่งก่อนหน้าต่ำกว่าเส้น แต่ราคาปัจจุบันอยู่เหนือเส้น (Breakout)
            if prev_price <= prev_ma10 and curr_price > curr_ma10:
                hit_list.append(f"✅ *{symbol}* Break MA10 Months! (${curr_price:.2f})")
        except Exception as e:
            print(f"Error scanning {symbol}: {e}")

    if hit_list:
        msg = "📊 *MA10 Months Breakout Report*\n\n" + "\n".join(hit_list)
        send_telegram(msg)
    else:
        print("No Breakout detected.")

if __name__ == "__main__":
    run_scan()
