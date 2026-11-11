#!/usr/bin/env python3
"""
Daily Stock Analysis Generator
================================
Generates a full stock analysis report from live data.
Used by: Gumroad reports, Substack newsletter, YouTube scripts

Usage:
  python daily_analysis.py NVDA
  python daily_analysis.py NVDA ORCL SPY
  python daily_analysis.py NVDA --format pdf    # Generate PDF
  python daily_analysis.py NVDA --format substack  # Substack post format
"""

import os
import urllib.request
import json
import datetime
import re
import math
import statistics
import sys
import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "shared" / "analysis_output"
DATA_DIR.mkdir(parents=True, exist_ok=True)

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}


def fetch_yahoo(sym: str) -> dict:
    """Fetch 2y daily chart data from Yahoo Finance."""
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=2y&interval=1d&includePrePost=false&events=div%2Csplits'
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
        chart = data['chart']['result'][0]
        meta = chart['meta']
        q = chart['indicators']['quote'][0]
        ts = chart['timestamp']

        rows = []
        for i, t in enumerate(ts):
            c = q['close'][i]
            if c is None: continue
            rows.append({
                'date': datetime.datetime.fromtimestamp(t, ZoneInfo('America/New_York')).date().isoformat(),
                'o': q['open'][i], 'h': q['high'][i], 'l': q['low'][i], 'c': c, 'v': q['volume'][i]
            })

        cl = [r['c'] for r in rows]
        def sma(n): return sum(cl[-n:])/n if len(cl) >= n else None

        # RSI
        gains, losses = [], []
        for a, b in zip(cl[-15:-1], cl[-14:]):
            d = b - a
            gains.append(max(d, 0))
            losses.append(max(-d, 0))
        avg_gain = sum(gains)/14
        avg_loss = sum(losses)/14 or 1e-9
        rsi = 100 - 100/(1 + avg_gain/avg_loss)

        # ATR
        trs = []
        for i in range(max(1, len(rows)-14), len(rows)):
            trs.append(max(rows[i]['h']-rows[i]['l'], abs(rows[i]['h']-rows[i-1]['c']), abs(rows[i]['l']-rows[i-1]['c'])))
        atr = sum(trs)/len(trs) if trs else 0

        close = meta.get('regularMarketPrice') or rows[-1]['c']
        prev = meta.get('chartPreviousClose') or rows[-2]['c']
        vol20 = sum((r['v'] or 0) for r in rows[-20:])/20

        # Swing levels
        subset = rows[-190:]
        piv_hi, piv_lo = [], []
        for i in range(3, len(subset)-3):
            if subset[i]['h'] >= max(r['h'] for r in subset[i-3:i+4]): piv_hi.append(subset[i])
            if subset[i]['l'] <= min(r['l'] for r in subset[i-3:i+4]): piv_lo.append(subset[i])

        supports = sorted([r for r in piv_lo if r['l'] <= close*1.01], key=lambda r: abs(r['l']-close))[:8]
        resistances = sorted([r for r in piv_hi if r['h'] >= close*0.99], key=lambda r: abs(r['h']-close))[:8]

        return {
            'symbol': sym,
            'close': close,
            'prev_close': prev,
            'change': close - prev,
            'change_pct': (close/prev - 1)*100 if prev else 0,
            'high_52w': meta.get('fiftyTwoWeekHigh'),
            'low_52w': meta.get('fiftyTwoWeekLow'),
            'day_high': meta.get('regularMarketDayHigh'),
            'day_low': meta.get('regularMarketDayLow'),
            'volume': meta.get('regularMarketVolume'),
            'vol20': vol20,
            'sma20': sma(20), 'sma50': sma(50), 'sma200': sma(200),
            'rsi': rsi, 'atr': atr,
            'supports': [{'date': s['date'], 'low': s['l']} for s in supports],
            'resistances': [{'date': r['date'], 'high': r['h']} for r in resistances],
            'latest': rows[-1],
            'name': meta.get('longName', sym),
        }
    except Exception as e:
        return {'symbol': sym, 'error': str(e)}


def fetch_finviz(sym: str) -> dict:
    """Fetch key metrics from Finviz."""
    try:
        url = f'https://finviz.com/quote.ashx?t={sym}&p=d'
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8', 'replace')

        plain = re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', html))
        vals = {}
        keys = ['P/E', 'Forward P/E', 'PEG', 'EPS next Y', 'Sales Q/Q', 'EPS Q/Q',
                'Recom', 'Target Price', 'Insider Trans', 'Inst Trans', 'Short Float',
                'Perf Week', 'Perf Month', 'RSI (14)', 'ATR (14)', 'Beta']
        for key in keys:
            ix = plain.find(key)
            if ix >= 0:
                vals[key] = plain[ix:ix+60]
        return vals
    except:
        return {}


def fetch_cboe(sym: str) -> dict:
    """Fetch CBOE options data."""
    try:
        url = f'https://cdn.cboe.com/api/global/delayed_quotes/quotes/{sym}.json'
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())['data']
        return {
            'spot': data.get('current_price') or data.get('close'),
            'iv30': data.get('iv30'),
            'bid': data.get('bid'),
            'ask': data.get('ask'),
        }
    except:
        return {}


def generate_report(sym: str, fmt: str = "markdown") -> str:
    """Generate full analysis report."""
    yahoo = fetch_yahoo(sym)
    if 'error' in yahoo:
        return f"Error fetching {sym}: {yahoo['error']}"

    finviz = fetch_finviz(sym)
    cboe = fetch_cboe(sym)

    now = datetime.datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%B %d, %Y')

    close = yahoo['close']
    change_pct = yahoo['change_pct']
    emoji = "🟢" if change_pct > 0 else "🔴"

    rsi = yahoo.get('rsi', 0)
    rsi_read = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"

    supports_str = "\n".join([f"| ${s['low']:.2f} | {s['date']} |" for s in yahoo.get('supports', [])[:5]])
    resistances_str = "\n".join([f"| ${r['high']:.2f} | {r['date']} |" for s in yahoo.get('resistances', [])[:5]])
    if not resistances_str:
        resistances_str = "\n".join([f"| ${r['high']:.2f} | {r['date']} |" for r in yahoo.get('resistances', [])[:5]])

    report = f"""# {sym} Analysis — {now}

## Summary

{emoji} **{sym}** ({yahoo.get('name', sym)}) is at **${close:.2f}** ({'+' if change_pct > 0 else ''}{change_pct:.2f}%)

| Metric | Value |
|---|---|
| Price | ${close:.2f} |
| Change | {'+' if yahoo['change'] > 0 else ''}${yahoo['change']:.2f} ({'+' if change_pct > 0 else ''}{change_pct:.2f}%) |
| 52-week high | ${yahoo.get('high_52w', 'N/A')} |
| 52-week low | ${yahoo.get('low_52w', 'N/A')} |
| Day range | ${yahoo.get('day_low', 'N/A')} – ${yahoo.get('day_high', 'N/A')} |
| RSI (14) | {rsi:.1f} ({rsi_read}) |
| ATR (14) | ${yahoo.get('atr', 0):.2f} |
| SMA 20 | ${yahoo.get('sma20', 0):.2f} |
| SMA 50 | ${yahoo.get('sma50', 0):.2f} |
| SMA 200 | ${yahoo.get('sma200', 0):.2f} |
| IV30 | {cboe.get('iv30', 'N/A')} |

## Support Levels

| Price | Date |
|---|---|
{supports_str}

## Resistance Levels

| Price | Date |
|---|---|
{resistances_str}

## Trade Plan

- **Entry zone:** Near current support
- **Stop:** Below nearest support
- **First target:** First resistance
- **Confirmation:** Add on reclaim above key moving averages

---
*Generated by Jarvis Market Desk — {now}*
*Not financial advice. Trade your own risk.*
"""

    return report


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Stock Analysis Generator")
    parser.add_argument("tickers", nargs="+", help="Stock tickers (e.g., NVDA ORCL SPY)")
    parser.add_argument("--format", choices=["markdown", "pdf", "substack"], default="markdown")

    args = parser.parse_args()

    for ticker in args.tickers:
        print(f"\n[ANALYZE] {ticker.upper()}...")
        report = generate_report(ticker.upper(), fmt=args.format)

        # Save
        timestamp = datetime.datetime.now().strftime('%Y%m%d')
        filepath = DATA_DIR / f"{ticker.upper()}_{timestamp}.md"
        filepath.write_text(report)
        print(f"[SAVED] {filepath}")
        print(report)
