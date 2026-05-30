"""
DREAMS Trading Co. — Portfolio Tracker Bot
==========================================
ส่ง P&L Report + SL/TP Alert เข้า Telegram อัตโนมัติ
Deploy บน GitHub Actions — ฟรี ไม่ต้องมี server

วิธีใช้:
1. แก้ PORTFOLIO และ ALERTS ด้านล่าง
2. ตั้ง GitHub Secrets: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
3. Push ขึ้น repo — GitHub Actions จะรันเอง
"""

import os
import json
import requests
import yfinance as yf
from datetime import datetime
import pytz

# ════════════════════════════════════════
# CONFIG — แก้ตรงนี้
# ════════════════════════════════════════

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

COMPANY_NAME = "DREAMS Trading Co."
CAPITAL      = 10000  # ทุนเริ่มต้น $

# พอร์ตหุ้น — แก้ตามพอร์ตจริง
# sym: ticker | qty: จำนวนหุ้น | cost: ราคาซื้อ | sl: stop loss | tp: take profit
PORTFOLIO = [
    {"sym": "SIDU", "qty": 175, "cost": 3.75,   "sl": 3.20, "tp": 6.00, "note": ""},
    {"sym": "AMD",  "qty": 2,   "cost": 439.39,  "sl": 400,  "tp": 560,  "note": ""},
    {"sym": "PLUG", "qty": 572, "cost": 3.51,    "sl": 3.00, "tp": 4.00, "note": "TP1 $4.00 ขาย 190 หุ้น"},
    {"sym": "APLD", "qty": 24,  "cost": 42.42,   "sl": 38,   "tp": 55,   "note": ""},
    {"sym": "AMAT", "qty": 5,   "cost": 429.66,  "sl": 400,  "tp": 480,  "note": ""},
    {"sym": "CEG",  "qty": 1,   "cost": 281.20,  "sl": 260,  "tp": 320,  "note": ""},
    {"sym": "VIAV", "qty": 20,  "cost": 50.87,   "sl": 48,   "tp": 58,   "note": "⚠️ ออกถ้าหลุด $48"},
]

CASH = 1706  # cash ปัจจุบัน $

TZ = pytz.timezone("America/New_York")

# ════════════════════════════════════════
# FETCH PRICES
# ════════════════════════════════════════

def fetch_prices(symbols: list[str]) -> dict:
    """ดึงราคาล่าสุดจาก yfinance"""
    prices = {}
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                info = tickers.tickers[sym].fast_info
                price = info.last_price or info.previous_close
                prices[sym] = round(float(price), 4)
            except Exception:
                # fallback: ดึงทีละตัว
                try:
                    t = yf.Ticker(sym)
                    hist = t.history(period="1d")
                    if not hist.empty:
                        prices[sym] = round(float(hist["Close"].iloc[-1]), 4)
                except Exception as e:
                    print(f"⚠️ ดึงราคา {sym} ไม่ได้: {e}")
                    prices[sym] = None
    except Exception as e:
        print(f"❌ fetch_prices error: {e}")
    return prices

# ════════════════════════════════════════
# CALC
# ════════════════════════════════════════

def calc_position(h: dict, prices: dict) -> dict:
    price = prices.get(h["sym"])
    if price is None:
        return {**h, "price": None, "pnl": None, "pct": None, "value": None,
                "sl_hit": False, "tp_hit": False, "sl_near": False, "tp_near": False}
    pnl   = (price - h["cost"]) * h["qty"]
    pct   = ((price - h["cost"]) / h["cost"]) * 100
    value = price * h["qty"]
    sl    = h.get("sl")
    tp    = h.get("tp")
    return {
        **h,
        "price":   price,
        "value":   value,
        "pnl":     pnl,
        "pct":     pct,
        "sl_hit":  sl and price <= sl,
        "tp_hit":  tp and price >= tp,
        "sl_near": sl and not (price <= sl) and price <= sl * 1.03,  # ห่าง SL < 3%
        "tp_near": tp and not (price >= tp) and price >= tp * 0.97,  # ห่าง TP < 3%
    }

def portfolio_summary(positions: list[dict]) -> dict:
    valid = [p for p in positions if p["price"] is not None]
    total_value = sum(p["value"] for p in valid)
    total_pnl   = sum(p["pnl"] for p in valid)
    total_port  = total_value + CASH
    yret        = (total_pnl / CAPITAL) * 100 if CAPITAL else 0
    return {
        "stock_value": total_value,
        "cash":        CASH,
        "total":       total_port,
        "total_pnl":   total_pnl,
        "yret":        yret,
        "wins":        sum(1 for p in valid if p["pnl"] >= 0),
        "total_pos":   len(valid),
    }

# ════════════════════════════════════════
# FORMAT MESSAGES
# ════════════════════════════════════════

def fmt_pnl(n: float) -> str:
    if n is None: return "N/A"
    sign = "+" if n >= 0 else ""
    return f"{sign}${abs(n):,.2f}"

def fmt_pct(n: float) -> str:
    if n is None: return "N/A"
    sign = "+" if n >= 0 else ""
    return f"{sign}{n:.2f}%"

def pnl_emoji(n: float) -> str:
    if n is None: return "❓"
    if n >= 10:  return "🚀"
    if n >= 5:   return "🔥"
    if n >= 0:   return "✅"
    if n >= -5:  return "⚠️"
    return "🔴"

def build_morning_report(positions: list[dict], summary: dict) -> str:
    now  = datetime.now(TZ).strftime("%d/%m/%Y %H:%M ET")
    rows = []
    sorted_pos = sorted(positions, key=lambda p: p["pnl"] or 0, reverse=True)

    for p in sorted_pos:
        if p["price"] is None:
            rows.append(f"  ❓ *{p['sym']}* — ดึงราคาไม่ได้")
            continue
        em = pnl_emoji(p["pct"])
        alert = ""
        if p["sl_hit"]:   alert = " 🛑 *SL HIT!*"
        elif p["tp_hit"]: alert = " 🎯 *TP HIT!*"
        elif p["sl_near"]:alert = " ⚠️ SL ใกล้!"
        elif p["tp_near"]:alert = " 🎯 TP ใกล้!"
        note = f"\n    _{p['note']}_" if p.get("note") else ""
        rows.append(
            f"  {em} *{p['sym']}* {p['qty']}หุ้น\n"
            f"    ราคา: `${p['price']:.2f}` | P&L: `{fmt_pnl(p['pnl'])}` ({fmt_pct(p['pct'])}){alert}{note}"
        )

    pnl_em = "📈" if summary["total_pnl"] >= 0 else "📉"
    report = f"""🌅 *{COMPANY_NAME}*
📋 *Morning Report* — {now}

{pnl_em} *Portfolio P&L*
├ หุ้นรวม: `${summary['stock_value']:,.0f}`
├ Cash:     `${summary['cash']:,.0f}`
├ รวมทั้งหมด: `${summary['total']:,.0f}`
├ กำไร YTD: `{fmt_pnl(summary['total_pnl'])}` ({fmt_pct(summary['yret'])})
└ Win/Total: `{summary['wins']}/{summary['total_pos']}`

📊 *Positions*
{chr(10).join(rows)}

💡 _กด Refresh ใน Dashboard เพื่ออัปเดตราคาจริง_"""
    return report

def build_alert_report(positions: list[dict]) -> str | None:
    alerts = []
    for p in positions:
        if p["price"] is None: continue
        if p["sl_hit"]:
            alerts.append(
                f"🛑 *SL HIT — {p['sym']}*\n"
                f"  ราคา: `${p['price']:.2f}` | SL: `${p['sl']}`\n"
                f"  P&L: `{fmt_pnl(p['pnl'])}` ({fmt_pct(p['pct'])})\n"
                f"  👉 *ออกได้เลย!*"
            )
        elif p["tp_hit"]:
            alerts.append(
                f"🎯 *TP HIT — {p['sym']}*\n"
                f"  ราคา: `${p['price']:.2f}` | TP: `${p['tp']}`\n"
                f"  P&L: `{fmt_pnl(p['pnl'])}` ({fmt_pct(p['pct'])})\n"
                f"  👉 *Take Profit ได้เลย!*" +
                (f"\n  _{p['note']}_" if p.get("note") else "")
            )
        elif p["sl_near"]:
            dist = p["price"] - p["sl"]
            alerts.append(
                f"⚠️ *SL ใกล้มาก — {p['sym']}*\n"
                f"  ราคา: `${p['price']:.2f}` | SL: `${p['sl']}` (ห่าง ${dist:.2f})\n"
                f"  👁 เฝ้าดูด้วย!"
            )
        elif p["tp_near"]:
            dist = p["tp"] - p["price"]
            alerts.append(
                f"🔔 *TP ใกล้ — {p['sym']}*\n"
                f"  ราคา: `${p['price']:.2f}` | TP: `${p['tp']}` (ห่าง ${dist:.2f})\n"
                f"  👁 เตรียม Take Profit!"
            )
    if not alerts:
        return None
    now = datetime.now(TZ).strftime("%H:%M ET")
    return f"🔔 *DREAMS Alerts* — {now}\n\n" + "\n\n".join(alerts)

def build_evening_report(positions: list[dict], summary: dict) -> str:
    now  = datetime.now(TZ).strftime("%d/%m/%Y %H:%M ET")
    winners = [p for p in positions if p["pnl"] and p["pnl"] >= 0]
    losers  = [p for p in positions if p["pnl"] and p["pnl"] < 0]

    best  = max(positions, key=lambda p: p["pnl"] or -999)
    worst = min(positions, key=lambda p: p["pnl"] or 999)

    hits = [p for p in positions if p.get("sl_hit") or p.get("tp_hit")]
    hit_txt = "\n".join(
        f"  {'🛑 SL' if p['sl_hit'] else '🎯 TP'} *{p['sym']}* `{fmt_pct(p['pct'])}`"
        for p in hits
    ) if hits else "  ✅ ไม่มี SL/TP triggered วันนี้"

    pnl_em = "📈" if summary["total_pnl"] >= 0 else "📉"
    return f"""🌙 *{COMPANY_NAME}*
📋 *Evening Report* — {now}

{pnl_em} *สรุปวันนี้*
├ กำไร YTD: `{fmt_pnl(summary['total_pnl'])}` ({fmt_pct(summary['yret'])})
├ พอร์ตรวม: `${summary['total']:,.0f}`
├ Winning: {len(winners)}/{summary['total_pos']} positions
└ Cash: `${summary['cash']:,.0f}`

🏆 *Best Today:* {pnl_emoji(best.get('pct'))} *{best['sym']}* `{fmt_pnl(best.get('pnl'))}` ({fmt_pct(best.get('pct'))})
💔 *Worst Today:* {pnl_emoji(worst.get('pct'))} *{worst['sym']}* `{fmt_pnl(worst.get('pnl'))}` ({fmt_pct(worst.get('pct'))})

🚨 *SL/TP Events*
{hit_txt}

_See you tomorrow 🌙_"""

# ════════════════════════════════════════
# SEND TELEGRAM
# ════════════════════════════════════════

def send_telegram(text: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ ไม่มี TELEGRAM_TOKEN หรือ TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown",
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print("✅ ส่ง Telegram สำเร็จ")
        return True
    except Exception as e:
        print(f"❌ ส่ง Telegram ไม่ได้: {e}")
        return False

# ════════════════════════════════════════
# MAIN
# ════════════════════════════════════════

def main():
    mode = os.environ.get("REPORT_MODE", "morning")  # morning | evening | alert
    print(f"🚀 DREAMS Portfolio Bot — mode: {mode}")
    print(f"⏰ {datetime.now(TZ).strftime('%Y-%m-%d %H:%M %Z')}")

    # Fetch prices
    symbols = [h["sym"] for h in PORTFOLIO]
    print(f"📡 กำลังดึงราคา: {', '.join(symbols)}")
    prices = fetch_prices(symbols)
    print(f"✅ ราคาที่ได้: {prices}")

    # Calc positions
    positions = [calc_position(h, prices) for h in PORTFOLIO]
    summary   = portfolio_summary(positions)

    print(f"📊 Portfolio: ${summary['total']:,.0f} | P&L: {fmt_pnl(summary['total_pnl'])} ({fmt_pct(summary['yret'])})")

    # Send report
    if mode == "morning":
        msg = build_morning_report(positions, summary)
        send_telegram(msg)

    elif mode == "evening":
        msg = build_evening_report(positions, summary)
        send_telegram(msg)

    elif mode == "alert":
        alert_msg = build_alert_report(positions)
        if alert_msg:
            print("🔔 พบ SL/TP alerts — กำลังส่ง...")
            send_telegram(alert_msg)
        else:
            print("✅ ไม่มี alerts วันนี้ — ทุกอย่างปกติ")

    else:
        # ส่งทั้งหมด
        send_telegram(build_morning_report(positions, summary))
        alert_msg = build_alert_report(positions)
        if alert_msg:
            send_telegram(alert_msg)

    print("🏁 Done")

if __name__ == "__main__":
    main()
