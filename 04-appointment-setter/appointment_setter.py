#!/usr/bin/env python3
"""
AI Appointment Setter for Local Businesses
==========================================
Lead form → AI qualifies → Auto SMS reply → Follow-up sequence → Google Sheets CRM

Setup:
1. pip install openai google-auth google-auth-oauthlib google-api-python-client twilio
2. Set environment variables: OPENAI_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
3. Create Google service account + sheet (see setup_sheet below)
4. Deploy with: python appointment_setter.py --serve (runs Flask webhook)
   or: python appointment_setter.py --process (batch process pending leads)

Revenue model: $299 setup + $149/mo per client
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

# Shared LLM client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts'))
from llm_client import qualify_lead as _llm_qualify, load_env
load_env()

# ── Configuration ──────────────────────────────────────────────────────────
BUSINESS_NAME = "CHANGE_ME"  # e.g., "Luxe Med Spa"
BUSINESS_PHONE = "CHANGE_ME"  # e.g., "+18145551234"
GOOGLE_SHEETS_ID = "CHANGE_ME"  # Created below
FOLLOWUP_SCHEDULE_HOURS = [1, 24, 72]  # When to send follow-ups
DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "04-appointment-setter" / "data"

# ── AI Qualification Prompt ───────────────────────────────────────────────
QUALIFY_PROMPT = """You are an appointment setter for {business_name}. A new lead has come in.

Lead info:
- Name: {name}
- Phone: {phone}
- Email: {email}
- Service interest: {service}
- Message: {message}
- Source: {source}

Tasks:
1. Qualify the lead (hot/warm/cold) based on service interest and urgency
2. Write a personalized SMS reply (under 160 chars) that:
   - Greets them by name
   - Acknowledges their specific interest
   - Offers 2-3 available appointment times
   - Ends with a clear call-to-action
3. Write a follow-up email (under 200 words) for later

Respond in JSON format:
{{
  "qualification": "hot|warm|cold",
  "urgency": "high|medium|low",
  "sms_reply": "...",
  "followup_email": "...",
  "suggested_times": ["Monday 10am", "Tuesday 2pm", "Wednesday 11am"]
}}
"""

# ── Lead intake ─────────────────────────────────────────────────────────────
def intake_lead(name: str, phone: str, email: str, service: str,
                message: str = "", source: str = "website") -> dict:
    """Process a new lead: qualify with AI, log to CRM, send SMS."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    lead = {
        "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        "name": name,
        "phone": phone,
        "email": email,
        "service": service,
        "message": message,
        "source": source,
        "status": "new",
        "qualification": None,
        "urgency": None,
        "sms_sent": False,
        "followups_sent": 0,
        "next_followup": None,
        "created_at": datetime.datetime.now().isoformat(),
        "notes": []
    }

    # Save lead
    lead_file = DATA_DIR / f"leads.jsonl"
    with open(lead_file, "a") as f:
        f.write(json.dumps(lead) + "\n")

    # Qualify with AI
    result = qualify_lead(lead)
    lead.update(result)
    lead["status"] = "qualified"

    # Update lead file
    update_lead(lead)

    # Log to Google Sheets (if configured)
    try:
        log_to_sheets(lead)
    except Exception as e:
        print(f"[WARN] Sheets logging failed: {e}")

    # Send SMS (if Twilio configured)
    try:
        send_sms(lead["phone"], result["sms_reply"])
        lead["sms_sent"] = True
    except Exception as e:
        print(f"[WARN] SMS failed: {e}")

    # Schedule follow-ups
    lead["next_followup"] = (
        datetime.datetime.now() + datetime.timedelta(hours=FOLLOWUP_SCHEDULE_HOURS[0])
    ).isoformat()

    update_lead(lead)

    return lead


def qualify_lead(lead: dict) -> dict:
    """Use AI to qualify the lead and generate responses (via shared LLM client)."""
    try:
        result = _llm_qualify(lead, business_name=BUSINESS_NAME)
        return result
    except Exception as e:
        print(f"[WARN] LLM qualification failed: {e}")
        return _template_qualify(lead)


def _template_qualify(lead: dict) -> dict:
    """Template fallback when LLM is unavailable."""
    return {
        "qualification": "warm",
        "urgency": "medium",
        "sms_reply": f"Hi {lead.get('name', 'there')}! Thanks for reaching out about {lead.get('service', 'our services')}. We have openings Mon 10am, Tue 2pm, or Wed 11am. Reply to book!",
        "followup_email": f"Hi {lead.get('name', 'there')},\n\nThanks for your interest in {lead.get('service', 'our services')} at {BUSINESS_NAME}. We'd love to help!\n\nBest times: Mon 10am, Tue 2pm, Wed 11am.\n\nReply to schedule!\n\n- {BUSINESS_NAME}",
        "suggested_times": ["Monday 10am", "Tuesday 2pm", "Wednesday 11am"]
    }


def send_sms(to_phone: str, message: str):
    """Send SMS via Twilio."""
    try:
        from twilio.rest import Client
        client = Client(
            os.environ["TWILIO_ACCOUNT_SID"],
            os.environ["TWILIO_AUTH_TOKEN"]
        )
        client.messages.create(
            body=message,
            from_=os.environ["TWILIO_PHONE_NUMBER"],
            to=to_phone
        )
        print(f"[SMS] Sent to {to_phone}: {message[:80]}...")
    except KeyError:
        print("[WARN] Twilio not configured. SMS would be:", message)


def log_to_sheets(lead: dict):
    """Log lead to Google Sheets CRM."""
    try:
        import gspread
        gc = gspread.service_account()
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)
        ws = sh.sheet1

        row = [
            lead.get("id", ""),
            lead.get("name", ""),
            lead.get("phone", ""),
            lead.get("email", ""),
            lead.get("service", ""),
            lead.get("qualification", ""),
            lead.get("urgency", ""),
            lead.get("status", ""),
            lead.get("sms_sent", False),
            lead.get("created_at", ""),
            lead.get("next_followup", ""),
        ]
        ws.append_row(row)
        print(f"[SHEETS] Logged lead {lead.get('id')}")
    except Exception as e:
        print(f"[WARN] Sheets not configured: {e}")


def update_lead(lead: dict):
    """Update lead in local JSONL file."""
    lead_file = DATA_DIR / "leads.jsonl"
    if lead_file.exists():
        lines = lead_file.read_text().strip().split("\n")
        updated = []
        for line in lines:
            existing = json.loads(line)
            if existing.get("id") == lead.get("id"):
                updated.append(json.dumps(lead))
            else:
                updated.append(line)
        lead_file.write_text("\n".join(updated) + "\n")


def process_followups():
    """Process all leads that need follow-ups."""
    lead_file = DATA_DIR / "leads.jsonl"
    if not lead_file.exists():
        print("No leads file found.")
        return

    now = datetime.datetime.now()
    lines = lead_file.read_text().strip().split("\n")
    updated = []
    followups_sent = 0

    for line in lines:
        lead = json.loads(line)
        next_fu = lead.get("next_followup")

        if next_fu and lead.get("followups_sent", 0) < len(FOLLOWUP_SCHEDULE_HOURS):
            next_time = datetime.datetime.fromisoformat(next_fu)
            if now >= next_time:
                # Send follow-up
                fu_number = lead["followups_sent"]
                message = f"Hi {lead.get('name', 'there')}! Just checking in — still interested in {lead.get('service', 'our services')}? Reply to book your spot!"
                try:
                    send_sms(lead.get("phone", ""), message)
                    lead["followups_sent"] = fu_number + 1
                    lead["notes"].append(f"Follow-up {fu_number + 1} sent at {now.isoformat()}")

                    # Schedule next follow-up
                    if fu_number + 1 < len(FOLLOWUP_SCHEDULE_HOURS):
                        lead["next_followup"] = (
                            now + datetime.timedelta(hours=FOLLOWUP_SCHEDULE_HOURS[fu_number + 1])
                        ).isoformat()
                    else:
                        lead["next_followup"] = None
                        lead["status"] = "exhausted"

                    followups_sent += 1
                except Exception as e:
                    print(f"[ERROR] Follow-up failed for {lead.get('id')}: {e}")

        updated.append(json.dumps(lead))

    lead_file.write_text("\n".join(updated) + "\n")
    print(f"[FOLLOWUPS] Sent {followups_sent} follow-ups")


def report():
    """Generate a simple CRM report."""
    lead_file = DATA_DIR / "leads.jsonl"
    if not lead_file.exists():
        print("No leads found.")
        return

    leads = [json.loads(line) for line in lead_file.read_text().strip().split("\n")]

    print(f"\n{'='*60}")
    print(f"  CRM Report — {BUSINESS_NAME}")
    print(f"{'='*60}")
    print(f"  Total leads:     {len(leads)}")
    print(f"  Hot:             {sum(1 for l in leads if l.get('qualification') == 'hot')}")
    print(f"  Warm:            {sum(1 for l in leads if l.get('qualification') == 'warm')}")
    print(f"  Cold:            {sum(1 for l in leads if l.get('qualification') == 'cold')}")
    print(f"  SMS sent:        {sum(1 for l in leads if l.get('sms_sent'))}")
    print(f"  Follow-ups sent: {sum(l.get('followups_sent', 0) for l in leads)}")
    print(f"  Exhausted:       {sum(1 for l in leads if l.get('status') == 'exhausted')}")
    print(f"{'='*60}\n")


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Appointment Setter")
    parser.add_argument("--process", action="store_true", help="Process pending follow-ups")
    parser.add_argument("--add", nargs=6, metavar=("NAME", "PHONE", "EMAIL", "SERVICE", "MESSAGE", "SOURCE"),
                       help="Add a new lead manually")
    parser.add_argument("--report", action="store_true", help="Show CRM report")

    args = parser.parse_args()

    if args.add:
        lead = intake_lead(*args.add)
        print(f"[OK] Lead {lead['id']} created. Qualification: {lead['qualification']}")
    elif args.process:
        process_followups()
    elif args.report:
        report()
    else:
        print("Usage:")
        print("  python appointment_setter.py --add 'John' '+15551234567' 'contact@example.com' 'Botox' 'Interested' 'website'")
        print("  python appointment_setter.py --process")
        print("  python appointment_setter.py --report")
