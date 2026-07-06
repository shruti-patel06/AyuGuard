"""
AyuGuard Rolling 14-Day Decay-Weighted Trend Window
=====================================================
Aggregates sparse, irregular caregiver logs into a single pattern vector.

Each symptom's contribution decays exponentially with age:
  weight = exp(-0.1 × days_ago)
  today  = 1.00  |  7 days ago = 0.50  |  14 days ago = 0.25

The avg_severity combines:
  - Caregiver-reported severity (mild=1, moderate=2, severe=3)
  - Dataset clinical severity weight from Symptom-severity.csv (1–7, normalised to 1–3)

This gives a richer severity signal than either source alone.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from ayuguard.tools.symptom_store import _load_store
from ayuguard.tools.dataset_search import get_symptom_severity_weight

DECAY_RATE: float = 0.1
_CAREGIVER_SEVERITY = {"mild": 1.0, "moderate": 2.0, "severe": 3.0}


def compute_pattern_vector(patient_id: str, window_days: int = 14) -> dict:
    """
    Compute the decay-weighted symptom pattern vector for a patient.

    Aggregates all symptom logs within the rolling window into per-symptom
    weighted scores, persistence metrics, and a combined severity estimate.

    Args:
        patient_id: Unique patient identifier.
        window_days: Size of the rolling window in days (default: 14).

    Returns:
        dict with:
          - symptom_scores: {symptom: weighted_score} sorted descending
          - persistence_days: distinct calendar days with any logged symptom
          - avg_severity: blended caregiver + dataset severity (1–3 scale)
          - symptom_text: space-separated symptom names for search
          - log_count: total log entries in window
          - date_range: "Jun 22 – Jul 5"
    """
    store = _load_store()
    logs: list[dict] = (
        store.get("patients", {})
        .get(patient_id, {})
        .get("logs", [])
    )

    now = datetime.now()
    cutoff = now - timedelta(days=window_days)

    symptom_scores: dict[str, float] = {}
    combined_severities: list[float] = []
    active_days: set[str] = set()
    min_date: datetime | None = None
    max_date: datetime | None = None
    log_count = 0

    for log in logs:
        try:
            log_date = datetime.strptime(log.get("date", "2000-01-01"), "%Y-%m-%d")
        except ValueError:
            continue
        if log_date < cutoff:
            continue

        symptom = log.get("symptom", "").strip().lower()
        if not symptom or symptom in ("none", "unclear"):
            continue

        # Temporal decay weight
        days_ago = max(0, (now - log_date).days)
        decay_w = math.exp(-DECAY_RATE * days_ago)

        # Blended severity: caregiver report + dataset clinical weight
        caregiver_sev = _CAREGIVER_SEVERITY.get(
            log.get("severity", "mild").lower(), 1.0
        )
        dataset_sev_raw = get_symptom_severity_weight(symptom)          # 1–7
        dataset_sev_norm = (dataset_sev_raw / 7.0) * 3.0               # → 1–3
        blended_sev = (caregiver_sev + dataset_sev_norm) / 2.0

        symptom_scores[symptom] = symptom_scores.get(symptom, 0.0) + decay_w
        combined_severities.append(blended_sev * decay_w)
        active_days.add(log_date.strftime("%Y-%m-%d"))
        log_count += 1

        if min_date is None or log_date < min_date:
            min_date = log_date
        if max_date is None or log_date > max_date:
            max_date = log_date

    if not symptom_scores:
        return {
            "symptom_scores": {},
            "persistence_days": 0,
            "avg_severity": 0.0,
            "symptom_text": "",
            "log_count": 0,
            "date_range": "no data in window",
        }

    avg_sev = (
        sum(combined_severities) / len(combined_severities)
        if combined_severities else 1.0
    )

    sorted_syms = sorted(symptom_scores.items(), key=lambda x: -x[1])
    symptom_text = " ".join(s for s, _ in sorted_syms)
    date_range = (
        f"{min_date.strftime('%b %d')} – {max_date.strftime('%b %d')}"
        if min_date and max_date else "—"
    )

    return {
        "symptom_scores": dict(sorted_syms),
        "persistence_days": len(active_days),
        "avg_severity": round(avg_sev, 2),
        "symptom_text": symptom_text,
        "log_count": log_count,
        "date_range": date_range,
    }
