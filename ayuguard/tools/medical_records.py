"""
AyuGuard Medical Records Tool
================================
Upload, analyse, and retrieve medical records and lab tests.
Uses Gemini multimodal (Vision + Files API) to extract structured
clinical information from PDFs, images, and scanned documents.

Supported file types:
  - PDF  — lab reports, discharge summaries, prescriptions
  - JPG/PNG/WEBP — prescription photos, scan images, handwritten notes

Storage:
  - Files saved to  : ayuguard/data/uploads/{patient_id}/
  - Metadata stored : ayuguard/data/medical_records.json
  - Firestore       : patients/{patient_id}/medical_records/{record_id}  (when configured)

Safety:
  The LLM analysis output is clearly labelled as "AI-extracted summary".
  It is NEVER presented as a definitive diagnosis — only as a structured
  reading of what is written in the document.
"""
from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_DATA_DIR   = Path(__file__).parent.parent / "data"
_UPLOADS    = _DATA_DIR / "uploads"
_RECORDS_FILE = _DATA_DIR / "medical_records.json"

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}
MAX_FILE_SIZE_MB   = 15

# ── Record type labels ────────────────────────────────────────────────────────
RECORD_TYPES = {
    "lab_test":           "🧪 Lab Test",
    "prescription":       "💊 Prescription",
    "discharge_summary":  "🏥 Discharge Summary",
    "scan_report":        "🔬 Scan / Imaging Report",
    "consultation_note":  "📋 Consultation Note",
    "vaccination":        "💉 Vaccination Record",
    "other":              "📄 Other",
}

# ── Gemini analysis prompt ─────────────────────────────────────────────────────
_ANALYSIS_PROMPT = """You are a medical document reader for AyuGuard, an elderly patient monitoring platform.

Carefully read this medical document and extract the following information in JSON format:

{
  "document_type": "<type: Lab Test | Prescription | Discharge Summary | Scan Report | Consultation Note | Vaccination | Other>",
  "report_date": "<YYYY-MM-DD or null if not found>",
  "hospital_or_lab": "<name of hospital, lab, or clinic or null>",
  "doctor_name": "<doctor's name or null>",
  "key_findings": ["<list of key findings, results, or observations — be specific>"],
  "abnormal_values": [
    {"parameter": "<test name>", "value": "<result>", "normal_range": "<range or null>", "flag": "HIGH|LOW|BORDERLINE"}
  ],
  "normal_values": ["<list of parameters that were within normal range>"],
  "medications_mentioned": ["<medication name + dose + frequency>"],
  "recommendations": ["<doctor's recommendations or instructions>"],
  "summary": "<2-3 sentence plain-English summary of this document's most important points>",
  "follow_up_required": "<yes / no / not mentioned>",
  "critical_values": ["<any critically abnormal values that need immediate attention>"]
}

IMPORTANT RULES:
- Extract ONLY what is written in the document — do NOT infer or add information
- Use null for fields not present in the document
- Flag abnormal values honestly — this is important for the patient's caregiver
- Keep the summary in simple, non-technical language suitable for a family caregiver
- If the document is a prescription, focus on medication list and instructions
- If the document is a scan report, summarise the radiologist's conclusion
- Output ONLY the JSON. No markdown, no explanation, just the JSON object.
"""


# ── Store helpers ─────────────────────────────────────────────────────────────
def _load_records() -> dict:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _RECORDS_FILE.exists():
        _RECORDS_FILE.write_text(json.dumps({}), encoding="utf-8")
        return {}
    return json.loads(_RECORDS_FILE.read_text(encoding="utf-8"))


def _save_records(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _RECORDS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Core tool functions ────────────────────────────────────────────────────────

def analyse_and_store_record(
    file_path: str,
    record_type: str,
    notes: str = "",
    patient_id: str = "patient_001",
    caregiver_name: str = "",
) -> dict:
    """
    Analyse a medical document with Gemini and store the structured results.

    This is called internally by the upload endpoint after saving the file.
    The Gemini model reads the document (PDF or image), extracts key clinical
    data, flags abnormal values, and stores everything for future reference.

    Args:
        file_path:     Absolute path to the saved file.
        record_type:   One of: lab_test | prescription | discharge_summary |
                       scan_report | consultation_note | vaccination | other
        notes:         Optional caregiver notes about this document.
        patient_id:    Patient identifier (default "patient_001").
        caregiver_name: Name of the caregiver who uploaded it.

    Returns:
        dict with record_id, status, analysis summary, and abnormal values.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    path    = Path(file_path)
    suffix  = path.suffix.lower()
    record_id = str(uuid.uuid4())[:8]

    # ── Gemini analysis ──────────────────────────────────────────────────────
    analysis = {}
    raw_text = ""

    if api_key:
        try:
            import google.genai as genai
            client = genai.Client(api_key=api_key)

            if suffix == ".pdf":
                raw_text = _extract_pdf_text(path)
                if raw_text.strip():
                    prompt = _ANALYSIS_PROMPT + f"\n\nDOCUMENT TEXT:\n{raw_text[:12000]}"
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                    )
                else:
                    # Scanned PDF with no extractable text — try Gemini Files API
                    uploaded = client.files.upload(file=str(path))
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[uploaded, _ANALYSIS_PROMPT],
                    )
            else:
                # Image — use inline base64
                mime_map = {
                    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp",
                    ".tiff": "image/tiff", ".bmp": "image/bmp",
                }
                mime = mime_map.get(suffix, "image/jpeg")
                img_b64 = base64.b64encode(path.read_bytes()).decode()
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        {"inline_data": {"mime_type": mime, "data": img_b64}},
                        _ANALYSIS_PROMPT,
                    ],
                )

            raw_json = resp.text.strip()
            if raw_json.startswith("```"):
                raw_json = "\n".join(raw_json.split("\n")[1:-1])
            analysis = json.loads(raw_json)

        except json.JSONDecodeError:
            analysis = {"summary": resp.text.strip()[:500], "error": "Could not parse structured JSON"}
        except Exception as exc:
            analysis = {"summary": f"Analysis failed: {exc}", "error": str(exc)}
    else:
        analysis = {"summary": "GOOGLE_API_KEY not set — document stored without analysis."}

    # ── Build record ──────────────────────────────────────────────────────────
    record = {
        "record_id":     record_id,
        "patient_id":    patient_id,
        "filename":      path.name,
        "file_path":     str(path),
        "record_type":   record_type,
        "record_type_label": RECORD_TYPES.get(record_type, "📄 Document"),
        "notes":         notes,
        "uploaded_by":   caregiver_name or "Caregiver",
        "uploaded_at":   datetime.now().isoformat(),
        "analysis":      analysis,
        "raw_text_preview": raw_text[:600] if raw_text else "",
    }

    # ── Persist locally ───────────────────────────────────────────────────────
    records = _load_records()
    records.setdefault(patient_id, []).insert(0, record)  # newest first
    _save_records(records)

    # ── GCS dual-write (best-effort) — persists uploads across Cloud Run restarts ──
    try:
        from ayuguard.gcs_client import upload_file as gcs_upload
        blob_name = f"medical_records/{patient_id}/{record_id}/{path.name}"
        gcs_uri = gcs_upload(path, blob_name)
        if gcs_uri:
            record["gcs_uri"] = gcs_uri
            records[patient_id][0]["gcs_uri"] = gcs_uri  # update in-memory
            _save_records(records)
    except Exception:
        pass

    # ── Firestore dual-write (best-effort) ────────────────────────────────────
    try:
        from ayuguard.firebase_client import get_firestore_client
        db = get_firestore_client()
        if db:
            store_record = {k: v for k, v in record.items() if k != "file_path"}
            db.collection("patients").document(patient_id)\
              .collection("medical_records").document(record_id).set(store_record)
    except Exception:
        pass


    # ── Build readable summary for return ────────────────────────────────────
    abnormal = analysis.get("abnormal_values", [])
    critical = analysis.get("critical_values", [])
    findings = analysis.get("key_findings", [])

    return {
        "status":         "success",
        "record_id":      record_id,
        "filename":       path.name,
        "record_type":    RECORD_TYPES.get(record_type, record_type),
        "summary":        analysis.get("summary", ""),
        "report_date":    analysis.get("report_date"),
        "abnormal_count": len(abnormal),
        "abnormal_values": abnormal[:5],
        "critical_values": critical,
        "key_findings":   findings[:5],
        "medications":    analysis.get("medications_mentioned", []),
        "recommendations": analysis.get("recommendations", []),
        "follow_up":      analysis.get("follow_up_required", "not mentioned"),
    }


def get_medical_records(patient_id: str = "patient_001") -> dict:
    """
    List all uploaded medical records and lab tests for a patient.

    Call this when the caregiver asks to review records, or when preparing
    context for a diagnosis discussion. Returns summaries — not full text.

    Args:
        patient_id: Patient identifier (default "patient_001").

    Returns:
        dict with status, records list (summary only), and total count.
    """
    # Try Firestore first
    try:
        from ayuguard.firebase_client import get_firestore_client
        db = get_firestore_client()
        if db:
            docs = (db.collection("patients").document(patient_id)
                      .collection("medical_records")
                      .order_by("uploaded_at", direction="DESCENDING")
                      .limit(20).stream())
            records = [d.to_dict() for d in docs]
            if records:
                return {"status": "ok", "total": len(records), "records": _summarise(records)}
    except Exception:
        pass

    # Local fallback
    all_records = _load_records()
    records = all_records.get(patient_id, [])
    return {
        "status": "ok",
        "total": len(records),
        "records": _summarise(records),
    }


def get_record_details(
    record_id: str,
    patient_id: str = "patient_001",
) -> dict:
    """
    Get full analysis details of a specific medical record.

    Call this when the caregiver wants to discuss a specific test result,
    or when the agent needs to reference a document in a diagnosis context.

    Args:
        record_id:  The 8-character record ID returned when the record was uploaded.
        patient_id: Patient identifier (default "patient_001").

    Returns:
        dict with full analysis including all findings, abnormal values,
        medications, recommendations, and the document summary.
    """
    all_records = _load_records()
    for r in all_records.get(patient_id, []):
        if r.get("record_id") == record_id:
            return {"status": "found", **r}
    return {"status": "not_found", "record_id": record_id}


def get_abnormal_history(patient_id: str = "patient_001") -> dict:
    """
    Get a consolidated view of all abnormal lab values across all uploaded records.

    Useful for tracking trends in blood sugar, HbA1c, blood pressure readings,
    kidney function, etc. across multiple lab reports over time.

    Args:
        patient_id: Patient identifier (default "patient_001").

    Returns:
        dict with consolidated abnormal_values list sorted by parameter name,
        and a list of records that had critical values.
    """
    all_records = _load_records()
    records = all_records.get(patient_id, [])

    all_abnormal: list[dict] = []
    critical_records: list[str] = []

    for r in records:
        analysis = r.get("analysis", {})
        for ab in analysis.get("abnormal_values", []):
            all_abnormal.append({
                **ab,
                "report_date": analysis.get("report_date", r.get("uploaded_at", "")[:10]),
                "record_id": r.get("record_id"),
                "document": r.get("filename"),
                "record_type": r.get("record_type_label", ""),
            })
        if analysis.get("critical_values"):
            critical_records.append(f"{r.get('filename')} ({analysis.get('report_date', 'unknown date')})")

    # Group by parameter
    by_param: dict[str, list] = {}
    for ab in all_abnormal:
        param = ab.get("parameter", "Unknown")
        by_param.setdefault(param, []).append(ab)

    return {
        "status": "ok",
        "total_abnormal_parameters": len(by_param),
        "abnormal_by_parameter": by_param,
        "critical_alerts": critical_records,
        "records_analysed": len(records),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────
def _summarise(records: list[dict]) -> list[dict]:
    """Return lightweight summary dicts (no raw text, smaller payload)."""
    out = []
    for r in records:
        analysis = r.get("analysis", {})
        out.append({
            "record_id":    r.get("record_id"),
            "filename":     r.get("filename"),
            "record_type":  r.get("record_type_label", r.get("record_type", "")),
            "report_date":  analysis.get("report_date") or r.get("uploaded_at", "")[:10],
            "uploaded_at":  r.get("uploaded_at", "")[:16],
            "uploaded_by":  r.get("uploaded_by", ""),
            "notes":        r.get("notes", ""),
            "summary":      analysis.get("summary", "")[:200],
            "abnormal_count": len(analysis.get("abnormal_values", [])),
            "critical_count": len(analysis.get("critical_values", [])),
            "follow_up":    analysis.get("follow_up_required", "not mentioned"),
        })
    return out


def _extract_pdf_text(path: Path) -> str:
    """Extract plain text from a PDF using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages[:10]:  # cap at 10 pages
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except ImportError:
        pass

    # Fallback: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages[:10]
        )
    except Exception:
        return ""
