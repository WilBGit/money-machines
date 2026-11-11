#!/usr/bin/env python3
"""
Daily Content Generator — Tweets, Discord Posts, Social Content
================================================================
Generates daily trading content for Twitter/X and Discord from live market data.
Designed to be run by cron every weekday morning.

Usage:
  python3 daily_content.py
  python3 daily_content.py --platform twitter
  python3 daily_content.py --platform discord
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

# Load .env
DOTENV = PROJECT_DIR / ".env"
if DOTENV.exists():
    for line in DOTENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() and value.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()

# Import LLM client
sys.path.insert(0, str(PROJECT_DIR / "shared" / "scripts"))
from llm_client import call_llm, load_env
load_env()

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
TODAY = datetime.datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
TODAY_FMT = datetime.datetime.now(ZoneInfo("US/Eastern")).strftime("%B %d, %Y")
OUTPUT_DIR = PROJECT_DIR / "06-content-repurposing" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_TICKERS = ["SPY", "QQQ", "NVDA", "ORCL"]


def fetch_yahoo(ticker: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d&includePrePost=true"
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except:
        return {}
    result = data.get("chart", {}).get("result", [{}])[0]
    meta = result.get("meta", {})
    quotes = result.get("indicators", {}).get("quote", [{}])[0]
    closes = [c for c in quotes.get("close", []) if c is not None]
    highs = [h for h in quotes.get("high", []) if h is not None]
    lows = [l for l in quotes.get("low", []) if l is not None]
    volumes = [v for v in quotes.get("volume", []) if v is not None]
    current = meta.get("regularMarketPrice", 0)
    prev = meta.get("chartPreviousClose", meta.get("previousClose", 0))
    change = current - prev if prev and current else 0
    change_pct = (change / prev * 100) if prev else 0
    rsi = 50
    if len(closes) >= 2:
        gains = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        avg_gain = sum(g for g in gains if g > 0) / len(gains) if gains else 0
        avg_loss = sum(abs(g) for g in gains if g < 0) / len(gains) if gains else 0.01
        rs = avg_gain / avg_loss if avg_loss else 100
        rsi = 100 - (100 / (1 + rs))
    return {
        "ticker": ticker, "price": round(current, 2) if current else None,
        "change": round(change, 2), "change_pct": round(change_pct, 2),
        "5d_high": round(max(highs), 2) if highs else None,
        "5d_low": round(min(lows), 2) if lows else None,
        "rsi": round(rsi, 1), "volume": volumes[-1] if volumes else 0,
        "avg_volume": int(sum(volumes)/len(volumes)) if volumes else 0,
    }


def generate_tweets(tickers: list) -> str:
    quotes = {t: fetch_yahoo(t) for t in tickers}
    data_lines = []
    for t in tickers:
        q = quotes.get(t, {})
        if q.get("price"):
            data_lines.append(f"{t}: ${q['price']:,.2f} ({'+' if q['change_pct']>=0 else ''}{q['change_pct']:.2f}%), RSI {q['rsi']}, Support ${q.get('5d_low','?')}, Resistance ${q.get('5d_high','?')}")

    data_str = "\n".join(data_lines)

    prompt = f"""You are @JarvisMarketDesk — a sharp, concise trading voice on Twitter/X.

Create 5 tweets based on today's market data. Rules:
- Each tweet under 280 characters
- Include specific ticker and price/level
- Mix: 2 analysis tweets, 2 actionable setup tweets, 1 hot take
- Sound human, confident, not salesy
- Use $TICKER format (not hashtags)
- Number each tweet

Today's data:
{data_str}"""

    result = call_llm(prompt, system="You are a professional stock market Twitter/X content creator.", temperature=0.85, max_tokens=4000)
    return result if result else "[LLM returned empty]"


def generate_discord_post(tickers: list) -> str:
    quotes = {t: fetch_yahoo(t) for t in tickers}
    spy = quotes.get("SPY", {})
    bias = "bullish" if spy.get("change_pct", 0) > 0.3 else "bearish" if spy.get("change_pct", 0) < -0.5 else "neutral"

    lines = [f"🤖 **Daily Market Analysis — {TODAY_FMT}**", ""]
    lines.append(f"**Market Bias: {bias.title()}** | SPY ${spy.get('price', '?')} ({'+' if spy.get('change_pct',0)>=0 else ''}{spy.get('change_pct',0):.2f}%)")
    lines.append("")
    lines.append("**Key Levels:**")

    for t in tickers:
        q = quotes.get(t, {})
        if q.get("price"):
            rsi = q.get("rsi", 50)
            rsi_emoji = "🟢" if rsi < 30 else "🔴" if rsi > 70 else "⚪"
            lines.append(f"  {rsi_emoji} **{t}** ${q['price']:,.2f} ({'+' if q['change_pct']>=0 else ''}{q['change_pct']:.2f}%) | RSI {rsi} | S:${q.get('5d_low','?')} R:${q.get('5d_high','?')}")

    lines.append("")
    # Gumroad link removed 2026-10-22 — strategy killed
    lines.append("")
    lines.append("⚠️ Not financial advice. Trade your own risk.")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Content Generator")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    parser.add_argument("--platform", choices=["twitter", "discord", "all"], default="all")
    args = parser.parse_args()

    if args.platform in ("twitter", "all"):
        print("[CONTENT] Generating tweets...")
        tweets = generate_tweets(args.tickers)
        tweet_path = OUTPUT_DIR / f"tweets-{TODAY}.md"
        tweet_path.write_text(tweets)
        print(f"[SAVED] {tweet_path}")
        print(tweets)

    if args.platform in ("discord", "all"):
        print("\n[CONTENT] Generating Discord post...")
        discord_post = generate_discord_post(args.tickers)
        discord_path = OUTPUT_DIR / f"discord-{TODAY}.md"
        discord_path.write_text(discord_post)
        print(f"[SAVED] {discord_path}")
        print(discord_post)
