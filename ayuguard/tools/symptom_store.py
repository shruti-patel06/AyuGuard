"""
AyuGuard Symptom Log Store
===========================
Firestore-equivalent local JSON persistence layer.
Schema is identical to what Firestore documents would hold —
swap in real Firestore by replacing _load_store/_save_store.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_LOG_FILE = _DATA_DIR / "symptom_logs.json"


def _load_store() -> dict:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _LOG_FILE.exists():
        store: dict = {"patients": {}, "alert_cooldowns": {}}
        _save_store(store)
        return store
    with _LOG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_store(store: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def store_symptom_log(patient_id: str, symptom_json: str) -> dict:
    """
    Store extracted symptom entries in the patient's persistent log.

    Writes to Firestore (when configured) AND local JSON (always).
    Called after every successful extraction. Each entry feeds the rolling
    14-day trend window that drives urgency scoring.

    Args:
        patient_id: Unique patient identifier, e.g. "patient_001".
        symptom_json: JSON string from the Extraction Agent — a single object
                     or an array. Each entry: symptom (str), severity
                     ("mild"/"moderate"/"severe"), date ("YYYY-MM-DD"),
                     source ("log"/"report"/"voice"), notes (str).

    Returns:
        dict with status, patient_id, entries_stored (int), total_log_count (int).
    """
    store = _load_store()

    try:
        data = json.loads(symptom_json)
        entries: list[dict] = [data] if isinstance(data, dict) else list(data)
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "message": f"Invalid symptom_json: {exc}"}

    if patient_id not in store["patients"]:
        store["patients"][patient_id] = {
            "name": patient_id,
            "created_at": datetime.now().isoformat(),
            "logs": [],
        }

    added = 0
    firestore_entries = []
    for entry in entries:
        sym = str(entry.get("symptom", "")).strip().lower()
        if sym in ("none", "", "unclear"):
            continue
        entry["stored_at"] = datetime.now().isoformat()
        store["patients"][patient_id]["logs"].append(entry)
        firestore_entries.append(entry)
        added += 1

    _save_store(store)

    # ── Firestore dual-write (best-effort) ────────────────────────────────────
    if firestore_entries:
        try:
            from ayuguard.firebase_client import get_firestore_client
            import uuid
            db = get_firestore_client()
            if db:
                col = (db.collection("patients")
                         .document(patient_id)
                         .collection("symptom_logs"))
                for entry in firestore_entries:
                    col.document(str(uuid.uuid4())).set(entry)
        except Exception:
            pass  # Firestore failure never breaks the pipeline

    return {
        "status": "success",
        "patient_id": patient_id,
        "entries_stored": added,
        "total_log_count": len(store["patients"][patient_id]["logs"]),
    }



def get_patient_history(patient_id: str, days: int = 14) -> dict:
    """
    Retrieve a summary of recent symptom history for a patient.

    Args:
        patient_id: The patient identifier, e.g. "patient_001".
        days: Number of recent days to retrieve (default: 14).

    Returns:
        dict with patient_name, total_logs, symptom_summary
        (sorted by frequency), date_range, and recent_entries (last 5).
    """
    store = _load_store()

    if patient_id not in store["patients"]:
        return {
            "status": "success",
            "patient_id": patient_id,
            "total_logs": 0,
            "symptom_summary": [],
            "message": "No logs yet. Start logging symptoms to begin trend tracking.",
        }

    cutoff = datetime.now() - timedelta(days=days)
    patient = store["patients"][patient_id]
    recent: list[dict] = []

    for log in patient.get("logs", []):
        try:
            d = datetime.strptime(log.get("date", "2000-01-01"), "%Y-%m-%d")
            if d >= cutoff:
                recent.append(log)
        except ValueError:
            recent.append(log)

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
