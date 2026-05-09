import asyncio, os
from datetime import datetime
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

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

def get_category(ticker):
    if ticker in MARKET_LEADERS: return "🟢 Market Leader"
    if ticker in NEXT_GEN_LEADERS: return "🔵 Next-Gen"
    return "🔴 Speculative"

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            return None
        hist_monthly = tk.history(period="3y", interval="1mo")
        if hist_monthly.empty or len(hist_monthly) < 11:
            return None
        ema10 = hist_monthly["Close"].ewm(span=10, adjust=False).mean()
        ema10_now  = ema10.iloc[-1]
        ema10_prev = ema10.iloc[-2]
        price_prev = hist_monthly["Close"].iloc[-2]
        is_breaking = (price > ema10_now) and (price_prev <= ema10_prev)
        pct_above = (price - ema10_now) / ema10_now * 100
        hist_daily = tk.history(period="6mo")
        if hist_daily.empty or len(hist_daily) < 21:
            return None
        momentum_1m = (price - hist_daily["Close"].iloc[-21]) / hist_daily["Close"].iloc[-21] * 100
        vol_ratio = hist_daily["Volume"].iloc[-5:].mean() / hist_daily["Volume"].iloc[-30:].mean()
        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "price": price,
            "ema10": ema10_now,
            "pct_above": pct_above,
            "is_breaking": is_breaking,
            "momentum_1m": momentum_1m,
            "vol_ratio": vol_ratio,
        }
    except:
        return None

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    breaking = []
    total = len(ALL_WATCHLIST)
    for i, ticker in enumerate(ALL_WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if d and d["is_breaking"]:
            breaking.append(d)
    breaking.sort(key=lambda x: x["pct_above"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")
    if not breaking:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 *EMA10 Monthly Break Scanner — {now}*\n\nไม่มีหุ้น Break EMA10 Monthly เดือนนี้",
            parse_mode=ParseMode.MARKDOWN)
        print("No breaking stocks.")
        return
    header = f"🚨 *EMA10 Monthly Break Scanner — {now}*\n"
    header += f"⚡ *{len(breaking)} หุ้นกำลัง BREAK EMA10 Monthly!*\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)
    for r in breaking:
        msg = f"🚀 *{r['ticker']}* — {r['name']}\n"
        msg += f"{get_category(r['ticker'])}\n"
        msg += "```\n"
        msg += f"Price          ${r['price']:.2f}\n"
        msg += f"EMA10 Monthly  ${r['ema10']:.2f}\n"
        msg += f"Above EMA10    +{r['pct_above']:.1f}%\n"
        msg += f"1M Momentum    +{r['momentum_1m']:.1f}%\n"
        msg += f"Volume         {r['vol_ratio']:.1f}x avg\n"
        msg += "```\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)
    print(f"Done! {len(breaking)} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
