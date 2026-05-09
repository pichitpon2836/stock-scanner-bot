import asyncio, os
from datetime import datetime
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

# Watchlist จากรูป - The Leading Stocks
MARKET_LEADERS = [
    "SNDK","BE","STX","LITE","WDC","CIEN","NOK","FIX",
    "ENLT","VRT","MRVL","ASX","ARM","MU","UI","GLW","NBIS","Q"
]

NEXT_GEN_LEADERS = [
    "AAOI","MXL","ICHR","VIAV","FSLY","POWL","AMPX","VICR",
    "FORM","CDNL","AGX","DOCN","ADEA","GNRC","PL","VSAT"
]

SPECULATIVE_LEADERS = [
    "AXTI","LWLG","AEHR","SATL","XNDU","OPTX","SPIR","NVTS",
    "UAMY","USAR","BKSY","WULF","FCEL","CRML"
]

ALL_WATCHLIST = MARKET_LEADERS + NEXT_GEN_LEADERS + SPECULATIVE_LEADERS

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None: return None

        # ดึงข้อมูล Monthly สำหรับ EMA 10
        hist_monthly = tk.history(period="3y", interval="1mo")
        if hist_monthly.empty or len(hist_monthly) < 11: return None

        ema10_monthly = hist_monthly["Close"].ewm(span=10, adjust=False).mean()
        ema10_current = ema10_monthly.iloc[-1]
        ema10_prev    = ema10_monthly.iloc[-2]
        price_prev    = hist_monthly["Close"].iloc[-2]

        # Break = ราคาเดือนนี้อยู่เหนือ EMA10 แต่เดือนก่อนอยู่ใต้
        is_breaking = price > ema10_current and price_prev <= ema10_prev

        # Momentum 1 เดือน
        hist_daily = tk.history(period="6mo")
        if hist_daily.empty or len(hist_daily) < 21: return None
        price_1m_ago = hist_daily["Close"].iloc[-21]
        momentum_1m  = (price - price_1m_ago) / price_1m_ago * 100

        # Volume
        vol_recent = hist_daily["Volume"].iloc[-5:].mean()
        vol_avg    = hist_daily["Volume"].iloc[-30:].mean()
        vol_ratio  = vol_recent / vol_avg if vol_avg > 0 else 0

        # % above EMA10
        pct_above_ema = (price - ema10_current) / ema10_current * 100

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "price": price,
            "ema10_monthly": ema10_current,
            "pct_above_ema": pct_above_ema,
            "is_breaking": is_breaking,
            "momentum_1m": momentum_1m,
            "vol_ratio": vol_ratio,
        }
    except:
        return None

def get_category(ticker):
    if ticker in MARKET_LEADERS: return "🟢 Market Leader"
    if ticker in NEXT_GEN_LEADERS: return "🔵 Next-Gen"
    return "🔴 Speculative"

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    results = []
    total = len(ALL_WATCHLIST)

    for i, ticker in enumerate(ALL_WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if not d: continue
        if d["is_breaking"]:  # กำลัง Break EMA10 Monthly เดือนนี้!


    # เรียงตาม % above EMA10
    results.sort(key=lambda x: x["pct_above_ema"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if not results:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 *EMA10 Monthly Scanner — {now}*\n\nไม่มีหุ้นอยู่เหนือ EMA10 Monthly วันนี้",
            parse_mode=ParseMode.MARKDOWN)
        return

    # แยก Breaking vs Above
    breaking = [r for r in results if r["is_breaking"]]
    above    = [r for r in results if not r["is_breaking"]]

    header = f"📊 *EMA10 Monthly Scanner — {now}*\n"
    header += f"✅ *{len(results)} หุ้นอยู่เหนือ EMA10 Monthly*\n"
    if breaking:
        header += f"🚨 *{len(breaking)} หุ้นกำลัง BREAK ขึ้นใหม่!*\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    # ส่งหุ้น Breaking ก่อน
    if breaking:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🚨 *กำลัง BREAK EMA10 Monthly!*",
            parse_mode=ParseMode.MARKDOWN)
        for r in breaking:
            msg = f"⚡ *{r['ticker']}* — {r['name']}\n"
            msg += f"{get_category(r['ticker'])}\n"
            msg += "```\n"
            msg += f"Price          ${r['price']:.2f}\n"
            msg += f"EMA10 Monthly  ${r['ema10_monthly']:.2f}\n"
            msg += f"Above EMA10    +{r['pct_above_ema']:.1f}%\n"
            msg += f"1M Momentum    +{r['momentum_1m']:.1f}%\n"
            msg += f"Volume         {r['vol_ratio']:.1f}x avg\n"
            msg += "```\n"
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.3)

    # ส่งหุ้นที่อยู่เหนือ EMA10 แล้ว
    if above:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="📈 *อยู่เหนือ EMA10 Monthly แล้ว*",
            parse_mode=ParseMode.MARKDOWN)
        for r in above:
            msg = f"✅ *{r['ticker']}* — {r['name']}\n"
            msg += f"{get_category(r['ticker'])}\n"
            msg += "```\n"
            msg += f"Price          ${r['price']:.2f}\n"
            msg += f"EMA10 Monthly  ${r['ema10_monthly']:.2f}\n"
            msg += f"Above EMA10    +{r['pct_above_ema']:.1f}%\n"
            msg += f"1M Momentum    +{r['momentum_1m']:.1f}%\n"
            msg += f"Volume         {r['vol_ratio']:.1f}x avg\n"
            msg += "```\n"
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.3)

    print(f"✅ Done! {len(results)} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
