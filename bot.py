import asyncio, os
from datetime import datetime
import yfinance as yf
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

# S&P500 + Nasdaq100 ครบถ้วน
SP500 = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB",
    "AKAM","ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN",
    "AMCR","AEE","AAL","AEP","AXP","AIG","AMT","AWK","AMP","AME","AMGN",
    "APH","ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET",
    "AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
    "BAC","BBWI","BAX","BDX","WRB","BRK-B","BBY","BIO","TECH","BIIB","BLK",
    "BX","BA","BCH","BSX","BMY","AVGO","BR","BRO","BF-B","BLDR","BG","CDNS",
    "CZR","CPT","CPB","COF","CAH","KMX","CCL","CARR","CTLT","CAT","CBOE",
    "CBRE","CDW","CE","COR","CNC","CNP","CF","CRL","SCHW","CHTR","CVX","CMG",
    "CB","CHD","CI","CINF","CTAS","CSCO","C","CFG","CLX","CME","CMS","KO",
    "CTSH","CL","CMCSA","CMA","CAG","COP","ED","STZ","CEG","COO","CPRT",
    "GLW","CPAY","CTVA","CSGP","COST","CTRA","CCI","CSX","CMI","CVS","DHI",
    "DHR","DRI","DVA","DAY","DECK","DE","DAL","DVN","DXCM","FANG","DLR",
    "DFS","DG","DLTR","D","DPZ","DOV","DOW","DHR","DTE","DUK","DD","EMN",
    "ETN","EBAY","ECL","EIX","EW","EA","ELV","LLY","EMR","ENPH","ETR","EOG",
    "EPAM","EQT","EFX","EQIX","EQR","ESS","EL","ETSY","EG","EVRG","ES",
    "EXC","EXPE","EXPD","EXR","XOM","FFIV","FDS","FICO","FAST","FRT","FDX",
    "FIS","FITB","FSLR","FE","FI","FLT","FMC","F","FTNT","FTV","FOXA","FOX",
    "BEN","FCX","GRMN","IT","GE","GEHC","GEV","GEN","GNRC","GD","GIS","GM",
    "GPC","GILD","GPN","GL","GDDY","GS","HAL","HIG","HAS","HCA","DOC","HSIC",
    "HSY","HES","HPE","HLT","HOLX","HD","HON","HRL","HST","HWM","HPQ","HUBB",
    "HUM","HBAN","HII","IBM","IEX","IDXX","ITW","INCY","IR","PODD","INTC",
    "ICE","IFF","IP","IPG","INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT",
    "JBL","JKHY","J","JNJ","JCI","JPM","JNPR","K","KVUE","KDP","KEY","KEYS",
    "KMB","KIM","KMI","KLAC","KHC","KR","LHX","LH","LRCX","LW","LVS","LDOS",
    "LEN","LNC","LIN","LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MRO",
    "MPC","MKTX","MAR","MMC","MLM","MAS","MA","MTCH","MKC","MCD","MCK","MDT",
    "MRK","META","MET","MTD","MGM","MCHP","MU","MSFT","MAA","MRNA","MHK",
    "MOH","TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ",
    "NTAP","NOC","NCLH","NRG","NEM","NFLX","NWS","NWSA","NEE","NKE","NI",
    "NDSN","NSC","NTRS","NOC","NTNX","NUE","NVDA","NVR","NXPI","ORLY","OXY",
    "ODFL","OMC","ON","OKE","ORCL","OTIS","PCAR","PKG","PLTR","PH","PAYX",
    "PAYC","PYPL","PNR","PEP","PFE","PCG","PM","PSX","PNW","PXD","PNC","POOL",
    "PPG","PPL","PFG","PG","PGR","PRU","PEG","PTC","PSA","PHM","QRVO","PWR",
    "QCOM","DGX","RL","RJF","RTX","O","REG","REGN","RF","RSG","RMD","RVTY",
    "ROL","ROP","ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SEE","SRE",
    "NOW","SHW","SPG","SWKS","SJM","SNA","SOLV","SO","LUV","SWK","SBUX",
    "STT","STLD","STE","SYK","SYF","SNPS","SYY","TMUS","TROW","TTWO","TPR",
    "TRGP","TGT","TEL","TDY","TFX","TER","TSLA","TXN","TXT","TMO","TJX",
    "TSCO","TT","TDG","TRV","TRMB","TFC","TYL","TSN","USB","UBER","UDR",
    "ULTA","UNP","UAL","UPS","URI","UNH","UHS","VLO","VTR","VLTO","VRSN",
    "VRSK","VZ","VRTX","VTRS","VICI","V","VST","VMC","WRK","WAB","WMT","WBD",
    "WM","WAT","WEC","WFC","WELL","WST","WDC","WRB","WHR","WMB","WTW","GWW",
    "WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
]

NASDAQ100 = [
    "ADBE","ADP","ABNB","GOOGL","GOOG","AMZN","AMD","AEP","AMGN","ADI",
    "ANSS","AAPL","AMAT","ASML","TEAM","ADSK","AZN","BIDU","BIIB","AVGO",
    "CDNS","CHTR","CTAS","CSCO","CTSH","CMCSA","CEG","CPRT","CSGP","COST",
    "CRWD","CSX","DDOG","DXCM","FANG","DLTR","DASH","EA","EBAY","ENPH",
    "EXC","FAST","FTNT","GEHC","GILD","GFS","HON","IDXX","ILMN","INTC",
    "INTU","ISRG","JD","KDP","KLAC","KHC","LRCX","LCID","LULU","MAR",
    "MRVL","MELI","META","MCHP","MU","MSFT","MRNA","MDLZ","MNST","NFLX",
    "NVDA","NXPI","ORLY","ON","PCAR","PANW","PAYX","PYPL","PDD","QCOM",
    "REGN","ROST","SIRI","SBUX","SNPS","TMUS","TSLA","TXN","TTD","VRSK",
    "VRTX","WBA","WDAY","XEL","ZS","ZM",
]

ALL_WATCHLIST = list(set(SP500 + NASDAQ100))

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            return None

        hist_m = tk.history(period="3y", interval="1mo")
        if hist_m.empty or len(hist_m) < 12:
            return None

        ma10       = hist_m["Close"].rolling(10).mean()
        close_now  = hist_m["Close"].iloc[-1]
        close_prev = hist_m["Close"].iloc[-2]
        ma10_now   = ma10.iloc[-1]
        ma10_prev  = ma10.iloc[-2]

        # Breakthrough: เดือนก่อนใต้ MA10 เดือนนี้เหนือ MA10
        if not ((close_now > ma10_now) and (close_prev <= ma10_prev)):
            return None

        pct_above = (price - ma10_now) / ma10_now * 100

        hist_d = tk.history(period="6mo")
        if hist_d.empty or len(hist_d) < 21:
            return None

        momentum_1m = (price - hist_d["Close"].iloc[-21]) / hist_d["Close"].iloc[-21] * 100
        vol_ratio   = hist_d["Volume"].iloc[-5:].mean() / hist_d["Volume"].iloc[-20:].mean()

        return {
            "ticker":      ticker,
            "name":        info.get("shortName", ticker),
            "price":       price,
            "ma10":        ma10_now,
            "pct_above":   pct_above,
            "momentum_1m": momentum_1m,
            "vol_ratio":   vol_ratio,
        }
    except:
        return None

async def run_scanner():
    bot = Bot(token=BOT_TOKEN)
    results = []
    total = len(ALL_WATCHLIST)

    for i, ticker in enumerate(ALL_WATCHLIST):
        print(f"[{i+1}/{total}] {ticker}...")
        d = fetch_data(ticker)
        if d:
            results.append(d)

    results.sort(key=lambda x: x["momentum_1m"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if not results:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 *MA10 Monthly Breakthrough — {now}*\n\nไม่มีหุ้น Break MA10 Monthly เดือนนี้",
            parse_mode=ParseMode.MARKDOWN)
        return

    header = f"🚨 *MA10 Monthly Breakthrough — {now}*\n"
    header += f"⚡ *{len(results)} หุ้นเพิ่ง Break!*\n"
    header += "📊 S&P500 + Nasdaq100\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    for r in results:
        msg = f"🚀 *{r['ticker']}* — {r['name']}\n"
        msg += "```\n"
        msg += f"Price        ${r['price']:.2f}\n"
        msg += f"MA10 Monthly ${r['ma10']:.2f}\n"
        msg += f"Above MA10   +{r['pct_above']:.1f}%\n"
        msg += f"1M Momentum  +{r['momentum_1m']:.1f}%\n"
        msg += f"Volume       {r['vol_ratio']:.1f}x avg\n"
        msg += "```\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.5)

    print(f"Done! {len(results)} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
