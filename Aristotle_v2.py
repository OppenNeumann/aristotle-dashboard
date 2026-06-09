"""
ARISTOTLE V2 - ENHANCED DAILY SCANNER
- Scans your 27 approved stocks
- PLUS scans entire market for other opportunities
- Sends daily email alerts automatically
- Writes dashboard.html for GitHub Pages
- Appends to history.json for 30-day history

Author: Joseph Nunes
Email: joe_nunes98@hotmail.com
"""

import yfinance as yf
import pandas as pd
import smtplib
import time
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ==================== EMAIL CONFIGURATION ====================

ALERT_EMAIL = "joe_nunes98@hotmail.com"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "reactive.saturday@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

# ==================== TRADING PARAMETERS ====================

DROP_THRESHOLD = 8.0
MIN_VOLUME = 200000
MIN_PRICE = 1.00
MAX_PRICE = 100.00
MAX_PRICE_BROAD = 300.00

# ==================== STOCK LISTS ====================

APPROVED_STOCKS = {
    'Biotech': ['SAVA', 'NVAX', 'MRNA', 'OCGN', 'BNTX'],
    'Cannabis': ['TLRY', 'SNDL', 'CRON', 'ACB'],
    'AI/Data': ['BBAI', 'SOUN', 'AI'],
    'Growth Tech': ['SOFI', 'UPST', 'SNAP', 'HOOD', 'SKLZ', 'RBLX'],
    'Crypto': ['RIOT', 'CLSK', 'BTBT'],
    'Space': ['ASTS', 'RKLB'],
    'Energy/EV': ['LCID', 'QS', 'RIVN', 'CHPT']
}

APPROVED_LIST = []
for stocks in APPROVED_STOCKS.values():
    APPROVED_LIST.extend(stocks)

BROADER_MARKET = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX',
    'CRM', 'ADBE', 'ORCL', 'CSCO', 'INTC', 'AMD', 'QCOM', 'AVGO', 'TXN', 'MU',
    'NOW', 'INTU', 'SNOW', 'DDOG', 'CRWD', 'ZS', 'PANW', 'FTNT', 'NET',
    'SHOP', 'UBER', 'LYFT', 'ABNB', 'DASH', 'BKNG', 'EBAY',
    'V', 'MA', 'JPM', 'BAC', 'WFC', 'GS', 'MS', 'PYPL', 'SQ', 'COIN', 'AXP',
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN', 'GILD', 'VRTX', 'REGN',
    'WMT', 'HD', 'COST', 'TGT', 'LOW', 'NKE', 'SBUX', 'MCD', 'CMG', 'YUM',
    'DIS', 'CMCSA', 'PARA', 'WBD', 'SPOT', 'ROKU',
    'AMAT', 'LRCX', 'KLAC', 'MRVL', 'ASML', 'TSM',
    'BA', 'RTX', 'LMT', 'NOC', 'GD', 'CAT', 'DE', 'HON', 'UPS', 'FDX', 'GE',
    'F', 'GM',
    'XOM', 'CVX', 'COP', 'SLB', 'OXY', 'MPC', 'PSX',
    'T', 'VZ', 'TMUS',
    'AMT', 'PLD', 'EQIX', 'PSA', 'SPG',
    'BIIB', 'ILMN', 'ALNY', 'BMRN', 'SRPT', 'RARE',
    'MDB', 'OKTA', 'ESTC',
    'FISV', 'FIS',
    'EA', 'TTWO',
    'EXPE', 'AAL', 'DAL', 'UAL', 'LUV',
    'SPGI', 'CME', 'ICE', 'MCO', 'BLK', 'SCHW'
]

BROADER_MARKET = list(dict.fromkeys([s for s in BROADER_MARKET if s not in APPROVED_LIST]))

# ==================== HISTORY ====================

HISTORY_FILE = "history.json"

def load_history():
    """Load existing scan history"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return []

def save_history(history):
    """Save history, keeping only last 30 days"""
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    history = [entry for entry in history if entry["date"] >= cutoff]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

def append_to_history(approved_signals, broader_signals):
    """Append today's results to history"""
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")

    # Remove any existing entry for today (re-run scenario)
    history = [e for e in history if e["date"] != today]

    entry = {
        "date": today,
        "scan_time": datetime.now().strftime("%H:%M UTC"),
        "approved": [
            {
                "ticker": s["ticker"],
                "sector": get_sector(s["ticker"]),
                "price": round(float(s["current_price"]), 2),
                "high_20d": round(float(s["high_20d"]), 2),
                "drop_pct": round(float(s["drop_pct"]), 1),
                "volume_ratio": round(float(s["volume_ratio"]), 2)
            } for s in approved_signals
        ],
        "broader": [
            {
                "ticker": s["ticker"],
                "price": round(float(s["current_price"]), 2),
                "high_20d": round(float(s["high_20d"]), 2),
                "drop_pct": round(float(s["drop_pct"]), 1),
                "volume_ratio": round(float(s["volume_ratio"]), 2)
            } for s in broader_signals[:20]
        ]
    }

    history.append(entry)
    history.sort(key=lambda x: x["date"], reverse=True)
    save_history(history)
    return history

# ==================== SCANNER FUNCTIONS ====================

def download_stock_data(tickers, days_back=30):
    print(f"Downloading data for {len(tickers)} stocks...")
    print("(This may take a few minutes...)\n")

    data_cache = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    for i, ticker in enumerate(tickers, 1):
        for attempt in range(2):
            try:
                if attempt > 0:
                    time.sleep(1)
                if i % 20 == 0:
                    print(f"  Progress: {i}/{len(tickers)}...")
                df = yf.download(ticker, start=start_date, end=end_date,
                                progress=False, show_errors=False)
                if hasattr(df.index, 'tz') and df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                if not df.empty and len(df) >= 20:
                    data_cache[ticker] = df
                    break
            except:
                pass
        time.sleep(0.2)

    print(f"✓ Loaded {len(data_cache)}/{len(tickers)} stocks\n")
    return data_cache


def scan_for_buy_signals(data_cache, max_price=MAX_PRICE):
    buy_signals = []

    for ticker, df in data_cache.items():
        try:
            recent_data = df.iloc[-20:]
            if len(recent_data) < 20:
                continue
            current_price = recent_data['Close'].iloc[-1]
            if current_price < MIN_PRICE or current_price >= max_price:
                continue
            avg_volume = recent_data['Volume'].iloc[-10:].mean()
            if avg_volume < MIN_VOLUME:
                continue
            high_20d = recent_data['Close'].max()
            drop_pct = ((high_20d - current_price) / high_20d) * 100
            if drop_pct >= DROP_THRESHOLD:
                recent_vol = recent_data['Volume'].iloc[-5:].mean()
                avg_vol_20d = recent_data['Volume'].mean()
                volume_ratio = recent_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0
                buy_signals.append({
                    'ticker': ticker,
                    'current_price': current_price,
                    'high_20d': high_20d,
                    'drop_pct': drop_pct,
                    'avg_volume': avg_volume,
                    'volume_ratio': volume_ratio,
                    'score': drop_pct * volume_ratio
                })
        except:
            continue

    buy_signals.sort(key=lambda x: x['score'], reverse=True)
    return buy_signals


def get_sector(ticker):
    for sector_name, stocks in APPROVED_STOCKS.items():
        if ticker in stocks:
            return sector_name
    return "Other"


# ==================== DASHBOARD HTML ====================

def generate_dashboard(history):
    """Generate the full dashboard HTML from history data"""

    today_entry = history[0] if history else None
    today_approved = today_entry["approved"] if today_entry else []
    today_broader = today_entry["broader"] if today_entry else []
    today_date = today_entry["date"] if today_entry else "No data yet"
    today_time = today_entry["scan_time"] if today_entry else ""
    total_today = len(today_approved) + len(today_broader)

    # Build today's approved table rows
    approved_rows = ""
    if today_approved:
        for i, s in enumerate(today_approved, 1):
            fire = "🔥" if s["volume_ratio"] > 1.5 else ""
            approved_rows += f"""
            <tr>
                <td class="rank">#{i}</td>
                <td class="ticker">{s['ticker']}</td>
                <td><span class="sector-badge">{s['sector']}</span></td>
                <td>${s['price']:.2f}</td>
                <td>${s['high_20d']:.2f}</td>
                <td class="drop">↓{s['drop_pct']:.1f}%</td>
                <td>{fire} {s['volume_ratio']:.2f}x</td>
            </tr>"""
    else:
        approved_rows = '<tr><td colspan="7" class="no-signals">No signals from approved stocks today</td></tr>'

    # Build today's broader table rows
    broader_rows = ""
    if today_broader:
        for i, s in enumerate(today_broader, 1):
            fire = "🔥" if s["volume_ratio"] > 1.5 else ""
            broader_rows += f"""
            <tr>
                <td class="rank">#{i}</td>
                <td class="ticker">{s['ticker']}</td>
                <td>${s['price']:.2f}</td>
                <td>${s['high_20d']:.2f}</td>
                <td class="drop">↓{s['drop_pct']:.1f}%</td>
                <td>{fire} {s['volume_ratio']:.2f}x</td>
            </tr>"""
    else:
        broader_rows = '<tr><td colspan="6" class="no-signals">No signals from broader market today</td></tr>'

    # Build history cards
    history_cards = ""
    for entry in history:
        total = len(entry["approved"]) + len(entry["broader"])
        signal_class = "has-signals" if total > 0 else "no-signal-day"
        approved_tickers = ", ".join([s["ticker"] for s in entry["approved"]]) or "—"
        broader_tickers = ", ".join([s["ticker"] for s in entry["broader"][:5]])
        if len(entry["broader"]) > 5:
            broader_tickers += f" +{len(entry['broader'])-5} more"
        if not broader_tickers:
            broader_tickers = "—"

        history_cards += f"""
        <div class="history-card {signal_class}">
            <div class="history-date">{entry['date']}</div>
            <div class="history-meta">{entry['scan_time']}</div>
            <div class="history-counts">
                <span class="count-pill approved-pill">{len(entry['approved'])} approved</span>
                <span class="count-pill broader-pill">{len(entry['broader'])} broader</span>
            </div>
            <div class="history-tickers">
                <div class="ticker-group"><strong>Approved:</strong> {approved_tickers}</div>
                <div class="ticker-group"><strong>Broader:</strong> {broader_tickers}</div>
            </div>
        </div>"""

    if not history_cards:
        history_cards = '<p class="no-signals">No history yet — runs daily after market close.</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aristotle Dashboard</title>
    <style>
        :root {{
            --bg: #0a0e1a;
            --surface: #111827;
            --surface2: #1a2236;
            --border: #1e2d45;
            --accent: #00d4aa;
            --accent2: #3b82f6;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text: #e2e8f0;
            --text-muted: #64748b;
            --approved-bg: rgba(0, 212, 170, 0.07);
            --broader-bg: rgba(59, 130, 246, 0.07);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, 'SF Pro Text', 'Segoe UI', sans-serif;
            font-size: 14px;
            line-height: 1.5;
            padding-bottom: 40px;
        }}

        /* HEADER */
        .header {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 20px 16px 16px;
        }}

        .header-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }}

        .logo {{
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: var(--accent);
        }}

        .logo span {{
            color: var(--text-muted);
            font-weight: 400;
            font-size: 12px;
            margin-left: 6px;
        }}

        .scan-time {{
            font-size: 11px;
            color: var(--text-muted);
            text-align: right;
        }}

        .scan-time strong {{
            color: var(--accent);
            display: block;
            font-size: 12px;
        }}

        /* STAT PILLS */
        .stats-row {{
            display: flex;
            gap: 10px;
        }}

        .stat-pill {{
            flex: 1;
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px 12px;
            text-align: center;
        }}

        .stat-pill .val {{
            font-size: 22px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 2px;
        }}

        .stat-pill .lbl {{
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .stat-pill.total .val {{ color: var(--warning); }}
        .stat-pill.approved .val {{ color: var(--accent); }}
        .stat-pill.broader .val {{ color: var(--accent2); }}

        /* TABS */
        .tab-bar {{
            display: flex;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        .tab {{
            flex-shrink: 0;
            padding: 12px 18px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            cursor: pointer;
            border-bottom: 2px solid transparent;
            white-space: nowrap;
            transition: color 0.15s;
            background: none;
            border-top: none;
            border-left: none;
            border-right: none;
        }}

        .tab.active {{
            color: var(--accent);
            border-bottom-color: var(--accent);
        }}

        /* PANELS */
        .panel {{ display: none; padding: 16px; }}
        .panel.active {{ display: block; }}

        /* SECTION HEADERS */
        .section-label {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid var(--border);
        }}

        .section-label.green {{ color: var(--accent); border-color: rgba(0,212,170,0.2); }}
        .section-label.blue {{ color: var(--accent2); border-color: rgba(59,130,246,0.2); }}

        /* TABLES */
        .table-wrap {{
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            margin-bottom: 24px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        thead th {{
            background: var(--surface2);
            color: var(--text-muted);
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            padding: 9px 12px;
            text-align: left;
            white-space: nowrap;
        }}

        tbody tr {{
            border-top: 1px solid var(--border);
        }}

        tbody tr:hover {{
            background: rgba(255,255,255,0.02);
        }}

        .approved-table tbody tr {{ background: var(--approved-bg); }}
        .broader-table tbody tr {{ background: var(--broader-bg); }}

        td {{
            padding: 10px 12px;
            white-space: nowrap;
        }}

        .rank {{ color: var(--text-muted); font-size: 11px; }}
        .ticker {{ font-weight: 700; font-size: 14px; color: var(--text); }}
        .drop {{ font-weight: 700; color: var(--danger); }}

        .sector-badge {{
            background: rgba(0,212,170,0.1);
            color: var(--accent);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 600;
        }}

        .no-signals {{
            color: var(--text-muted);
            font-style: italic;
            padding: 16px;
            text-align: center;
        }}

        /* HISTORY */
        .history-grid {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .history-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px;
        }}

        .history-card.has-signals {{
            border-color: rgba(0,212,170,0.25);
        }}

        .history-card.no-signal-day {{
            opacity: 0.5;
        }}

        .history-date {{
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 2px;
        }}

        .history-meta {{
            font-size: 11px;
            color: var(--text-muted);
            margin-bottom: 8px;
        }}

        .history-counts {{
            display: flex;
            gap: 6px;
            margin-bottom: 8px;
        }}

        .count-pill {{
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 20px;
        }}

        .approved-pill {{
            background: rgba(0,212,170,0.15);
            color: var(--accent);
        }}

        .broader-pill {{
            background: rgba(59,130,246,0.15);
            color: var(--accent2);
        }}

        .history-tickers {{
            font-size: 12px;
            color: var(--text-muted);
            line-height: 1.6;
        }}

        .ticker-group strong {{
            color: var(--text);
        }}
    </style>
</head>
<body>

    <div class="header">
        <div class="header-top">
            <div class="logo">ARISTOTLE <span>v2</span></div>
            <div class="scan-time">
                <strong>{today_date}</strong>
                Last scan: {today_time}
            </div>
        </div>
        <div class="stats-row">
            <div class="stat-pill total">
                <div class="val">{total_today}</div>
                <div class="lbl">Total</div>
            </div>
            <div class="stat-pill approved">
                <div class="val">{len(today_approved)}</div>
                <div class="lbl">Approved</div>
            </div>
            <div class="stat-pill broader">
                <div class="val">{len(today_broader)}</div>
                <div class="lbl">Broader</div>
            </div>
        </div>
    </div>

    <div class="tab-bar">
        <button class="tab active" onclick="showTab('today')">Today</button>
        <button class="tab" onclick="showTab('history')">30-Day History</button>
    </div>

    <!-- TODAY PANEL -->
    <div id="panel-today" class="panel active">

        <p class="section-label green">✅ Approved Stocks — {len(today_approved)} signal(s)</p>
        <div class="table-wrap">
            <table class="approved-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Ticker</th>
                        <th>Sector</th>
                        <th>Price</th>
                        <th>20D High</th>
                        <th>Drop</th>
                        <th>Vol Ratio</th>
                    </tr>
                </thead>
                <tbody>{approved_rows}</tbody>
            </table>
        </div>

        <p class="section-label blue">🌍 Broader Market — {len(today_broader)} signal(s)</p>
        <div class="table-wrap">
            <table class="broader-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Ticker</th>
                        <th>Price</th>
                        <th>20D High</th>
                        <th>Drop</th>
                        <th>Vol Ratio</th>
                    </tr>
                </thead>
                <tbody>{broader_rows}</tbody>
            </table>
        </div>

    </div>

    <!-- HISTORY PANEL -->
    <div id="panel-history" class="panel">
        <p class="section-label">📅 Last 30 Days</p>
        <div class="history-grid">
            {history_cards}
        </div>
    </div>

    <script>
        function showTab(name) {{
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById('panel-' + name).classList.add('active');
            event.target.classList.add('active');
        }}
    </script>

</body>
</html>"""

    return html


# ==================== EMAIL ====================

def format_alert_email(approved_signals, broader_signals):
    total_signals = len(approved_signals) + len(broader_signals)
    html = f"""
    <html><head><style>
        body {{ font-family: Arial, sans-serif; }}
        h1 {{ color: #2E7D32; }}
        h2 {{ color: #1565C0; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 15px; margin-bottom: 30px; }}
        th {{ background-color: #1565C0; color: white; padding: 12px; text-align: left; }}
        td {{ border: 1px solid #ddd; padding: 12px; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .approved {{ background-color: #E8F5E9; }}
        .summary {{ background-color: #E3F2FD; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        .no-signals {{ color: #666; font-style: italic; }}
    </style></head><body>
    <h1>🎯 ARISTOTLE DAILY SCAN</h1>
    <p><strong>{datetime.now().strftime('%A, %B %d, %Y')}</strong></p>
    <div class="summary">
        <h3>📊 Today's Summary</h3>
        <ul>
            <li><strong>Approved Stocks:</strong> {len(approved_signals)} signal(s)</li>
            <li><strong>Broader Market:</strong> {len(broader_signals)} signal(s)</li>
            <li><strong>Total:</strong> {total_signals}</li>
        </ul>
    </div>
    <h2>✅ APPROVED STOCKS</h2>"""

    if approved_signals:
        html += "<table><tr><th>#</th><th>Ticker</th><th>Sector</th><th>Price</th><th>20D High</th><th>Drop %</th><th>Vol Ratio</th></tr>"
        for i, s in enumerate(approved_signals, 1):
            fire = "🔥" if s['volume_ratio'] > 1.5 else ""
            html += f"<tr class='approved'><td>#{i}</td><td><strong>{s['ticker']}</strong></td><td>{get_sector(s['ticker'])}</td><td>${s['current_price']:.2f}</td><td>${s['high_20d']:.2f}</td><td><strong>{s['drop_pct']:.1f}%</strong></td><td>{fire} {s['volume_ratio']:.2f}x</td></tr>"
        html += "</table>"
    else:
        html += '<p class="no-signals">No signals from approved stocks today.</p>'

    html += "<h2>🌍 BROADER MARKET</h2>"
    if broader_signals:
        display = broader_signals[:20]
        html += "<table><tr><th>#</th><th>Ticker</th><th>Price</th><th>20D High</th><th>Drop %</th><th>Vol Ratio</th></tr>"
        for i, s in enumerate(display, 1):
            fire = "🔥" if s['volume_ratio'] > 1.5 else ""
            html += f"<tr><td>#{i}</td><td><strong>{s['ticker']}</strong></td><td>${s['current_price']:.2f}</td><td>${s['high_20d']:.2f}</td><td>{s['drop_pct']:.1f}%</td><td>{fire} {s['volume_ratio']:.2f}x</td></tr>"
        html += "</table>"
    else:
        html += '<p class="no-signals">No signals from broader market today.</p>'

    html += f"""<div class="footer">
        <p>Generated by Aristotle Scanner v2 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><a href="https://josephnunes.github.io/aristotle-dashboard">View full dashboard →</a></p>
    </div></body></html>"""
    return html


def send_email_alert(subject, html_content):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_USERNAME
        msg['To'] = ALERT_EMAIL
        msg.attach(MIMEText(html_content, 'html'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"✗ Email failed: {str(e)}")
        return False


# ==================== MAIN ====================

def main():
    print("\n" + "="*70)
    print("ARISTOTLE V2 - DAILY MARKET SCANNER")
    print("="*70)
    print(f"\nDate: {datetime.now().strftime('%A, %B %d, %Y %H:%M')}")
    print(f"  • {len(APPROVED_LIST)} approved stocks")
    print(f"  • {len(BROADER_MARKET)} broader market stocks\n")

    # Scan approved
    print("SCANNING APPROVED STOCKS\n")
    approved_data = download_stock_data(APPROVED_LIST)
    approved_signals = scan_for_buy_signals(approved_data, max_price=MAX_PRICE)
    print(f"✓ Found {len(approved_signals)} signals from approved stocks\n")

    # Scan broader
    print("SCANNING BROADER MARKET\n")
    broader_data = download_stock_data(BROADER_MARKET)
    broader_signals = scan_for_buy_signals(broader_data, max_price=MAX_PRICE_BROAD)
    print(f"✓ Found {len(broader_signals)} signals from broader market\n")

    # Append to history and generate dashboard
    print("GENERATING DASHBOARD\n")
    history = append_to_history(approved_signals, broader_signals)
    dashboard_html = generate_dashboard(history)
    with open("dashboard.html", "w") as f:
        f.write(dashboard_html)
    print("✓ dashboard.html written\n")

    # Send email
    if SMTP_PASSWORD:
        html_email = format_alert_email(approved_signals, broader_signals)
        total = len(approved_signals) + len(broader_signals)
        subject = f"🎯 ARISTOTLE: {len(approved_signals)} Approved + {len(broader_signals)} Market Signals" if total > 0 else "📊 ARISTOTLE: Daily Scan Complete (No Signals Today)"
        if send_email_alert(subject, html_email):
            print(f"✓ Email sent to {ALERT_EMAIL}")
        else:
            print("✗ Email failed")
    else:
        print("⚠️  No SMTP_PASSWORD set — skipping email")

    print("\n" + "="*70)
    print("SCAN COMPLETE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
