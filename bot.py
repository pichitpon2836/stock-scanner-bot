import asyncio, os
from datetime import datetime
import yfinance as yf
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

ALL_WATCHLIST = list(set([
    "MMM","ABT","ABBV","ACN","ADBE","AMD","AFL","A","APD","ABNB","AKAM","ALB",
    "ALL","GOOGL","GOOG","MO","AMZN","AEP","AXP","AIG","AMT","AMP","AMGN",
    "ADI","ANSS","AON","AAPL","AMAT","ANET","T","ADSK","ADP","AZO","BKR",
    "BAC","BAX","BDX","BRK-B","BIO","BIIB","BLK","BX","BA","BSX","BMY",
    "AVGO","BR","CDNS","COF","CAH","CAT","CBOE","CBRE","CNC","SCHW","CHTR",
    "CVX","CMG","CB","CI","CTAS","CSCO","C","CLX","CME","KO","CTSH","CL",
    "CMCSA","COP","STZ","CEG","CPRT","GLW","COST","CCI","CSX","CMI","CVS",
    "DHI","DHR","DRI","DE","DAL","DVN","DXCM","DLR","DFS","DG","DLTR","D",
    "DOV","DOW","DTE","DUK","DD","EMN","ETN","EBAY","ECL","EW","EA","ELV",
    "LLY","EMR","ENPH","ETR","EOG","EFX","EQIX","EL","EXC","XOM","FDS",
    "FICO","FAST","FDX","FIS","FITB","FE","FI","FLT","F","FTNT","FCX",
    "GRMN","GE","GEHC","GD","GIS","GM","GILD","GS","HAL","HIG","HCA","HSY",
    "HES","HPE","HLT","HD","HON","HRL","HPQ","HUM","IBM","IDXX","ITW","IR",
    "INTC","ICE","INTU","ISRG","IQV","JNJ","JCI","JPM","K","KDP","KEY",
    "KMB","KMI","KLAC","KHC","KR","LHX","LH","LRCX","LIN","LKQ","LMT","L",
    "LOW","LULU","MTB","MRO","MPC","MAR","MMC","MA","MKC","MCD","MCK","MDT",
    "MRK","META","MET","MGM","MCHP","MU","MSFT","MRNA","MDLZ","MNST","MCO",
    "MS","MSI","NDAQ","NOC","NRG","NEM","NFLX","NEE","NKE","NSC","NUE",
    "NVDA","NXPI","ORLY","OXY","ODFL","ON","OKE","ORCL","PCAR","PLTR","PH",
    "PAYX","PEP","PFE","PM","PSX","PNC","PPG","PG","PGR","PRU","PSA","PHM",
    "PWR","QCOM","RTX","REGN","RSG","RMD","ROP","ROST","SPGI","CRM","SLB",
    "SRE","NOW","SHW","SNA","SO","SWK","SBUX","STT","STE","SYK","SYF",
    "SNPS","SYY","TMUS","TROW","TGT","TEL","TSLA","TXN","TMO","TJX","TT",
    "TDG","TRV","TFC","TSN","USB","UBER","UNP","UPS","URI","UNH","VLO","VZ",
    "VRTX","V","VMC","WMT","WM","WAT","WEC","WFC","WELL","WDC","WMB","GWW",
    "XEL","XYL","YUM","ZBRA","ZBH","ZTS",
    # Nasdaq100
    "ADBE","ADP","ABNB","AMZN","AMD","AMGN","ADI","ANSS","AAPL","AMAT",
    "ASML","TEAM","ADSK","BIIB","AVGO","CDNS","CHTR","CTAS","CSCO","CTSH",
    "CMCSA","CEG","CPRT","COST","CRWD","CSX","DDOG","DXCM","FANG","DLTR",
    "DASH","EA","EBAY","ENPH","FAST","FTNT","GEHC","GILD","HON","IDXX",
    "INTC","INTU","ISRG","KDP","KLAC","LRCX","LULU","MAR","MRVL","MELI",
    "META","MCHP","MU","MSFT","MRNA","MDLZ","MNST","NFLX","NVDA","NXPI",
    "ORLY","ON","PCAR","PANW","PAYX","PYPL","QCOM","REGN","ROST","SBUX",
    "SNPS","TMUS","TSLA","TXN","TTD","VRSK","VRTX","WDAY","XEL","ZS",
    "ARM","PLTR","APP","MSTR","COIN",
    # Dow Jones
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WMT",
]))

def fetch_data(ticker):
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not price or price <= 0:
            return None

        roe = info.get("returnOnEquity")
        debt_eq = info.get("debtToEquity")
        if roe is None or debt_eq is None:
            return None
        debt_eq = debt_eq / 100.0
        if not (roe * 100 > 10 and debt_eq < 2.0):
            return None

        growth = info.get("earningsGrowth")
        if growth is None or growth < 0:
            return None

        
        except:
            pass
        if not fcf_ok:
            return None

        eps = info.get("trailingEps")
        book_value = info.get("bookValue")
        g = growth * 100

        graham = eps * (8.5 + 2 * g) * 0.67 if eps and eps > 0 else None
        buffett = book_value * ((1 + roe) ** 5) * 0.75 if book_value and roe else None
        lynch = eps * g * 0.80 if eps and eps > 0 and g > 0 else None

        prices = [p for p in [graham, buffett, lynch] if p]
        if not prices:
            return None
        avg = sum(prices) / len(prices)
        discount = (avg - price) / avg * 100
        mktcap = info.get("marketCap", 0)

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
            "growth":   g,
            "mktcap":   mktcap,
            "is_small": price < 20,
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

    results.sort(key=lambda x: x["discount"], reverse=True)
    now = datetime.now().strftime("%d %b %Y %H:%M")

    if not results:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📊 *VI Legends Scanner — {now}*\n\nไม่มีหุ้นผ่านเกณฑ์วันนี้",
            parse_mode=ParseMode.MARKDOWN)
        return

    header = f"💎 *VI Legends Scanner — {now}*\n"
    header += f"📊 SP500 + Nasdaq + Dow Jones\n"
    header += f"✅ *{len(results)} หุ้นผ่านเกณฑ์!*\n"
    header += "─────────────────────\n"
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode=ParseMode.MARKDOWN)

    for r in results:
        mktcap_str = f"${r['mktcap']/1e9:.1f}B" if r['mktcap'] > 1e9 else f"${r['mktcap']/1e6:.0f}M" if r['mktcap'] else "N/A"
        star = "⭐" if r["is_small"] else "✅"
        msg = f"{star} *{r['ticker']}* — {r['name']}\n"
        msg += "```\n"
        msg += f"Price      {fmt(r['price'])}\n"
        msg += f"Graham     {fmt(r['graham'])}\n"
        msg += f"Buffett    {fmt(r['buffett'])}\n"
        msg += f"Lynch      {fmt(r['lynch'])}\n"
        msg += f"Avg Legend {fmt(r['avg'])}\n"
        msg += f"Discount   {r['discount']:+.1f}%\n"
        msg += f"ROE        {r['roe']:.1f}%\n"
        msg += f"D/E        {r['debt_eq']:.2f}\n"
        msg += f"Growth     {r['growth']:.1f}%\n"
        msg += f"Mkt Cap    {mktcap_str}\n"
        msg += "```\n"
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(0.3)

    print(f"Done! {len(results)} stocks sent.")

if __name__ == "__main__":
    asyncio.run(run_scanner())
