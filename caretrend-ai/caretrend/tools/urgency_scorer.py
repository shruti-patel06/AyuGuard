"""
Deterministic Urgency Scorer — No LLM in the Decision Path
============================================================
This is the technical safety centrepiece of CareTrend.

The LLM never decides what is dangerous.
A deterministic formula decides that.
The LLM only explains it.

Formula:
  composite = similarity × 0.5
            + (persistence_days / 14) × 0.3
            + (avg_severity / 3) × 0.2

  composite ≥ 0.65  → "escalate"
  composite ≥ 0.42  → "watch"
  composite < 0.42  → "low"

A 48-hour cooldown per (patient, cluster) pair prevents alert fatigue.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from caretrend.tools.trend_window import compute_pattern_vector
from caretrend.tools.vector_search import search_condition_patterns
from caretrend.tools.symptom_store import _load_store, _save_store

# ── Thresholds ─────────────────────────────────────────────────────────────────
_ESCALATE_THRESHOLD: float = 0.65
_WATCH_THRESHOLD: float = 0.42
_COOLDOWN_HOURS: int = 48


# ── Pure scoring formula ────────────────────────────────────────────────────────

def compute_urgency(similarity: float, persistence_days: int, avg_severity: float) -> str:
    """
    Deterministic urgency band — no LLM, no external calls.

    Args:
        similarity: Cosine similarity score from vector search (0.0–1.0).
        persistence_days: Number of distinct days with symptom logs in the window.
        avg_severity: Decay-weighted average severity (1.0=mild, 2.0=moderate, 3.0=severe).

    Returns:
        One of "escalate", "watch", or "low".
    """
    composite = (
        similarity * 0.5
        + min(persistence_days / 14.0, 1.0) * 0.3
        + min(avg_severity / 3.0, 1.0) * 0.2
    )
    if composite >= _ESCALATE_THRESHOLD:
        return "escalate"
    if composite >= _WATCH_THRESHOLD:
        return "watch"
    return "low"


# ── Cooldown management ────────────────────────────────────────────────────────

def _is_in_cooldown(patient_id: str, cluster_id: str) -> bool:
    """Return True if this cluster alert fired within the last COOLDOWN_HOURS."""
    store = _load_store()
    cooldown_ts = (
        store.get("alert_cooldowns", {})
        .get(patient_id, {})
        .get(cluster_id)
    )
    if not cooldown_ts:
        return False
    try:
        last = datetime.fromisoformat(cooldown_ts)
        return (datetime.now() - last) < timedelta(hours=_COOLDOWN_HOURS)
    except ValueError:
        return False


def _record_cooldown(patient_id: str, cluster_id: str) -> None:
    """Record that an alert just fired for (patient, cluster)."""
    store = _load_store()
    store.setdefault("alert_cooldowns", {})
    store["alert_cooldowns"].setdefault(patient_id, {})
    store["alert_cooldowns"][patient_id][cluster_id] = datetime.now().isoformat()
    _save_store(store)


# ── ADK Tool ───────────────────────────────────────────────────────────────────

def compute_trend_score(patient_id: str) -> dict:
    """
    Compute the full longitudinal trend score for a patient.

    Orchestrates the complete deterministic pipeline:
      1. Build the 14-day decay-weighted pattern vector (trend_window)
      2. Find the closest matching condition cluster (vector_search)
      3. Apply the urgency scoring formula (no LLM)
      4. Enforce the 48-hour cooldown gate

    This tool is the SINGLE source of urgency decisions in CareTrend.
    The LLM orchestrator MUST use this result — it must never decide urgency itself.

    Args:
        patient_id: Unique patient identifier, e.g. "patient_001".

    Returns:
        A dict with:
          - status: "success" or "error"
          - urgency: "low" | "watch" | "escalate"
          - similarity_score: float (0–1)
          - persistence_days: int
          - avg_severity: float
          - composite_score: float (the raw formula output, for transparency)
          - top_cluster_id: str
          - top_cluster_name: str
          - top_cluster_description: str (retrieved, never generated)
          - pattern_summary: human-readable summary of what was observed
          - cooldown_active: bool (True = alert suppressed, already fired recently)
          - date_range: e.g. "Jun 22 – Jul 5"
          - log_count: int
    """
    # ── Step 1: Build pattern vector ───────────────────────────────────────────
    pattern = compute_pattern_vector(patient_id)

    if not pattern["symptom_text"]:
        return {
            "status": "success",
            "urgency": "low",
            "similarity_score": 0.0,
            "persistence_days": 0,
            "avg_severity": 0.0,
            "composite_score": 0.0,
            "top_cluster_id": None,
            "top_cluster_name": "No symptoms logged in the last 14 days",
            "top_cluster_description": "",
            "pattern_summary": "No symptom data available. Please log symptoms first.",
            "cooldown_active": False,
            "date_range": "—",
            "log_count": 0,
        }

    # ── Step 2: Vector similarity search ──────────────────────────────────────
    try:
        search_result = search_condition_patterns(
            symptom_list=pattern["symptom_text"],
            top_k=1,
        )
        if search_result["status"] == "success" and search_result["matches"]:
            top = search_result["matches"][0]
            similarity = top["similarity_score"]
            top_cluster_id = top["id"]
            top_cluster_name = top["name"]
            top_cluster_description = top["description"]
        else:
            similarity = 0.0
            top_cluster_id = "unknown"
            top_cluster_name = "No matching pattern found"
            top_cluster_description = ""
    except Exception as exc:  # noqa: BLE001
        similarity = 0.0
        top_cluster_id = "unknown"
        top_cluster_name = f"Search error: {exc}"
        top_cluster_description = ""

    # ── Step 3: Deterministic scoring ─────────────────────────────────────────
    persistence_days = pattern["persistence_days"]
    avg_severity = pattern["avg_severity"]
    urgency = compute_urgency(similarity, persistence_days, avg_severity)

    composite_score = (
        similarity * 0.5
        + min(persistence_days / 14.0, 1.0) * 0.3
        + min(avg_severity / 3.0, 1.0) * 0.2
    )

    # ── Step 4: Cooldown gate ──────────────────────────────────────────────────
    cooldown_active = False
    if urgency in ("watch", "escalate") and top_cluster_id not in (None, "unknown"):
        if _is_in_cooldown(patient_id, top_cluster_id):
            cooldown_active = True
            urgency = "low"   # suppress — already alerted recently
        else:
            _record_cooldown(patient_id, top_cluster_id)

    # ── Step 5: Human-readable summary ────────────────────────────────────────
    symptom_list = list(pattern["symptom_scores"].keys())[:6]
    severity_label = (
        "mild" if avg_severity <= 1.5
        else "moderate" if avg_severity <= 2.5
        else "severe"
    )
    pattern_summary = (
        f"Over {persistence_days} day(s) ({pattern['date_range']}), "
        f"the following symptoms were observed: {', '.join(symptom_list)}. "
        f"Average severity: {severity_label}. "
        f"Similarity to '{top_cluster_name}': {similarity:.1%}. "
        f"Urgency composite score: {composite_score:.3f}."
    )

    return {
        "status": "success",
        "urgency": urgency,
        "similarity_score": round(similarity, 4),
        "persistence_days": persistence_days,
        "avg_severity": round(avg_severity, 2),
        "composite_score": round(composite_score, 4),
        "top_cluster_id": top_cluster_id,
        "top_cluster_name": top_cluster_name,
        "top_cluster_description": top_cluster_description,
        "pattern_summary": pattern_summary,
        "cooldown_active": cooldown_active,
        "date_range": pattern["date_range"],
        "log_count": pattern["log_count"],
        "symptom_scores": pattern["symptom_scores"],
    }
