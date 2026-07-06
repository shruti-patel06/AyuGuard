"""
Rolling 14-Day Decay-Weighted Trend Window
==========================================
Aggregates sparse, irregular symptom logs into a single pattern vector.

Key design:
  weight = exp(-DECAY_RATE * days_ago)
  → today  = 1.00  (full weight)
  → 7 days = 0.50  (half weight)
  → 14 days = 0.25  (quarter weight)

This correctly handles the caregiver's inconsistent logging behaviour —
a symptom mentioned 3 days ago counts more than one mentioned 10 days ago,
even if each was logged only once.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from caretrend.tools.symptom_store import _load_store

DECAY_RATE: float = 0.1
SEVERITY_MAP: dict[str, float] = {"mild": 1.0, "moderate": 2.0, "severe": 3.0}


def compute_pattern_vector(patient_id: str, window_days: int = 14) -> dict:
    """
    Compute a decay-weighted pattern vector from a patient's recent symptom logs.

    Aggregates every symptom entry within the rolling window into a weighted
    score per symptom type. Used by the urgency scorer to determine persistence
    and severity before running the similarity search.

    Args:
        patient_id: Unique patient identifier.
        window_days: Size of the rolling window in days (default: 14).

    Returns:
        A dict with:
          - symptom_scores: {symptom_name: weighted_score} sorted descending
          - persistence_days: number of distinct calendar days with any log
          - avg_severity: decay-weighted average severity (1.0=mild … 3.0=severe)
          - symptom_text: space-separated symptom names (for embedding)
          - log_count: total log entries within the window
          - date_range: human-readable "Jun 22 – Jul 5" string
    """
    store = _load_store()
    patient = store.get("patients", {}).get(patient_id, {})
    logs: list[dict] = patient.get("logs", [])

    now = datetime.now()
    cutoff = now - timedelta(days=window_days)

    symptom_scores: dict[str, float] = {}
    weighted_severities: list[float] = []
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

        severity_val = SEVERITY_MAP.get(log.get("severity", "mild").lower(), 1.0)
        days_ago = max(0, (now - log_date).days)
        weight = math.exp(-DECAY_RATE * days_ago)

        symptom_scores[symptom] = symptom_scores.get(symptom, 0.0) + weight
        weighted_severities.append(severity_val * weight)
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

    total_weight = sum(weighted_severities) / len(weighted_severities) if weighted_severities else 1.0
    sorted_syms = sorted(symptom_scores.items(), key=lambda x: -x[1])
    symptom_text = " ".join(sym for sym, _ in sorted_syms)

    date_range = (
        f"{min_date.strftime('%b %d')} – {max_date.strftime('%b %d')}"
        if min_date and max_date
        else "—"
    )

    return {
        "symptom_scores": dict(sorted_syms),
        "persistence_days": len(active_days),
        "avg_severity": round(total_weight, 2),
        "symptom_text": symptom_text,
        "log_count": log_count,
        "date_range": date_range,
    }


def _in_window(log: dict, cutoff: datetime) -> bool:
    """Helper to check if a log entry falls within the cutoff date."""
    try:
        return datetime.strptime(log.get("date", "2000-01-01"), "%Y-%m-%d") >= cutoff
    except ValueError:
        return False
