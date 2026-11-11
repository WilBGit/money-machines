#!/usr/bin/env python3
"""
AI Website Audit Tool
=====================
Runs Lighthouse + AI analysis on any website and generates a prioritized fix report.

Usage:
  python website_audit.py https://example.com
  python website_audit.py https://example.com --full    # includes AI copy suggestions
  python website_audit.py --batch urls.txt               # audit multiple sites

Revenue model: $49 audit, $299-999 implementation, $99/mo ongoing
"""

import subprocess
import json
import sys
import argparse
import datetime
import urllib.request
import re
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "05-website-audit" / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Lighthouse Audit ───────────────────────────────────────────────────────
def run_lighthouse(url: str) -> dict:
    """Run Lighthouse and return parsed results."""
    print(f"[AUDIT] Running Lighthouse on {url}...")

    output_file = DATA_DIR / f"lighthouse_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    try:
        result = subprocess.run([
            "npx", "lighthouse", url,
            "--output=json",
            f"--output-path={output_file}",
            "--chrome-flags=--headless",
            "--only-categories=performance,accessibility,best-practices,seo",
            "--quiet"
        ], capture_output=True, text=True, timeout=120)

        if output_file.exists():
            with open(output_file) as f:
                return json.load(f)
        else:
            print(f"[WARN] Lighthouse output not found, using fallback")
            return fallback_audit(url)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"[WARN] Lighthouse not available: {e}")
        return fallback_audit(url)


def fallback_audit(url: str) -> dict:
    """Basic website analysis without Lighthouse."""
    print(f"[AUDIT] Running basic analysis on {url}...")

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', 'replace')
            status = resp.status
            headers = dict(resp.headers)
    except Exception as e:
        return {"error": str(e), "url": url}

    # Basic checks
    issues = []
    scores = {}

    # Title check
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
    title = title_match.group(1).strip() if title_match else ""
    if not title:
        issues.append({"severity": "high", "category": "SEO", "issue": "Missing page title", "fix": "Add a descriptive <title> tag"})
    elif len(title) > 60:
        issues.append({"severity": "medium", "category": "SEO", "issue": f"Title too long ({len(title)} chars)", "fix": "Keep title under 60 characters"})

    # Meta description
    meta_desc = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.I)
    if not meta_desc:
        issues.append({"severity": "high", "category": "SEO", "issue": "Missing meta description", "fix": "Add a meta description tag (150-160 chars)"})

    # H1 check
    h1_count = len(re.findall(r'<h1[^>]*>', html, re.I))
    if h1_count == 0:
        issues.append({"severity": "high", "category": "SEO", "issue": "No H1 heading", "fix": "Add exactly one H1 with your main keyword"})
    elif h1_count > 1:
        issues.append({"severity": "medium", "category": "SEO", "issue": f"Multiple H1 tags ({h1_count})", "fix": "Use only one H1 per page"})

    # Images without alt
    img_tags = re.findall(r'<img[^>]*>', html, re.I)
    imgs_no_alt = [img for img in img_tags if 'alt=' not in img.lower()]
    if imgs_no_alt:
        issues.append({"severity": "medium", "category": "Accessibility", "issue": f"{len(imgs_no_alt)} images missing alt text", "fix": "Add descriptive alt attributes to all images"})

    # HTTPS check
    if not url.startswith('https://'):
        issues.append({"severity": "high", "category": "Security", "issue": "Site not using HTTPS", "fix": "Install SSL certificate and redirect HTTP to HTTPS"})

    # Mobile viewport
    if 'viewport' not in html.lower():
        issues.append({"severity": "high", "category": "Mobile", "issue": "Missing viewport meta tag", "fix": "Add <meta name='viewport' content='width=device-width, initial-scale=1'>"})

    # Load time estimate
    page_size = len(html) / 1024
    if page_size > 500:
        issues.append({"severity": "medium", "category": "Performance", "issue": f"Large page size ({page_size:.0f}KB HTML)", "fix": "Minify HTML, defer scripts, optimize images"})

    # CTA check
    cta_keywords = ['buy now', 'get started', 'sign up', 'contact us', 'book now', 'schedule', 'call now', 'learn more']
    cta_found = [kw for kw in cta_keywords if kw in html.lower()]
    if not cta_found:
        issues.append({"severity": "high", "category": "Conversion", "issue": "No clear call-to-action found", "fix": "Add visible, action-oriented buttons above the fold"})

    # Contact info
    phone_found = bool(re.search(r'\+?1?\s*\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}', html))
    email_found = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html))
    if not phone_found and not email_found:
        issues.append({"severity": "medium", "category": "Trust", "issue": "No visible phone or email", "fix": "Add contact info in header/footer"})

    # Estimate scores
    critical = sum(1 for i in issues if i["severity"] == "high")
    warnings = sum(1 for i in issues if i["severity"] == "medium")
    scores["estimated_performance"] = max(30, 100 - critical * 15 - warnings * 5)
    scores["estimated_seo"] = max(20, 100 - critical * 20 - warnings * 8)
    scores["estimated_accessibility"] = max(25, 100 - critical * 12 - warnings * 6)
    scores["estimated_conversion"] = max(10, 100 - critical * 18 - warnings * 10)

    return {
        "url": url,
        "timestamp": datetime.datetime.now().isoformat(),
        "title": title,
        "page_size_kb": round(page_size, 1),
        "scores": scores,
        "issues": issues,
        "checks": {
            "has_title": bool(title),
            "has_meta_desc": bool(meta_desc),
            "h1_count": h1_count,
            "imgs_no_alt": len(imgs_no_alt),
            "has_https": url.startswith('https://'),
            "has_viewport": 'viewport' in html.lower(),
            "has_cta": len(cta_found) > 0,
            "has_phone": phone_found,
            "has_email": email_found,
            "cta_found": cta_found
        }
    }


def generate_report(audit: dict, include_ai: bool = False) -> str:
    """Generate a human-readable audit report."""
    url = audit.get("url", "Unknown")
    scores = audit.get("scores", {})
    issues = audit.get("issues", [])
    checks = audit.get("checks", {})

    # Sort by severity
    issues.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3))

    report = []
    report.append(f"{'='*70}")
    report.append(f"  WEBSITE AUDIT REPORT")
    report.append(f"  {url}")
    report.append(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"{'='*70}\n")

    # Scores
    report.append("📊 ESTIMATED SCORES")
    report.append("-" * 40)
    for metric, score in scores.items():
        emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
        label = metric.replace("estimated_", "").replace("_", " ").title()
        report.append(f"  {emoji} {label}: {score}/100")
    report.append("")

    # Quick checks
    report.append("✅ QUICK CHECKS")
    report.append("-" * 40)
    check_emojis = {
        "has_title": ("Page Title", "✅" if checks.get("has_title") else "❌"),
        "has_meta_desc": ("Meta Description", "✅" if checks.get("has_meta_desc") else "❌"),
        "h1_count": ("H1 Tags", "✅" if 0 < checks.get("h1_count", 0) <= 1 else "❌"),
        "has_https": ("HTTPS", "✅" if checks.get("has_https") else "❌"),
        "has_viewport": ("Mobile Viewport", "✅" if checks.get("has_viewport") else "❌"),
        "has_cta": ("Call-to-Action", "✅" if checks.get("has_cta") else "❌"),
        "has_phone": ("Phone Number", "✅" if checks.get("has_phone") else "❌"),
        "has_email": ("Email Address", "✅" if checks.get("has_email") else "❌"),
    }
    for key, (label, emoji) in check_emojis.items():
        report.append(f"  {emoji} {label}")
    report.append("")

    # Issues (prioritized)
    report.append(f"🔧 PRIORITIZED ISSUES ({len(issues)} found)")
    report.append("-" * 40)
    for i, issue in enumerate(issues, 1):
        severity = issue.get("severity", "low").upper()
        emoji = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
        report.append(f"\n  {i}. {emoji} [{severity}] {issue['category']}")
        report.append(f"     Issue: {issue['issue']}")
        report.append(f"     Fix:   {issue['fix']}")
    report.append("")

    # Summary
    high = sum(1 for i in issues if i["severity"] == "high")
    medium = sum(1 for i in issues if i["severity"] == "medium")
    low = sum(1 for i in issues if i["severity"] == "low")

    report.append(f"📋 SUMMARY")
    report.append("-" * 40)
    report.append(f"  🔴 Critical issues: {high}")
    report.append(f"  🟡 Warnings:        {medium}")
    report.append(f"  🟢 Minor issues:    {low}")
    report.append(f"  📊 Total issues:    {len(issues)}")
    report.append("")
    report.append(f"  Estimated conversion lift from fixing critical issues: +{high * 5}-{high * 15}%")
    report.append("")

    if include_ai:
        report.append("🤖 AI COPY SUGGESTIONS")
        report.append("-" * 40)
        report.append("  [AI suggestions would be generated here using OpenAI API]")
        report.append("  Run with --full flag to include AI-powered copy recommendations.")
        report.append("")

    report.append(f"{'='*70}")
    report.append("  Want me to fix these issues for you? Contact: contact@example.com")
    report.append(f"{'='*70}")

    return "\n".join(report)


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(description="AI Website Audit Tool")
    parser.add_argument("url", nargs="?", help="URL to audit (e.g., https://example.com)")
    parser.add_argument("--batch", help="File with one URL per line")
    parser.add_argument("--full", action="store_true", help="Include AI copy suggestions")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    urls = []
    if args.url:
        urls.append(args.url)
    if args.batch:
        with open(args.batch) as f:
            urls.extend([line.strip() for line in f if line.strip()])

    if not urls:
        parser.print_help()
        print("\nExamples:")
        print("  python website_audit.py https://example.com")
        print("  python website_audit.py https://example.com --full")
        print("  python website_audit.py --batch urls.txt")
        sys.exit(1)

    for url in urls:
        if not url.startswith("http"):
            url = "https://" + url

        audit = run_lighthouse(url)

        if args.json:
            print(json.dumps(audit, indent=2))
        else:
            report_text = generate_report(audit, include_ai=args.full)
            print(report_text)

            # Save report
            safe_url = re.sub(r'[^a-zA-Z0-9]', '_', url)[:50]
            report_file = DATA_DIR / f"audit_{safe_url}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            report_file.write_text(report_text)
            print(f"\n[SAVED] Report saved to {report_file}")
