#!/usr/bin/env python3
"""
Substack Newsletter Generator
================================
Converts daily market analysis into Substack-ready posts.
Auto-generates from the Gumroad daily report data.

Usage:
  python3 substack_newsletter.py
  python3 substack_newsletter.py --tickers SPY QQQ NVDA ORCL
"""

import os
import sys
import json
import datetime
import urllib.request
import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent.parent
OUTPUT_DIR = PROJECT_DIR / "02-substack-newsletter" / "posts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load .env
DOTENV = PROJECT_DIR / ".env"
if DOTENV.exists():
    for line in DOTENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() and value.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
TODAY = datetime.datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
TODAY_FMT = datetime.datetime.now(ZoneInfo("US/Eastern")).strftime("%B %d, %Y")

DEFAULT_TICKERS = ["SPY", "QQQ", "NVDA", "ORCL", "AAPL", "TSLA", "META", "AMZN"]

# ── Data Fetching (same as Gumroad report) ──────────────────────────────────

def fetch_yahoo(ticker: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d&includePrePost=true"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[WARN] Yahoo fetch failed for {ticker}: {e}")
        return {}

    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    quotes = result.get("indicators", {}).get("quote", [{}])[0]
    closes = [c for c in quotes.get("close", []) if c is not None]
    volumes = [v for v in quotes.get("volume", []) if v is not None]
    highs = [h for h in quotes.get("high", []) if h is not None]
    lows = [l for l in quotes.get("low", []) if l is not None]

    current = meta.get("regularMarketPrice", 0)
    prev_close = meta.get("chartPreviousClose", meta.get("previousClose", 0))
    change = current - prev_close if prev_close and current else 0
    change_pct = (change / prev_close * 100) if prev_close else 0

    rsi = 50
    if len(closes) >= 2:
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(diff if diff > 0 else 0)
            losses.append(abs(diff) if diff < 0 else 0)
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0.01
        rs = avg_gain / avg_loss if avg_loss else 100
        rsi = 100 - (100 / (1 + rs))

    return {
        "ticker": ticker,
        "name": meta.get("shortName", ticker),
        "price": round(current, 2) if current else None,
        "prev_close": round(prev_close, 2) if prev_close else None,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "day_high": round(max(highs), 2) if highs else None,
        "day_low": round(min(lows), 2) if lows else None,
        "5d_high": round(max(highs), 2) if highs else None,
        "5d_low": round(min(lows), 2) if lows else None,
        "volume": volumes[-1] if volumes else 0,
        "avg_volume": int(sum(volumes) / len(volumes)) if volumes else 0,
        "rsi": round(rsi, 1),
    }

def fetch_yahoo_key_stats(ticker: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=defaultKeyStatistics,financialData"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except:
        return {}
    summary = data.get("quoteSummary", {}).get("result", [{}])[0]
    stats = summary.get("defaultKeyStatistics", {})
    financial = summary.get("financialData", {})

    def safe_get(d, *keys, default=None):
        current = d
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, {})
            else:
                return default
        return current if current != {} else default

    return {
        "pe_ratio": safe_get(financial, "currentPrice", "raw"),
        "forward_pe": safe_get(stats, "forwardPE", "raw"),
        "peg_ratio": safe_get(stats, "pegRatio", "raw"),
        "revenue_growth": safe_get(financial, "revenueGrowth", "raw"),
        "eps_growth": safe_get(financial, "earningsGrowth", "raw"),
        "profit_margin": safe_get(financial, "profitMargins", "raw"),
        "target_mean": safe_get(financial, "targetMeanPrice", "raw"),
        "recommendation": safe_get(financial, "recommendationKey", "raw"),
    }

# ── Substack Post Generation ────────────────────────────────────────────────

def generate_substack_post(tickers: list) -> str:
    """Generate a Substack-ready newsletter post."""
    print(f"[NEWSLETTER] Fetching data for {len(tickers)} tickers...")
    quotes = {}
    fundamentals = {}
    for ticker in tickers:
        print(f"  Fetching {ticker}...")
        quotes[ticker] = fetch_yahoo(ticker)
        fundamentals[ticker] = fetch_yahoo_key_stats(ticker)

    # Determine market mood
    spy = quotes.get("SPY", {})
    qqq = quotes.get("QQQ", {})
    market_bias = "bullish" if spy.get("change_pct", 0) > 0.3 else "bearish" if spy.get("change_pct", 0) < -0.5 else "neutral"

    # Find top movers
    sorted_tickers = sorted(tickers, key=lambda t: abs(quotes.get(t, {}).get("change_pct", 0)), reverse=True)
    top_mover = sorted_tickers[0] if sorted_tickers else "SPY"
    top_mover_data = quotes.get(top_mover, {})

    # Find oversold (buy opportunity) and overbought (risk)
    oversold = [t for t in tickers if quotes.get(t, {}).get("rsi", 50) < 35]
    overbought = [t for t in tickers if quotes.get(t, {}).get("rsi", 50) > 70]

    # Build post
    post = f"""# Market Levels — {TODAY_FMT}

"""

    # Market pulse
    spy_price = spy.get("price", "?")
    spy_chg = spy.get("change_pct", 0)
    qqq_price = qqq.get("price", "?")
    qqq_chg = qqq.get("change_pct", 0)

    mood_emoji = "🟢" if market_bias == "bullish" else "🔴" if market_bias == "bearish" else "⚪"

    post += f"""{mood_emoji} **Market bias: {market_bias.title()}** | SPY ${spy_price} ({'+' if spy_chg >= 0 else ''}{spy_chg:.2f}%) | QQQ ${qqq_price} ({'+' if qqq_chg >= 0 else ''}{qqq_chg:.2f}%)

---

"""

    # Top mover spotlight
    if top_mover_data and top_mover_data.get("price"):
        tm = top_mover_data
        post += f"""## 🔥 Today's Focus: {top_mover}

${tm['price']:,.2f} ({'+' if tm.get('change_pct',0) >= 0 else ''}{tm.get('change_pct',0):.2f}%)

- **5-day range:** ${tm.get('5d_low', '?')} – ${tm.get('5d_high', '?')}
- **RSI:** {tm.get('rsi', '?')}
- **Volume:** {tm.get('volume', 0):,.0f} {'(above average)' if tm.get('volume', 0) > tm.get('avg_volume', 0) * 1.2 else '(normal)'}

"""

    # Levels table
    post += """## 🎯 Key Levels

| Ticker | Price | Change | Support | Resistance | RSI | Bias |
|--------|-------|--------|---------|------------|-----|------|
"""
    for ticker in tickers:
        q = quotes.get(ticker, {})
        if not q or not q.get("price"):
            continue
        rsi = q.get("rsi", 50)
        if rsi < 30:
            bias = "🟢 Oversold"
        elif rsi < 45:
            bias = "🟡 Near support"
        elif rsi > 70:
            bias = "🔴 Overbought"
        elif rsi > 55:
            bias = "🟡 Bullish"
        else:
            bias = "⚪ Neutral"

        post += f"| {ticker} | ${q['price']:,.2f} | {'+' if q.get('change_pct',0) >= 0 else ''}{q.get('change_pct',0):.2f}% | ${q.get('5d_low', '?'):,} | ${q.get('5d_high', '?'):,} | {rsi} | {bias} |\n"

    # Fundamentals
    post += "\n---\n\n## 📊 Fundamentals\n\n"
    post += "| Ticker | Fwd P/E | PEG | Rev Growth | Target | Consensus |\n"
    post += "|--------|---------|-----|------------|--------|----------|\n"
    for ticker in tickers:
        f = fundamentals.get(ticker, {})
        if not f:
            continue
        def fmt(v, pct=False):
            if v is None: return "N/A"
            if pct: return f"{v*100:.1f}%"
            return f"{v:.2f}" if abs(v) < 1000 else f"{v:,.0f}"
        post += f"| {ticker} | {fmt(f.get('forward_pe'))} | {fmt(f.get('peg_ratio'))} | {fmt(f.get('revenue_growth'), True)} | ${fmt(f.get('target_mean')) if f.get('target_mean') else 'N/A'} | {(f.get('recommendation') or 'N/A').title()} |\n"

    # Risk flags
    post += "\n---\n\n## 🚨 Risk Flags\n\n"
    flags = []
    if abs(spy.get("change_pct", 0)) > 1.5:
        flags.append(f"⚠️ **SPY moved {spy.get('change_pct', 0):+.2f}%** — elevated volatility")
    if oversold:
        flags.append(f"🟢 **Oversold:** {', '.join(oversold)} — potential bounce setups")
    if overbought:
        flags.append(f"🔴 **Overbought:** {', '.join(overbought)} — pullback risk")
    for ticker in tickers:
        q = quotes.get(ticker, {})
        if q.get("volume", 0) and q.get("avg_volume", 1) and q["volume"] > q["avg_volume"] * 1.5:
            flags.append(f"📊 **{ticker} volume {q['volume']/q['avg_volume']:.1f}x average**")
    if not flags:
        flags.append("✅ Normal market conditions — no major flags")
    post += "\n".join(flags)

    # Trade plan
    post += f"""

---

## 📋 Today's Trade Plan

**Bias:** {market_bias.title()} | **Action:** {"Look for longs on support tests" if market_bias == "bullish" else "Reduce risk, tighten stops" if market_bias == "bearish" else "Be selective, wait for setups"}

1. Watch SPY ${spy.get('5d_low', '?')} — {"uptrend intact above this" if spy.get('change_pct', 0) >= 0 else "breakdown risk if loses"}
2. Monitor volume on top movers for confirmation
3. {"Oversold bounces: " + ", ".join(oversold) if oversold else "No oversold setups today"}
4. LEAP entries only on green days or strong support tests

---

*🤖 Jarvis Market Desk • {TODAY_FMT} • [Subscribe free](https://jarvismarketdesk.substack.com)*

*⚠️ Not financial advice. All trades involve risk.*

---

**Like this? [Subscribe for free](https://jarvismarketdesk.substack.com) — daily levels delivered every morning.**
"""
    return post

def save_post(post: str) -> str:
    filename = f"substack-{TODAY}.md"
    filepath = OUTPUT_DIR / filename
    filepath.write_text(post)
    print(f"[SAVED] {filepath}")
    return str(filepath)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Substack Newsletter Generator")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    args = parser.parse_args()

    post = generate_substack_post(args.tickers)
    filepath = save_post(post)
    print(f"\n✅ Newsletter ready: {filepath}")
    print(f"   Copy to Substack or schedule via API")
