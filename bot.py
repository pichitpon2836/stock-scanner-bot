import asyncio, os
from datetime import datetime
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

# หุ้นจิ๋วราคาต่ำที่ Active ใน NYSE + Nasdaq
# คัดมาเฉพาะ Small/Micro Cap ที่ Trade Active
WATCHLIST = [
    # Speculative / Small Cap ที่ Active
    "SOUN","BBAI","GFAI","AITX","RGTI","QBTS","IONQ","ARQQ","QUBT","BSFC",
    "NKLA","RIDE","GOEV","WKHS","SOLO","AYRO","ARVL","KNDI","FFIE","MULN",
    "ILUS","OCGN","SIGA","NVAX","BNTX","INO","SRNE","VXRT","HGEN","AKER",
    "SHIP","TOPS","FREE","GOGL","EGLE","GNK","SALT","EDRY","SMHI","GASS",
    "CLOV","HIMS","OPEN","PRPB","BARK","SPCE","RKLB","MNTS","PL","ASTR",
    "NNDM","XONE","DM","VJET","SSYS","MKFG","FORG","SHPW","LAZR","LIDR",
    "OPAD","ATIP","ACMR","CXAI","GXAI","BBSI","MIND","CLBT","EBON","MIGI",
    "AIOT","GIGA","BTBT","MARA","RIOT","CLSK","CIFR","IREN","WULF","HUT",
    "BITI","BTCS","BSRT","LTRY","LIQT","IDEX","ABEV","VALE","ITUB","PBR",
    "GRAB","SEA","GOTU","LKNCY","IQ","DOYU","HUYA","QFIN","JFIN","LX",
    "CNEY","TAOP","PETZ","GFAI","SHOT","KAVL","MDJH","NISN","HOUR","OXUS",
    "CELH","MAMA","TBLT","ACER","SOPA","SIDU","EDTK","AIXI","ATXG","ATIF",
    "MFON","NCTY","XFIN","KPLT","SPRC","QNRX","IMMP","IMVT","IMUX","IMCR",
    "AXSM","ACAD","ACLS","ACNB","ACST","ACVA","ADAG","ADAP","ADCT","ADGM",
    "SFIX","REAL","RENT","TRST","BGFV","CONN","PRTY","BBBY","CATO","EXPR",
    "VERB","RVNC","FIGS","GUTS","VNCE","LOVE","GOED","BTRS","ACMR","ATRA",
    "MYPS","MOBX","FWAA","GSMG","TANH","CLPS","CIFS","CHNR","CATO","CODA",
    "ABIO","ABUS","ABCL","ABCM","ABEO","ABST","ABTS","ABVC","ABVX","ABXX",
    "NVTS","NVNI","NVVE","NVOS","NVAX","NVNO","NVCN","NVFY","NVEI","NVEC",
    "DRUG","DRRX","DRTS","DSGX","DSGT","DSNY","DSOM","DSPG","DSSI","DSTX",
]

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None or price <= 0:
            return None

        # กรองราคา $1 - $20
        if not (1 <= price <= 20):
            return None

        # Market Cap ไม่เกิน $2B
        mktcap = info.get("marketCap", 0)
        if mktcap and mktcap > 2_000_000_000:
            return None

        hist = tk.history(period="6mo")
        if hist.empty or len(hist) < 30:
            return None

        # SMA21
        sma21 = hist["Close"].rolling(21).mean().iloc[-1]
        if price <= sma21:
            return None

        # Momentum 1 เดือน > 30%
        price_1m = hist["Close"].iloc[-21]
        momentum_1m = (price - price_1m) / price_1m * 100
        if momentum_1m < 30:
            return None

        # Volume > 2x avg
        vol_recent = hist["Volume"].iloc[-5:].mean()
        vol_avg    = hist["Volume"].iloc[-20:].mean()
        vol_ratio  = vol_recent / vol_avg if vol_avg > 0 else 0
        if vol_ratio < 2.0:
            return None

        # Momentum 1 สัปดาห์
        momentum_1w = (price - hist["Close"].iloc[-5]) / hist["Close"].iloc[-5] * 100

        return {
            "ticker":      ticker,
            "name":        info.get("shortName", ticker),
            "price":       price,
            "mktcap":      mktcap,
            "sma21":       sma21,
            "momentum_1m": momentum_1m,
            "momentum_1w": momentum_1w,
            "vol_ratio":   vol_ratio,
        }
    except:
        return None

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    results = []
    total = len(WATCHLIST)

    for i, ticker in enumerate(WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if d:
            results.append(d)

    results.sort(key=lambda x: x["momentum_1m"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if not results:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"💎 *หุ้นจิ๋ว Momentum Scanner — {now}*\n\nไม่มีหุ้นจิ๋วที่ผ่านเกณฑ์วันนี้",
            parse_mode=ParseMode.MARKDOWN)
        print("No stocks found.")
        return

    header = f"💎 *หุ้นจิ๋ว Momentum Scanner — {now}*\n"
    header += f"⚡ *{len(results)} หุ้นผ่าน!*\n"
    header += "💰 ราคา $1-$20 | 🚀 +30% 1M | 📊 Volume 2x\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    for r in results:
        mktcap_str = f"${r['mktcap']/1e6:.0f}M" if r['mktcap'] else "N/A"
        msg = f"🚀 *{r['ticker']}* — {r['name']}\n"
        msg += "```\n"
        msg += f"Price        ${r['price']:.2f}\n"
        msg += f"Market Cap   {mktcap_str}\n"
        msg += f"SMA21        ${r['sma21']:.2f}\n"
        msg += f"1W Momentum  +{r['momentum_1w']:.1f}%\n"
        msg += f"1M Momentum  +{r['momentum_1m']:.1f}%\n"
        msg += f"Volume       {r['vol_ratio']:.1f}x avg\n"
        msg += "```\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)

    print(f"Done! {len(results)} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
