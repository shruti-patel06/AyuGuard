"""
AyuGuard Communication Tool
==============================
A typed Python function tool that generates warm, localized caregiver messages.

Addresses both the caregiver and patient by name in every response.
"""
from __future__ import annotations

import os

import google.genai as genai

_SYSTEM_INSTRUCTION = """You are the voice of AyuGuard (आयुगार्ड).
You write warm, caring messages for family caregivers and elderly patients.

RULES:
- ALWAYS address the caregiver by their first name at the start (e.g. "Priya,")
- ALWAYS refer to the patient by their name throughout — NEVER say "the patient"
- Tone: caring, knowledgeable family member — NOT a doctor, not clinical
- Keep under 150 words
- Be SPECIFIC — use the exact symptoms and dates given to you
- NEVER diagnose ("you have X") — say "this kind of pattern is sometimes associated with..."
- NEVER invent symptoms, dates, or precautions not given to you
- For urgency=escalate: name the symptoms + duration; recommend mentioning to doctor;
  include the dataset precautions warmly; close with reassurance
- For urgency=watch: gently note the pattern is building; suggest keeping a log;
  recommend mentioning at next scheduled doctor visit; stay calm
- For urgency=low: confirm the symptom was logged; 1-2 sentences of warm reassurance
- Language=Hindi → respond in Hindi (Devanagari) with English for medical terms
- Language=Hinglish → comfortable mix, like a caring relative would speak
- Language=English → clear, simple English, no jargon
- Always end warmly. AyuGuard supplements — never replaces — the doctor's advice.
"""


def generate_caregiver_message(
    urgency: str,
    top_disease: str,
    precautions: str,
    pattern_summary: str,
    caregiver_original_message: str = "",
    language: str = "English",
    patient_name: str = "",
    caregiver_name: str = "",
) -> str:
    """
    Generate a warm, localized AyuGuard message that addresses caregiver and patient by name.

    Call this AFTER compute_trend_score() has returned the urgency and pattern details.

    Args:
        urgency: One of "low", "watch", or "escalate" — from compute_trend_score().
        top_disease: The top matching disease name from the dataset, e.g. "Diabetes".
        precautions: Dataset precautions as a comma-separated string.
        pattern_summary: The pattern_summary string from compute_trend_score().
        caregiver_original_message: The caregiver's original message (optional).
        language: "English", "Hindi", or "Hinglish". Default: "English".
        patient_name: The patient's name from the saved profile (e.g. "Rajan Sharma").
                      Always pass this so the response addresses the patient by name.
        caregiver_name: The caregiver's name from the saved profile (e.g. "Priya").
                        Always pass this so the response opens with the caregiver's name.

    Returns:
        A warm plain-text message string that uses both names throughout.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return (
            "I've noted this symptom and AyuGuard is watching the pattern. "
            "Please ensure your GOOGLE_API_KEY is set. Take care and stay well. 🌸"
        )

    client = genai.Client(api_key=api_key)

    name_context = ""
    if caregiver_name:
        name_context += f"Caregiver's name: {caregiver_name} — open the message addressing them by name.\n"
    if patient_name:
        name_context += f"Patient's name: {patient_name} — refer to the patient by this name throughout.\n"

    prompt = (
        f"{name_context}"
        f"Urgency level: {urgency}\n"
        f"Top dataset pattern match: {top_disease}\n"
        f"Dataset precautions: {precautions}\n"
        f"Pattern observed: {pattern_summary}\n"
        f"Caregiver said: {caregiver_original_message or '(not provided)'}\n"
        f"Response language: {language}\n\n"
        "Write the AyuGuard caregiver message now. "
        "Remember to address the caregiver and patient by name."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                max_output_tokens=250,
                temperature=0.4,
            ),
        )
        return response.text.strip()
    except Exception as exc:  # noqa: BLE001
        name_str = f" for {patient_name}" if patient_name else ""
        return (
            f"Symptom logged{name_str}. AyuGuard is tracking the pattern "
            f"(urgency: {urgency}). Keep logging daily — patterns across days matter most. "
            f"Stay well! 🌸 [Note: {exc}]"
        )
