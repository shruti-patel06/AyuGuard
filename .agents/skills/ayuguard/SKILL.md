---
name: ayuguard-care-platform
description: >
  Build, extend, debug, and operate the AyuGuard Ambient Caregiver Platform —
  a longitudinal elderly-patient health monitoring system powered by Google ADK,
  Gemini multimodal AI, and a real-time SPA UI. Use this skill when the user asks
  to add features, fix bugs, modify agent behaviour, update the UI, extend the
  tool pipeline, manage patient/caregiver data, or understand the system architecture
  of the AyuGuard project.
---

# AyuGuard Care Platform — Skill Reference

## What Is AyuGuard?

AyuGuard (आयुगार्ड) is an ambient elderly-patient care system. It has three roles:

| Role | Interface | Purpose |
|---|---|---|
| **Caregiver** | Chat (port 8001) | Logs symptoms, manages care plan, uploads medical records |
| **Patient** | Chat (port 8001) | Reports feelings, views care plan, asks health questions |
| **Agent** | ADK orchestrator (port 8000) | Extracts symptoms → scores patterns → diagnoses → communicates |

The system tracks symptoms over 14 days, detects patterns, cross-references lab reports,
and alerts caregivers without ever diagnosing directly.

---

## Project Root

```
c:\Users\Shruti\OneDrive\Desktop\ayuguard-care-platform\
```

---

## How to Run

```powershell
# Terminal 1 — ADK Agent (port 8000)
cd c:\Users\Shruti\OneDrive\Desktop\ayuguard-care-platform
adk web

# Terminal 2 — UI Server (port 8001)
python ui/server.py
```

Open: **http://127.0.0.1:8001**

> ADK web must be running BEFORE the UI server starts, or chat sessions will fail.

---

## Directory Structure

```
ayuguard-care-platform/
├── ayuguard/                    # ADK agent package
│   ├── __init__.py              # Exports root_agent
│   ├── agent.py                 # Root orchestrator + full instruction
│   ├── prompts.py               # Shared prompt fragments
│   ├── firebase_client.py       # Firestore singleton (best-effort dual-write)
│   ├── .env                     # GOOGLE_API_KEY, FIREBASE_* env vars
│   │
│   ├── sub_agents/
│   │   ├── extraction.py        # symptom_extraction_agent (Gemini JSON extractor)
│   │   └── retrieval.py         # condition_retrieval_agent (dataset search)
│   │
│   ├── tools/
│   │   ├── patient_profile.py   # get/save patient + caregiver profile
│   │   ├── symptom_store.py     # store/load symptom logs (JSON + Firestore)
│   │   ├── urgency_scorer.py    # compute_trend_score() — DETERMINISTIC
│   │   ├── dataset_search.py    # TF-IDF search over symptom datasets
│   │   ├── diagnosis.py         # diagnose_non_critical() — safe-list gating
│   │   ├── care_plan.py         # get/save care plan + patient notifications
│   │   ├── communication.py     # generate_caregiver_message() — Gemini call
│   │   └── medical_records.py   # upload/analyse/retrieve medical documents
│   │
│   └── data/
│       ├── symptom_logs.json    # Patient symptom history (source of truth)
│       ├── patient_profile.json # Patient + caregiver profile
│       ├── care_plan.json       # Meals, medications, activities
│       ├── medical_records.json # Uploaded document metadata + AI analysis
│       └── uploads/patient_001/ # Saved PDFs and images
│
├── datasets/                    # CSV datasets for pattern matching
│   ├── Symptom2Disease.csv
│   ├── symptom_Description.csv
│   ├── symptom_precaution.csv
│   └── Symptom-severity.csv
│
├── ui/
│   ├── index.html               # SPA — 4-tab UI (Caregiver/Dashboard/Patient/Records)
│   └── server.py                # FastAPI server on port 8001
│
└── .agents/skills/ayuguard/SKILL.md
```

---

## Architecture: The 6-Step Pipeline

Every caregiver message describing symptoms runs through:

```
STEP 0  get_patient_profile("patient_001")
        → Load patient_name, caregiver_name, language, known_conditions

STEP 1  symptom_extraction_agent("caregiver message")
        → Returns JSON: [{symptom, severity, date, source, notes}]
        NOTE: date injected at import (_TODAY = date.today().strftime("%Y-%m-%d"))

STEP 2  store_symptom_log(patient_id="patient_001", symptom_json=<JSON>)
        → Saves to data/symptom_logs.json + Firestore (best-effort)

STEP 3  compute_trend_score("patient_001")   [DETERMINISTIC — never LLM-decided]
        → Returns: urgency, score, top_disease, pattern_summary,
                   persistence_days, similarity_score, top_disease_precautions
        urgency in {"low", "watch", "escalate"}

STEP 4  diagnose_non_critical(symptom_text, urgency, top_disease, similarity_score)
        → Returns: can_diagnose (bool), home_care_tips, disclaimer
        → can_diagnose=False if urgency=escalate OR disease in CRITICAL_LIST

STEP 5  condition_retrieval_agent("symptom keywords")   [only if watch/escalate]
        → Returns related conditions from dataset

STEP 6  generate_caregiver_message(
            urgency, top_disease, precautions, pattern_summary,
            caregiver_original_message, language,
            patient_name=<from profile>,
            caregiver_name=<from profile>   ← ALWAYS pass both names
        )
        → Warm, personalised message in English/Hindi/Hinglish
```

---

## Key Rules (Non-Negotiable)

1. The LLM NEVER decides urgency — compute_trend_score() is deterministic.
2. The LLM NEVER decides criticality — diagnose_non_critical() uses a hardcoded safe-list.
3. ALWAYS pass patient_name and caregiver_name to generate_caregiver_message().
4. Date injection at import time prevents wrong-year dates in extracted logs.
5. urgency=escalate → no home care tips, just pattern + doctor referral.
6. Emergency symptoms (chest pain, unconsciousness, stroke) → always refer to doctor.

---

## Data Schemas

### symptom_logs.json
```json
{
  "patients": {
    "patient_001": {
      "logs": [
        {
          "symptom": "fatigue",
          "severity": "moderate",
          "date": "2026-07-05",
          "source": "log",
          "notes": "caregiver words",
          "stored_at": "2026-07-05T17:30:00.000000"
        }
      ]
    }
  }
}
```

### patient_profile.json
```json
{
  "patient_001": {
    "name": "Rajan Sharma",
    "age": 68,
    "caregiver_name": "Priya",
    "caregiver_relationship": "daughter",
    "language": "English",
    "known_conditions": ["Type 2 Diabetes", "Hypertension"],
    "profile_complete": true
  }
}
```

### medical_records.json
```json
{
  "patient_001": [
    {
      "record_id": "abc12345",
      "filename": "blood_test.pdf",
      "record_type": "lab_test",
      "uploaded_at": "2026-07-05T18:00:00",
      "analysis": {
        "summary": "HbA1c mildly elevated...",
        "abnormal_values": [
          {"parameter": "HbA1c", "value": "7.2%", "normal_range": "<5.7%", "flag": "HIGH"}
        ],
        "critical_values": [],
        "medications_mentioned": [],
        "recommendations": [],
        "follow_up_required": "yes"
      }
    }
  ]
}
```

---

## UI — 4 Tabs

| Tab | HTML ID | Who Uses It |
|---|---|---|
| Caregiver | view-caregiver | Log symptoms, chat, update care plan |
| Dashboard | view-dashboard | Trends, urgency ring, frequency, care plan |
| Patient Chat | view-patient | Patient reports feelings, views updates |
| Records | view-records | Upload PDFs/images, view AI-extracted lab results |

### All API Endpoints (port 8001)

| Method | Path | Description |
|---|---|---|
| GET | / | Serve index.html |
| POST | /api/session | Create ADK chat session |
| POST | /api/chat | SSE-proxied chat (streams from port 8000) |
| GET | /api/profile | Get patient profile |
| GET | /api/stats | Log count, top symptom, days tracked |
| GET | /api/trend | Current urgency + pattern summary |
| GET | /api/history | All symptom logs |
| GET | /api/care-plan | Current care plan |
| GET | /api/notifications | Patient notifications |
| POST | /api/upload-record | Upload medical document (multipart) |
| GET | /api/records | List all records (summaries) |
| GET | /api/records/{id} | Full AI analysis of one record |
| GET | /api/abnormal-history | Cross-report abnormal lab trends |
| DELETE | /api/records/{id} | Remove a record |

---

## All Agent Tools

| Tool | File | Description |
|---|---|---|
| get_patient_profile | patient_profile.py | Load profile |
| save_patient_profile | patient_profile.py | Save updated profile |
| symptom_extraction_agent | sub_agents/extraction.py | text → structured JSON |
| condition_retrieval_agent | sub_agents/retrieval.py | symptom → related conditions |
| store_symptom_log | symptom_store.py | Persist to JSON + Firestore |
| get_patient_history | symptom_store.py | Return last N logs |
| compute_trend_score | urgency_scorer.py | Deterministic urgency scoring |
| diagnose_non_critical | diagnosis.py | Safe-list gated home care |
| generate_caregiver_message | communication.py | Gemini warm message |
| get_care_plan | care_plan.py | Fetch meal/medication plan |
| save_care_plan | care_plan.py | Update plan + notify patient |
| get_patient_notifications | care_plan.py | Fetch unread notifications |
| get_medical_records | medical_records.py | List uploaded records |
| get_record_details | medical_records.py | Full record analysis |
| get_abnormal_history | medical_records.py | Cross-report trends |

---

## How to Extend

### Add a new tool
1. Create function in ayuguard/tools/your_tool.py with typed params + docstring.
2. Import in ayuguard/agent.py.
3. Add to tools=[...] list in root_agent.
4. Add routing rule to orchestrator instruction string.

### Add a new UI section
1. Add CSS in <style> block of ui/index.html.
2. Add tab button in <div class="tabs"> header.
3. Add id="sbn-yourview" sidebar nav button.
4. Add <div id="view-yourview" style="display:none"> in <main>.
5. Update setMode() JS to handle the new view name.
6. Add endpoint in ui/server.py if data is needed.

### Change urgency thresholds
Edit ayuguard/tools/urgency_scorer.py:
- TREND_WINDOW_DAYS (default: 14)
- ESCALATE_THRESHOLD / WATCH_THRESHOLD
- COOLDOWN_HOURS

### Change which diseases allow home-care tips
Edit SAFE_LIST in ayuguard/tools/diagnosis.py.

---

## Common Debugging

### Logs not showing in Dashboard
Check dates in data/symptom_logs.json — must be within TREND_WINDOW_DAYS of today.
Run: python -c "from ayuguard.tools.urgency_scorer import compute_trend_score; print(compute_trend_score('patient_001'))"

### Names not appearing
Verify patient_profile.json has name and caregiver_name set.
Verify generate_caregiver_message() is called with patient_name= and caregiver_name= kwargs.

### UI views bleeding into each other
All views start display:none via CSS. setMode() sets active view to display:flex.
Check for orphaned HTML outside view divs in index.html.

### ADK chat not working
Confirm adk web is running on port 8000 before starting ui/server.py.

### Medical record analysis failing
Verify GOOGLE_API_KEY in ayuguard/.env.
Max file size: 15 MB. Supported: .pdf .jpg .jpeg .png .webp .tiff .bmp

---

## Environment Variables (ayuguard/.env)

```
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_GENAI_USE_VERTEXAI=FALSE
FIREBASE_PROJECT_ID=your_project_id    # optional
FIREBASE_SA_PATH=firebase-service-account.json  # optional
```

---

## Tone and Language Rules

- Address caregiver by first name always.
- Refer to patient by name — NEVER say "the patient".
- Hindi/Hinglish welcome based on language field in profile.
- Speak like a caring family member — not a doctor.
- AyuGuard supplements — never replaces — the doctor's advice.
