import asyncio, os
from datetime import datetime
import yfinance as yf
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

        hist = tk.history(period="6mo")
        if hist.empty or len(hist) < 30:
            return None

        # คำนวณ SMA21
        sma21 = hist["Close"].rolling(21).mean()

        close_today    = hist["Close"].iloc[-1]
        close_prev     = hist["Close"].iloc[-2]
        close_2d_ago   = hist["Close"].iloc[-3]
        sma21_today    = sma21.iloc[-1]
        sma21_prev     = sma21.iloc[-2]
        sma21_2d_ago   = sma21.iloc[-3]

        # 2 Close Above SMA21
        two_close_above = (
            close_today  > sma21_today  and
            close_prev   > sma21_prev
        )

        # เพิ่งทะลุ = วันก่อนหน้าอยู่ใต้ SMA21
        just_broke = (
            two_close_above and
            close_2d_ago <= sma21_2d_ago
        )

        if not two_close_above:
            return None

        # Momentum
        price_1m_ago = hist["Close"].iloc[-21]
        momentum_1m  = (price - price_1m_ago) / price_1m_ago * 100

        # Volume
        vol_recent = hist["Volume"].iloc[-5:].mean()
        vol_avg    = hist["Volume"].iloc[-20:].mean()
        vol_ratio  = vol_recent / vol_avg if vol_avg > 0 else 0

        pct_above_sma = (price - sma21_today) / sma21_today * 100

        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "price": price,
            "sma21": sma21_today,
            "pct_above_sma": pct_above_sma,
            "just_broke": just_broke,
            "momentum_1m": momentum_1m,
            "vol_ratio": vol_ratio,
        }
    except:
        return None

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    just_broke_list = []
    above_list = []
    total = len(ALL_WATCHLIST)

    for i, ticker in enumerate(ALL_WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if not d:
            continue
        if d["just_broke"]:
            just_broke_list.append(d)
        else:
            above_list.append(d)

    just_broke_list.sort(key=lambda x: x["pct_above_sma"], reverse=True)
    above_list.sort(key=lambda x: x["pct_above_sma"], reverse=True)
    total_found = len(just_broke_list) + len(above_list)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if total_found == 0:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 *21 SMA Scanner — {now}*\n\nไม่มีหุ้น 2 Close Above SMA21 วันนี้",
            parse_mode=ParseMode.MARKDOWN)
        print("No stocks found.")
        return

    header = f"📊 *21 SMA Scanner — {now}*\n"
    header += f"✅ *{total_found} หุ้น 2 Close Above SMA21*\n"
    if just_broke_list:
        header += f"🚨 *{len(just_broke_list)} หุ้นเพิ่งทะลุขึ้นมาใหม่!*\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    # ส่งหุ้นที่เพิ่งทะลุก่อน
    if just_broke_list:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🚨 *เพิ่ง Break SMA21 — 2 Close Above!*",
            parse_mode=ParseMode.MARKDOWN)
        for r in just_broke_list:
            msg = f"⚡ *{r['ticker']}* — {r['name']}\n"
            msg += f"{get_category(r['ticker'])}\n"
            msg += "```\n"
            msg += f"Price        ${r['price']:.2f}\n"
            msg += f"SMA21        ${r['sma21']:.2f}\n"
            msg += f"Above SMA21  +{r['pct_above_sma']:.1f}%\n"
            msg += f"1M Momentum  +{r['momentum_1m']:.1f}%\n"
            msg += f"Volume       {r['vol_ratio']:.1f}x avg\n"
            msg += "```\n"
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.3)

    # ส่งหุ้นที่อยู่เหนือ SMA21 แล้ว
    if above_list:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="📈 *2 Close Above SMA21 แล้ว*",
            parse_mode=ParseMode.MARKDOWN)
        for r in above_list:
            msg = f"✅ *{r['ticker']}* — {r['name']}\n"
            msg += f"{get_category(r['ticker'])}\n"
            msg += "```\n"
            msg += f"Price        ${r['price']:.2f}\n"
            msg += f"SMA21        ${r['sma21']:.2f}\n"
            msg += f"Above SMA21  +{r['pct_above_sma']:.1f}%\n"
            msg += f"1M Momentum  +{r['momentum_1m']:.1f}%\n"
            msg += f"Volume       {r['vol_ratio']:.1f}x avg\n"
            msg += "```\n"
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.3)

    print(f"Done! {total_found} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
