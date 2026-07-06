"""
AyuGuard Care Plan Tool
=========================
Manages caregiver-created meal plans, medications schedules, and
daily activity plans for the patient.

Stored in:
  - Firestore: patients/{patient_id}/care_plans/current  (when Firebase configured)
  - Local JSON: ayuguard/data/symptom_logs.json under "care_plans" key (fallback)

When a caregiver updates the care plan, a notification is automatically
added to the patient's notification queue so the patient view reflects
the change immediately.
"""
from __future__ import annotations

from datetime import datetime
from ayuguard.tools.symptom_store import _load_store, _save_store


def get_care_plan(patient_id: str = "patient_001") -> dict:
    """
    Retrieve the current care plan for a patient.

    Returns the latest caregiver-defined meal plan, medication schedule,
    and activity plan. Called by the patient view dashboard and by the
    orchestrator when generating patient-facing responses.

    Args:
        patient_id: The patient identifier (default "patient_001").

    Returns:
        dict with:
          - status: "found" | "not_found"
          - meals: list[str] — meal plan items
          - medications: list[str] — medication schedule
          - activities: list[str] — daily activity plan
          - notes: str — caregiver notes
          - updated_by: str — caregiver name
          - updated_at: str — ISO datetime
    """
    # Try Firestore first
    try:
        from ayuguard.firebase_client import get_firestore_client
        db = get_firestore_client()
        if db:
            doc = db.collection("patients").document(patient_id)\
                    .collection("care_plans").document("current").get()
            if doc.exists:
                data = doc.to_dict()
                data["status"] = "found"
                return data
    except Exception:
        pass

    # Fallback: local JSON
    store = _load_store()
    plans = store.get("care_plans", {})
    plan = plans.get(patient_id)
    if not plan:
        return {
            "status": "not_found",
            "meals": [],
            "medications": [],
            "activities": [],
            "notes": "",
            "updated_by": "",
            "updated_at": None,
        }
    plan["status"] = "found"
    return plan


def save_care_plan(
    meals: str,
    medications: str,
    activities: str,
    notes: str = "",
    patient_id: str = "patient_001",
    caregiver_name: str = "",
) -> dict:
    """
    Save or update the patient's care plan.

    Call this when the caregiver specifies a new meal plan, medication
    schedule, or activity plan. Each field is a comma-separated string
    of items. A patient notification is automatically added on every update.

    Args:
        meals:          Comma-separated meal plan items.
                        Example: "Low-carb breakfast, Dal with roti for lunch, Light dinner by 7pm"
        medications:    Comma-separated medication schedule.
                        Example: "Metformin 500mg after dinner, Vitamin D in morning"
        activities:     Comma-separated activity plan.
                        Example: "15 min walk after lunch, Evening stretching"
        notes:          Any additional caregiver notes. Optional.
        patient_id:     The patient identifier (default "patient_001").
        caregiver_name: The caregiver's name (for the update notification).

    Returns:
        dict with status, message, and the saved plan.
    """
    now = datetime.now().isoformat()

    def parse_list(s: str) -> list[str]:
        return [item.strip() for item in s.split(",") if item.strip()] if s else []

    plan = {
        "meals":        parse_list(meals),
        "medications":  parse_list(medications),
        "activities":   parse_list(activities),
        "notes":        notes.strip(),
        "updated_by":   caregiver_name or "Caregiver",
        "updated_at":   now,
    }

    # Build human-readable change summary for notification
    parts = []
    if plan["meals"]:        parts.append(f"Meal plan updated: {', '.join(plan['meals'][:2])}")
    if plan["medications"]:  parts.append(f"Medications: {', '.join(plan['medications'][:2])}")
    if plan["activities"]:   parts.append(f"Activities: {', '.join(plan['activities'][:2])}")
    if plan["notes"]:        parts.append(f"Note from {caregiver_name or 'your caregiver'}: {plan['notes']}")
    change_summary = " | ".join(parts) if parts else "Care plan updated"

    # Try Firestore
    try:
        from ayuguard.firebase_client import get_firestore_client
        db = get_firestore_client()
        if db:
            db.collection("patients").document(patient_id)\
              .collection("care_plans").document("current").set(plan)
            _add_notification_fs(db, patient_id, change_summary, "care_plan", caregiver_name)
    except Exception:
        pass

    # Always write to local JSON (dual-write / fallback)
    store = _load_store()
    store.setdefault("care_plans", {})[patient_id] = plan
    notifications = store.setdefault("notifications", {}).setdefault(patient_id, [])
    notifications.append({
        "message":    change_summary,
        "type":       "care_plan",
        "read":       False,
        "created_at": now,
    })
    _save_store(store)

    return {
        "status":  "success",
        "message": f"Care plan saved for patient. Notification sent: '{change_summary}'",
        "plan":    plan,
    }


def get_patient_notifications(
    patient_id: str = "patient_001",
    unread_only: bool = False,
    limit: int = 10,
) -> dict:
    """
    Return the patient's notification queue (caregiver updates).

    Called by the patient view to show what the caregiver has changed.

    Args:
        patient_id:   The patient identifier.
        unread_only:  If True, only return unread notifications.
        limit:        Maximum number of notifications to return.

    Returns:
        dict with status, notifications list, and unread_count.
    """
    # Try Firestore
    try:
        from ayuguard.firebase_client import get_firestore_client
        db = get_firestore_client()
        if db:
            query = db.collection("patients").document(patient_id)\
                      .collection("notifications").order_by(
                          "created_at", direction="DESCENDING"
                      ).limit(limit)
            if unread_only:
                query = query.where("read", "==", False)
            docs = query.stream()
            notifs = [d.to_dict() for d in docs]
            return {"status": "ok", "notifications": notifs, "unread_count": len([n for n in notifs if not n.get("read")])}
    except Exception:
        pass

    # Fallback: local JSON
    store = _load_store()
    notifs = store.get("notifications", {}).get(patient_id, [])
    notifs = sorted(notifs, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]
    if unread_only:
        notifs = [n for n in notifs if not n.get("read")]
    return {
        "status": "ok",
        "notifications": notifs,
        "unread_count": len([n for n in notifs if not n.get("read")]),
    }


def _add_notification_fs(db, patient_id: str, message: str, notif_type: str, from_name: str) -> None:
    """Helper: write a notification document to Firestore."""
    import uuid
    db.collection("patients").document(patient_id)\
      .collection("notifications").document(str(uuid.uuid4())).set({
          "message":    message,
          "type":       notif_type,
          "from":       from_name or "Caregiver",
          "read":       False,
          "created_at": datetime.now().isoformat(),
      })
