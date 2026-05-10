“””
VI Stock Scanner — Buffett / Lynch / Nick Sleep
GitHub Actions: อ่าน TELEGRAM_TOKEN และ TELEGRAM_CHAT_ID จาก Secrets
“””

import os, sys, time, requests, yfinance as yf
from datetime import datetime
import pytz

BOT_TOKEN = os.environ[“TELEGRAM_TOKEN”]
CHAT_ID   = os.environ[“TELEGRAM_CHAT_ID”]
TIMEZONE  = “Asia/Bangkok”
TOP_N     = 3

WATCHLIST = [
“AAPL”,“MSFT”,“GOOGL”,“AMZN”,“META”,“NVDA”,“BRK-B”,
“JPM”,“V”,“MA”,“UNH”,“JNJ”,“PG”,“KO”,“WMT”,
“HD”,“COST”,“ADBE”,“CRM”,“NFLX”,“TSM”,“AVGO”,
“LLY”,“TMO”,“ABBV”,“MCD”,“NKE”,“SBUX”,“DIS”,
“SCHW”,“CI”,“TTD”,“FDS”,“KR”,
]

# ── Telegram ──────────────────────────────────

def send(text: str):
r = requests.post(
f”https://api.telegram.org/bot{BOT_TOKEN}/sendMessage”,
json={“chat_id”: CHAT_ID, “text”: text, “parse_mode”: “HTML”},
timeout=15,
)
r.raise_for_status()
time.sleep(0.5)

# ── Fetch ─────────────────────────────────────

def fetch(ticker: str) -> dict | None:
try:
info = yf.Ticker(ticker).info
price = info.get(“currentPrice”) or info.get(“regularMarketPrice”)
if not price:
return None
return dict(
ticker       = ticker,
name         = info.get(“shortName”, ticker),
price        = price,
eps_fwd      = info.get(“forwardEps”),
eps_ttm      = info.get(“trailingEps”),
growth       = info.get(“earningsGrowth”) or info.get(“revenueGrowth”),
rev_growth   = info.get(“revenueGrowth”),
fcf          = info.get(“freeCashflow”),
shares       = info.get(“sharesOutstanding”),
roe          = info.get(“returnOnEquity”),
net_margin   = info.get(“profitMargins”),
gross_margin = info.get(“grossMargins”),
peg          = info.get(“pegRatio”),
insider_pct  = info.get(“heldPercentInsiders”),
desc         = (info.get(“longBusinessSummary”) or “”)[:120],
)
except:
return None

# ── Quality score ─────────────────────────────

def score(d: dict) -> int:
s = 0
if d[“roe”]          and d[“roe”]          >= 0.15: s += 25
if d[“net_margin”]   and d[“net_margin”]   >= 0.15: s += 25
if d[“gross_margin”] and d[“gross_margin”] >= 0.40: s += 25
if d[“rev_growth”]   and d[“rev_growth”]   >= 0.10: s += 25
return s

# ── Legend logic ──────────────────────────────

def buffett(d):
eps = d[“eps_fwd”]
if not eps or eps <= 0: return None
fair = eps * 22
buy  = fair * 0.85
gap  = (d[“price”] - buy) / buy
if gap > 0.10: return None
m = []
if d[“roe”]:         m.append(f”ROE {d[‘roe’]*100:.0f}%”)
if d[“net_margin”]:  m.append(f”NM {d[‘net_margin’]*100:.0f}%”)
if d[“gross_margin”]:m.append(f”GM {d[‘gross_margin’]*100:.0f}%”)
return _row(d, fair, buy, gap, “ · “.join(m))

def lynch(d):
eps    = d[“eps_ttm”] or d[“eps_fwd”]
growth = d[“growth”]
if not eps or eps <= 0 or not growth or growth <= 0: return None
gp   = growth * 100
fair = eps * gp
buy  = fair * 0.95
gap  = (d[“price”] - buy) / buy
if gap > 0.10: return None
peg  = f”PEG {d[‘peg’]:.2f}” if d[“peg”] else f”PEG ~{d[‘price’]/fair:.2f}”
m    = [peg, f”EPS +{gp:.0f}%”]
if d[“rev_growth”]: m.append(f”Rev +{d[‘rev_growth’]*100:.0f}%”)
return _row(d, fair, buy, gap, “ · “.join(m))

def sleep(d):
if not d[“fcf”] or not d[“shares”] or d[“shares”] <= 0: return None
fcf_ps = d[“fcf”] / d[“shares”]
if fcf_ps <= 0: return None
fair = fcf_ps / 0.04
buy  = fair * 0.90
gap  = (d[“price”] - buy) / buy
if gap > 0.10: return None
m = []
if d[“rev_growth”]:  m.append(f”Rev +{d[‘rev_growth’]*100:.0f}%”)
if d[“roe”]:         m.append(f”ROE {d[‘roe’]*100:.0f}%”)
if d[“insider_pct”]: m.append(f”Insider {d[‘insider_pct’]*100:.1f}%”)
return _row(d, fair, buy, gap, “ · “.join(m))

def _row(d, fair, buy, gap, metrics):
return dict(
ticker  = d[“ticker”],
name    = d[“name”],
score   = score(d),
status  = “🟢 BUY ZONE” if d[“price”] <= buy else “🟡 WATCH”,
price   = d[“price”],
fair    = fair,
buy     = buy,
disc    = (d[“price”] - fair) / fair * 100,
metrics = metrics,
desc    = d[“desc”],
gap     = gap,
)

# ── Format ────────────────────────────────────

def fmt(rank, s, prefix=””):
lines = [
f”\n#{rank} {prefix}{s[‘ticker’]} — {s[‘name’]}”,
f”  Quality: {s[‘score’]}/100 | Status: {s[‘status’]}”,
f”  Current: ${s[‘price’]:.2f} | Fair: ${s[‘fair’]:.2f} ({s[‘disc’]:+.0f}%) | Buy: ${s[‘buy’]:.2f}”,
f”  ✓ {s[‘metrics’]}”,
]
if s[“desc”]:
lines.append(f”  💼 {s[‘desc’]}”)
return “\n”.join(lines)

# ── Main ──────────────────────────────────────

def main():
print(f”Scanning {len(WATCHLIST)} tickers…”)
buf, lyn, slp = [], [], []

```
for t in WATCHLIST:
    d = fetch(t)
    if not d: continue
    if r := buffett(d): buf.append(r)
    if r := lynch(d):   lyn.append(r)
    if r := sleep(d):   slp.append(r)

key = lambda x: (x["gap"], -x["score"])
buf.sort(key=key); lyn.sort(key=key); slp.sort(key=key)

today = datetime.now(pytz.timezone(TIMEZONE)).strftime("%d %b %Y")

# Header
send(
    f"📊 <b>VI Daily Scan — {today}</b>\n"
    f"🟢 BUY ZONE = ราคา ≤ Buy Price\n"
    f"🟡 WATCH = เหนือ Buy 0–10%\n"
    f"⚠️ ตรวจสอบก่อนลงทุนทุกครั้ง"
)

# Buffett
if buf:
    send(
        "🏰 <b>What WARREN BUFFETT Would Buy Today</b>\n"
        "(Fair = EPS × 22 · Buy = Fair × 0.85)"
        + "".join(fmt(i+1, s) for i, s in enumerate(buf[:TOP_N]))
    )

# Lynch
if lyn:
    send(
        "📈 <b>What PETER LYNCH Would Buy Today</b>\n"
        "(Fair = EPS × Growth · Buy = Fair × 0.95)"
        + "".join(fmt(i+1, s, "🚀 Fast Grower · ") for i, s in enumerate(lyn[:TOP_N]))
    )

# Sleep
if slp:
    send(
        "🎯 <b>What NICK SLEEP Would Buy Today</b>\n"
        "(Fair = FCF/0.04 · Buy = Fair × 0.90)"
        + "".join(fmt(i+1, s) for i, s in enumerate(slp[:TOP_N]))
    )

if not buf and not lyn and not slp:
    send("📊 VI Daily Scan — ไม่พบหุ้นใน BUY/WATCH ZONE วันนี้")

print("Done.")
```

if **name** == “**main**”:
main()
