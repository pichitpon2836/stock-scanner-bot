"""
DREAMS Trading Co. — Pullback Scanner
======================================
สแกนหาหุ้นที่ราคาปิด pullback มาใกล้ 21DMA
Universe: อ่านจาก universe.txt (อัปเดตมือทุกอาทิตย์จาก X)

Logic:
1. อ่าน universe.txt
2. ดึงราคาจาก Yahoo Finance
3. คำนวณ 21DMA, MA10, MA50, MA200, ATR
4. Filter: ราคาปิดใกล้ 21DMA ±5% + Price > MA50 > MA200
5. คำนวณ Alert Price (21DMA +3%) และ SL (1.5x ATR)
6. ส่ง Telegram

รัน: ทุกวัน จ-ศ เวลา 06:00 ไทย (23:00 UTC)
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, date

# ─── Config ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
UNIVERSE_FILE = "universe.txt"

# Filter thresholds
PULLBACK_ZONE_MIN = -0.05   # ราคาปิดต่ำกว่า 21DMA ไม่เกิน -5%
PULLBACK_ZONE_MAX = 0.05    # ราคาปิดสูงกว่า 21DMA ไม่เกิน +5%
ALERT_BUFFER = 0.03         # Alert = 21DMA + 3%
ATR_SL_MULTIPLIER = 1.5     # SL = Entry - (ATR x 1.5)
LOOKBACK_DAYS = 60          # ดึงข้อมูล 60 วันย้อนหลัง


# ─── Telegram ─────────────────────────────────────────────
def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Missing Telegram credentials")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print("✅ Telegram sent")
    except Exception as e:
        print(f"❌ Telegram error: {e}")


# ─── Load Universe ────────────────────────────────────────
def load_universe() -> list:
    if not os.path.exists(UNIVERSE_FILE):
        print(f"❌ {UNIVERSE_FILE} not found")
        return []
    with open(UNIVERSE_FILE, "r") as f:
        tickers = [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]
    print(f"📋 Universe: {len(tickers)} tickers — {', '.join(tickers)}")
    return tickers


# ─── Calculate Indicators ─────────────────────────────────
def calculate_indicators(ticker: str) -> dict | None:
    try:
        df = yf.download(ticker, period=f"{LOOKBACK_DAYS}d", interval="1d",
                         auto_adjust=True, progress=False)
        if df.empty or len(df) < 25:
            print(f"⚠️ {ticker}: ข้อมูลไม่พอ")
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Moving Averages
        ma10  = float(close.rolling(10).mean().iloc[-1])
        ma21  = float(close.ewm(span=21, adjust=False).mean().iloc[-1])  # EMA21 = 21DMA
        ma50  = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

        # ATR 14 วัน
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])

        price = float(close.iloc[-1])
        atr_pct = atr / price

        # % ห่างจาก 21DMA
        dist_21dma = (price - ma21) / ma21

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "ma10": round(ma10, 2),
            "ma21": round(ma21, 2),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2) if ma200 else None,
            "atr": round(atr, 2),
            "atr_pct": round(atr_pct * 100, 1),
            "dist_21dma_pct": round(dist_21dma * 100, 1),
        }
    except Exception as e:
        print(f"❌ {ticker} error: {e}")
        return None


# ─── Filter Pullback ──────────────────────────────────────
def is_pullback_setup(data: dict) -> bool:
    """
    ผ่านทุกข้อ = setup จริง

    1. ราคาปิดอยู่ใกล้ 21DMA ระหว่าง -5% ถึง +5%
    2. Price > MA50 (Tier 1 หรือ 2)
    3. MA50 > MA200 ถ้ามีข้อมูล (Tier 1 เท่านั้น)
    4. ATR ≤ 10% (hard filter Phase 1)
    """
    # 1. Pullback zone
    in_zone = PULLBACK_ZONE_MIN <= (data["dist_21dma_pct"] / 100) <= PULLBACK_ZONE_MAX
    if not in_zone:
        return False

    # 2. Price > MA50
    if data["price"] <= data["ma50"]:
        return False

    # 3. MA50 > MA200 (ถ้ามีข้อมูล)
    if data["ma200"] and data["ma50"] <= data["ma200"]:
        return False

    # 4. ATR ≤ 10%
    if data["atr_pct"] > 10:
        return False

    return True


# ─── Format Message ───────────────────────────────────────
def format_setup(data: dict, rank: int) -> str:
    alert_price = round(data["ma21"] * (1 + ALERT_BUFFER), 2)
    sl_price = round(data["price"] - (data["atr"] * ATR_SL_MULTIPLIER), 2)
    sl_pct = round((sl_price - data["price"]) / data["price"] * 100, 1)
    dist = data["dist_21dma_pct"]
    dist_str = f"+{dist}%" if dist >= 0 else f"{dist}%"

    return (
        f"\n#{rank} <b>{data['ticker']}</b>\n"
        f"   ราคาปิด: ${data['price']}\n"
        f"   21DMA: ${data['ma21']} ({dist_str})\n"
        f"   🔔 Alert เข้า: ${alert_price} (21DMA +3%)\n"
        f"   🛑 SL แนะนำ: ${sl_price} ({sl_pct}%)\n"
        f"   ATR: {data['atr_pct']}%\n"
        f"   MA10: ${data['ma10']} | MA50: ${data['ma50']}\n"
    )


# ─── Main ─────────────────────────────────────────────────
def main():
    today = datetime.now().strftime("%d %b %Y")
    tickers = load_universe()

    if not tickers:
        send_telegram(f"⚠️ Pullback Scanner — {today}\nไม่พบ universe.txt หรือไฟล์ว่างเปล่า")
        return

    setups = []
    skipped = []

    for ticker in tickers:
        data = calculate_indicators(ticker)
        if data is None:
            skipped.append(ticker)
            continue
        if is_pullback_setup(data):
            setups.append(data)
            print(f"✅ {ticker}: dist={data['dist_21dma_pct']}% ATR={data['atr_pct']}%")
        else:
            print(f"⏭️ {ticker}: dist={data['dist_21dma_pct']}% — ไม่อยู่ใน pullback zone")

    # ─── Build Message ────────────────────────────────────
    if setups:
        msg = f"📊 <b>Pullback Scanner — {today}</b>\n"
        msg += f"✅ พบ {len(setups)} setup วันนี้\n"
        msg += f"Universe: {len(tickers)} ตัว\n"
        msg += "─────────────────────────"

        for i, s in enumerate(setups, 1):
            msg += format_setup(s, i)

        msg += "\n─────────────────────────\n"
        msg += "⚠️ <b>ต้องผ่าน checklist 4/6 + volume >1.5x ก่อนเข้าเสมอ</b>\n"
        msg += "📌 ดูราคาปิดเท่านั้น ไม่ใช่ไส้เทียน"
    else:
        msg = f"📊 <b>Pullback Scanner — {today}</b>\n"
        msg += f"✅ Scan complete — ไม่มี setup ใหม่วันนี้\n"
        msg += f"Universe: {len(tickers)} ตัว | ผ่าน filter: 0"

    if skipped:
        msg += f"\n\n⚠️ ดึงข้อมูลไม่ได้: {', '.join(skipped)}"

    print("\n" + msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
