"""
DREAMS Trading Co. — AI Analyst Bot
=====================================
Phase 3: Claude AI วิเคราะห์พอร์ต + ตอบคำถามใน Telegram

Features:
- พิมพ์ถามใน Telegram → Claude ตอบทันที
- ส่ง AI Analysis อัตโนมัติพร้อม Morning Report
- Commands: /analyze /ask /portfolio /watchlist /alerts /help

อัปเดต 30 มิ.ย. 2026:
1. เปลี่ยนจาก Gemini เป็น Claude API จริง (ตามชื่อไฟล์)
2. ปรับ PORTFOLIO ให้ตรงกับ paper account ปัจจุบัน (FLEX, ทุน $1,000)

วิธี Deploy:
1. เพิ่ม ANTHROPIC_API_KEY ใน GitHub Secrets / Railway env vars
2. รัน ai_analyst_bot.py แยกต่างหาก (polling mode)
   หรือ webhook บน Railway/Render ฟรี
"""

import os
import json
import time
import requests
import yfinance as yf
from datetime import datetime
import pytz

# ════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════

TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL       = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

COMPANY_NAME = "DREAMS Trading Co."
CAPITAL      = 1000        # ทุนเริ่มต้น paper trading (อัปเดต 30 มิ.ย. 2026)
CASH         = 869.85      # เงินสดคงเหลือล่าสุด
TZ           = pytz.timezone("America/New_York")

# Portfolio ปัจจุบัน (อัปเดต 30 มิ.ย. 2026 — หลังตลาดปิด)
PORTFOLIO = [
    {"sym": "FLEX", "qty": 1, "cost": 150.05, "sl": 143.00, "tp": 166.86, "note": "Momentum / AI Infra, TP1 ใกล้มาก"},
]

# Watchlist (max 5 ตัว ตามกฎเหล็ก — รวม open position)
WATCHLIST = [
    {"sym": "NBIS", "reason": "RS 86, AI Infra — รอ stabilize", "entry": "21DMA +3%"},
    {"sym": "UCTT", "reason": "RS 93, Semi Equip — extended +26%, รอ pullback", "entry": "21DMA +3%"},
    {"sym": "ICHR", "reason": "RS 94, Semi Equip — extended +27%, รอ pullback", "entry": "21DMA +3%"},
    {"sym": "INTC", "reason": "RS 91, AI Hardware — extended +9.8%, รอ pullback", "entry": "21DMA +3%"},
]

# ════════════════════════════════════════
# FETCH PRICES
# ════════════════════════════════════════

def fetch_prices(symbols: list) -> dict:
    prices = {}
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                info  = tickers.tickers[sym].fast_info
                price = info.last_price or info.previous_close
                prices[sym] = round(float(price), 4)
            except Exception:
                try:
                    hist = yf.Ticker(sym).history(period="1d")
                    if not hist.empty:
                        prices[sym] = round(float(hist["Close"].iloc[-1]), 4)
                except Exception:
                    prices[sym] = None
    except Exception as e:
        print(f"fetch_prices error: {e}")
    return prices

def calc_positions(prices: dict) -> list:
    result = []
    for h in PORTFOLIO:
        p = prices.get(h["sym"])
        if p:
            pnl = (p - h["cost"]) * h["qty"]
            pct = ((p - h["cost"]) / h["cost"]) * 100
            result.append({**h, "price": p, "pnl": pnl, "pct": pct,
                           "value": p * h["qty"],
                           "sl_hit": h["sl"] and p <= h["sl"],
                           "tp_hit": h["tp"] and p >= h["tp"],
                           "sl_near": h["sl"] and not (p <= h["sl"]) and p <= h["sl"] * 1.03,
                           "tp_near": h["tp"] and not (p >= h["tp"]) and p >= h["tp"] * 0.97})
        else:
            result.append({**h, "price": None, "pnl": None, "pct": None,
                           "value": None, "sl_hit": False, "tp_hit": False,
                           "sl_near": False, "tp_near": False})
    return result

def portfolio_context(positions: list) -> str:
    """สร้าง context ให้ Claude รู้จักพอร์ต"""
    valid = [p for p in positions if p["price"]]
    sv    = sum(p["value"] for p in valid)
    tp    = sum(p["pnl"]   for p in valid)
    now   = datetime.now(TZ).strftime("%Y-%m-%d %H:%M ET")

    rows = "\n".join(
        f"  {p['sym']}: {p['qty']}หุ้น | ซื้อ ${p['cost']} | ราคา ${p['price']:.2f} | "
        f"P&L {'+' if p['pnl']>=0 else ''}${p['pnl']:.2f} ({'+' if p['pct']>=0 else ''}{p['pct']:.2f}%) | "
        f"SL=${p['sl']} TP1=${p['tp']}"
        + (f" ← {p['note']}" if p.get("note") else "")
        for p in valid
    ) or "  (ไม่มี open position)"
    watch = "\n".join(f"  {w['sym']}: {w['reason']} | alert {w['entry']}" for w in WATCHLIST)

    alerts = [p for p in valid if p["sl_hit"] or p["tp_hit"] or p["sl_near"] or p["tp_near"]]
    alert_txt = "\n".join(
        f"  {'🛑 SL HIT' if p['sl_hit'] else '🎯 TP HIT' if p['tp_hit'] else '⚠️ SL ใกล้' if p['sl_near'] else '🔔 TP ใกล้'}: {p['sym']} ราคา ${p['price']:.2f}"
        for p in alerts
    ) or "  ไม่มี alerts"

    return f"""[{COMPANY_NAME} — Portfolio Context]
เวลา: {now}
ทุนเริ่มต้น (paper): ${CAPITAL:,}
Cash ปัจจุบัน: ${CASH:,.2f}
มูลค่า open positions: ${sv:,.2f}
พอร์ตรวม: ${sv+CASH:,.2f}
P&L (open positions): {'+'if tp>=0 else''}${tp:.2f}

Open Positions:
{rows}

Watchlist (max 5 ตัว, รวม open position):
{watch}

Active Alerts:
{alert_txt}

ระบบ: DREAMS Trading Co. — Aggressive Momentum, ซื้อหุ้น pullback มาที่ 21DMA ใน Top 5 Leading Theme
Paper Trade บน Webull (Phase 1: $1,000-$1,500, สร้าง process discipline ก่อนลงเงินจริง)
กฎเหล็ก: ตัด SL ทุกครั้ง / ไม่ average down / ดูราคาปิดเท่านั้น ไม่ใช่ไส้เทียน / ไม่ chase ของ extended
"""

# ════════════════════════════════════════
# CLAUDE AI (Anthropic API)
# ════════════════════════════════════════

SYSTEM_PROMPT = """คุณเป็น AI Analyst ของ DREAMS Trading Company
นักเทรดสไตล์ Aggressive Momentum — Paper Trading บน Webull, เน้นสร้าง process discipline

หน้าที่:
- วิเคราะห์พอร์ตหุ้น US จากข้อมูลที่ให้
- แนะนำกลยุทธ์ตรงๆ ไม่อ้อมค้อม โดยยึดกฎเหล็กของระบบ DREAMS เสมอ
  (ดูราคาปิดเท่านั้น / ไม่ chase ของ extended / ไม่แทรกแซง SL / Top 5 Theme เท่านั้น)
- บอกชัดว่า Hold / Cut / Add / TP ตาม SL/TP ที่ตั้งไว้ ไม่ใช่ความรู้สึก
- ใช้ภาษาไทย กระชับ ได้ใจความ
- ขึ้นต้นด้วย emoji เสมอ
- ถ้าถามเรื่องหุ้นนอกพอร์ต วิเคราะห์ให้ได้ แต่เตือนถ้าราคาเกิน $300 หรือ ATR เกิน 10% ว่าไม่ผ่าน pre-filter ของระบบ

ห้าม:
- พูดอ้อมค้อม "ขึ้นอยู่กับ risk tolerance"
- ปฏิเสธให้ข้อมูล
- แนะนำให้แทรกแซง stop order ที่ตั้งไว้แล้ว
- ตอบยาวเกินไป — max 300 คำ"""

def ask_claude(question: str, positions: list) -> str:
    if not ANTHROPIC_API_KEY:
        return "❌ ไม่มี ANTHROPIC_API_KEY — ตั้งใน GitHub Secrets / Railway env vars ด้วยครับ"
    try:
        ctx = portfolio_context(positions)
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 700,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": f"{ctx}\n\nคำถาม: {question}"}
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks) if text_blocks else "❌ ไม่ได้รับคำตอบจาก Claude"
    except requests.exceptions.HTTPError as e:
        return f"❌ Claude API error: {e} — {resp.text[:200] if 'resp' in dir() else ''}"
    except Exception as e:
        return f"❌ Claude error: {e}"

def build_ai_analysis(positions: list) -> str:
    """สร้าง AI Analysis สำหรับส่งพร้อม Morning Report"""
    question = (
        "วิเคราะห์พอร์ตทั้งหมด:\n"
        "1. ตัวไหนน่าห่วงที่สุด?\n"
        "2. ตัวไหนมีโอกาสวิ่งต่อ?\n"
        "3. Priority action วันนี้คืออะไร?\n"
        "ตอบกระชับ 3 ข้อ"
    )
    analysis = ask_claude(question, positions)
    now = datetime.now(TZ).strftime("%H:%M ET")
    return f"🤖 *AI Analysis* — {now}\n\n{analysis}"

# ════════════════════════════════════════
# TELEGRAM
# ════════════════════════════════════════

def send_telegram(text: str, chat_id: str = None) -> bool:
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": cid, "text": text, "parse_mode": "Markdown"
        }, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"send_telegram error: {e}")
        return False

def get_updates(offset: int = 0) -> list:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
        r.raise_for_status()
        return r.json().get("result", [])
    except Exception as e:
        print(f"get_updates error: {e}")
        return []

def handle_command(text: str, chat_id: str, positions: list) -> str:
    text = text.strip()
    low  = text.lower()

    if low in ["/help", "/start"]:
        return (
            "🤖 *DREAMS AI Analyst*\n\n"
            "Commands:\n"
            "/portfolio — ดูพอร์ตทั้งหมด\n"
            "/analyze — AI วิเคราะห์พอร์ต\n"
            "/alerts — เช็ค SL/TP\n"
            "/watchlist — ดู watchlist\n"
            "/ask [คำถาม] — ถามอะไรก็ได้\n\n"
            "หรือพิมพ์คำถามตรงๆ ได้เลย 👇"
        )

    elif low == "/portfolio":
        valid = [p for p in positions if p["price"]]
        sv    = sum(p["value"] for p in valid)
        tp    = sum(p["pnl"]   for p in valid)
        if valid:
            rows  = "\n".join(
                f"  {'✅' if p['pnl']>=0 else '🔴'} *{p['sym']}* `${p['price']:.2f}` "
                f"{'+' if p['pnl']>=0 else ''}{p['pct']:.1f}%"
                for p in sorted(valid, key=lambda x: x["pnl"], reverse=True)
            )
        else:
            rows = "  (ไม่มี open position)"
        return (
            f"📊 *Portfolio — DREAMS Co. (Paper)*\n\n{rows}\n\n"
            f"💰 Open positions: `${sv:,.2f}` | Cash: `${CASH:,.2f}`\n"
            f"📈 P&L (open): `{'+'if tp>=0 else''}${tp:,.2f}`"
        )

    elif low == "/alerts":
        hits = [p for p in positions if p.get("sl_hit") or p.get("tp_hit") or
                p.get("sl_near") or p.get("tp_near")]
        if not hits:
            return "✅ ไม่มี alerts — ทุกอย่างปกติ"
        rows = "\n\n".join(
            f"{'🛑' if p['sl_hit'] else '🎯' if p['tp_hit'] else '⚠️' if p['sl_near'] else '🔔'} "
            f"*{p['sym']}* ราคา `${p['price']:.2f}`\n"
            f"  {'SL HIT!' if p['sl_hit'] else 'TP HIT!' if p['tp_hit'] else 'SL ใกล้!' if p['sl_near'] else 'TP ใกล้!'}"
            for p in hits
        )
        return f"🔔 *Active Alerts*\n\n{rows}"

    elif low == "/watchlist":
        rows = "\n".join(f"  👁 *{w['sym']}* — {w['reason']}" for w in WATCHLIST)
        return f"👁 *Watchlist* (max 5 ตัว)\n\n{rows}\n\n💵 Cash พร้อม: `${CASH:,.2f}`"

    elif low == "/analyze":
        send_telegram("🤖 กำลังวิเคราะห์... รอแป๊บนึงครับ", chat_id)
        return ask_claude(
            "วิเคราะห์พอร์ตทั้งหมด บอก:\n"
            "1. ตัวที่น่าห่วง + เหตุผล\n"
            "2. ตัวที่มีโอกาสวิ่ง\n"
            "3. Priority action วันนี้\n"
            "4. ควรใช้ cash ทำอะไร? (เทียบกับ watchlist)",
            positions
        )

    elif low.startswith("/ask "):
        q = text[5:].strip()
        if not q:
            return "❓ พิมพ์คำถามต่อจาก /ask เลยครับ\nเช่น: /ask FLEX ควร hold ต่อจนถึง TP1 ไหม?"
        send_telegram("🤖 กำลังคิด...", chat_id)
        return ask_claude(q, positions)

    elif not text.startswith("/"):
        send_telegram("🤖 กำลังคิด...", chat_id)
        return ask_claude(text, positions)

    else:
        return "❓ ไม่รู้จัก command — พิมพ์ /help เพื่อดูคำสั่งทั้งหมด"

# ════════════════════════════════════════
# POLLING MODE (สำหรับ run แบบ long-running)
# ════════════════════════════════════════

def run_polling():
    """รัน bot แบบ polling — ใช้บน Railway/Render"""
    print(f"🤖 DREAMS AI Bot เริ่มทำงาน (polling mode, Claude API)")
    offset   = 0
    prices   = {}
    last_fetch = 0

    while True:
        try:
            now_ts = time.time()
            if now_ts - last_fetch > 300:
                syms   = [h["sym"] for h in PORTFOLIO]
                prices = fetch_prices(syms)
                last_fetch = now_ts
                print(f"✅ ราคาอัปเดตแล้ว")

            positions = calc_positions(prices)
            updates   = get_updates(offset)

            for upd in updates:
                offset = upd["update_id"] + 1
                msg    = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                text    = msg.get("text", "").strip()
                chat_id = str(msg["chat"]["id"])
                if not text:
                    continue

                print(f"📩 [{chat_id}]: {text}")
                reply = handle_command(text, chat_id, positions)
                send_telegram(reply, chat_id)

            time.sleep(1)

        except KeyboardInterrupt:
            print("🛑 หยุดทำงาน")
            break
        except Exception as e:
            print(f"❌ polling error: {e}")
            time.sleep(5)

# ════════════════════════════════════════
# ONE-SHOT MODE (สำหรับ GitHub Actions)
# ════════════════════════════════════════

def run_oneshot():
    """ส่ง AI Analysis ครั้งเดียว — ใช้ใน GitHub Actions"""
    mode = os.environ.get("REPORT_MODE", "ai_analysis")
    print(f"🚀 One-shot mode: {mode}")

    syms      = [h["sym"] for h in PORTFOLIO]
    prices    = fetch_prices(syms)
    positions = calc_positions(prices)

    if mode == "ai_analysis":
        analysis = build_ai_analysis(positions)
        send_telegram(analysis)
        print("✅ ส่ง AI Analysis แล้ว")

# ════════════════════════════════════════
# MAIN
# ════════════════════════════════════════

if __name__ == "__main__":
    run_mode = os.environ.get("BOT_MODE", "oneshot")
    if run_mode == "polling":
        run_polling()
    else:
        run_oneshot()
