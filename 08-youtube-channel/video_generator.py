#!/usr/bin/env python3
"""
Faceless YouTube Video Generator
=================================
Takes a stock analysis script → generates voiceover + chart overlays → outputs MP4

Usage:
  python video_generator.py --ticker NVDA --script script.txt
  python video_generator.py --ticker NVDA --auto    # auto-generate from analysis

Requires: ffmpeg, Pillow
Optional: ElevenLabs API key, OpenAI API key
"""

import argparse
import datetime
import json
import os
import subprocess
import textwrap
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~")) / "money-machines" / "08-youtube-channel" / "output"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def generate_script_from_analysis(ticker: str) -> str:
    """Generate a video script from stock analysis data."""
    # This would integrate with our existing stock analysis pipeline
    # For now, generate a template script

    script = f"""[HOOK - 10 seconds]
{ticker} is at a critical level right now. Here are the exact numbers you need to know before your next trade.

[MARKET CONTEXT - 30 seconds]
The market is digesting recent moves. SPY and QQQ are both near key support. VIX is elevated. For {ticker}, we're looking at an important test of the current zone.

[MAIN ANALYSIS - 2 minutes]
{ticker} is currently trading in a range that sets up two clear scenarios.

Scenario one: If {ticker} holds current support, we could see a bounce toward the first reclaim level. The RSI is in oversold territory, and volume is declining on the down days — which is actually bullish.

Scenario two: If {ticker} breaks below current support, the next downside target comes into play, and we need to reassess.

Key levels to watch:
- Support zone: current area
- First resistance: the reclaim level
- Stop level: below the support zone

[TRADE PLAN - 45 seconds]
If you're looking for an entry, here's the plan:
- Starter position near current support
- Add only on confirmation above the first reclaim level
- Stop below support
- Target the next resistance zone

[LEAP PICK - 30 seconds]
For longer-term players, the LEAP call strategy makes sense here. Check the description for the full analysis with specific strikes and breakevens.

[CTA - 15 seconds]
If you found this helpful, hit subscribe for daily stock levels. Link in the description for the full PDF report with options chain analysis and insider data. See you tomorrow.
"""
    return script


def generate_voiceover_tts(script: str, ticker: str, output_path: str) -> str:
    """Generate voiceover using available TTS engine."""
    audio_path = output_path.replace(".mp4", ".wav")

    # Try ElevenLabs first
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
    if elevenlabs_key:
        try:
            import elevenlabs
            audio = elevenlabs.generate(
                text=script,
                voice="Adam",
                model="eleven_multilingual_v2"
            )
            with open(audio_path, "wb") as f:
                f.write(audio)
            print(f"[TTS] ElevenLabs voiceover saved to {audio_path}")
            return audio_path
        except Exception as e:
            print(f"[WARN] ElevenLabs failed: {e}")

    # Try OpenAI TTS
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=script
            )
            with open(audio_path, "wb") as f:
                f.write(response.content)
            print(f"[TTS] OpenAI voiceover saved to {audio_path}")
            return audio_path
        except Exception as e:
            print(f"[WARN] OpenAI TTS failed: {e}")

    # Fallback: macOS say command
    try:
        # Clean script for say command
        clean = script.replace("[", "").replace("]", "").replace("\n", " ... ")
        result = subprocess.run(
            ["say", "-v", "Alex", "-o", audio_path, clean],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            print(f"[TTS] macOS 'say' voiceover saved to {audio_path}")
            return audio_path
    except Exception as e:
        print(f"[WARN] macOS 'say' failed: {e}")

    # Final fallback: gTTS
    try:
        from gtts import gTTS
        tts = gTTS(text=script, lang='en', slow=False)
        tts.save(audio_path)
        print(f"[TTS] gTTS voiceover saved to {audio_path}")
        return audio_path
    except Exception as e:
        print(f"[WARN] gTTS failed: {e}")

    print("[ERROR] No TTS engine available. Install one of: elevenlabs, openai, or gTTS")
    return ""


def generate_chart_overlay(ticker: str, output_dir: str) -> list:
    """Generate chart images with level overlays using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("[ERROR] Pillow required. Install with: pip install Pillow")
        return []

    images = []
    width, height = 1920, 1080

    # Title card
    img = Image.new('RGB', (width, height), color=(15, 15, 25))
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        font_medium = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Draw title
    draw.text((width//2, height//3), f"${ticker} LEVELS", fill=(255, 255, 255), font=font_large, anchor="mm")
    draw.text((width//2, height//3 + 80), f"Daily Stock Analysis", fill=(150, 150, 170), font=font_medium, anchor="mm")
    draw.text((width//2, height*2//3), f"{datetime.datetime.now().strftime('%B %d, %Y')}", fill=(100, 200, 100), font=font_medium, anchor="mm")

    title_path = str(Path(output_dir) / f"{ticker}_01_title.png")
    img.save(title_path)
    images.append(title_path)

    # Analysis card
    img2 = Image.new('RGB', (width, height), color=(15, 15, 25))
    draw2 = ImageDraw.Draw(img2)

    # Header
    draw2.rectangle([(0, 0), (width, 80)], fill=(25, 25, 45))
    draw2.text((30, 20), f"{ticker} ANALYSIS", fill=(255, 255, 255), font=font_medium)

    # Support levels
    y = 120
    draw2.text((60, y), "SUPPORT LEVELS", fill=(100, 200, 100), font=font_medium)
    y += 60
    for level in ["Zone 1: Current support", "Zone 2: Key must-hold", "Zone 3: Major support"]:
        draw2.text((100, y), f"▸ {level}", fill=(200, 200, 200), font=font_small)
        y += 45

    # Resistance levels
    y += 30
    draw2.text((60, y), "RESISTANCE LEVELS", fill=(200, 100, 100), font=font_medium)
    y += 60
    for level in ["Level 1: First reclaim", "Level 2: Confirmation", "Level 3: Supply zone"]:
        draw2.text((100, y), f"▸ {level}", fill=(200, 200, 200), font=font_small)
        y += 45

    # Trade plan
    y += 30
    draw2.text((60, y), "TRADE PLAN", fill=(100, 150, 255), font=font_medium)
    y += 60
    for plan in ["Entry: Near support zone", "Stop: Below support", "Target: Resistance zone"]:
        draw2.text((100, y), f"▸ {plan}", fill=(200, 200, 200), font=font_small)
        y += 45

    analysis_path = str(Path(output_dir) / f"{ticker}_02_analysis.png")
    img2.save(analysis_path)
    images.append(analysis_path)

    # CTA card
    img3 = Image.new('RGB', (width, height), color=(15, 15, 25))
    draw3 = ImageDraw.Draw(img3)

    draw3.text((width//2, height//3), "SUBSCRIBE", fill=(255, 50, 50), font=font_large, anchor="mm")
    draw3.text((width//2, height//3 + 80), "for daily stock levels", fill=(150, 150, 170), font=font_medium, anchor="mm")
    draw3.text((width//2, height//2 + 40), "Full PDF report → link in description", fill=(100, 200, 100), font=font_small, anchor="mm")

    cta_path = str(Path(output_dir) / f"{ticker}_03_cta.png")
    img3.save(cta_path)
    images.append(cta_path)

    print(f"[OK] Generated {len(images)} frame images")
    return images


def create_video(images: list, audio_path: str, ticker: str, output_path: str) -> str:
    """Combine images + audio into MP4 using ffmpeg."""
    if not images or not audio_path or not os.path.exists(audio_path):
        print("[ERROR] Missing images or audio")
        return ""

    # Get audio duration
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
    except:
        duration = 300  # default 5 minutes

    per_slide = duration / len(images)

    # Create video from images + audio
    concat_file = DATA_DIR / f"{ticker}_concat.txt"
    with open(concat_file, "w") as f:
        for img in images:
            f.write(f"file '{img}'\n")
            f.write(f"duration {per_slide:.1f}\n")
        # Add last image again (ffmpeg requires it)
        f.write(f"file '{images[-1]}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", audio_path,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"[VIDEO] Creating {output_path}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode == 0:
        print(f"[OK] Video saved to {output_path}")
        return output_path
    else:
        print(f"[ERROR] ffmpeg failed: {result.stderr[:500]}")
        return ""


# ── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser(description="Faceless YouTube Video Generator")
    parser.add_argument("--ticker", required=True, help="Stock ticker (e.g., NVDA)")
    parser.add_argument("--script", help="Path to script file")
    parser.add_argument("--auto", action="store_true", help="Auto-generate script from analysis")
    parser.add_argument("--output", default="", help="Output video path")

    args = parser.parse_args()

    # Get script
    if args.script:
        with open(args.script) as f:
            script = f.read()
    elif args.auto:
        script = generate_script_from_analysis(args.ticker)
        script_path = DATA_DIR / f"{args.ticker}_script_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
        script_path.write_text(script)
        print(f"[OK] Auto-generated script saved to {script_path}")
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python video_generator.py --ticker NVDA --auto")
        print("  python video_generator.py --ticker ORCL --script my_script.txt")
        sys.exit(1)

    # Generate voiceover
    output_base = DATA_DIR / f"{args.ticker}_{datetime.datetime.now().strftime('%Y%m%d')}"
    audio_path = generate_voiceover_tts(script, args.ticker, str(output_base) + ".mp4")

    # Generate chart overlays
    images = generate_chart_overlay(args.ticker, str(DATA_DIR))

    # Create video
    if audio_path and images:
        output_path = args.output or str(output_base) + ".mp4"
        create_video(images, audio_path, args.ticker, output_path)
    else:
        print("[INFO] Generated script and images. Run with TTS engine for full video.")
