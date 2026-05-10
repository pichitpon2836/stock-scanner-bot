import asyncio, os
from datetime import datetime
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

DOW_JONES = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT"
]

SP500 = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB",
    "AKAM","ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN",
    "AMCR","AEE","AAL","AEP","AXP","AIG","AMT","AWK","AMP","AME","AMGN",
    "APH","ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET",
    "AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
    "BAC","BBWI","BAX","BDX","WRB","BRK-B","BBY","BIO","TECH","BIIB","BLK",
    "BX","BA","BSX","BMY","AVGO","BR","BRO","BLDR","BG","CDNS","CZR","CPT",
    "CPB","COF","CAH","KMX","CCL","CARR","CAT","CBOE","CBRE","CDW","CE",
    "COR","CNC","CNP","CF","CRL","SCHW","CHTR","CVX","CMG","CB","CHD","CI",
    "CINF","CTAS","CSCO","C","CFG","CLX","CME","CMS","KO","CTSH","CL",
    "CMCSA","CAG","COP","ED","STZ","CEG","COO","CPRT","GLW","CPAY","CTVA",
    "CSGP","COST","CTRA","CCI","CSX","CMI","CVS","DHI","DHR","DRI","DVA",
    "DECK","DE","DAL","DVN","DXCM","FANG","DLR","DFS","DG","DLTR","D",
    "DPZ","DOV","DOW","DTE","DUK","DD","EMN","ETN","EBAY","ECL","EIX","EW",
    "EA","ELV","LLY","EMR","ENPH","ETR","EOG","EQT","EFX","EQIX","EQR",
    "ESS","EL","ETSY","EG","EVRG","ES","EXC","EXPE","EXPD","EXR","XOM",
    "FFIV","FDS","FICO","FAST","FRT","FDX","FIS","FITB","FSLR","FE","FI",
    "FLT","FMC","F","FTNT","FTV","FOXA","FOX","BEN","FCX","GRMN","IT","GE",
    "GEHC","GEV","GEN","GNRC","GD","GIS","GM","GPC","GILD","GPN","GL",
    "GDDY","GS","HAL","HIG","HAS","HCA","HSIC","HSY","HES","HPE","HLT",
    "HOLX","HD","HON","HRL","HST","HWM","HPQ","HUBB","HUM","HBAN","HII",
    "IBM","IEX","IDXX","ITW","INCY","IR","INTC","ICE","IFF","IP","IPG",
    "INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT","JBL","JKHY","J","JNJ",
    "JCI","JPM","JNPR","K","KVUE","KDP","KEY","KEYS","KMB","KIM","KMI",
    "KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS","LDOS","LEN","LIN",
    "LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MRO","MPC","MKTX",
    "MAR","MMC","MLM","MAS","MA","MTCH","MKC","MCD","MCK","MDT","MRK",
    "META","MET","MTD","MGM","MCHP","MU","MSFT","MAA","MRNA","MOH","TAP",
    "MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ","NTAP","NOC",
    "NCLH","NRG","NEM","NFLX","NEE","NKE","NI","NDSN","NSC","NTRS","NUE",
    "NVDA","NVR","NXPI","ORLY","OXY","ODFL","OMC","ON","OKE","ORCL","OTIS",
    "PCAR","PKG","PLTR","PH","PAYX","PAYC","PYPL","PNR","PEP","PFE","PCG",
    "PM","PSX","PNW","PNC","POOL","PPG","PPL","PFG","PG","PGR","PRU","PEG",
    "PTC","PSA","PHM","PWR","QCOM","DGX","RL","RJF","RTX","O","REG","REGN",
    "RF","RSG","RMD","RVTY","ROL","ROP","ROST","RCL","SPGI","CRM","SBAC",
    "SLB","STX","SEE","SRE","NOW","SHW","SPG","SWKS","SJM","SNA","SOLV",
    "SO","LUV","SWK","SBUX","STT","STLD","STE","SYK","SYF","SNPS","SYY",
    "TMUS","TROW","TTWO","TPR","TRGP","TGT","TEL","TDY","TFX","TER","TSLA",
    "TXN","TXT","TMO","TJX","TSCO","TT","TDG","TRV","TRMB","TFC","TYL",
    "TSN","USB","UBER","UDR","ULTA","UNP","UAL","UPS","URI","UNH","UHS",
    "VLO","VTR","VLTO","VRSN","VRSK","VZ","VRTX","VTRS","VICI","V","VST",
    "VMC","WAB","WMT","WBD","WM","WAT","WEC","WFC","WELL","WST","WDC",
    "WHR","WMB","WTW","GWW","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
]

NASDAQ100 = [
    "ADBE","ADP","ABNB","GOOGL","GOOG","AMZN","AMD","AEP","AMGN","ADI",
    "ANSS","AAPL","AMAT","ASML","TEAM","ADSK","AZN","BIDU","BIIB","AVGO",
    "CDNS","CHTR","CTAS","CSCO","CTSH","CMCSA","CEG","CPRT","CSGP","COST",
    "CRWD","CSX","DDOG","DXCM","FANG","DLTR","DASH","EA","EBAY","ENPH",
    "EXC","FAST","FTNT","GEHC","GILD","GFS","HON","IDXX","ILMN","INTC",
    "INTU","ISRG","JD","KDP","KLAC","KHC","LRCX","LULU","MAR","MRVL",
    "MELI","META","MCHP","MU","MSFT","MRNA","MDLZ","MNST","NFLX","NVDA",
    "NXPI","ORLY","ON","PCAR","PANW","PAYX","PYPL","PDD","QCOM","REGN",
    "ROST","SBUX","SNPS","TMUS","TSLA","TXN","TTD","VRSK","VRTX","WDAY",
    "XEL","ZS","ARM","PLTR","CRWD","DDOG","APP","MSTR","COIN",
]

ALL_WATCHLIST = list(set(SP500 + NASDAQ100 + DOW_JONES))

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price or price <= 0:
            return None

        # ── Buffett Filter ─────────────────────
        roe    = info.get("returnOnEquity")
        debt_eq = info.get("debtToEquity")
        if roe is None or debt_eq is None:
            return None
        debt_eq = debt_eq / 100.0
        if not (roe * 100 > 15 and debt_eq < 1.0):
            return None

        # ── Lynch Filter ───────────────────────
        growth = info.get("earningsGrowth")
        if growth is None or growth * 100 < 10:
            return None

        # ── Nick Sleep Filter ──────────────────
        fcf_list = []
        try:
            cf = tk.cashflow
            if cf is not None and not cf.empty:
                for label in ["Free Cash Flow", "freeCashFlow"]:
                    if label in cf.index:
                        fcf_list = cf.loc[label].dropna().values[:3].tolist()
                        break
        except:
            pass
        if len(fcf_list) < 3 or not all(v > 0 for v in fcf_list):
            return None

        # ── Buy Price Calculation ──────────────
        eps        = info.get("trailingEps")
        book_value = info.get("bookValue")

        graham = None
        if eps and eps > 0:
            g = growth * 100
            graham = eps * (8.5 + 2 * g) * 0.67

        buffett = None
        if book_value and roe:
            buffett = book_value * ((1 + roe) ** 5) * 0.75

        lynch = None
        if eps and eps > 0:
            lynch = eps * (growth * 100) * 0.80

        prices = [p for p in [graham, buffett, lynch] if p]
        if not prices:
            return None
        avg = sum(prices) / len(prices)
        discount = (avg - price) / avg * 100

        mktcap   = info.get("marketCap", 0)
        is_small = price < 20

        return {
            "ticker":   ticker,
            "name":     info.get("shortName", ticker),
            "price":    price,
            "graham":   graham,
            "buffett":  buffett,
            "lynch":    lynch,
            "avg":      avg,
            "discount": discount,
            "roe":      roe * 100,
            "debt_eq":  debt_eq,
            "growth":   growth * 100,
            "mktcap":   mktcap,
            "is_small": is_small,
        }
    except:
        return None

def fmt(val):
    return f"${val:.2f}" if val else "N/A"

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    results = []
    total = len(ALL_WATCHLIST)

    for i, ticker in enumerate(ALL_WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if d:
            results.append(d)

    # เรียงตาม Discount มากสุดก่อน
    results.sort(key=lambda x: x["discount"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if not results:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 *VI Legends Scanner — {now}*\n\nไม่มีหุ้นผ่านเกณฑ์ VI Legends วันนี้\n📊 SP500 + Nasdaq + Dow Jones",
            parse_mode=ParseMode.MARKDOWN)
        return

    small = [r for r in results if r["is_small"]]
    big   = [r for r in results if not r["is_small"]]

    header = f"💎 *VI Legends Scanner — {now}*\n"
    header += f"📊 SP500 + Nasdaq + Dow Jones\n"
    header += f"✅ *{len(results)} หุ้นผ่านเกณฑ์ Buffett + Lynch + Nick Sleep!*\n"
    if small:
        header += f"⭐ {len(small)} หุ้นจิ๋ว < $20\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    for r in results:
        mktcap_str = f"${r['mktcap']/1e9:.1f}B" if r['mktcap'] > 1e9 else f"${r['mktcap']/1e6:.0f}M" if r['mktcap'] else "N/A"
        star = "⭐" if r["is_small"] else "✅"
        msg = f"{star} *{r['ticker']}* — {r['name']}\n"
        msg += "```\n"
        msg += f"Price        {fmt(r['price'])}\n"
        msg += f"Graham       {fmt(r['graham'])}\n"
        msg += f"Buffett      {fmt(r['buffett'])}\n"
        msg += f"Lynch        {fmt(r['lynch'])}\n"
        msg += f"Avg Legend   {fmt(r['avg'])}\n"
        msg += f"Discount     {r['discount']:+.1f}%\n"
        msg += f"─────────────────\n"
        msg += f"ROE          {r['roe']:.1f}%\n"
        msg += f"D/E          {r['debt_eq']:.2f}\n"
        msg += f"Growth       {r['growth']:.1f}%\n"
        msg += f"Market Cap   {mktcap_str}\n"
        msg += "```\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)

    print(f"Done! {len(results)} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
