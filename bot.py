import subprocess
subprocess.run(["pip", "install", "python-telegram-bot", "yfinance", "pandas", "-q"])

import asyncio
from datetime import datetime
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

import os
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")


# หุ้น NYSE ยอดนิยม
WATCHLIST = [
    # Finance
    "JPM","BAC","WFC","GS","MS","AXP","BLK","C","USB","PNC",
    "TFC","COF","MCO","SPGI","ICE","CME","BX","KKR","APO","CG",
    # Healthcare
    "JNJ","PFE","MRK","ABT","TMO","DHR","BSX","SYK","MDT","EW",
    "HUM","UNH","ELV","CVS","CI","HCA","DGX","LH","IQV","A",
    # Energy
    "XOM","CVX","COP","SLB","EOG","MPC","PSX","VLO","OXY","HAL",
    "DVN","FANG","MRO","APA","HES","BKR","NOV","HP","WHD","LBRT",
    # Industrial
    "CAT","DE","HON","GE","ETN","EMR","PH","ROK","ITW","DOV",
    "XYL","AME","FTV","ROP","GNRC","TT","IR","OTIS","CARR","LII",
    # Consumer
    "WMT","HD","TGT","LOW","COST","MCD","YUM","DRI","CMG","SHW",
    "NKE","PVH","RL","TPR","TJX","ROST","KSS","M","GPS","ANF",
    # Real Estate & Utilities
    "AMT","PLD","CCI","EQIX","PSA","SPG","O","WELL","AVB","EQR",
    # Materials
    "LIN","APD","ECL","DD","DOW","NEM","FCX","AA","X","CLF",
    # Tech on NYSE
    "IBM","HPE","HPQ","NCR","DELL","WDC","STX","JNPR","CSCO","GLW",
    # New & Hot NYSE stocks
    "COIN","HOOD","RIVN","LCID","F","GM","STLA","TM","HMC","RACE",
    "UAL","DAL","AAL","LUV","CCL","RCL","NCLH","MAR","HLT","H",
    "DIS","CMCSA","FOX","FOXA","WBD","PARA","NYT","NWS","OMC","IPG",
]

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        # กรอง NYSE เท่านั้น
        exchange = info.get("exchange", "")
        if exchange not in ["NYQ", "NYSE"]:
            return None

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None: return None

        hist = tk.history(period="6mo")
        if hist.empty or len(hist) < 30: return None

        ma20 = hist["Close"].rolling(20).mean().iloc[-1]
        price_1m_ago = hist["Close"].iloc[-21] if len(hist) >= 21 else hist["Close"].iloc[0]
        price_3m_ago = hist["Close"].iloc[-63] if len(hist) >= 63 else hist["Close"].iloc[0]
        momentum_1m  = (price - price_1m_ago) / price_1m_ago * 100
        momentum_3m  = (price - price_3m_ago) / price_3m_ago * 100
        vol_recent = hist["Volume"].iloc[-5:].mean()
        vol_avg    = hist["Volume"].iloc[-30:].mean()
        vol_ratio  = vol_recent / vol_avg if vol_avg > 0 else 0

        roe = info.get("returnOnEquity")
        fcf_3yr = []
        cf = tk.cashflow
        if cf is not None and not cf.empty:
            for label in ["Free Cash Flow","freeCashFlow"]:
                if label in cf.index:
                    fcf_3yr = cf.loc[label].dropna().values[:3].tolist()
                    break

        return {"ticker":ticker,"name":info.get("shortName",ticker),
                "price":price,"roe":roe,"fcf_3yr":fcf_3yr,
                "ma20":ma20,"momentum_1m":momentum_1m,
                "momentum_3m":momentum_3m,"vol_ratio":vol_ratio,
                "exchange":exchange}
    except:
        return None

def passes_filters(d):
    notes, passed = [], True

    # 1. ROE > 10%
    roe = d["roe"]
    if roe and roe*100 > 10:
        notes.append(f"Quality ✔ ROE {roe*100:.1f}%")
    else:
        notes.append("Quality ✗ ROE ต่ำ"); passed = False

    # 2. FCF บวกล่าสุด
    fcf = d["fcf_3yr"]
    if fcf and fcf[0] > 0:
        notes.append("FCF ✔ บวกล่าสุด")
    else:
        notes.append("FCF ✗ ติดลบ"); passed = False

    # 3. Price > MA20
    if d["price"] > d["ma20"]:
        notes.append("Trend ✔ Price > MA20")
    else:
        notes.append("Trend ✗ Price < MA20"); passed = False

    # 4. ขึ้น > 20% ใน 1 เดือน
    m1 = d["momentum_1m"]
    if m1 >= 20:
        notes.append(f"🔥 +{m1:.1f}% ใน 1 เดือน")
    else:
        notes.append(f"Momentum ✗ {m1:.1f}% (ต้อง ≥20%)"); passed = False

    # 5. Volume > 1.5x
    vol = d["vol_ratio"]
    if vol >= 1.5:
        notes.append(f"Volume 🔥 {vol:.1f}x avg")
    else:
        notes.append(f"Volume ✗ {vol:.1f}x (ต้อง ≥1.5x)"); passed = False

    return passed, notes

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    results = []
    total = len(WATCHLIST)
    for i, ticker in enumerate(WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if not d: continue
        passed, notes = passes_filters(d)
        if not passed: continue
        results.append({"ticker":d["ticker"],"name":d["name"],
                        "price":d["price"],"momentum_1m":d["momentum_1m"],
                        "momentum_3m":d["momentum_3m"],
                        "vol":d["vol_ratio"],"notes":notes})

    results.sort(key=lambda x: x["momentum_1m"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if not results:
        await bot.send_message(chat_id=CHAT_ID,
            text=f"🔥 *NYSE หุ้นซิ่ง — {now}*\n\nไม่มีหุ้นซิ่งใน NYSE วันนี้ครับ",
            parse_mode=ParseMode.MARKDOWN)
        print("No stocks passed.")
        return

    header = f"🔥 *NYSE หุ้นซิ่ง — {now}*\n"
    header += f"✅ *{len(results)} หุ้นผ่าน!*\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    for r in results:
        msg = f"🚀 *{r['ticker']}* — {r['name']}\n"
        msg += "```\n"
        msg += f"Price        ${r['price']:.2f}\n"
        msg += f"1M Gain      +{r['momentum_1m']:.1f}%\n"
        msg += f"3M Gain      +{r['momentum_3m']:.1f}%\n"
        msg += f"Volume       {r['vol']:.1f}x avg\n"
        msg += "```\n"
        for n in r["notes"]:
            msg += f"  • {n}\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)

    print(f"✅ Done! {len(results)} stocks sent.")

await run_scanner()
