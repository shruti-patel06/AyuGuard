"""
AyuGuard UI Companion Server
==============================
FastAPI server on port 8001 that:
  - Serves the frontend SPA (ui/index.html)
  - Exposes /api/* endpoints for patient data (profile, history, trend, care plan, notifications)
  - Proxies SSE chat to the ADK server on port 8000

Run from ayuguard-care-platform/:
  python ui/server.py
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import AsyncGenerator, Optional

import httpx
import uvicorn
from fastapi import FastAPI, File, Form, Request, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

ROOT = Path(__file__).parent.parent.resolve()
UI_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from ayuguard.tools.patient_profile import get_patient_profile
from ayuguard.tools.symptom_store import _load_store
from ayuguard.tools.urgency_scorer import compute_trend_score
from ayuguard.tools.care_plan import get_care_plan, get_patient_notifications
from ayuguard.tools.medical_records import (
    analyse_and_store_record,
    get_medical_records,
    get_record_details,
    get_abnormal_history,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_MB,
    _UPLOADS,
)

# Cloud Run: set ADK_BASE_URL env var to the agent service URL.
# Local dev: defaults to http://127.0.0.1:8000
ADK_BASE = os.environ.get("ADK_BASE_URL", "http://127.0.0.1:8000")

app = FastAPI(title="AyuGuard UI Server", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    html_path = UI_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.get("/api/profile")
async def api_profile(patient_id: str = "patient_001"):
    return JSONResponse(content=get_patient_profile(patient_id=patient_id))


@app.get("/api/history")
async def api_history(patient_id: str = "patient_001", limit: int = 30):
    store = _load_store()
    patient = store.get("patients", {}).get(patient_id)
    if not patient:
        return JSONResponse(content={"status": "no_data", "logs": []})
    logs = patient.get("logs", [])
    recent = sorted(logs, key=lambda x: x.get("date", ""), reverse=True)[:limit]
    return JSONResponse(content={
        "status": "ok",
        "patient_id": patient_id,
        "total_logs": len(logs),
        "logs": recent,
    })


@app.get("/api/trend")
async def api_trend(patient_id: str = "patient_001"):
    try:
        result = compute_trend_score(patient_id=patient_id)
        return JSONResponse(content=result)
    except Exception as exc:
        return JSONResponse(
            content={"status": "error", "error": str(exc), "urgency": "low",
                     "composite_score": 0, "persistence_days": 0},
            status_code=200,
        )


@app.get("/api/stats")
async def api_stats(patient_id: str = "patient_001"):
    store = _load_store()
    logs = store.get("patients", {}).get(patient_id, {}).get("logs", [])
    if not logs:
        return JSONResponse(content={"total_logs": 0, "streak_days": 0, "top_symptom": None})
    from collections import Counter
    symptom_counts = Counter(l["symptom"] for l in logs)
    top = symptom_counts.most_common(1)[0] if symptom_counts else (None, 0)
    dates = sorted(set(l["date"] for l in logs), reverse=True)
    return JSONResponse(content={
        "total_logs": len(logs),
        "days_tracked": len(dates),
        "top_symptom": top[0],
        "top_symptom_count": top[1],
        "symptom_breakdown": dict(symptom_counts.most_common(8)),
    })


@app.get("/api/care-plan")
async def api_care_plan(patient_id: str = "patient_001"):
    """Return the caregiver-set care plan for display on the patient dashboard."""
    plan = get_care_plan(patient_id=patient_id)
    return JSONResponse(content=plan)


@app.get("/api/notifications")
async def api_notifications(
    patient_id: str = "patient_001",
    unread_only: bool = False,
    limit: int = 20,
):
    """Return patient notifications (caregiver plan updates, alerts)."""
    result = get_patient_notifications(
        patient_id=patient_id,
        unread_only=unread_only,
        limit=limit,
    )
    return JSONResponse(content=result)


@app.post("/api/notifications/mark-read")
async def mark_notifications_read(request: Request):
    """Mark all notifications as read (local JSON store)."""
    body = await request.json()
    patient_id = body.get("patient_id", "patient_001")
    from ayuguard.tools.symptom_store import _load_store, _save_store
    store = _load_store()
    notifs = store.get("notifications", {}).get(patient_id, [])
    for n in notifs:
        n["read"] = True
    _save_store(store)
    return JSONResponse(content={"status": "ok"})


@app.post("/api/session")
async def create_session(request: Request):
    """Create a new ADK session."""
    body = await request.json()
    user_id = body.get("user_id", "caregiver-001")
    app_name = body.get("app_name", "ayuguard")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{ADK_BASE}/apps/{app_name}/users/{user_id}/sessions",
            json={},
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            return JSONResponse(content={"session_id": data.get("id", data.get("session_id", ""))})
        raise HTTPException(status_code=resp.status_code, detail=resp.text)


@app.post("/api/chat")
async def chat_proxy(request: Request):
    """Proxy chat messages to the ADK /run_sse endpoint (SSE streaming)."""
    body = await request.json()

    async def stream_adk() -> AsyncGenerator[bytes, None]:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{ADK_BASE}/run_sse",
                json=body,
                headers={"Accept": "text/event-stream"},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        yield (line + "\n\n").encode()

    return StreamingResponse(
        stream_adk(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Medical Records endpoints ─────────────────────────────────────────────────

@app.post("/api/upload-record")
async def upload_record(
    file: UploadFile = File(...),
    record_type: str = Form("lab_test"),
    notes: str = Form(""),
    patient_id: str = Form("patient_001"),
    caregiver_name: str = Form(""),
):
    """
    Accept a medical document upload, analyse with Gemini, and store results.
    Supports PDF, JPG, PNG, WEBP up to 15 MB.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save to uploads directory
    upload_dir = _UPLOADS / patient_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    import time
    safe_name = f"{int(time.time())}_{file.filename}"
    dest = upload_dir / safe_name

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.",
        )
    dest.write_bytes(contents)

    # Run Gemini analysis (synchronous — runs in FastAPI's thread pool)
    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: analyse_and_store_record(
            file_path=str(dest),
            record_type=record_type,
            notes=notes,
            patient_id=patient_id,
            caregiver_name=caregiver_name,
        ),
    )

    return JSONResponse(content=result)


@app.get("/api/records")
async def api_records(patient_id: str = "patient_001"):
    """List all uploaded medical records with summaries."""
    result = get_medical_records(patient_id=patient_id)
    return JSONResponse(content=result)


@app.get("/api/records/{record_id}")
async def api_record_detail(record_id: str, patient_id: str = "patient_001"):
    """Get full analysis details for a specific record."""
    result = get_record_details(record_id=record_id, patient_id=patient_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Record not found")
    return JSONResponse(content=result)


@app.get("/api/abnormal-history")
async def api_abnormal_history(patient_id: str = "patient_001"):
    """Get consolidated abnormal lab values across all uploaded records."""
    result = get_abnormal_history(patient_id=patient_id)
    return JSONResponse(content=result)


@app.delete("/api/records/{record_id}")
async def delete_record(record_id: str, patient_id: str = "patient_001"):
    """Delete a medical record (metadata only; file is kept for audit)."""
    from ayuguard.tools.medical_records import _load_records, _save_records
    records = _load_records()
    patient_records = records.get(patient_id, [])
    new_list = [r for r in patient_records if r.get("record_id") != record_id]
    if len(new_list) == len(patient_records):
        raise HTTPException(status_code=404, detail="Record not found")
    records[patient_id] = new_list
    _save_records(records)
    return JSONResponse(content={"status": "deleted", "record_id": record_id})


if __name__ == "__main__":
    _port = int(os.environ.get("PORT", 8001))  # Cloud Run sets PORT=8080
    _host = "0.0.0.0"                          # must bind 0.0.0.0 in Cloud Run
    print("\n" + "=" * 62)
    print("  AyuGuard UI Server v2")
    print("=" * 62)
    print(f"  UI:         http://{_host}:{_port}")
    print(f"  ADK Agent:  {ADK_BASE}")
    print("=" * 62 + "\n")
    uvicorn.run(app, host=_host, port=_port, log_level="info")
