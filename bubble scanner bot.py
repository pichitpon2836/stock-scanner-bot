import os
import time
import requests
import yfinance as yf
import pytz
from datetime import datetime
from curl_cffi import requests as cffi_requests

# ============================================================
# CONFIG
# ============================================================
BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
CHAT_ID   = os.environ['TELEGRAM_CHAT_ID']
TIMEZONE  = 'Asia/Bangkok'

# S&P 500 stocks grouped by sector
SECTOR_STOCKS = {
    'Technology': [
        'NVDA','AAPL','MSFT','AVGO','AMD','AMAT','QCOM','MU','WDC',
        'INTC','RKLB','ASTS','APP','APLD','TOST','SIDU','VIAV','AEHR'
    ],
    'Healthcare': [
        'LLY','UNH','JNJ','ABBV','TMO','ISRG','VRTX','GILD','REGN'
    ],
    'Financials': [
        'JPM','BAC','GS','BLK','V','MA','MS','SCHW','SPGI'
    ],
    'Consumer Discr.': [
        'AMZN','TSLA','MCD','NKE','SBUX','HD','COST','CELH','BKNG'
    ],
    'Industrials': [
        'GE','ETN','VRT','PWR','CAT','HON','RTX','LMT','NOC'
    ],
    'Communication': [
        'GOOGL','META','NFLX','DIS','TTWO','T','CMCSA','VZ'
    ],
    'Consumer Staples': [
        'PG','KO','WMT','COST','PEP','PM','MDLZ'
    ],
    'Energy': [
        'XOM','CVX','FCEL','PLUG','BE','BLDP','CEG','VST','NRG'
    ],
    'Materials': [
        'LIN','APD','ECL','NEM','FCX'
    ],
    'Real Estate': [
        'AMT','PLD','EQIX','SPG','PSA'
    ],
    'Utilities': [
        'NEE','CEG','DUK','SO','AEP','EXC'
    ],
}

# ============================================================
# TELEGRAM
# ============================================================
def send(text, parse_mode='HTML'):
    if len(text) > 4000:
        text = text[:3990] + '...'
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': parse_mode},
            timeout=15,
        )
        if r.status_code != 200:
            plain = text.replace('<b>','').replace('</b>','').replace('<i>','').replace('</i>','')
            requests.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                json={'chat_id': CHAT_ID, 'text': plain},
                timeout=15,
            )
    except Exception as e:
        print(f'Telegram error: {e}')
    time.sleep(0.5)

# ============================================================
# FETCH STOCK DATA
# ============================================================
def fetch_stock(ticker):
    try:
        session = cffi_requests.Session(impersonate='chrome')
        t = yf.Ticker(ticker, session=session)
        info = t.info
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        prev  = info.get('previousClose') or info.get('regularMarketPreviousClose')
        if not price or not prev or prev == 0:
            return None
        ch_pct = (price - prev) / prev * 100
        cap    = (info.get('marketCap') or 0) / 1e9  # in billions
        return {
            'ticker': ticker,
            'name':   (info.get('shortName') or ticker)[:20],
            'price':  float(price),
            'prev':   float(prev),
            'ch_pct': round(float(ch_pct), 2),
            'cap_b':  round(cap, 1),
            'volume': info.get('volume') or 0,
            'avg_vol':info.get('averageVolume') or 1,
        }
    except Exception as e:
        print(f'{ticker} error: {e}')
        return None

# ============================================================
# BUBBLE ANALYSIS
# ============================================================
def analyze_sectors(sector_data):
    results = {}
    for sector, stocks in sector_data.items():
        if not stocks:
            continue
        changes = [s['ch_pct'] for s in stocks]
        avg_ch  = sum(changes) / len(changes)
        up      = sum(1 for c in changes if c > 0)
        down    = sum(1 for c in changes if c < 0)
        top     = max(stocks, key=lambda x: x['ch_pct'])
        bot     = min(stocks, key=lambda x: x['ch_pct'])
        results[sector] = {
            'avg_ch': round(avg_ch, 2),
            'up': up, 'down': down,
            'total': len(stocks),
            'top': top,
            'bot': bot,
            'stocks': sorted(stocks, key=lambda x: -x['ch_pct']),
        }
    return results

def bubble_position(ch_pct):
    """Visual indicator of bubble Y position"""
    if ch_pct >= 10: return '🚀🚀🚀'
    if ch_pct >= 5:  return '🚀🚀'
    if ch_pct >= 2:  return '🚀'
    if ch_pct >= 0:  return '🟢'
    if ch_pct >= -2: return '🔴'
    if ch_pct >= -5: return '🔴🔴'
    return '🔴🔴🔴'

def bar_chart(ch_pct, width=10):
    """Mini text bar chart"""
    if ch_pct >= 0:
        filled = min(int(abs(ch_pct) / 2 * width / 5), width)
        return '█' * filled + '░' * (width - filled)
    else:
        filled = min(int(abs(ch_pct) / 2 * width / 5), width)
        return '░' * (width - filled) + '▒' * filled

# ============================================================
# FORMAT MESSAGES
# ============================================================
def fmt_cap(cap_b):
    if cap_b >= 1000: return f'${cap_b/1000:.1f}T'
    if cap_b >= 1:    return f'${cap_b:.0f}B'
    return f'${cap_b*1000:.0f}M'

def fmt_vol_surge(stock):
    if stock['avg_vol'] <= 0: return ''
    ratio = stock['volume'] / stock['avg_vol']
    if ratio >= 2: return f' | Vol {ratio:.1f}x⚡'
    return ''

def build_sector_overview(analysis, today):
    """Main overview message"""
    # Sort sectors by avg change
    sorted_sectors = sorted(analysis.items(), key=lambda x: -x[1]['avg_ch'])

    msg = f'<b>📊 Bubble Sector Scanner — {today}</b>\n'
    msg += f'<i>Axis Y = %Change | Size = Market Cap</i>\n'
    msg += '─' * 28 + '\n\n'

    msg += '<b>SECTOR BUBBLE MAP</b>\n'
    msg += '<code>SECTOR          AVG%   UP/DN  BAR</code>\n'

    for sector, data in sorted_sectors:
        avg   = data['avg_ch']
        sign  = '+' if avg >= 0 else ''
        bar   = bar_chart(avg)
        emoji = '🟢' if avg >= 1 else ('🔴' if avg <= -1 else '⬜')
        msg += f'{emoji} <b>{sector[:14]:<14}</b> {sign}{avg:+.1f}%  {data["up"]}/{data["down"]}  <code>{bar}</code>\n'

    # Overall stats
    all_stocks = [s for d in analysis.values() for s in d['stocks']]
    total_up   = sum(d['up'] for d in analysis.values())
    total_down = sum(d['down'] for d in analysis.values())
    top_overall = max(all_stocks, key=lambda x: x['ch_pct'])
    bot_overall = min(all_stocks, key=lambda x: x['ch_pct'])

    msg += f'\n<b>MARKET BREADTH</b>\n'
    msg += f'ADV/DEC: <b>{total_up}</b> ↑ / <b>{total_down}</b> ↓\n'
    msg += f'Top Gainer: <b>{top_overall["ticker"]}</b> +{top_overall["ch_pct"]:.1f}%\n'
    msg += f'Top Loser:  <b>{bot_overall["ticker"]}</b> {bot_overall["ch_pct"]:.1f}%\n'

    return msg

def build_hot_sectors(analysis):
    """Top 3 hot sectors with stock details"""
    sorted_sectors = sorted(analysis.items(), key=lambda x: -x[1]['avg_ch'])
    hot = [(s, d) for s, d in sorted_sectors if d['avg_ch'] > 0][:3]

    if not hot:
        return '📊 No hot sectors today.'

    msg = '<b>🔥 HOT SECTORS — Top Performers</b>\n'
    msg += f'<i>(วงกลมลอยเหนือ 0 — Bubble above zero line)</i>\n\n'

    for i, (sector, data) in enumerate(hot):
        avg = data['avg_ch']
        msg += f'#{i+1} <b>{sector}</b> — Avg +{avg:.1f}%\n'

        # Top 5 stocks in sector
        top5 = data['stocks'][:5]
        for s in top5:
            pos   = bubble_position(s['ch_pct'])
            sign  = '+' if s['ch_pct'] >= 0 else ''
            vsurge = fmt_vol_surge(s)
            cap_str = f' [{fmt_cap(s["cap_b"])}]' if s['cap_b'] > 0 else ''
            msg += f'  {pos} <b>{s["ticker"]}</b> {sign}{s["ch_pct"]:.1f}%{cap_str}{vsurge}\n'

        msg += '\n'

    return msg

def build_cold_sectors(analysis):
    """Bottom sectors warning"""
    sorted_sectors = sorted(analysis.items(), key=lambda x: x[1]['avg_ch'])
    cold = [(s, d) for s, d in sorted_sectors if d['avg_ch'] < 0][:3]

    if not cold:
        return '✅ No cold sectors today — full bull market!'

    msg = '<b>🧊 COLD SECTORS — Avoid / Watch</b>\n'
    msg += f'<i>(วงกลมจมใต้ 0 — Bubble below zero line)</i>\n\n'

    for i, (sector, data) in enumerate(cold):
        avg = data['avg_ch']
        msg += f'⚠️ <b>{sector}</b> — Avg {avg:.1f}%\n'
        worst3 = sorted(data['stocks'], key=lambda x: x['ch_pct'])[:3]
        for s in worst3:
            msg += f'  🔴 <b>{s["ticker"]}</b> {s["ch_pct"]:.1f}%\n'
        msg += '\n'

    return msg

def build_standout_stocks(analysis):
    """Stocks that outperform their sector — the KEY bubble scanner insight"""
    msg = '<b>⚡ STANDOUT STOCKS — ฉีกจากกลุ่ม!</b>\n'
    msg += '<i>(วงกลมที่กระโดดสูงกว่าเพื่อนใน sector เดียวกัน)</i>\n\n'

    standouts = []
    for sector, data in analysis.items():
        avg = data['avg_ch']
        for s in data['stocks']:
            diff = s['ch_pct'] - avg  # how much it outperforms sector avg
            if diff >= 3 and s['ch_pct'] > 0:
                standouts.append({**s, 'sector': sector, 'sector_avg': avg, 'outperform': diff})

    standouts.sort(key=lambda x: -x['outperform'])

    if not standouts:
        msg += 'No standout stocks today.\n'
        return msg

    for i, s in enumerate(standouts[:8]):
        vsurge = fmt_vol_surge(s)
        cap_str = fmt_cap(s['cap_b']) if s['cap_b'] > 0 else 'N/A'
        msg += (
            f'#{i+1} <b>{s["ticker"]}</b> — {s["name"]}\n'
            f'   Change: <b>+{s["ch_pct"]:.1f}%</b> | Sector avg: {s["sector_avg"]:+.1f}%\n'
            f'   Outperform: <b>+{s["outperform"]:.1f}%</b> vs {s["sector"]}\n'
            f'   Cap: {cap_str}{vsurge}\n\n'
        )

    return msg

def build_finviz_links():
    """Finviz bubble map direct links"""
    msg = '<b>🔗 FINVIZ LIVE BUBBLE MAP</b>\n\n'
    links = [
        ('S&P 500', 'sp500'),
        ('Nasdaq 100', 'ndx'),
        ('Russell 2000', 'rut'),
        ('Dow Jones', 'dji'),
    ]
    base = 'https://finviz.com/bubbles?x=sector&y=lastChange&size=marketCap&color=sector&idx='
    for name, idx in links:
        msg += f'📈 <a href="{base}{idx}">{name}</a>\n'

    msg += '\n<b>วิธีอ่าน:</b>\n'
    msg += '• วงกลมสูง = บวกเยอะ\n'
    msg += '• วงกลมใหญ่ = market cap ใหญ่\n'
    msg += '• หาวงกลมเล็กที่อยู่สูงกว่ากลุ่ม = standout\n'
    msg += '• กลุ่มสีเดียวกัน = sector เดียวกัน\n'
    return msg

# ============================================================
# MAIN
# ============================================================
def main():
    tz    = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime('%d %b %Y %H:%M')

    print(f'[{today}] Starting Bubble Sector Scanner...')

    # Fetch all stocks
    sector_data = {}
    total = sum(len(v) for v in SECTOR_STOCKS.values())
    done  = 0

    for sector, tickers in SECTOR_STOCKS.items():
        sector_data[sector] = []
        for ticker in tickers:
            result = fetch_stock(ticker)
            if result:
                sector_data[sector].append(result)
            done += 1
            print(f'  [{done}/{total}] {ticker}')
            time.sleep(0.2)

    # Analyze
    analysis = analyze_sectors(sector_data)

    # Send messages
    send(build_sector_overview(analysis, today))
    time.sleep(1)
    send(build_hot_sectors(analysis))
    time.sleep(1)
    send(build_cold_sectors(analysis))
    time.sleep(1)
    send(build_standout_stocks(analysis))
    time.sleep(1)
    send(build_finviz_links())

    print('Done.')

if __name__ == '__main__':
    main()
