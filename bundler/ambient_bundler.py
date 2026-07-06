#!/usr/bin/env python3
"""
AyuGuard Ambient Bundler
=========================
Standalone script that reads the live health_profile.json and generates
a single, warm, cohesive daily care message in the patient's preferred language.

Bundles together:
  • Morning greeting personalised to the patient
  • Today's medication reminders (from active medications array)
  • Today's meal plan (acute mode OR chronic mode based on active events)
  • Motivational / wellness closing

Usage:
  python bundler/ambient_bundler.py
  python bundler/ambient_bundler.py --language English
  python bundler/ambient_bundler.py --output message.txt

Dependencies:  google-genai (bundled with google-adk), python-dotenv
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Windows Unicode fix ───────────────────────────────────────────────────────
# Reconfigure stdout/stderr to UTF-8 so Devanagari prints correctly in
# PowerShell / Windows Terminal. Has no effect on Linux/macOS.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

# ── Path resolution ────────────────────────────────────────────────────────────
_BUNDLER_DIR = Path(__file__).parent.resolve()
_PROJECT_ROOT = _BUNDLER_DIR.parent
_PROFILE_PATH = _PROJECT_ROOT / "mcp_server" / "health_profile.json"
_ENV_PATH = _PROJECT_ROOT / "ayuguard" / ".env"

# Load environment (for GOOGLE_API_KEY)
load_dotenv(dotenv_path=_ENV_PATH)


# ── Profile Loader ─────────────────────────────────────────────────────────────

def load_profile() -> dict:
    if not _PROFILE_PATH.exists():
        raise FileNotFoundError(f"health_profile.json not found at {_PROFILE_PATH}")
    with _PROFILE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ── Prompt Builder ─────────────────────────────────────────────────────────────

def build_bundler_prompt(profile: dict, language_override: str | None = None) -> str:
    """Build a Gemini prompt that generates the warm ambient message."""

    patient = profile.get("patient", {})
    name = patient.get("preferred_name") or patient.get("name", "रोगी")
    age = patient.get("age", "")
    language = language_override or patient.get("language", "Hindi")
    location = patient.get("location", "India")

    chronic = profile.get("chronic_conditions", [])
    acute = profile.get("acute_events", [])
    medications = profile.get("medications", [])
    restrictions = profile.get("dietary_restrictions", [])

    now = datetime.now()
    greeting_time = (
        "सुबह" if 5 <= now.hour < 12
        else "दोपहर" if 12 <= now.hour < 17
        else "शाम" if 17 <= now.hour < 21
        else "रात"
    )
    greeting_en = (
        "Good morning" if 5 <= now.hour < 12
        else "Good afternoon" if 12 <= now.hour < 17
        else "Good evening" if 17 <= now.hour < 21
        else "Good night"
    )
    time_str = now.strftime("%I:%M %p")

    # Format medications for prompt
    med_lines = []
    for m in medications:
        mname = m.get("name", "")
        schedule = m.get("schedule", "")
        times = ", ".join(m.get("reminder_times", []))
        notes = m.get("notes", m.get("notes_en", ""))
        med_lines.append(f"- {mname}: {schedule} (times: {times}). Notes: {notes}")
    meds_text = "\n".join(med_lines) if med_lines else "No medications on file."

    # Paradigm shift context for prompt
    if acute:
        mode = "ACUTE CARE MODE"
        diet_context = (
            f"IMPORTANT: The patient has ACTIVE ACUTE EVENTS: {', '.join(acute)}. "
            f"You MUST suppress all chronic dietary recommendations (millets, chana, rajma, "
            f"high-fiber foods). Instead, ONLY recommend acute-phase safe foods: "
            f"plain khichdi, white rice, banana, plain curd, ORS, coconut water, nimbu paani. "
            f"Hydration is the PRIORITY. Mention ORS prominently."
        )
    else:
        mode = "CHRONIC MANAGEMENT MODE"
        conditions_text = ", ".join(chronic) if chronic else "general wellness"
        diet_context = (
            f"The patient's conditions are: {conditions_text}. "
            f"Recommend appropriate chronic-condition foods: "
            f"{'millets (ragi, bajra, jowar), chana, moong dal, leafy greens, low-GI fruits' if 'Type 2 Diabetes' in chronic else 'balanced whole grains and legumes'}. "
            f"{'Avoid salt, pickles, papad for hypertension.' if 'Hypertension' in chronic else ''}"
        )

    lang_instruction = (
        "Write primarily in Hindi (Devanagari script) with English for medication names and medical terms. "
        "Use a warm, conversational Hinglish tone — like speaking to your grandmother."
        if language == "Hindi"
        else "Write in simple, warm English. Avoid medical jargon."
    )

    prompt = f"""You are AyuGuard, a compassionate caregiver assistant. Generate a warm, cohesive daily care message for this patient.

PATIENT PROFILE:
- Name / Preferred Address: {name}
- Age: {age}
- Location: {location}
- Mode: {mode}
- Current time: {time_str}, Greeting period: {greeting_en} / {greeting_time}

MEDICATIONS ACTIVE:
{meds_text}

DIETARY CONTEXT:
{diet_context}

LANGUAGE: {lang_instruction}

STRUCTURE YOUR MESSAGE IN EXACTLY THESE 4 SECTIONS:
1. 🙏 GREETING — Personal, warm greeting using their name and the time of day
2. 💊 MEDICATION REMINDERS — List each active medication with timing. Use the exact medication names. Make it easy to follow. Include notes.
3. 🍽️ TODAY'S MEAL PLAN — Suggest breakfast, lunch, dinner, and 1-2 healthy snacks based on the current mode ({mode}). Be specific with Indian food names.
4. 💪 WELLNESS CLOSING — A warm, motivating closing message (2-3 sentences). Include a reminder to drink enough water and to contact their doctor if anything feels wrong.

Keep the total message under 350 words. Do NOT use formal headers — make it flow naturally like a voice message from a caring grandchild.
"""
    return prompt


# ── Gemini API call ─────────────────────────────────────────────────────────────

def generate_message_via_gemini(prompt: str) -> str:
    """Call Gemini to generate the bundled message."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY not set. Add it to ayuguard/.env\n"
            "Example: GOOGLE_API_KEY=AIza..."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError(
            "google-genai not installed. Run: pip install google-adk"
        )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=600,
            system_instruction=(
                "You are AyuGuard — a warm, caring caregiver assistant for elderly patients "
                "in India. You write in a gentle, respectful, grandchild-to-grandparent tone."
            ),
        ),
    )
    return response.text.strip()


# ── Fallback template (no API key) ─────────────────────────────────────────────

def generate_message_template(profile: dict, language: str = "Hindi") -> str:
    """Simple template-based fallback when no API key is available."""
    patient = profile.get("patient", {})
    name = patient.get("preferred_name") or patient.get("name", "")
    acute = profile.get("acute_events", [])
    medications = profile.get("medications", [])

    now = datetime.now()
    is_morning = 5 <= now.hour < 12

    if language == "Hindi":
        greeting = f"🙏 नमस्ते {name}जी!"
        if is_morning:
            greeting += " सुबह की शुभकामनाएँ!"

        med_section = "\n💊 आज की दवाइयाँ:\n"
        for m in medications:
            med_section += f"  • {m.get('name')} — {m.get('schedule', '')}\n"
            if m.get("notes"):
                med_section += f"    ({m['notes']})\n"

        if acute:
            events = "、".join(acute)
            diet_section = (
                f"\n🍽️ आज का खाना ({events} के कारण हल्का खाना):\n"
                "  सुबह: ORS पानी + 1 केला\n"
                "  दोपहर: सादी खिचड़ी (चावल + मूंग दाल) + थोड़ी दही\n"
                "  शाम: नारियल पानी + साबूदाना खिचड़ी\n"
                "  रात: सादा चावल + पतली दाल का सूप\n"
                "  ⚠️ तला-भुना, मसालेदार, और मैदा से परहेज़ करें।"
            )
        else:
            diet_section = (
                "\n🍽️ आज का खाना:\n"
                "  सुबह: रागी दलिया + 1 उबला अंडा या मूंग दाल चीला\n"
                "  दोपहर: बाजरे की रोटी + पालक दाल + सलाद\n"
                "  शाम: मुट्ठी भर भुना चना\n"
                "  रात: खिचड़ी + दही"
            )

        closing = "\n💪 खूब पानी पिएं, अपनी दवाइयाँ समय पर लें, और कोई तकलीफ हो तो डॉक्टर को ज़रूर बताएं। आप जल्दी ठीक होंगी! 🌸"
        return greeting + med_section + diet_section + closing
    else:
        return (
            f"Hello {name}! Wishing you a healthy day.\n\n"
            + "💊 Medications: "
            + "; ".join(f"{m['name']} ({m.get('schedule','')})" for m in medications)
            + "\n\n💧 Stay hydrated and take your medicines on time. Take care!"
        )


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AyuGuard Ambient Bundler — Generate daily care message from health profile"
    )
    parser.add_argument(
        "--language",
        choices=["Hindi", "English"],
        default=None,
        help="Override patient's preferred language (default: from profile)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save message to file instead of printing to stdout",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use template-based fallback (no API call)",
    )
    args = parser.parse_args()

    # Load profile
    try:
        profile = load_profile()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    language = args.language or profile.get("patient", {}).get("language", "Hindi")

    print("=" * 60, file=sys.stderr)
    print("  AyuGuard Ambient Bundler", file=sys.stderr)
    print(f"  Patient : {profile.get('patient', {}).get('name', 'Unknown')}", file=sys.stderr)
    print(f"  Language: {language}", file=sys.stderr)
    print(f"  Acute   : {profile.get('acute_events', [])}", file=sys.stderr)
    print(f"  Chronic : {profile.get('chronic_conditions', [])}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Generate message
    if args.no_llm or not os.environ.get("GOOGLE_API_KEY"):
        if not os.environ.get("GOOGLE_API_KEY"):
            print("⚠️  No GOOGLE_API_KEY — using template fallback", file=sys.stderr)
        message = generate_message_template(profile, language)
    else:
        print("🤖 Calling Gemini API...", file=sys.stderr)
        try:
            prompt = build_bundler_prompt(profile, language_override=args.language)
            message = generate_message_via_gemini(prompt)
        except Exception as e:
            print(f"⚠️  Gemini call failed: {e}\n   Falling back to template.", file=sys.stderr)
            message = generate_message_template(profile, language)

    # Output
    separator = "\n" + "─" * 60 + "\n"
    output_text = separator + message + separator

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        print(f"✅ Message saved to: {args.output}", file=sys.stderr)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
