#!/usr/bin/env python3
"""
AI Lead List Generator + Cold Email Writer
==========================================
Scrapes Google Maps for businesses, generates personalized cold emails.

Usage:
  python lead_generator.py "med spa" "Los Angeles, CA" --limit 50
  python lead_generator.py "dentist" "New York, NY" --limit 100 --output leads.csv
  python lead_generator.py --personalize leads.csv            # Add AI emails

Revenue model: $199 for 250 leads, $399 for 500, $799/mo ongoing
"""

import os
import sys
import json
import csv
import argparse
import datetime
import re
import urllib.request
import urllib.parse
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "10-lead-list-service" / "output"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Shared LLM client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts'))
from llm_client import personalize_email as _llm_personalize, load_env
load_env()


def search_google_maps(business_type: str, location: str, limit: int = 50) -> list:
    """Search Google Maps for businesses using Places API or web scraping."""
    leads = []

    # Try Google Places API first (requires API key)
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")

    if api_key:
        print(f"[SEARCH] Using Google Places API for '{business_type}' in '{location}'...")
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"{business_type} in {location}",
            "key": api_key,
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(full_url, timeout=15) as resp:
                data = json.loads(resp.read())

            for place in data.get("results", [])[:limit]:
                lead = {
                    "name": place.get("name", ""),
                    "address": place.get("formatted_address", ""),
                    "phone": place.get("formatted_phone_number", ""),
                    "rating": place.get("rating", ""),
                    "review_count": place.get("user_ratings_total", 0),
                    "website": place.get("website", ""),
                    "types": ", ".join(place.get("types", [])),
                    "lat": place.get("geometry", {}).get("location", {}).get("lat", ""),
                    "lng": place.get("geometry", {}).get("location", {}).get("lng", ""),
                    "source": "google_places",
                    "scraped_at": datetime.datetime.now().isoformat(),
                }
                leads.append(lead)
        except Exception as e:
            print(f"[WARN] Places API failed: {e}")
    else:
        print(f"[SEARCH] No Google Places API key found. Using demo data...")
        print(f"[TIP] Set GOOGLE_PLACES_API_KEY env var for real data.")
        print(f"[TIP] Get one at: https://console.cloud.google.com/apis/credentials")

        # Generate demo leads for the business type
        demo_templates = {
            "med spa": ["Luxe Med Spa", "Glow Aesthetics", "Rejuvenate Spa", "Skin & Beauty Center", "Elite Med Spa"],
            "dentist": ["Smile Dental", "Bright Teeth DDS", "Family Dental Care", "Premier Dentistry", "Modern Dental"],
            "roofer": ["Top Roof Co", "Summit Roofing", "Pro Roof Masters", "AllWeather Roofs", "Shield Roofing"],
            "plumber": ["QuickFix Plumbing", "FlowMasters", "DrainPro", "A1 Plumbing", "PipeDreams"],
            "realtor": ["Premier Realty", "HomeFinders", "Key Properties", "DreamHome Realty", "CityHomes"],
        }

        template = demo_templates.get(business_type.lower(),
            [f"{business_type.title()} Pro", f"Best {business_type.title()}", f"Top {business_type.title()} Co"])

        for i, name in enumerate(template[:min(limit, len(template))]):
            leads.append({
                "name": name,
                "address": f"{100+i} Main St, {location}",
                "phone": f"(555) {100+i*11:04d}",
                "rating": 4.0 + (i % 5) * 0.2,
                "review_count": 50 + i * 23,
                "website": f"www.{name.lower().replace(' ', '')}.com",
                "business_type": business_type,
                "location": location,
                "source": "demo",
                "scraped_at": datetime.datetime.now().isoformat(),
            })

    print(f"[OK] Found {len(leads)} leads")
    return leads


def personalize_emails(leads: list, service_description: str = "") -> list:
    """Add personalized cold emails to each lead using shared LLM client."""
    for i, lead in enumerate(leads):
        print(f"[PERSONALIZE] {i+1}/{len(leads)}: {lead.get('name', 'Unknown')}...")

        try:
            result = _llm_personalize(lead, service_description or "AI automation that handles lead follow-up, appointment booking, and customer engagement 24/7")
            lead["email_subject"] = result.get("subject", f"Quick question about {lead.get('name', 'your business')}")
            lead["email_body"] = result.get("body", template_email(lead, service_description))
        except Exception as e:
            print(f"[WARN] Personalization failed for {lead.get('name')}: {e}")
            lead["email_subject"] = f"Quick question about {lead.get('name', 'your business')}"
            lead["email_body"] = template_email(lead, service_description)

    return leads


def template_email(lead: dict, service: str = "") -> str:
    """Generate a template email without AI."""
    name = lead.get('name', 'your business')
    bt = lead.get('business_type', 'business')
    loc = lead.get('location', 'your area')

    return f"""Hi {name} team,

I noticed {name} has great reviews in {loc}. Quick question — are you still handling lead follow-ups manually?

I build AI agents that respond to new leads in under 60 seconds, book appointments automatically, and follow up 3x so nothing falls through the cracks.

Most {bt} businesses lose 30-40% of potential clients just from slow follow-up. I can fix that.

Can I show you a 2-minute demo?

Best,
Project Contributor"""


def save_leads(leads: list, filepath: str):
    """Save leads to CSV."""
    if not leads:
        print("[WARN] No leads to save.")
        return

    fieldnames = list(leads[0].keys())
    # Add email fields if present
    if "email_subject" not in fieldnames and any(l.get("email_subject") for l in leads):
        fieldnames.extend(["email_subject", "email_body"])

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow({k: lead.get(k, "") for k in fieldnames})

    print(f"[SAVED] {len(leads)} leads saved to {filepath}")


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="AI Lead List Generator")
    parser.add_argument("business_type", nargs="?", help="Type of business (e.g., 'med spa', 'dentist')")
    parser.add_argument("location", nargs="?", help="Location (e.g., 'Los Angeles, CA')")
    parser.add_argument("--limit", type=int, default=50, help="Max leads to fetch")
    parser.add_argument("--personalize", action="store_true", help="Generate personalized emails")
    parser.add_argument("--service", default="", help="Description of your service for email personalization")
    parser.add_argument("--output", default="", help="Output CSV file path")
    parser.add_argument("--input-csv", default="", help="Input CSV to personalize (skip scraping)")

    args = parser.parse_args()

    if args.input_csv:
        # Load existing leads and personalize
        leads = []
        with open(args.input_csv, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                leads.append(dict(row))
        print(f"[OK] Loaded {len(leads)} leads from {args.input_csv}")
        leads = personalize_emails(leads, args.service)
        output = args.output or str(DATA_DIR / f"personalized_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        save_leads(leads, output)

    elif args.business_type and args.location:
        # Search + optionally personalize
        leads = search_google_maps(args.business_type, args.location, args.limit)

        if args.personalize:
            leads = personalize_emails(leads, args.service)

        output = args.output or str(DATA_DIR / f"leads_{args.business_type.replace(' ','_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        save_leads(leads, output)

    else:
        parser.print_help()
        print("\nExamples:")
        print('  python lead_generator.py "med spa" "Los Angeles, CA" --limit 50')
        print('  python lead_generator.py "dentist" "New York, NY" --limit 100 --personalize')
        print('  python lead_generator.py --input-csv leads.csv --personalize --service "AI appointment booking"')
        print("\nSetup:")
        print("  export GOOGLE_PLACES_API_KEY=your_key  # Optional, for real data")
        print("  export OPENAI_API_KEY=your_key          # For email personalization")
