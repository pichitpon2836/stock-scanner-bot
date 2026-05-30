"""
DREAMS Trading Co. — Monthly PDF Report Generator
===================================================
Phase 4: สร้าง P&L Report สวยงาม ส่ง Telegram อัตโนมัติ

Features:
- รายงาน P&L รายเดือน พร้อมตาราง + กราฟ
- สรุป Win/Loss ratio, Best/Worst positions
- ส่ง PDF เข้า Telegram อัตโนมัติ
- รันผ่าน GitHub Actions ทุกสิ้นเดือน
"""

import os
import io
import requests
import yfinance as yf
from datetime import datetime, timedelta
import pytz
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

# ════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

COMPANY_NAME = "DREAMS Trading Co."
CAPITAL      = 10000
CASH         = 1706
TZ           = pytz.timezone("America/New_York")

# สีบริษัท
C_DARK   = colors.HexColor("#0a0e1a")
C_GOLD   = colors.HexColor("#f5c518")
C_GREEN  = colors.HexColor("#00c96e")
C_RED    = colors.HexColor("#ff3d5a")
C_BLUE   = colors.HexColor("#38bdf8")
C_PANEL  = colors.HexColor("#111827")
C_DIM    = colors.HexColor("#4a6080")
C_TEXT   = colors.HexColor("#c8d8f0")
C_WHITE  = colors.white
C_LGRAY  = colors.HexColor("#1e2d4a")

PORTFOLIO = [
    {"sym": "SIDU", "qty": 175, "cost": 3.75,   "sl": 3.20, "tp": 6.00},
    {"sym": "AMD",  "qty": 2,   "cost": 439.39,  "sl": 400,  "tp": 560},
    {"sym": "PLUG", "qty": 572, "cost": 3.51,    "sl": 3.00, "tp": 4.00},
    {"sym": "APLD", "qty": 24,  "cost": 42.42,   "sl": 38,   "tp": 55},
    {"sym": "AMAT", "qty": 5,   "cost": 429.66,  "sl": 400,  "tp": 480},
    {"sym": "CEG",  "qty": 1,   "cost": 281.20,  "sl": 260,  "tp": 320},
    {"sym": "VIAV", "qty": 20,  "cost": 50.87,   "sl": 48,   "tp": 58},
]

# ════════════════════════════════════════
# FETCH & CALC
# ════════════════════════════════════════

def fetch_prices(symbols):
    prices = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if not hist.empty:
                prices[sym] = round(float(hist["Close"].iloc[-1]), 4)
        except Exception as e:
            print(f"⚠️ {sym}: {e}")
            prices[sym] = None
    return prices

def calc_positions(prices):
    result = []
    for h in PORTFOLIO:
        p = prices.get(h["sym"])
        if p:
            pnl   = (p - h["cost"]) * h["qty"]
            pct   = ((p - h["cost"]) / h["cost"]) * 100
            value = p * h["qty"]
            result.append({**h, "price": p, "pnl": pnl, "pct": pct, "value": value})
        else:
            result.append({**h, "price": None, "pnl": 0, "pct": 0, "value": h["cost"]*h["qty"]})
    return result

# ════════════════════════════════════════
# PDF BUILDER
# ════════════════════════════════════════

def build_pdf(positions: list) -> bytes:
    now      = datetime.now(TZ)
    month_th = ["", "มกราคม","กุมภาพันธ์","มีนาคม","เมษายน","พฤษภาคม","มิถุนายน",
                 "กรกฎาคม","สิงหาคม","กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม"]
    month_str = f"{month_th[now.month]} {now.year + 543}"  # พ.ศ.

    valid    = [p for p in positions if p["price"]]
    sv       = sum(p["value"] for p in valid)
    total_pnl = sum(p["pnl"] for p in valid)
    total_v  = sv + CASH
    yret     = (total_pnl / CAPITAL) * 100
    wins     = [p for p in valid if p["pnl"] >= 0]
    losses   = [p for p in valid if p["pnl"] < 0]
    best     = max(valid, key=lambda x: x["pnl"]) if valid else None
    worst    = min(valid, key=lambda x: x["pnl"]) if valid else None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    def sty(name, **kw):
        return ParagraphStyle(name, **kw)

    s_title = sty("title", fontName="Helvetica-Bold", fontSize=22,
                  textColor=C_GOLD, spaceAfter=2)
    s_sub   = sty("sub", fontName="Helvetica", fontSize=10,
                  textColor=C_DIM, spaceAfter=8)
    s_h2    = sty("h2", fontName="Helvetica-Bold", fontSize=13,
                  textColor=C_GOLD, spaceBefore=10, spaceAfter=6)
    s_body  = sty("body", fontName="Helvetica", fontSize=9,
                  textColor=C_TEXT, leading=14)
    s_small = sty("small", fontName="Helvetica", fontSize=8, textColor=C_DIM)
    s_green = sty("green", fontName="Helvetica-Bold", fontSize=11, textColor=C_GREEN)
    s_red   = sty("red",   fontName="Helvetica-Bold", fontSize=11, textColor=C_RED)

    story = []

    # ── HEADER ──
    header_data = [[
        Paragraph(f"★  {COMPANY_NAME}", sty("hn", fontName="Helvetica-Bold",
                  fontSize=20, textColor=C_GOLD)),
        Paragraph(f"Monthly P&L Report<br/><font size=9 color='#4a6080'>{month_str}</font>",
                  sty("hr", fontName="Helvetica", fontSize=12,
                      textColor=C_TEXT, alignment=2))
    ]]
    header_tbl = Table(header_data, colWidths=["60%","40%"])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0),(-1,-1), C_DARK),
        ("PADDING",     (0,0),(-1,-1), 12),
        ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
        ("LINEBELOW",   (0,0),(-1,-1), 2, C_GOLD),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 8))

    # ── SUMMARY CARDS ──
    def pnl_str(n): return f"{'+'if n>=0 else ''}${abs(n):,.2f}"
    def pct_str(n): return f"{'+'if n>=0 else ''}{n:.2f}%"

    cards = [
        ["TOTAL P&L", pnl_str(total_pnl), pct_str(yret), C_GREEN if total_pnl>=0 else C_RED],
        ["STOCK VALUE", f"${sv:,.0f}", f"{len(valid)} positions", C_BLUE],
        ["CASH",  f"${CASH:,}", f"Total ${total_v:,.0f}", C_GOLD],
        ["WIN RATE", f"{len(wins)}/{len(valid)}", f"Loss: {len(losses)}", C_GREEN if len(wins)>len(losses) else C_RED],
    ]

    card_rows = []
    for label, val, sub, col in cards:
        card_rows.append(
            Table([[
                Paragraph(label, sty(f"cl{label}", fontName="Helvetica-Bold",
                          fontSize=7, textColor=C_DIM)),
                Paragraph(val,   sty(f"cv{label}", fontName="Helvetica-Bold",
                          fontSize=14, textColor=col)),
                Paragraph(sub,   sty(f"cs{label}", fontName="Helvetica",
                          fontSize=8, textColor=C_TEXT)),
            ]], colWidths=["100%"])
        )

    card_data  = [card_rows]
    card_table = Table(card_data, colWidths=["25%","25%","25%","25%"])
    card_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0),(-1,-1), C_PANEL),
        ("PADDING",     (0,0),(-1,-1), 10),
        ("GRID",        (0,0),(-1,-1), 1, C_LGRAY),
        ("LINEABOVE",   (0,0),(-1,0),  2, C_GOLD),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 12))

    # ── HOLDINGS TABLE ──
    story.append(Paragraph("📊 Holdings", s_h2))

    sorted_pos = sorted(valid, key=lambda x: x["pnl"], reverse=True)
    tbl_data   = [[
        Paragraph("TICKER", sty("th", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("QTY",    sty("th2", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("COST",   sty("th3", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("PRICE",  sty("th4", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("VALUE",  sty("th5", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("P&L $",  sty("th6", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("P&L %",  sty("th7", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("SL / TP",sty("th8", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
    ]]

    row_styles = [
        ("BACKGROUND", (0,0), (-1,0), C_DARK),
        ("GRID",       (0,0), (-1,-1), 0.5, C_LGRAY),
        ("PADDING",    (0,0), (-1,-1), 6),
        ("FONTNAME",   (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("TEXTCOLOR",  (0,0), (-1,-1), C_TEXT),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_PANEL, C_DARK]),
    ]

    for i, p in enumerate(sorted_pos):
        col = C_GREEN if p["pnl"] >= 0 else C_RED
        tbl_data.append([
            Paragraph(f"<b>{p['sym']}</b>",   sty(f"td{i}a", fontName="Helvetica-Bold", fontSize=9, textColor=C_GOLD)),
            Paragraph(str(p["qty"]),           sty(f"td{i}b", fontSize=8, textColor=C_TEXT, fontName="Helvetica")),
            Paragraph(f"${p['cost']:.2f}",     sty(f"td{i}c", fontSize=8, textColor=C_DIM,  fontName="Helvetica")),
            Paragraph(f"${p['price']:.2f}",    sty(f"td{i}d", fontSize=8, textColor=C_TEXT, fontName="Helvetica")),
            Paragraph(f"${p['value']:,.0f}",   sty(f"td{i}e", fontSize=8, textColor=C_TEXT, fontName="Helvetica")),
            Paragraph(pnl_str(p["pnl"]),       sty(f"td{i}f", fontSize=8, textColor=col,   fontName="Helvetica-Bold")),
            Paragraph(pct_str(p["pct"]),       sty(f"td{i}g", fontSize=8, textColor=col,   fontName="Helvetica-Bold")),
            Paragraph(f"SL ${p['sl']} / TP ${p['tp']}", sty(f"td{i}h", fontSize=7, textColor=C_DIM, fontName="Helvetica")),
        ])

    # Total row
    tbl_data.append([
        Paragraph("<b>TOTAL</b>", sty("tft", fontName="Helvetica-Bold", fontSize=8, textColor=C_GOLD)),
        Paragraph("", s_small), Paragraph("", s_small),
        Paragraph("", s_small),
        Paragraph(f"${sv:,.0f}", sty("tfv", fontName="Helvetica-Bold", fontSize=8, textColor=C_TEXT)),
        Paragraph(pnl_str(total_pnl), sty("tfp", fontName="Helvetica-Bold", fontSize=8,
                  textColor=C_GREEN if total_pnl>=0 else C_RED)),
        Paragraph(pct_str(yret), sty("tfr", fontName="Helvetica-Bold", fontSize=8,
                  textColor=C_GREEN if yret>=0 else C_RED)),
        Paragraph("", s_small),
    ])
    row_styles.append(("BACKGROUND", (0, len(tbl_data)-1), (-1,-1), C_DARK))
    row_styles.append(("LINEABOVE",  (0, len(tbl_data)-1), (-1,-1), 1, C_GOLD))

    hold_tbl = Table(tbl_data, colWidths=["12%","8%","10%","10%","12%","13%","10%","25%"])
    hold_tbl.setStyle(TableStyle(row_styles))
    story.append(hold_tbl)
    story.append(Spacer(1, 12))

    # ── P&L BAR CHART ──
    story.append(Paragraph("📈 P&L By Position", s_h2))

    drawing = Drawing(170*mm, 60*mm)
    bc = VerticalBarChart()
    bc.x  = 10*mm
    bc.y  = 8*mm
    bc.width  = 150*mm
    bc.height = 48*mm
    bc.data   = [[p["pnl"] for p in sorted_pos]]
    bc.categoryAxis.categoryNames = [p["sym"] for p in sorted_pos]
    bc.categoryAxis.labels.fontName  = "Helvetica"
    bc.categoryAxis.labels.fontSize  = 7
    bc.valueAxis.labels.fontName     = "Helvetica"
    bc.valueAxis.labels.fontSize     = 7
    bc.valueAxis.strokeColor         = colors.HexColor("#1e2d4a")
    bc.categoryAxis.strokeColor      = colors.HexColor("#1e2d4a")
    bc.bars[0].fillColor = C_GREEN

    drawing.add(bc)
    story.append(drawing)
    story.append(Spacer(1, 10))

    # ── HIGHLIGHTS ──
    story.append(Paragraph("🏆 Highlights", s_h2))

    hi_data = []
    if best:
        hi_data.append([
            Paragraph("Best Position", sty("hbl", fontName="Helvetica-Bold", fontSize=9, textColor=C_GREEN)),
            Paragraph(f"{best['sym']} — {pnl_str(best['pnl'])} ({pct_str(best['pct'])})",
                      sty("hbv", fontName="Helvetica-Bold", fontSize=10, textColor=C_GREEN)),
        ])
    if worst:
        hi_data.append([
            Paragraph("Worst Position", sty("hwl", fontName="Helvetica-Bold", fontSize=9, textColor=C_RED)),
            Paragraph(f"{worst['sym']} — {pnl_str(worst['pnl'])} ({pct_str(worst['pct'])})",
                      sty("hwv", fontName="Helvetica-Bold", fontSize=10, textColor=C_RED)),
        ])
    hi_data.append([
        Paragraph("Win Rate",  sty("wrl", fontName="Helvetica-Bold", fontSize=9, textColor=C_BLUE)),
        Paragraph(f"{len(wins)}/{len(valid)} positions ({len(wins)/len(valid)*100:.0f}%)" if valid else "N/A",
                  sty("wrv", fontName="Helvetica", fontSize=10, textColor=C_TEXT)),
    ])
    hi_data.append([
        Paragraph("Capital",   sty("cpl", fontName="Helvetica-Bold", fontSize=9, textColor=C_GOLD)),
        Paragraph(f"เริ่มต้น ${CAPITAL:,} → ปัจจุบัน ${total_v:,.0f} ({pct_str(yret)})",
                  sty("cpv", fontName="Helvetica", fontSize=10, textColor=C_TEXT)),
    ])

    hi_tbl = Table(hi_data, colWidths=["30%","70%"])
    hi_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0),(-1,-1), C_PANEL),
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [C_PANEL, C_DARK]),
        ("PADDING",     (0,0),(-1,-1), 10),
        ("GRID",        (0,0),(-1,-1), 0.5, C_LGRAY),
        ("LINEABOVE",   (0,0),(-1,0),  2, C_GOLD),
        ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(hi_tbl)
    story.append(Spacer(1, 12))

    # ── FOOTER ──
    story.append(HRFlowable(width="100%", thickness=1, color=C_LGRAY))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"DREAMS Trading Co. · Paper Trade · รายงานประจำ{month_str} · "
        f"สร้างเมื่อ {now.strftime('%d/%m/%Y %H:%M ET')}",
        sty("ft", fontName="Helvetica", fontSize=7, textColor=C_DIM, alignment=1)
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()

# ════════════════════════════════════════
# SEND TO TELEGRAM
# ════════════════════════════════════════

def send_pdf_telegram(pdf_bytes: bytes, caption: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ ไม่มี TELEGRAM credentials")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    now = datetime.now(TZ)
    filename = f"DREAMS_Report_{now.strftime('%Y%m')}.pdf"
    try:
        r = requests.post(url, data={
            "chat_id":    TELEGRAM_CHAT_ID,
            "caption":    caption,
            "parse_mode": "Markdown",
        }, files={"document": (filename, pdf_bytes, "application/pdf")}, timeout=30)
        r.raise_for_status()
        print(f"✅ ส่ง PDF สำเร็จ: {filename}")
        return True
    except Exception as e:
        print(f"❌ ส่ง PDF ไม่ได้: {e}")
        return False

def send_msg_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"
        }, timeout=15)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ ส่ง message ไม่ได้: {e}")
        return False

# ════════════════════════════════════════
# MAIN
# ════════════════════════════════════════

def main():
    now = datetime.now(TZ)
    print(f"📄 DREAMS PDF Report Generator")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M %Z')}")

    # Fetch prices
    symbols   = [h["sym"] for h in PORTFOLIO]
    print(f"📡 ดึงราคา: {', '.join(symbols)}")
    prices    = fetch_prices(symbols)
    positions = calc_positions(prices)

    valid     = [p for p in positions if p["price"]]
    total_pnl = sum(p["pnl"] for p in valid)
    sv        = sum(p["value"] for p in valid)
    yret      = (total_pnl / CAPITAL) * 100

    print(f"📊 P&L: {'+'if total_pnl>=0 else ''}${total_pnl:,.2f} ({yret:+.2f}%)")

    # Build PDF
    print("🖨️ กำลังสร้าง PDF...")
    pdf_bytes = build_pdf(positions)
    print(f"✅ PDF size: {len(pdf_bytes):,} bytes")

    # Caption
    month_en  = now.strftime("%B %Y")
    sign      = "📈" if total_pnl >= 0 else "📉"
    caption = (
        f"📄 *DREAMS Trading Co.*\n"
        f"Monthly Report — {month_en}\n\n"
        f"{sign} P&L: `{'+'if total_pnl>=0 else ''}${abs(total_pnl):,.2f}` ({yret:+.2f}%)\n"
        f"💼 Portfolio: `${sv+CASH:,.0f}`\n"
        f"🏆 Win: `{sum(1 for p in valid if p['pnl']>=0)}/{len(valid)}`"
    )

    # Send to Telegram
    send_pdf_telegram(pdf_bytes, caption)

    # Save local copy
    output_path = f"DREAMS_Report_{now.strftime('%Y%m')}.pdf"
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"💾 บันทึกไฟล์: {output_path}")

if __name__ == "__main__":
    main()
