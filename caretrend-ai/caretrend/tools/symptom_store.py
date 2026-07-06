"""
CareTrend Symptom Log Store
============================
Firestore-equivalent local JSON persistence layer.
Schema matches what Firestore documents would hold — swap in real Firestore
by replacing _load_store / _save_store with Firestore calls in a single file.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

# ── Path resolution ────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent.parent / "data"
_LOG_FILE = _HERE / "symptom_logs.json"


# ── Internal helpers (also used by urgency_scorer + trend_window) ──────────────

def _load_store() -> dict:
    """Load the full store from disk."""
    _HERE.mkdir(parents=True, exist_ok=True)
    if not _LOG_FILE.exists():
        store: dict = {"patients": {}, "alert_cooldowns": {}}
        _save_store(store)
        return store
    with _LOG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_store(store: dict) -> None:
    """Persist the store to disk as formatted JSON."""
    _HERE.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


# ── ADK Function Tools ─────────────────────────────────────────────────────────

def store_symptom_log(patient_id: str, symptom_json: str) -> dict:
    """
    Stores extracted symptom entries in the patient's persistent symptom log.

    This is the write interface to the CareTrend data layer (Firestore-equivalent).
    Call this after every successful extraction to ensure the longitudinal trend
    window has data to aggregate.

    Args:
        patient_id: Unique patient identifier, e.g. "patient_001".
        symptom_json: JSON string produced by the Extraction Agent. Can be a
                     single JSON object or an array of objects. Each entry must
                     contain: symptom (str), severity ("mild"/"moderate"/"severe"),
                     date ("YYYY-MM-DD"), source ("log"/"report"/"voice"), notes (str).

    Returns:
        A dict with: status ("success"/"error"), patient_id, entries_stored (int),
        total_log_count (int), and a message. On error, includes "message".
    """
    store = _load_store()

    # Parse symptom JSON
    try:
        data = json.loads(symptom_json)
        entries: list[dict] = [data] if isinstance(data, dict) else data
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "message": f"Invalid symptom_json: {exc}"}

    # Initialise patient record
    if patient_id not in store["patients"]:
        store["patients"][patient_id] = {
            "name": patient_id,
            "created_at": datetime.now().isoformat(),
            "logs": [],
        }

    # Append valid entries
    added = 0
    skipped = 0
    for entry in entries:
        symptom_val = str(entry.get("symptom", "")).strip().lower()
        if symptom_val in ("none", "", "unclear"):
            skipped += 1
            continue
        entry["stored_at"] = datetime.now().isoformat()
        store["patients"][patient_id]["logs"].append(entry)
        added += 1

    _save_store(store)

    return {
        "status": "success",
        "patient_id": patient_id,
        "entries_stored": added,
        "entries_skipped": skipped,
        "total_log_count": len(store["patients"][patient_id]["logs"]),
    }


def get_patient_history(patient_id: str, days: int = 14) -> dict:
    """
    Retrieves a summary of recent symptom history for a patient.

    Useful for the caregiver to review what has been logged, or as context
    for the Communication Agent when building a weekly summary.

    Args:
        patient_id: The patient identifier, e.g. "patient_001".
        days: Number of recent days to retrieve (default: 14).

    Returns:
        A dict with: status, patient_id, patient_name, total_logs (int),
        symptom_summary (list of {symptom, count} dicts sorted by frequency),
        date_range (str), and recent_entries (last 5 entries).
    """
    store = _load_store()

    if patient_id not in store["patients"]:
        return {
            "status": "success",
            "patient_id": patient_id,
            "total_logs": 0,
            "symptom_summary": [],
            "message": "No logs found for this patient. Start logging symptoms to begin trend tracking.",
        }

    cutoff = datetime.now() - timedelta(days=days)
    patient = store["patients"][patient_id]
    recent: list[dict] = []

    for log in patient.get("logs", []):
        try:
            log_date = datetime.strptime(log.get("date", "2000-01-01"), "%Y-%m-%d")
            if log_date >= cutoff:
                recent.append(log)
        except ValueError:
            recent.append(log)

    # Aggregate symptom counts
    counts: dict[str, int] = {}
    for log in recent:
        sym = log.get("symptom", "").strip().lower()
        if sym and sym != "none":
            counts[sym] = counts.get(sym, 0) + 1

    return {
        "status": "success",
        "patient_id": patient_id,
        "patient_name": patient.get("name", patient_id),
        "total_logs": len(recent),
        "symptom_summary": [
            {"symptom": k, "count": v}
            for k, v in sorted(counts.items(), key=lambda x: -x[1])
        ],
        "date_range": f"last {days} days",
        "recent_entries": recent[-5:],
    }
