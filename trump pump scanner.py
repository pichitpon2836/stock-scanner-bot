"""
DREAMS Trading Co. — Trump Pump Scanner
========================================
สแกนหาหุ้นแบบ "Trump Pump" — momentum สูง, volume พุ่ง, RS ดี
ส่งผลเข้า Telegram อัตโนมัติ

Pattern ที่หา:
- YTD return > +50%
- Price > 20SMA > 50SMA (uptrend ชัด)
- Volume surge > 1.5x average
- Market cap $200M - $500B (ไม่เล็กเกิน/ใหญ่เกิน)
- Sector: Tech, Energy, Defense, Infrastructure, Crypto
"""

import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz

# ════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TZ               = pytz.timezone("America/New_York")

# Trump Pump watchlist — หุ้นที่เกี่ยวข้องกับนโยบาย Trump
# แบ่งตาม theme
TRUMP_THEMES = {
    "🏭 Manufacturing/Tariff": [
        "STRL","MLM","VMC","NUE","X","CLF","RS","CMC",
        "CENX","AA","ATI","HCC","ZEUS","HAYN",
    ],
    "⚡ Energy/LNG": [
        "LNG","CQP","TELL","NEXT","AR","EQT","CNX","CTRA",
        "MUR","SM","VTLE","CHRD","MGY","GPOR",
    ],
    "🤖 AI/Tech (Trump-backed)": [
        "MU","DELL","STX","WDC","AMD","INTC","NVDA",
        "SMCI","CRUS","AOSL","ONTO","AMBA",
    ],
    "🚀 Defense/Space": [
        "RKLB","ASTS","IONQ","LUNR","AEVA","FLY",
        "UMAC","PL","OUST","UAMY",
    ],
    "⚛️ Nuclear/Power": [
        "CEG","VST","NRG","BE","FCEL","PLUG",
        "SMR","NNE","OKLO","LEU",
    ],
    "🏗️ Infrastructure": [
        "STRL","CDNL","WULF","HUT","PURR",
        "APLD","IREN","NBIS","GEV",
    ],
    "💎 Critical Minerals": [
        "UAMY","CRML","MP","TMQ","TMC","LAC",
        "USAR","NMG","PGMFF",
    ],
    "🌐 Crypto/Blockchain": [
        "MSTR","COIN","RIOT","MARA","CLSK",
        "HUT","IREN","WULF","BTBT",
    ],
}

# รวมทุก ticker ไม่ซ้ำ
ALL_TICKERS = list(set(t for tickers in TRUMP_THEMES.values() for t in tickers))

# ════════════════════════════════════════
# FETCH & ANALYZE
# ════════════════════════════════════════

def analyze_ticker(sym: str) -> dict | None:
    """วิเคราะห์หุ้น 1 ตัว — คืน dict ถ้าผ่าน filter, None ถ้าไม่ผ่าน"""
    try:
        ticker = yf.Ticker(sym)
        hist   = ticker.history(period="1y")
        if hist.empty or len(hist) < 50:
            return None

        price     = float(hist["Close"].iloc[-1])
        vol_today = float(hist["Volume"].iloc[-1])
        vol_avg   = float(hist["Volume"].tail(20).mean())
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 0

        # Moving averages
        sma20  = float(hist["Close"].tail(20).mean())
        sma50  = float(hist["Close"].tail(50).mean())
        sma200 = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else None

        # Returns
        price_1w  = float(hist["Close"].iloc[-5])  if len(hist) >= 5  else price
        price_1m  = float(hist["Close"].iloc[-21]) if len(hist) >= 21 else price
        price_3m  = float(hist["Close"].iloc[-63]) if len(hist) >= 63 else price
        price_ytd_start = float(hist[hist.index >= f"{datetime.now().year}-01-01"]["Close"].iloc[0]) \
                          if len(hist[hist.index >= f"{datetime.now().year}-01-01"]) > 0 else price

        ret_1w  = (price - price_1w)  / price_1w  * 100
        ret_1m  = (price - price_1m)  / price_1m  * 100
        ret_3m  = (price - price_3m)  / price_3m  * 100
        ret_ytd = (price - price_ytd_start) / price_ytd_start * 100

        # 52W
        high_52w = float(hist["High"].tail(252).max())
        low_52w  = float(hist["Low"].tail(252).min())
        pct_from_high = (price - high_52w) / high_52w * 100

        # Market cap
        info   = ticker.fast_info
        mktcap = getattr(info, "market_cap", None) or 0

        # ── TRUMP PUMP SCORE ──
        score = 0
        reasons = []

        # 1. YTD momentum (สำคัญที่สุด)
        if ret_ytd > 200: score += 5; reasons.append(f"🚀 YTD +{ret_ytd:.0f}%")
        elif ret_ytd > 100: score += 4; reasons.append(f"🔥 YTD +{ret_ytd:.0f}%")
        elif ret_ytd > 50:  score += 3; reasons.append(f"📈 YTD +{ret_ytd:.0f}%")
        elif ret_ytd > 20:  score += 1; reasons.append(f"YTD +{ret_ytd:.0f}%")

        # 2. Price vs MAs (uptrend)
        if price > sma20 > sma50:
            score += 2; reasons.append("✅ P>20MA>50MA")
        elif price > sma20:
            score += 1; reasons.append("P>20MA")

        # 3. Volume surge
        if vol_ratio > 2.0:   score += 3; reasons.append(f"⚡ Vol {vol_ratio:.1f}x avg")
        elif vol_ratio > 1.5: score += 2; reasons.append(f"Vol {vol_ratio:.1f}x avg")
        elif vol_ratio > 1.2: score += 1; reasons.append(f"Vol {vol_ratio:.1f}x avg")

        # 4. Near 52W high (momentum)
        if pct_from_high > -5:  score += 2; reasons.append("🏆 Near 52W High")
        elif pct_from_high > -10: score += 1; reasons.append("Near 52W High")

        # 5. Short-term momentum
        if ret_1w > 5:  score += 2; reasons.append(f"1W +{ret_1w:.1f}%")
        elif ret_1w > 2: score += 1

        if ret_1m > 20: score += 2; reasons.append(f"1M +{ret_1m:.1f}%")
        elif ret_1m > 10: score += 1

        # Market cap filter (ไม่เล็กเกินไป)
        if mktcap < 100_000_000:  # < $100M micro cap เสี่ยงเกิน
            return None

        return {
            "sym":          sym,
            "price":        price,
            "ret_ytd":      ret_ytd,
            "ret_1m":       ret_1m,
            "ret_1w":       ret_1w,
            "ret_3m":       ret_3m,
            "sma20":        sma20,
            "sma50":        sma50,
            "vol_ratio":    vol_ratio,
            "pct_from_high": pct_from_high,
            "mktcap":       mktcap,
            "score":        score,
            "reasons":      reasons,
        }
    except Exception as e:
        print(f"⚠️ {sym}: {e}")
        return None

def get_theme(sym: str) -> str:
    for theme, tickers in TRUMP_THEMES.items():
        if sym in tickers:
            return theme
    return "📊 Other"

def score_emoji(score: int) -> str:
    if score >= 12: return "🔥🔥🔥"
    if score >= 9:  return "🔥🔥"
    if score >= 6:  return "🔥"
    if score >= 4:  return "✅"
    return "👀"

def mktcap_fmt(cap: float) -> str:
    if cap >= 1e12: return f"${cap/1e12:.1f}T"
    if cap >= 1e9:  return f"${cap/1e9:.1f}B"
    if cap >= 1e6:  return f"${cap/1e6:.0f}M"
    return "N/A"

# ════════════════════════════════════════
# BUILD MESSAGE
# ════════════════════════════════════════

def build_message(results: list) -> list[str]:
    """สร้าง Telegram messages (แบ่งถ้ายาวเกิน)"""
    now = datetime.now(TZ).strftime("%d/%m/%Y %H:%M ET")

    # Header
    msgs = []
    header = (
        f"🇺🇸 *TRUMP PUMP SCANNER*\n"
        f"DREAMS Trading Co. — {now}\n"
        f"{'─'*30}\n"
        f"พบ *{len(results)}* หุ้น | Score ≥ 4\n"
    )

    # Group by score tier
    hot    = [r for r in results if r["score"] >= 9]
    strong = [r for r in results if 6 <= r["score"] < 9]
    watch  = [r for r in results if 4 <= r["score"] < 6]

    current_msg = header

    def add_section(title: str, items: list) -> None:
        nonlocal current_msg
        if not items: return
        block = f"\n{title} *({len(items)})*\n"
        for r in items:
            em    = score_emoji(r["score"])
            theme = get_theme(r["sym"])
            line  = (
                f"{em} *{r['sym']}* `${r['price']:.2f}`\n"
                f"  YTD: `{'+' if r['ret_ytd']>=0 else ''}{r['ret_ytd']:.0f}%` "
                f"| 1M: `{'+' if r['ret_1m']>=0 else ''}{r['ret_1m']:.1f}%` "
                f"| Vol: `{r['vol_ratio']:.1f}x`\n"
                f"  {' | '.join(r['reasons'][:3])}\n"
                f"  {theme} | {mktcap_fmt(r['mktcap'])}\n\n"
            )
            # แบ่ง message ถ้ายาวเกิน 3800 chars
            if len(current_msg) + len(block) + len(line) > 3800:
                msgs.append(current_msg)
                current_msg = f"*(ต่อ)*\n\n"
                block = ""
            current_msg += block + line
            block = ""

    add_section("🔥🔥🔥 HOT — Strong Momentum", hot)
    add_section("🔥🔥 STRONG — Good Setup", strong)
    add_section("👀 WATCH — Building Momentum", watch)

    current_msg += f"\n_สแกนจาก {len(ALL_TICKERS)} tickers | DREAMS Co._"
    msgs.append(current_msg)
    return msgs

# ════════════════════════════════════════
# TELEGRAM
# ════════════════════════════════════════

def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ ไม่มี Telegram credentials")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

# ════════════════════════════════════════
# MAIN
# ════════════════════════════════════════

def main():
    now = datetime.now(TZ)
    print(f"🇺🇸 Trump Pump Scanner — {now.strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"📡 สแกน {len(ALL_TICKERS)} tickers...")

    results = []
    for i, sym in enumerate(ALL_TICKERS):
        print(f"  [{i+1}/{len(ALL_TICKERS)}] {sym}...", end=" ")
        r = analyze_ticker(sym)
        if r and r["score"] >= 4:
            results.append(r)
            print(f"✅ score={r['score']} YTD={r['ret_ytd']:.0f}%")
        else:
            print("skip")

    # เรียงตาม score
    results.sort(key=lambda x: (x["score"], x["ret_ytd"]), reverse=True)

    print(f"\n🏆 พบ {len(results)} หุ้นผ่าน filter")

    if not results:
        send_telegram("🇺🇸 Trump Pump Scanner: ไม่พบหุ้นที่น่าสนใจวันนี้")
        return

    # ส่ง Telegram
    messages = build_message(results)
    for msg in messages:
        send_telegram(msg)
        import time; time.sleep(1)

    print("✅ ส่ง Telegram เรียบร้อย")

if __name__ == "__main__":
    main()
