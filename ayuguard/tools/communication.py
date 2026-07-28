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
- ALWAYS address the caregiver directly by her name at the very beginning of your message (e.g. "Namaste Priya! 🌿" or "Priya,"). NEVER start with "Call!" or abrupt words.
- ALWAYS refer to the patient as Rajan ji (or their name) throughout — NEVER say "the patient".
- Tone: caring, knowledgeable family member — NOT clinical or mechanical.
- Keep output concise, complete, and formatted as a single clean paragraph or bulleted list.
- NEVER repeat or duplicate sentences or phrases within your response.
- NEVER mention internal system terms like "automated scoring", "composite score", or "urgency formula".
- For urgency=escalate: State clearly that the symptoms are serious and require immediate medical attention / doctor visit; guide on what to do while waiting for help; end with warm support.
- For urgency=watch: Gently note the pattern is building; suggest keeping a log; recommend mentioning at next doctor visit.
- For urgency=low: Confirm the symptom was logged warmly; 1-2 sentences of reassurance.
- Always end warmly. AyuGuard supplements — never replaces — professional medical advice.
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
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "silken-dogfish-484814-g9")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        client = genai.Client(vertexai=True, project=project, location=location)
    else:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return (
                "I've noted this symptom and AyuGuard is watching the pattern. "
                "Please ensure your GOOGLE_API_KEY or Vertex AI credentials are set. Take care and stay well. 🌸"
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
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                max_output_tokens=300,
                temperature=0.7,
            ),
        )
        return response.text.strip()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        name_str = f" for {patient_name}" if patient_name else ""
        error_detail = str(exc)
        return (
            f"⚠️ AyuGuard could not generate a response right now.\n"
            f"Symptom logged{name_str} (urgency: {urgency}).\n"
            f"Error: {error_detail}\n"
            f"Please check that the GOOGLE_API_KEY in ayuguard/.env is valid and restart the servers."
        )
