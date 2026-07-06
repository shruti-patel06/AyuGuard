"""
AyuGuard Deterministic Urgency Scorer
======================================
THE SINGLE SOURCE OF URGENCY DECISIONS IN AYUGUARD.

The LLM never decides what is dangerous.
This formula decides that.
The LLM only explains it.

Formula:
  composite = similarity × 0.50
            + (persistence_days / 14) × 0.30
            + (avg_severity / 3) × 0.20

  composite >= 0.65  →  "escalate"  (pattern worth a doctor visit)
  composite >= 0.42  →  "watch"     (pattern emerging, keep monitoring)
  composite <  0.42  →  "low"       (log saved, nothing to flag yet)

A 48-hour cooldown per (patient, disease) pair prevents alert fatigue.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ayuguard.tools.trend_window import compute_pattern_vector
from ayuguard.tools.dataset_search import search_disease_patterns
from ayuguard.tools.symptom_store import _load_store, _save_store

_ESCALATE: float = 0.65
_WATCH: float = 0.42
_COOLDOWN_HOURS: int = 48


def compute_urgency(similarity: float, persistence_days: int, avg_severity: float) -> str:
    """
    Deterministic urgency formula — no LLM, no randomness.

    Args:
        similarity: Dataset match score (0.0–1.0).
        persistence_days: Distinct days with logged symptoms in the 14-day window.
        avg_severity: Blended caregiver + dataset severity on a 1–3 scale.

    Returns:
        One of "escalate", "watch", or "low".
    """
    score = (
        similarity * 0.50
        + min(persistence_days / 14.0, 1.0) * 0.30
        + min(avg_severity / 3.0, 1.0) * 0.20
    )
    if score >= _ESCALATE:
        return "escalate"
    if score >= _WATCH:
        return "watch"
    return "low"


def _in_cooldown(patient_id: str, disease: str) -> bool:
    store = _load_store()
    ts = store.get("alert_cooldowns", {}).get(patient_id, {}).get(disease)
    if not ts:
        return False
    try:
        return (datetime.now() - datetime.fromisoformat(ts)) < timedelta(hours=_COOLDOWN_HOURS)
    except ValueError:
        return False


def _record_cooldown(patient_id: str, disease: str) -> None:
    store = _load_store()
    store.setdefault("alert_cooldowns", {}).setdefault(patient_id, {})
    store["alert_cooldowns"][patient_id][disease] = datetime.now().isoformat()
    _save_store(store)


def compute_trend_score(patient_id: str) -> dict:
    """
    Compute the full longitudinal trend urgency score for a patient.

    Runs the complete deterministic pipeline:
      1. 14-day decay-weighted pattern vector (trend_window)
      2. Dataset similarity search against 41 real disease clusters (dataset_search)
      3. Urgency scoring formula — no LLM
      4. 48-hour cooldown gate to prevent alert fatigue

    The LLM orchestrator MUST use the urgency returned here.
    It must NEVER override or re-interpret this result.

    Args:
        patient_id: Unique patient identifier, e.g. "patient_001".

    Returns:
        dict with:
          - status, urgency ("low"/"watch"/"escalate")
          - similarity_score, persistence_days, avg_severity
          - composite_score (raw formula output — fully auditable)
          - top_disease, top_disease_description, top_disease_precautions
          - matched_symptoms (which dataset symptoms were matched)
          - pattern_summary (human-readable string for the Communication Agent)
          - cooldown_active (bool — True means alert suppressed)
          - date_range, log_count
    """
    # Step 1 — Build pattern vector
    pattern = compute_pattern_vector(patient_id)

    if not pattern["symptom_text"]:
        return {
            "status": "success",
            "urgency": "low",
            "similarity_score": 0.0,
            "persistence_days": 0,
            "avg_severity": 0.0,
            "composite_score": 0.0,
            "top_disease": None,
            "top_disease_description": "",
            "top_disease_precautions": [],
            "matched_symptoms": [],
            "pattern_summary": "No symptoms logged in the last 14 days.",
            "cooldown_active": False,
            "date_range": "—",
            "log_count": 0,
        }

    # Step 2 — Dataset similarity search
    try:
        result = search_disease_patterns(symptom_list=pattern["symptom_text"], top_k=1)
        if result["status"] == "success" and result["matches"]:
            top = result["matches"][0]
            similarity = top["similarity_score"]
            top_disease = top["disease"]
            top_desc = top["description"]
            top_prec = top["precautions"]
            matched_syms = top["matched_symptoms"]
        else:
            similarity, top_disease, top_desc, top_prec, matched_syms = (
                0.0, "Unknown", "", [], []
            )
    except Exception as exc:  # noqa: BLE001
        similarity, top_disease, top_desc, top_prec, matched_syms = (
            0.0, f"Search error: {exc}", "", [], []
        )

    # Step 3 — Deterministic urgency
    persistence_days = pattern["persistence_days"]
    avg_severity = pattern["avg_severity"]
    urgency = compute_urgency(similarity, persistence_days, avg_severity)

    composite = (
        similarity * 0.50
        + min(persistence_days / 14.0, 1.0) * 0.30
        + min(avg_severity / 3.0, 1.0) * 0.20
    )

    # Step 4 — Cooldown gate
    cooldown_active = False
    if urgency in ("watch", "escalate") and top_disease not in (None, "Unknown"):
        if _in_cooldown(patient_id, top_disease):
            cooldown_active = True
            urgency = "low"
        else:
            _record_cooldown(patient_id, top_disease)

    # Step 5 — Human-readable summary for the Communication Agent
    syms_listed = list(pattern["symptom_scores"].keys())[:6]
    sev_label = (
        "mild" if avg_severity <= 1.5
        else "moderate" if avg_severity <= 2.5
        else "severe"
    )
    pattern_summary = (
        f"Over {persistence_days} day(s) ({pattern['date_range']}), these symptoms "
        f"were observed: {', '.join(syms_listed)}. "
        f"Average severity: {sev_label}. "
        f"Closest dataset match: '{top_disease}' "
        f"(similarity {similarity:.1%}, composite score {composite:.3f})."
    )

    return {
        "status": "success",
        "urgency": urgency,
        "similarity_score": round(similarity, 4),
        "persistence_days": persistence_days,
        "avg_severity": round(avg_severity, 2),
        "composite_score": round(composite, 4),
        "top_disease": top_disease,
        "top_disease_description": top_desc,
        "top_disease_precautions": top_prec,
        "matched_symptoms": matched_syms,
        "pattern_summary": pattern_summary,
        "cooldown_active": cooldown_active,
        "date_range": pattern["date_range"],
        "log_count": pattern["log_count"],
        "symptom_scores": pattern["symptom_scores"],
    }
