"""
AyuGuard Patient Profile Tool
===============================
Manages the patient's persistent profile — name, age, caregiver relationship,
known conditions, preferred language.

Stored alongside symptom logs in ayuguard/data/symptom_logs.json under a
top-level "profiles" key, so it Firestore-compatible.

Profile schema:
  {
    "name": "Rajan",
    "age": 68,
    "caregiver_name": "Priya",
    "caregiver_relationship": "daughter",
    "known_conditions": ["Type 2 Diabetes", "Hypertension"],
    "language": "English",
    "profile_complete": true,
    "created_at": "...",
    "updated_at": "..."
  }
"""
from __future__ import annotations

from datetime import datetime
from ayuguard.tools.symptom_store import _load_store, _save_store


def get_patient_profile(patient_id: str = "patient_001") -> dict:
    """
    Retrieve the saved patient profile for a given patient ID.

    Call this at the START of every conversation to check whether a
    patient profile has already been set up. If profile_complete is False
    or the profile does not exist, ask the caregiver for patient details
    before proceeding with symptom logging.

    Args:
        patient_id: The patient identifier (default "patient_001").

    Returns:
        dict with:
          - status: "found" | "not_found"
          - profile_complete: bool
          - name, age, caregiver_name, caregiver_relationship,
            known_conditions, language  (all empty/None if not set)
          - patient_id
    """
    store = _load_store()
    profiles = store.get("profiles", {})
    profile = profiles.get(patient_id)

    if not profile:
        return {
            "status": "not_found",
            "profile_complete": False,
            "patient_id": patient_id,
            "name": None,
            "age": None,
            "caregiver_name": None,
            "caregiver_relationship": None,
            "known_conditions": [],
            "language": "English",
        }

    return {
        "status": "found",
        "profile_complete": profile.get("profile_complete", False),
        "patient_id": patient_id,
        "name": profile.get("name"),
        "age": profile.get("age"),
        "caregiver_name": profile.get("caregiver_name"),
        "caregiver_relationship": profile.get("caregiver_relationship"),
        "known_conditions": profile.get("known_conditions", []),
        "language": profile.get("language", "English"),
        "updated_at": profile.get("updated_at"),
    }


def save_patient_profile(
    patient_name: str,
    patient_age: int,
    caregiver_name: str,
    caregiver_relationship: str,
    known_conditions: str = "",
    language: str = "English",
    patient_id: str = "patient_001",
) -> dict:
    """
    Save or update the patient profile.

    Call this after collecting patient details from the caregiver at the
    start of the first session. Once saved, the profile is loaded at the
    start of every future session so the agent addresses the patient by name.

    Args:
        patient_name: The patient's full name or preferred name, e.g. "Rajan Sharma".
        patient_age: The patient's age in years, e.g. 68.
        caregiver_name: The caregiver's own name, e.g. "Priya".
        caregiver_relationship: How the caregiver is related to the patient,
                                e.g. "daughter", "son", "spouse", "caregiver".
        known_conditions: Comma-separated list of known medical conditions,
                          e.g. "Type 2 Diabetes, Hypertension".
                          Leave empty if none known.
        language: Preferred response language — "English", "Hindi", or "Hinglish".
                  Default: "English".
        patient_id: Internal patient identifier (default "patient_001").

    Returns:
        dict with status, patient_id, and the saved profile fields.
    """
    store = _load_store()
    now = datetime.now().isoformat()

    store.setdefault("profiles", {})

    conditions = [
        c.strip()
        for c in known_conditions.split(",")
        if c.strip()
    ] if known_conditions else []

    profile = {
        "name": patient_name.strip(),
        "age": patient_age,
        "caregiver_name": caregiver_name.strip(),
        "caregiver_relationship": caregiver_relationship.strip(),
        "known_conditions": conditions,
        "language": language.strip(),
        "profile_complete": True,
        "updated_at": now,
        "created_at": store["profiles"].get(patient_id, {}).get("created_at", now),
    }

    store["profiles"][patient_id] = profile

    # Also update the patient name in the logs entry if it exists
    if patient_id in store.get("patients", {}):
        store["patients"][patient_id]["name"] = patient_name.strip()

    _save_store(store)

    return {
        "status": "success",
        "patient_id": patient_id,
        "message": (
            f"Profile saved for {patient_name} (age {patient_age}). "
            f"Caregiver: {caregiver_name} ({caregiver_relationship}). "
            f"Known conditions: {', '.join(conditions) if conditions else 'none logged'}. "
            f"Language: {language}."
        ),
        "profile": profile,
    }
