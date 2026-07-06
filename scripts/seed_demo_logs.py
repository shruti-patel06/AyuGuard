#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AyuGuard Demo Seed Script
==========================
Pre-seeds 14 days of realistic, individually harmless caregiver logs
that converge into an early warning pattern on Day 14.

Demo scenario: Rajan, 68-year-old male, fatigue + thirst + vision changes
Matches "Diabetes" cluster from the real dataset on the final trigger.

No single day looks alarming. Together they cross the threshold.

Run from project root (ayuguard-care-platform/):
  python scripts/seed_demo_logs.py
"""
from __future__ import annotations

import io
import sys
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path so ayuguard package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from ayuguard.tools.symptom_store import _load_store, _save_store
from ayuguard.tools.patient_profile import save_patient_profile


def seed() -> None:
    store = _load_store()

    # Initialise patient record
    patient_id = "patient_001"
    if patient_id not in store["patients"]:
        store["patients"][patient_id] = {
            "name": "Rajan Sharma",
            "age": 68,
            "created_at": datetime.now().isoformat(),
            "logs": [],
        }
    else:
        # Clear existing logs for a clean demo run
        store["patients"][patient_id]["logs"] = []

    # Seed patient profile so onboarding is skipped in the demo session
    _save_store(store)  # flush before calling save_patient_profile
    save_patient_profile(
        patient_name="Rajan Sharma",
        patient_age=68,
        caregiver_name="Priya",
        caregiver_relationship="daughter",
        known_conditions="Type 2 Diabetes, Hypertension",
        language="English",
        patient_id=patient_id,
    )
    store = _load_store()  # reload after profile save

    # Clear cooldowns too so escalation fires fresh
    if "alert_cooldowns" in store:
        store["alert_cooldowns"].pop(patient_id, None)

    today = datetime.now()

    # ── Seed entries: individually harmless, collectively alarming ─────────────
    # Pattern builds towards "Diabetes" cluster (dataset.csv):
    #   fatigue, weight_loss, increased_appetite, polyuria, blurred_and_distorted_vision,
    #   irregular_sugar_level, excessive_hunger
    seed_entries = [
        # (days_ago, symptom, severity, caregiver_note)
        # 13 unique days → persistence drives composite above escalate threshold
        (13, "fatigue",            "mild",     "Dad seemed tired today, went to bed early after dinner"),
        (12, "increased thirst",   "mild",     "He drank a lot of water today — refilled his bottle twice"),
        (11, "fatigue",            "mild",     "Still tired, slept an extra hour in the afternoon"),
        (10, "increased thirst",   "mild",     "Very thirsty again, kept asking for water"),
        ( 9, "blurry vision",      "mild",     "Mentioned his vision was a bit blurry while reading newspaper"),
        ( 8, "weight loss",        "mild",     "Weight down roughly 1 kg compared to last week"),
        ( 7, "fatigue",            "mild",     "Low energy, did not want to go for his evening walk"),
        ( 6, "increased thirst",   "mild",     "Thirsty again — had 6-7 glasses of water through the day"),
        ( 5, "frequent urination", "mild",     "Bathroom trips more often than usual, including at night"),
        ( 4, "fatigue",            "moderate", "Very tired today, skipped lunch, felt weak"),
        ( 3, "blurry vision",      "mild",     "Eyes bothering him again while reading"),
        ( 2, "frequent urination", "mild",     "Had to get up 3 times at night"),
        ( 1, "fatigue",            "moderate", "Tired and irritable — no energy for his walk"),
        ( 0, "increased thirst",   "mild",     "Drinking a lot of water again today"),
    ]

    logs = store["patients"][patient_id]["logs"]
    print("\nAyuGuard Demo Seed")
    print("=" * 62)
    print(f"Patient: Rajan (68) | patient_id: {patient_id}")
    print("=" * 62)

    for days_ago, symptom, severity, note in seed_entries:
        entry_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        entry = {
            "symptom": symptom,
            "severity": severity,
            "date": entry_date,
            "source": "log",
            "notes": note,
            "stored_at": datetime.now().isoformat(),
        }
        logs.append(entry)
        print(f"  [{entry_date}]  {symptom:<22} ({severity})")

    _save_store(store)

    print("=" * 62)
    print(f"Seeded {len(seed_entries)} log entries for {patient_id}")
    print()
    print("Pattern summary:")
    print("  fatigue (5x) + increased thirst (4x) + frequent urination (2x)")
    print("  + blurry vision (2x) + weight loss (1x)")
    print("  Spread over 14 days -> matches Diabetes cluster in dataset")
    print()
    print("Next steps:")
    print("  1. Ensure ayuguard/.env has your GOOGLE_API_KEY")
    print("  2. Run:  adk web   (from ayuguard-care-platform/ directory)")
    print("  3. Open: http://localhost:8000")
    print()
    print("Demo prompt to try:")
    print('  "Dad was tired again today and very thirsty"')
    print("  Expected: pipeline fires -> ESCALATE -> warm Diabetes-pattern message")
    print()
    print("Low-urgency test:")
    print('  "He had a slight cough today"')
    print("  Expected: log saved -> LOW urgency -> brief reassurance only")
    print()


if __name__ == "__main__":
    seed()
