#!/usr/bin/env python3
"""
Shared LLM Client for Money Machines
======================================
Supports: Hermes OAuth routing (Grok/GPT), OpenRouter, OpenAI, or template fallback.

Configuration via ~/money-machines/.env:
  LLM_PROVIDER=hermes|openrouter|openai|template   (default: hermes)
  LLM_MODEL=grok-4.6|gpt-5.4-mini|...             (default: grok-4.6)
  LLM_HERMES_PROVIDER=xai-oauth|openai-codex       (default: xai-oauth)
  OPENROUTER_API_KEY=sk-or-v1-...
  OPENAI_API_KEY=sk-...

When no API key is set, falls back to enhanced template mode (no API needed).
"""

import os
import json
import urllib.request
import urllib.error
from pathlib import Path

DOTENV_PATH = Path(os.path.expanduser("~")) / "money-machines" / ".env"

def load_env():
    """Load .env file into environment variables."""
    if DOTENV_PATH.exists():
        for line in DOTENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and value and key not in os.environ:
                    os.environ[key] = value

# Load on import
load_env()


def call_llm(prompt: str, system: str = "", model: str = None, temperature: float = 0.7,
             max_tokens: int = 2000, json_mode: bool = False) -> str:
    """
    Call an LLM with the configured provider.

    Provider priority:
    1. Explicit LLM_PROVIDER=hermes → Hermes CLI OAuth routing (Grok/GPT)
    2. OPENROUTER_API_KEY → OpenRouter API
    3. OPENAI_API_KEY → OpenAI API
    4. Template fallback (no API call)

    Returns the LLM response text.
    """
    model = model or os.environ.get("LLM_MODEL", "grok-4.6")
    provider = os.environ.get("LLM_PROVIDER", "").lower()

    # Auto-detect provider from available keys/endpoints
    if not provider:
        if os.environ.get("OPENROUTER_API_KEY"):
            provider = "openrouter"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "hermes"

    if provider in {"hermes", "xai-oauth", "openai-codex"}:
        hermes_provider = os.environ.get("LLM_HERMES_PROVIDER", "xai-oauth")
        if provider in {"xai-oauth", "openai-codex"}:
            hermes_provider = provider
        return _call_hermes(prompt, system, model, hermes_provider, max_tokens, json_mode)
    elif provider == "openrouter":
        return _call_openrouter(prompt, system, model, temperature, max_tokens, json_mode)
    elif provider == "openai":
        return _call_openai(prompt, system, model, temperature, max_tokens, json_mode)
    else:
        return _call_template(prompt)


def _call_hermes(prompt: str, system: str, model: str, provider: str,
                 max_tokens: int, json_mode: bool) -> str:
    """Route a content request through Hermes' authenticated CLI providers."""
    import shutil
    import subprocess

    hermes_bin = os.environ.get(
        "HERMES_BIN",
        "/path/to/project/.hermes/hermes-agent/.hermes/bin/hermes",
    )
    if not Path(hermes_bin).exists():
        hermes_bin = shutil.which("hermes") or hermes_bin

    combined = f"{system.strip()}\\n\\n{prompt.strip()}" if system else prompt.strip()
    if json_mode:
        combined += "\\n\\nReturn only valid JSON. Do not use markdown fences or commentary."

    command = [
        hermes_bin,
        "chat",
        "-Q",
        "--ignore-rules",
        "-t",
        "safe",
        "-q",
        combined,
        "-m",
        model,
        "--provider",
        provider,
        "--reasoning",
        "none",
        "--max-turns",
        "1",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("HERMES_LLM_TIMEOUT", "180")),
            check=False,
        )
    except Exception as exc:
        return f"[ERROR] Hermes request failed: {type(exc).__name__}: {str(exc)[:200]}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "provider process failed").strip()
        return f"[ERROR] Hermes provider failed ({result.returncode}): {detail[:500]}"

    text = (result.stdout or "").strip()
    if "\\nsession_id:" in text:
        text = text.split("\\nsession_id:", 1)[0].rstrip()
    if not text:
        return "[ERROR] Hermes provider returned empty content"
    return text


def _call_openrouter(prompt: str, system: str, model: str, temperature: float,
                     max_tokens: int, json_mode: bool) -> str:
    """Call OpenRouter API (supports GPT-5.5, Claude, Gemini, etc.)."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return _call_template(prompt)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://money-machines.local",
        "X-Title": "Money Machines",
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return f"[ERROR] OpenRouter API error {e.code}: {error_body[:500]}"
    except Exception as e:
        return f"[ERROR] OpenRouter request failed: {type(e).__name__}: {str(e)[:200]}"


def _call_openai(prompt: str, system: str, model: str, temperature: float,
                 max_tokens: int, json_mode: bool) -> str:
    """Call OpenAI API directly."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _call_template(prompt)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return f"[ERROR] OpenAI API error {e.code}: {error_body[:500]}"
    except Exception as e:
        return f"[ERROR] OpenAI request failed: {type(e).__name__}: {str(e)[:200]}"


def _call_template(prompt: str) -> str:
    """Enhanced template fallback when no provider is available."""
    return f"[TEMPLATE MODE] No LLM provider is available. To enable AI personalization:\n" \
           f"  1. Authenticate Hermes with the configured Grok/GPT provider\n" \
           f"  2. Or add OPENROUTER_API_KEY / OPENAI_API_KEY to ~/money-machines/.env\n" \
           f"  3. Set LLM_PROVIDER=hermes (default), openrouter, or openai\n\n" \
           f"Original prompt was:\n{prompt[:500]}..."


# ── Convenience functions for specific tasks ─────────────────────────────────

def personalize_email(lead: dict, service_description: str = "") -> dict:
    """Generate a personalized cold email for a lead."""
    prompt = f"""Write a personalized cold email to {lead.get('name', 'the business owner')} at a {lead.get('business_type', 'business')} in {lead.get('location', 'their area')}.

Business details:
- Name: {lead.get('name', '')}
- Rating: {lead.get('rating', 'N/A')}
- Address: {lead.get('address', '')}
- Website: {lead.get('website', '')}

Our service: {service_description or 'AI automation that handles lead follow-up, appointment booking, and customer engagement 24/7'}

Requirements:
- Subject line (under 50 chars, compelling)
- Email body (under 150 words)
- Reference their specific business name and location
- Focus on their pain point (missed leads, slow follow-up, manual scheduling)
- Clear CTA: "Can I show you a 2-minute demo?"
- Professional but casual tone
- No generic templates — make it feel handwritten

Output as JSON: {{"subject": "...", "body": "..."}}"""

    system = "You are an expert cold email writer for B2B sales. Write concise, personalized emails that get replies."
    response = call_llm(prompt, system=system, temperature=0.8, json_mode=True)

    try:
        # Try to parse JSON from response
        if "[" in response and "TEMPLATE MODE" in response:
            return {"subject": f"Quick question about {lead.get('name', 'your business')}",
                    "body": _template_email(lead, service_description)}
        # Extract JSON from potential markdown code blocks
        import re
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)
    except (json.JSONDecodeError, ValueError):
        return {"subject": f"Quick question about {lead.get('name', 'your business')}",
                "body": _template_email(lead, service_description)}


def _template_email(lead: dict, service: str = "") -> str:
    """Generate a template email without AI."""
    name = lead.get('name', 'your business')
    bt = lead.get('business_type', 'business')
    loc = lead.get('location', 'your area')
    rating = lead.get('rating', '')

    rating_line = f" With a {rating}-star rating, you're clearly doing great work — but" if rating else ""

    return f"""Hi {name} team,

I noticed {name} in {loc}.{rating_line} I wanted to reach out because most {bt} businesses lose 30-40% of potential clients just from slow follow-up.

I build AI agents that respond to new leads in under 60 seconds, book appointments automatically, and follow up 3x so nothing falls through the cracks.

The result? More booked appointments, fewer missed calls, and you only deal with qualified leads.

Can I show you a 2-minute demo?

Best,
Project Contributor"""


def qualify_lead(lead: dict, business_name: str = "") -> dict:
    """Qualify a lead and generate SMS reply + follow-up email."""
    prompt = f"""You are an appointment setter for {business_name or 'our business'}. A new lead has come in.

Lead info:
- Name: {lead.get('name', 'Friend')}
- Phone: {lead.get('phone', '')}
- Email: {lead.get('email', '')}
- Service interest: {lead.get('service', 'general')}
- Message: {lead.get('message', '')}
- Source: {lead.get('source', 'website')}

Tasks:
1. Qualify the lead (hot/warm/cold)
2. Write a personalized SMS reply (under 160 chars)
3. Write a follow-up email (under 200 words)

Respond in JSON: {{"qualification": "hot|warm|cold", "urgency": "high|medium|low", "sms_reply": "...", "followup_email": "...", "suggested_times": ["Mon 10am", "Tue 2pm", "Wed 11am"]}}"""

    system = "You are a professional appointment setter. Be warm, concise, and action-oriented."
    response = call_llm(prompt, system=system, temperature=0.7, json_mode=True)

    try:
        if "TEMPLATE MODE" in response:
            return _template_qualify(lead, business_name)
        import re
        json_match = re.search(r'\{[^{}]*"qualification"[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)
    except (json.JSONDecodeError, ValueError):
        return _template_qualify(lead, business_name)


def _template_qualify(lead: dict, business_name: str = "") -> dict:
    """Template-based lead qualification."""
    name = lead.get('name', 'Friend')
    service = lead.get('service', 'our services')

    return {
        "qualification": "warm",
        "urgency": "medium",
        "sms_reply": f"Hi {name}! Thanks for reaching out about {service}. We have openings Mon 10am, Tue 2pm, or Wed 11am. Reply to book!",
        "followup_email": f"Hi {name},\n\nThanks for your interest in {service} at {business_name or 'our office'}. We'd love to help!\n\nBest times: Mon 10am, Tue 2pm, Wed 11am.\n\nReply to schedule!\n\n- {business_name or 'Our Team'}",
        "suggested_times": ["Monday 10am", "Tuesday 2pm", "Wednesday 11am"]
    }


def repurpose_content(content: str, content_type: str = "all") -> dict:
    """Repurpose long-form content into tweets, LinkedIn posts, newsletter, blog, clips."""
    prompts = {
        "tweets": """You are a viral content creator. Create 10 engaging tweets from this content.

Rules:
- Each tweet under 280 characters
- Mix of hooks, insights, and calls-to-action
- Use 1-2 hashtags max
- Make them feel human, not AI-generated
- Number each tweet 1-10

Content:
{content}""",

        "linkedin": """You are a LinkedIn thought leadership writer. Create 5 LinkedIn posts from this content.

Rules:
- Each post 150-300 words
- Start with a hook (question, stat, or bold claim)
- Include 1 personal insight or lesson
- End with a question to drive engagement
- Professional but conversational tone
- Number each post 1-5

Content:
{content}""",

        "newsletter": """You are an email newsletter writer. Create a newsletter issue from this content.

Format:
- Subject line (5 options)
- Preview text (under 100 chars)
- Opening hook (2-3 sentences)
- Main content (300-500 words, broken into sections)
- 3 key takeaways (bulleted)
- Closing CTA
- P.S. line

Content:
{content}""",

        "blog": """You are an SEO blog writer. Create a blog post from this content.

Requirements:
- Title (SEO-optimized, under 60 chars)
- Meta description (under 155 chars)
- H2 sections with clear subheadings
- 800-1200 words
- Include 3-5 key insights in bold
- End with a call-to-action
- Conversational, authoritative tone

Content:
{content}""",

        "clips": """You are a short-form video strategist. Suggest 5 short video clip ideas from this content.

For each clip:
- Hook (first 3 seconds — must grab attention)
- Key message (1 sentence)
- Suggested platform (TikTok, Reels, YouTube Shorts)
- Estimated best duration (15-60 seconds)

Content:
{content}"""
    }

    types = [content_type] if content_type != "all" else list(prompts.keys())
    results = {}

    for ct in types:
        if ct not in prompts:
            continue
        print(f"[GENERATE] Creating {ct}...")
        response = call_llm(
            prompts[ct].format(content=content[:15000]),
            system="You are an expert content creator and marketer.",
            temperature=0.8,
            max_tokens=2000
        )
        results[ct] = response

    return results


# ── Test ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python llm_client.py test              # Test LLM connection")
        print("  python llm_client.py personalize        # Test email personalization")
        print("  python llm_client.py status             # Show current config")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        provider = os.environ.get("LLM_PROVIDER", "auto")
        model = os.environ.get("LLM_MODEL", "gpt-5.5")
        has_or = "YES" if os.environ.get("OPENROUTER_API_KEY") else "NO"
        has_oai = "YES" if os.environ.get("OPENAI_API_KEY") else "NO"

        if not os.environ.get("LLM_PROVIDER"):
            if os.environ.get("OPENROUTER_API_KEY"):
                provider = "openrouter"
            elif os.environ.get("OPENAI_API_KEY"):
                provider = "openai"
            else:
                provider = "template (no API key)"

        print(f"LLM Client Status:")
        print(f"  Provider: {provider}")
        print(f"  Model: {model}")
        print(f"  OpenRouter key: {has_or}")
        print(f"  OpenAI key: {has_oai}")
        print(f"  .env path: {DOTENV_PATH}")

    elif cmd == "test":
        print("Testing LLM connection...")
        response = call_llm("Say 'Hello! LLM connection works.' and nothing else.", temperature=0)
        print(f"Response: {response}")

    elif cmd == "personalize":
        test_lead = {
            "name": "Luxe Med Spa",
            "business_type": "med spa",
            "location": "Azusa, CA",
            "rating": 4.8,
            "address": "123 E Foothill Blvd, Azusa, CA 91702",
        }
        result = personalize_email(test_lead, "AI appointment booking that responds to leads in 60 seconds")
        print(json.dumps(result, indent=2))
