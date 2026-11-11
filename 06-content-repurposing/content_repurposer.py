#!/usr/bin/env python3
"""
AI Content Repurposing Engine
==============================
Input: One YouTube video / podcast / Zoom call URL or transcript
Output: 10 tweets, 5 LinkedIn posts, 1 newsletter, 1 blog post, 5 short clip ideas

Usage:
  python content_repurposer.py "https://youtube.com/watch?v=XXX"
  python content_repurposer.py --transcript transcript.txt
  python content_repusser.py --text "Paste your long-form content here..."

Revenue model: $299/mo for 4 videos, $499/mo for 8, $999/mo for full engine
"""
import os
import sys
import json
import argparse
import datetime
import subprocess
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "06-content-repurposing" / "output"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Shared LLM client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared', 'scripts'))
from llm_client import call_llm, repurpose_content as _llm_repurpose, load_env
load_env()

# ── AI Prompts ──────────────────────────────────────────────────────────────
TWEETS_PROMPT = """You are a viral content creator. Take this transcript/content and create 10 engaging tweets.

Rules:
- Each tweet under 280 characters
- Mix of hooks, insights, and calls-to-action
- Use 1-2 relevant hashtags max
- Make them feel human, not AI-generated
- Number each tweet 1-10

Content:
{content}
"""

LINKEDIN_PROMPT = """You are a LinkedIn thought leadership writer. Take this transcript/content and create 5 LinkedIn posts.

Rules:
- Each post 150-300 words
- Start with a hook (question, stat, or bold claim)
- Include 1 personal insight or lesson
- End with a question to drive engagement
- Professional but conversational tone
- Number each post 1-5

Content:
{content}
"""

NEWSLETTER_PROMPT = """You are an email newsletter writer. Take this transcript/content and create a newsletter issue.

Format:
- Subject line (5 options)
- Preview text (under 100 chars)
- Opening hook (2-3 sentences)
- Main content (300-500 words, broken into sections)
- 3 key takeaways (bulleted)
- Closing CTA
- P.S. line

Content:
{content}
"""

BLOG_PROMPT = """You are an SEO blog writer. Take this transcript/content and create a blog post.

Requirements:
- Title (SEO-optimized, under 60 chars)
- Meta description (under 155 chars)
- H2 sections with clear subheadings
- 800-1200 words
- Include 3-5 key insights in bold
- End with a call-to-action
- Write in a conversational, authoritative tone

Content:
{content}
"""

CLIP_IDEAS_PROMPT = """You are a short-form video strategist. Take this transcript/content and suggest 5 short video clip ideas.

For each clip, provide:
- Timestamp range (or section)
- Hook (first 3 seconds - must grab attention)
- Key message (1 sentence)
- Suggested platform (TikTok, Reels, YouTube Shorts)
- Estimated best duration (15-60 seconds)

Content:
{content}
"""


def get_transcript_from_url(url: str) -> str:
    """Download transcript from YouTube URL."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--sub-lang", "en", "--skip-download",
             "--print", "%(id)s", url],
            capture_output=True, text=True, timeout=60
        )
        # Try to read the subtitle file
        video_id = result.stdout.strip()
        subtitle_files = list(Path(".").glob(f"*{video_id}*.vtt")) + list(Path(".").glob(f"*{video_id}*.srt"))
        if subtitle_files:
            return subtitle_files[0].read_text()
    except Exception as e:
        print(f"[WARN] Could not download transcript: {e}")

    # Fallback: use YouTube transcript API
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        video_id = url.split("v=")[1].split("&")[0] if "v=" in url else url.split("/")[-1]
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        print(f"[WARN] YouTube transcript API failed: {e}")
        return ""


def generate_content(transcript: str, content_type: str = "all") -> dict:
    """Generate repurposed content using the shared LLM client."""
    try:
        results = _llm_repurpose(transcript, content_type=content_type)
        return results
    except Exception as e:
        print(f"[ERROR] LLM content generation failed: {e}")
        return {}


def format_output(results: dict) -> str:
    """Format all generated content into a readable report."""
    output = []
    output.append(f"{'='*70}")
    output.append(f"  CONTENT REPURPOSING REPORT")
    output.append(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    output.append(f"{'='*70}\n")

    if "tweets" in results:
        output.append("🐦 TWEETS (10)")
        output.append("-" * 40)
        output.append(results["tweets"])
        output.append("")

    if "linkedin" in results:
        output.append("💼 LINKEDIN POSTS (5)")
        output.append("-" * 40)
        output.append(results["linkedin"])
        output.append("")

    if "newsletter" in results:
        output.append("📧 NEWSLETTER")
        output.append("-" * 40)
        output.append(results["newsletter"])
        output.append("")

    if "blog" in results:
        output.append("📝 BLOG POST")
        output.append("-" * 40)
        output.append(results["blog"])
        output.append("")

    if "clips" in results:
        output.append("🎬 SHORT VIDEO CLIP IDEAS (5)")
        output.append("-" * 40)
        output.append(results["clips"])
        output.append("")

    output.append(f"{'='*70}")

    return "\n".join(output)


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import subprocess

    parser = argparse.ArgumentParser(description="AI Content Repurposing Engine")
    parser.add_argument("url", nargs="?", help="YouTube URL or content source")
    parser.add_argument("--transcript", help="Path to transcript file")
    parser.add_argument("--text", help="Raw text content (in quotes)")
    parser.add_argument("--type", choices=["tweets", "linkedin", "newsletter", "blog", "clips", "all"],
                       default="all", help="Type of content to generate")

    args = parser.parse_args()

    transcript = ""

    if args.transcript:
        with open(args.transcript) as f:
            transcript = f.read()
    elif args.text:
        transcript = args.text
    elif args.url:
        transcript = get_transcript_from_url(args.url)
        if not transcript:
            print("[ERROR] Could not extract transcript. Use --transcript or --text instead.")
            sys.exit(1)
    else:
        parser.print_help()
        print("\nExamples:")
        print('  python content_repurposer.py "https://youtube.com/watch?v=XXX"')
        print('  python content_repurposer.py --transcript my_talk.txt')
        print('  python content_repurposer.py --text "My long-form content here..."')
        sys.exit(1)

    results = generate_content(transcript, content_type=args.type)
    output = format_output(results)
    print(output)

    # Save
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = DATA_DIR / f"repurposed_{timestamp}.md"
    output_file.write_text(output)
    print(f"\n[SAVED] Output saved to {output_file}")
