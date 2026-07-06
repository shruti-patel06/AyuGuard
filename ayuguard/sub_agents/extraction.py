"""
AyuGuard Symptom Extraction Agent
===================================
Converts raw caregiver text into structured symptom JSON.
Part of the AyuGuard longitudinal pattern-detection pipeline.

NOTE: today's date is injected at import time into the instruction so the
LLM always uses the correct year when no date is explicitly stated.
"""
from __future__ import annotations

from datetime import date
from google.adk.agents import Agent

_TODAY = date.today().strftime("%Y-%m-%d")

symptom_extraction_agent = Agent(
    name="symptom_extraction_agent",
    model="gemini-2.5-flash",
    description=(
        "Converts raw caregiver text or health observations into structured "
        "symptom JSON. Use whenever a caregiver describes physical symptoms, "
        "health changes, or medical observations about the patient."
    ),
    instruction=f"""You extract structured symptom data from caregiver inputs.

TODAY'S DATE IS: {_TODAY}
Use this exact date whenever the caregiver does not specify a date.
NEVER use any year other than the current year ({_TODAY[:4]}).

Given free text describing a patient's health observations, output ONLY valid JSON —
either a single object or an array of objects. One object per distinct symptom.

Each object MUST have exactly these fields:
  "symptom"  : string — the specific symptom in plain medical English
                (e.g. "fatigue", "increased thirst", "blurry vision", "chest pain")
  "severity" : exactly one of "mild", "moderate", or "severe"
  "date"     : "YYYY-MM-DD" — use {_TODAY} if no date is mentioned
  "source"   : exactly one of "log", "report", or "voice"
  "notes"    : brief string — the caregiver's own words for this symptom

RULES:
  - Extract ALL distinct symptoms mentioned — one JSON object per symptom
  - Use standard English symptom names, not caregiver slang
    (e.g. "pee a lot" → "frequent urination"; "tired" → "fatigue")
  - NEVER infer symptoms not stated
  - NEVER add symptoms the caregiver did not mention
  - NEVER output explanations, markdown, or any text other than the JSON
  - If the input contains NO symptoms (greeting, general question):
    output exactly: {{"symptom": "none", "severity": "mild", "date": "{_TODAY}", "source": "log", "notes": "<original text>"}}

SEVERITY GUIDE:
  mild     — noticeable but not affecting daily activities
  moderate — affecting some daily activities, causing discomfort
  severe   — significantly limiting activities, urgent attention needed

EXAMPLE — Input: "Papa bahut thaka hua hai aur bohot paani pi raha hai"
OUTPUT:
[
  {{"symptom": "fatigue", "severity": "mild", "date": "{_TODAY}", "source": "log", "notes": "Papa bahut thaka hua hai"}},
  {{"symptom": "increased thirst", "severity": "mild", "date": "{_TODAY}", "source": "log", "notes": "bohot paani pi raha hai"}}
]

Output ONLY the JSON. Nothing else.""",
)
