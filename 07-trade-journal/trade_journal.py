#!/usr/bin/env python3
"""
AI Trade Journal Analyzer
==========================
Upload your trade CSV → get a full behavioral + performance review.

Expected CSV columns: date, ticker, side, entry_price, exit_price, qty, pnl, notes
Or use any format and map columns interactively.

Usage:
  python trade_journal.py trades.csv
  python trade_journal.py trades.csv --full    # includes AI coaching tips

Revenue model: $49 one-time report, $99-299/mo ongoing, or $9-29/mo SaaS later
"""

import csv
import json
import argparse
import datetime
import statistics
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "07-trade-journal" / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Trade Processing ─────────────────────────────────────────────────────────
def load_trades(filepath: str) -> list:
    """Load trades from CSV."""
    trades = []
    with open(filepath, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize column names
            trade = {}
            for key, value in row.items():
                k = key.strip().lower().replace(" ", "_")
                trade[k] = value.strip() if value else ""

            # Parse numeric fields
            for field in ["entry_price", "exit_price", "qty", "pnl", "fees"]:
                if field in trade and trade[field]:
                    try:
                        trade[field] = float(trade[field].replace("$", "").replace(",", ""))
                    except ValueError:
                        trade[field] = 0

            # Calculate derived fields
            if "pnl" not in trade or not trade["pnl"]:
                if "entry_price" in trade and "exit_price" in trade and "qty" in trade:
                    side = trade.get("side", "long").lower()
                    if side == "short" or side == "sell":
                        trade["pnl"] = (trade["entry_price"] - trade["exit_price"]) * trade.get("qty", 1)
                    else:
                        trade["pnl"] = (trade["exit_price"] - trade["entry_price"]) * trade.get("qty", 1)
                else:
                    trade["pnl"] = 0

            trades.append(trade)

    return trades


def analyze_trades(trades: list) -> dict:
    """Generate comprehensive trade analysis."""
    if not trades:
        return {"error": "No trades found"}

    pnls = [t.get("pnl", 0) for t in trades if t.get("pnl") is not None]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    # Basic stats
    total_trades = len(trades)
    total_pnl = sum(pnls)
    win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0

    avg_win = statistics.mean(winners) if winners else 0
    avg_loss = statistics.mean(losers) if losers else 0
    max_win = max(winners) if winners else 0
    max_loss = min(losers) if losers else 0

    # Profit factor
    gross_profit = sum(winners) if winners else 0
    gross_loss = abs(sum(losers)) if losers else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Expectancy
    avg_pnl = statistics.mean(pnls) if pnls else 0

    # R-multiple analysis (if entry/exit available)
    r_multiples = []
    for t in trades:
        if t.get("entry_price") and t.get("exit_price") and t.get("pnl"):
            risk = abs(t.get("entry_price", 0) - t.get("exit_price", 0)) * t.get("qty", 1) * 0.02  # Assume 2% stop
            if risk > 0:
                r_multiples.append(t["pnl"] / risk)

    # By ticker
    by_ticker = defaultdict(list)
    for t in trades:
        ticker = t.get("ticker", t.get("symbol", "UNKNOWN"))
        by_ticker[ticker.upper()].append(t.get("pnl", 0))

    ticker_stats = {}
    for ticker, pnls_list in by_ticker.items():
        t_wins = [p for p in pnls_list if p > 0]
        t_losses = [p for p in pnls_list if p < 0]
        ticker_stats[ticker] = {
            "trades": len(pnls_list),
            "pnl": round(sum(pnls_list), 2),
            "win_rate": round(len(t_wins) / len(pnls_list) * 100, 1) if pnls_list else 0,
            "avg_trade": round(statistics.mean(pnls_list), 2) if pnls_list else 0,
        }

    # By day of week
    by_dow = defaultdict(list)
    for t in trades:
        date_str = t.get("date", t.get("entry_date", ""))
        if date_str:
            try:
                dt = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d")
                by_dow[dt.strftime("%A")].append(t.get("pnl", 0))
            except ValueError:
                pass

    dow_stats = {}
    for day, pnls_list in by_dow.items():
        dow_stats[day] = {
            "trades": len(pnls_list),
            "pnl": round(sum(pnls_list), 2),
            "avg_trade": round(statistics.mean(pnls_list), 2) if pnls_list else 0,
        }

    # By side (long/short)
    by_side = defaultdict(list)
    for t in trades:
        side = t.get("side", "long").lower()
        by_side[side].append(t.get("pnl", 0))

    side_stats = {}
    for side, pnls_list in by_side.items():
        s_wins = [p for p in pnls_list if p > 0]
        side_stats[side] = {
            "trades": len(pnls_list),
            "pnl": round(sum(pnls_list), 2),
            "win_rate": round(len(s_wins) / len(pnls_list) * 100, 1) if pnls_list else 0,
        }

    # Streak analysis
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    for p in pnls:
        if p > 0:
            if current_streak > 0:
                current_streak += 1
            else:
                current_streak = 1
            max_win_streak = max(max_win_streak, current_streak)
        elif p < 0:
            if current_streak < 0:
                current_streak -= 1
            else:
                current_streak = -1
            max_loss_streak = min(max_loss_streak, current_streak)
        else:
            current_streak = 0

    # Drawdown analysis
    peak = 0
    max_dd = 0
    running_pnl = 0
    for p in pnls:
        running_pnl += p
        peak = max(peak, running_pnl)
        dd = running_pnl - peak
        max_dd = min(max_dd, dd)

    return {
        "summary": {
            "total_trades": total_trades,
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "max_win": round(max_win, 2),
            "max_loss": round(max_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_trade": round(avg_pnl, 2),
            "max_drawdown": round(max_dd, 2),
            "max_win_streak": max_win_streak,
            "max_loss_streak": abs(max_loss_streak),
        },
        "by_ticker": ticker_stats,
        "by_day": dow_stats,
        "by_side": side_stats,
        "best_ticker": max(ticker_stats, key=lambda t: ticker_stats[t]["pnl"]) if ticker_stats else None,
        "worst_ticker": min(ticker_stats, key=lambda t: ticker_stats[t]["pnl"]) if ticker_stats else None,
        "best_day": max(dow_stats, key=lambda d: dow_stats[d]["pnl"]) if dow_stats else None,
        "worst_day": min(dow_stats, key=lambda d: dow_stats[d]["pnl"]) if dow_stats else None,
    }


def generate_report(analysis: dict, include_ai: bool = False) -> str:
    """Generate human-readable trade journal report."""
    s = analysis.get("summary", {})

    report = []
    report.append(f"{'='*70}")
    report.append(f"  TRADE JOURNAL REVIEW")
    report.append(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"{'='*70}\n")

    # Summary
    report.append("📊 PERFORMANCE SUMMARY")
    report.append("-" * 40)
    report.append(f"  Total trades:     {s.get('total_trades', 0)}")
    report.append(f"  Total P&L:        ${s.get('total_pnl', 0):.2f}")
    report.append(f"  Win rate:         {s.get('win_rate', 0):.1f}%")
    report.append(f"  Avg winner:       ${s.get('avg_win', 0):.2f}")
    report.append(f"  Avg loser:        ${s.get('avg_loss', 0):.2f}")
    report.append(f"  Best trade:       ${s.get('max_win', 0):.2f}")
    report.append(f"  Worst trade:      ${s.get('max_loss', 0):.2f}")
    report.append(f"  Profit factor:    {s.get('profit_factor', 0):.2f}")
    report.append(f"  Avg per trade:    ${s.get('avg_trade', 0):.2f}")
    report.append(f"  Max drawdown:     ${s.get('max_drawdown', 0):.2f}")
    report.append(f"  Best win streak:  {s.get('max_win_streak', 0)}")
    report.append(f"  Worst loss streak:{s.get('max_loss_streak', 0)}")
    report.append("")

    # By ticker
    if analysis.get("by_ticker"):
        report.append("🏷️ BY TICKER")
        report.append("-" * 40)
        report.append(f"  {'Ticker':<8} {'Trades':>6} {'P&L':>10} {'Win%':>6} {'Avg':>8}")
        report.append(f"  {'-'*42}")
        for ticker, stats in sorted(analysis["by_ticker"].items(), key=lambda x: x[1]["pnl"], reverse=True):
            report.append(f"  {ticker:<8} {stats['trades']:>6} ${stats['pnl']:>9.2f} {stats['win_rate']:>5.1f}% ${stats['avg_trade']:>7.2f}")
        report.append(f"  Best ticker:  {analysis.get('best_ticker', 'N/A')}")
        report.append(f"  Worst ticker: {analysis.get('worst_ticker', 'N/A')}")
        report.append("")

    # By day
    if analysis.get("by_day"):
        report.append("📅 BY DAY OF WEEK")
        report.append("-" * 40)
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            if day in analysis["by_day"]:
                stats = analysis["by_day"][day]
                emoji = "🟢" if stats["pnl"] > 0 else "🔴"
                report.append(f"  {emoji} {day:<12} {stats['trades']:>3} trades  ${stats['pnl']:>8.2f}  avg ${stats['avg_trade']:>7.2f}")
        report.append(f"  Best day:  {analysis.get('best_day', 'N/A')}")
        report.append(f"  Worst day: {analysis.get('worst_day', 'N/A')}")
        report.append("")

    # By side
    if analysis.get("by_side"):
        report.append("📈 BY SIDE")
        report.append("-" * 40)
        for side, stats in analysis["by_side"].items():
            emoji = "🟢" if stats["pnl"] > 0 else "🔴"
            report.append(f"  {emoji} {side:<8} {stats['trades']:>3} trades  ${stats['pnl']:>8.2f}  win {stats['win_rate']:.1f}%")
        report.append("")

    # Behavioral insights
    report.append("🧠 BEHAVIORAL INSIGHTS")
    report.append("-" * 40)

    if s.get("win_rate", 0) < 45:
        report.append("  ⚠️  Win rate below 45%. Consider tightening entry criteria or reducing trade frequency.")
    elif s.get("win_rate", 0) < 55:
        report.append("  🟡 Win rate is marginal (45-55%). Focus on risk/reward to maintain profitability.")
    else:
        report.append("  🟢 Win rate above 55%. Good edge — focus on sizing and consistency.")

    if s.get("profit_factor", 0) < 1.5:
        report.append("  ⚠️  Profit factor below 1.5. Winners aren't big enough relative to losers.")

    if s.get("avg_win", 0) < abs(s.get("avg_loss", 0)):
        report.append("  ⚠️  Average winner smaller than average loser. Need to let winners run or cut losers faster.")

    if s.get("max_loss_streak", 0) >= 4:
        report.append(f"  🔴 Had a {s['max_loss_streak']}-trade losing streak. Check if you revenge-traded after losses.")

    if analysis.get("worst_day"):
        report.append(f"  💡 Your worst day is {analysis['worst_day']}. Consider reducing size or skipping that day.")

    if analysis.get("worst_ticker"):
        report.append(f"  💡 Your worst ticker is {analysis['worst_ticker']}. Review your setup/thesis on this name.")

    report.append("")
    report.append(f"{'='*70}")
    report.append("  Want a personalized coaching session? contact@example.com")
    report.append(f"{'='*70}")

    return "\n".join(report)


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="AI Trade Journal Analyzer")
    parser.add_argument("csv_file", help="Path to trades CSV file")
    parser.add_argument("--full", action="store_true", help="Include AI coaching tips")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if not Path(args.csv_file).exists():
        print(f"[ERROR] File not found: {args.csv_file}")
        sys.exit(1)

    trades = load_trades(args.csv_file)
    print(f"[OK] Loaded {len(trades)} trades")

    analysis = analyze_trades(trades)

    if args.json:
        print(json.dumps(analysis, indent=2))
    else:
        report = generate_report(analysis, include_ai=args.full)
        print(report)

        # Save
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = DATA_DIR / f"journal_review_{timestamp}.txt"
        report_file.write_text(report)
        print(f"\n[SAVED] Report saved to {report_file}")
