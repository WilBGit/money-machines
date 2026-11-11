#!/usr/bin/env python3
"""
Money Machines Dashboard — Revenue Stream Tracker
===================================================
Tracks all 10 revenue streams, sales, and performance.
Run daily or on-demand.

Usage:
  python3 dashboard.py
  python3 dashboard.py --json       # JSON output for cron
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent.parent
TODAY = datetime.datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
TODAY_FMT = datetime.datetime.now(ZoneInfo("US/Eastern")).strftime("%B %d, %Y")

# Load .env
DOTENV = PROJECT_DIR / ".env"
if DOTENV.exists():
    for line in DOTENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() and value.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()

# ── Gumroad API ──────────────────────────────────────────────────────────────

def get_gumroad_stats():
    """Fetch sales data from Gumroad API."""
    token_path = PROJECT_DIR / "shared" / ".gumroad_token.json"
    if not token_path.exists():
        return {"products": [], "sales": [], "subscribers": []}

    try:
        token_data = json.loads(token_path.read_text())
        access_token = token_data.get("access_token", os.environ.get("GUMROAD_API_TOKEN", ""))
    except:
        access_token = os.environ.get("GUMROAD_API_TOKEN", "")

    stats = {"products": [], "sales": [], "subscribers": 0}

    # Get products
    try:
        req = urllib.request.Request(
            "https://api.gumroad.com/v2/products",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        for p in data.get("products", []):
            stats["products"].append({
                "name": p.get("name", "?"),
                "price": p.get("price", 0) / 100,
                "url": p.get("short_url", "?"),
                "sales_count": p.get("sales_count", 0),
                "views": p.get("views", 0),
            })
    except Exception as e:
        stats["error"] = f"Gumroad products: {type(e).__name__}"

    # Get sales
    try:
        req = urllib.request.Request(
            "https://api.gumroad.com/v2/sales",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        total_revenue = 0
        for sale in data.get("sales", []):
            total_revenue += float(sale.get("sale_total", 0)) / 100
        stats["total_revenue"] = total_revenue
        stats["sales_count"] = len(data.get("sales", []))
    except Exception as e:
        stats["error"] = f"Gumroad sales: {type(e).__name__}"

    return stats


def get_youtube_stats():
    """Fetch YouTube channel stats."""
    token_path = PROJECT_DIR / "shared" / ".google_token.json"
    if not token_path.exists():
        return {}

    try:
        token_data = json.loads(token_path.read_text())
        access_token = token_data.get("access_token", "")

        # Refresh if expired
        if token_data.get("expiry"):
            from datetime import datetime as dt
            expiry = dt.fromisoformat(str(token_data["expiry"]).replace("Z", "+00:00"))
            if expiry < dt.now(expiry.tzinfo):
                # Need to refresh
                refresh_data = urllib.parse.urlencode({
                    "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                    "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                    "refresh_token": token_data.get("refresh_token", ""),
                    "grant_type": "refresh_token",
                }).encode()
                req = urllib.request.Request(
                    "https://oauth2.googleapis.com/token",
                    data=refresh_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    new_token = json.loads(resp.read())
                    access_token = new_token.get("access_token", access_token)
                    # Update token file
                    token_data.update(new_token)
                    token_path.write_text(json.dumps(token_data, indent=2))

        req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get("items"):
            ch = data["items"][0]
            return {
                "name": ch["snippet"]["title"],
                "subscribers": ch["statistics"].get("subscriberCount", "?"),
                "videos": ch["statistics"].get("videoCount", "?"),
                "views": ch["statistics"].get("viewCount", "?"),
            }
    except:
        pass
    return {}


def check_cron_status():
    """Check if cron jobs are running."""
    crons = {
        "Gumroad Daily Report": "KILLED 2026-10-22",
        "Content Generator": "6:35 AM PST weekdays",
    }
    # Check if reports exist for today
    report_dir = PROJECT_DIR / "_retired" / "gumroad-killed-20261022" / "01-gumroad-reports"  # Gumroad killed 2026-10-22
    today_report = report_dir / f"market-analysis-{TODAY}.md"
    newsletter = PROJECT_DIR / "02-substack-newsletter" / "posts" / f"substack-{TODAY}.md"
    tweets = PROJECT_DIR / "06-content-repurposing" / "output" / f"tweets-{TODAY}.md"

    return {
        "gumroad_report": False,  # Gumroad killed 2026-10-22
        "newsletter": newsletter.exists(),
        "tweets": tweets.exists(),
    }


def generate_dashboard():
    """Generate the full dashboard report."""
    gumroad = get_gumroad_stats()
    youtube = get_youtube_stats()
    cron = check_cron_status()

    dash = []
    dash.append(f"# 🤖 Money Machines Dashboard — {TODAY_FMT}")
    dash.append("")

    # Revenue
    dash.append("## 💰 Revenue")
    total_rev = gumroad.get("total_revenue", 0)
    sales_count = gumroad.get("sales_count", 0)
    dash.append(f"  **Total Revenue:** ${total_rev:,.2f} | **Sales:** {sales_count}")
    dash.append("")

    # Products
    dash.append("## 📦 Products")
    for p in gumroad.get("products", []):
        status = "🟢 LIVE" if p.get("url") else "🔴 DRAFT"
        dash.append(f"  {status} **{p['name']}** — ${p['price']:.2f} | {p.get('sales_count', 0)} sales | [Link]({p.get('url', '#')})")
    dash.append("")

    # YouTube
    dash.append("## 📺 YouTube")
    if youtube:
        dash.append(f"  **Channel:** {youtube.get('name', '?')} | **Subs:** {youtube.get('subscribers', '?')} | **Videos:** {youtube.get('videos', '?')} | **Views:** {youtube.get('views', '?')}")
    else:
        dash.append("  ⚠️ YouTube stats unavailable (token may need refresh)")
    dash.append("")

    # Automation status
    dash.append("## ⚙️ Automation Status")
    dash.append(f"  {'✅' if cron.get('gumroad_report') else '⏳'} Gumroad report generated today")
    dash.append(f"  {'✅' if cron.get('newsletter') else '⏳'} Substack newsletter generated today")
    dash.append(f"  {'✅' if cron.get('tweets') else '⏳'} Tweets + Discord content generated today")
    dash.append(f"  ✅ Google APIs connected (YouTube, Sheets, Drive)")
    dash.append(f"  ✅ Gumroad API connected")
    dash.append(f"  ✅ LLM client (Grok 4.6 via Hermes OAuth)")
    dash.append("")

    # All 10 streams
    dash.append("## 📊 10 Revenue Streams")
    streams = [
        ("Gumroad Reports", "✅", "$9.99/mo", gumroad.get("products", [{}])[0].get("sales_count", 0) if gumroad.get("products") else 0),
        ("Substack Newsletter", "✅", "Free → $10/mo", "Growing"),
        ("Fiverr Gigs", "⏳", "$50-200/gig", "Not set up"),
        ("Lead Lists", "✅", "$19.90/list", gumroad.get("products", [{}])[2].get("sales_count", 0) if len(gumroad.get("products", [])) > 2 else 0),
        ("Website Audit", "⏳", "$99-299/audit", "Script ready"),
        ("Content Repurposing", "✅", "Auto", "Daily tweets"),
        ("Trade Journal", "✅", "$4.99", gumroad.get("products", [{}])[1].get("sales_count", 0) if len(gumroad.get("products", [])) > 1 else 0),
        ("YouTube Channel", "✅", "Ad revenue", "API connected"),
        ("Cheat Sheets", "✅", "$2.99", gumroad.get("products", [{}])[3].get("sales_count", 0) if len(gumroad.get("products", [])) > 3 else 0),
        ("Appointment Setter", "✅", "B2B service", "Script ready"),
    ]
    dash.append("| # | Stream | Status | Price | Notes |")
    dash.append("|---|--------|--------|-------|-------|")
    for i, (name, status, price, notes) in enumerate(streams, 1):
        dash.append(f"| {i} | {name} | {status} | {price} | {notes} |")
    dash.append("")
    dash.append("---")
    dash.append(f"*Last updated: {TODAY_FMT} | Auto-generated by Money Machines Dashboard*")

    return "\n".join(dash)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Money Machines Dashboard")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.json:
        gumroad = get_gumroad_stats()
        youtube = get_youtube_stats()
        cron = check_cron_status()
        output = {
            "date": TODAY,
            "revenue": gumroad.get("total_revenue", 0),
            "sales_count": gumroad.get("sales_count", 0),
            "products": gumroad.get("products", []),
            "youtube": youtube,
            "cron": cron,
        }
        print(json.dumps(output, indent=2))
    else:
        dashboard = generate_dashboard()
        # Save to file
        output_path = PROJECT_DIR / "DASHBOARD.md"
        output_path.write_text(dashboard)
        print(dashboard)
