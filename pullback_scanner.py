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
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
UNIVERSE_FILE      = "universe.txt"

PULLBACK_ZONE_MIN  = -0.05   # ราคาปิดต่ำกว่า 21DMA ไม่เกิน -5%
PULLBACK_ZONE_MAX  =  0.05   # ราคาปิดสูงกว่า 21DMA ไม่เกิน +5%
ALERT_BUFFER       =  0.03   # Alert = 21DMA + 3%
ATR_SL_MULT        =  1.5    # SL = Entry - (ATR x 1.5)
LOOKBACK_DAYS      = "3mo"   # ดึง 3 เดือน


# ─── Telegram ─────────────────────────────────────────────
def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Missing Telegram credentials")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
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
        content = f.read()
    tickers = [
        t.strip().upper()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
        for t in line.split(",")
        if t.strip()
    ]   
    print(f"📋 Universe: {len(tickers)} tickers — {', '.join(tickers)}")
    return tickers


# ─── Calculate Indicators ─────────────────────────────────
def get_series(df: pd.DataFrame, col: str) -> pd.Series:
    """ดึง column จาก DataFrame รองรับทั้ง single และ MultiIndex"""
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance >= 0.2.x returns MultiIndex like ('Close', 'AAPL')
        cols = [c for c in df.columns if c[0] == col]
        if cols:
            return df[cols[0]].squeeze()
    if col in df.columns:
        return df[col].squeeze()
    raise KeyError(f"Column '{col}' not found")


def calculate_indicators(ticker: str) -> dict | None:
    try:
        df = yf.download(
            ticker,
            period=LOOKBACK_DAYS,
            interval="1d",
            auto_adjust=True,
            progress=False
        )

        if df is None or df.empty:
            print(f"⚠️ {ticker}: ไม่มีข้อมูล")
            return None

        if len(df) < 22:
            print(f"⚠️ {ticker}: ข้อมูลไม่พอ ({len(df)} วัน)")
            return None

        close = get_series(df, "Close")
        high  = get_series(df, "High")
        low   = get_series(df, "Low")

        # Moving Averages
        ma10  = float(close.rolling(10).mean().iloc[-1])
        ma21  = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ma50  = float(close.rolling(min(50, len(df))).mean().iloc[-1])
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(df) >= 200 else None

        # ATR 14 วัน
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])

        price    = float(close.iloc[-1])
        atr_pct  = (atr / price) * 100
        dist_pct = ((price - ma21) / ma21) * 100

        print(f"✅ {ticker}: price=${price} 21DMA=${round(ma21,2)} dist={round(dist_pct,1)}% ATR={round(atr_pct,1)}%")

        return {
            "ticker":       ticker,
            "price":        round(price, 2),
            "ma10":         round(ma10, 2),
            "ma21":         round(ma21, 2),
            "ma50":         round(ma50, 2),
            "ma200":        round(ma200, 2) if ma200 else None,
            "atr":          round(atr, 2),
            "atr_pct":      round(atr_pct, 1),
            "dist_21dma_pct": round(dist_pct, 1),
        }

    except Exception as e:
        print(f"❌ {ticker} error: {e}")
        return None


# ─── Filter ───────────────────────────────────────────────
def is_pullback_setup(d: dict) -> bool:
    dist = d["dist_21dma_pct"] / 100

    # 1. ใกล้ 21DMA ±5%
    if not (PULLBACK_ZONE_MIN <= dist <= PULLBACK_ZONE_MAX):
        return False

    # 2. Price > MA50
    if d["price"] <= d["ma50"]:
        return False

    # 3. MA50 > MA200 ถ้ามีข้อมูล
    if d["ma200"] and d["ma50"] <= d["ma200"]:
        return False

    return True


# ─── Format ───────────────────────────────────────────────
def format_setup(d: dict, rank: int) -> str:
    alert = round(d["ma21"] * (1 + ALERT_BUFFER), 2)
    sl    = round(d["price"] - d["atr"] * ATR_SL_MULT, 2)
    sl_pct = round((sl - d["price"]) / d["price"] * 100, 1)
    dist  = d["dist_21dma_pct"]
    dist_str = f"+{dist}%" if dist >= 0 else f"{dist}%"

    return (
        f"\n<b>#{rank} {d['ticker']}</b>\n"
        f"   ราคาปิด: ${d['price']} ({dist_str} จาก 21DMA)\n"
        f"   21DMA: ${d['ma21']}\n"
        f"   🔔 Alert เข้า: ${alert} (21DMA +3%)\n"
        f"   🛑 SL แนะนำ: ${sl} ({sl_pct}%)\n"
        f"   ATR: {d['atr_pct']}% | MA10: ${d['ma10']}\n"
    )


# ─── Main ─────────────────────────────────────────────────
def main():
    today   = datetime.now().strftime("%d %b %Y")
    tickers = load_universe()

    if not tickers:
        send_telegram(f"⚠️ Pullback Scanner — {today}\nไม่พบ universe.txt หรือไฟล์ว่างเปล่า")
        return

    setups  = []
    skipped = []

    for ticker in tickers:
        data = calculate_indicators(ticker)
        if data is None:
            skipped.append(ticker)
            continue
        if is_pullback_setup(data):
            setups.append(data)
        else:
            print(f"⏭️  {ticker}: ไม่อยู่ใน pullback zone")

    # Build message
    if setups:
        msg  = f"📊 <b>Pullback Scanner — {today}</b>\n"
        msg += f"✅ พบ {len(setups)} setup วันนี้\n"
        msg += f"Universe: {len(tickers)} ตัว\n"
        msg += "─────────────────────"
        for i, s in enumerate(setups, 1):
            msg += format_setup(s, i)
        msg += "\n─────────────────────\n"
        msg += "⚠️ <b>ต้องผ่าน checklist 4/6 + volume &gt;1.5x ก่อนเข้าเสมอ</b>\n"
        msg += "📌 ดูราคาปิดเท่านั้น ไม่ใช่ไส้เทียน"
    else:
        msg  = f"📊 <b>Pullback Scanner — {today}</b>\n"
        msg += f"✅ Scan complete — ไม่มี setup ใหม่วันนี้\n"
        msg += f"Universe: {len(tickers)} ตัว | ผ่าน filter: 0"

    if skipped:
        msg += f"\n\n⚠️ ดึงข้อมูลไม่ได้: {', '.join(skipped)}"

    print("\n" + "="*40)
    print(msg)
    send_telegram(msg)


if __name__ == "__main__":
    main()
