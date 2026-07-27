<p align="center">
  <img src="ui/static/Logo.png" alt="AyuGuard Logo" width="420"/>
</p>

<h1 align="center">AyuGuard — Ambient Multi-Agent Caregiver Platform</h1>

<p align="center">
  <em>Longitudinal elderly health monitoring, multi-agent AI collaboration, and real-time care plan reconciliation powered by Google ADK & Vertex AI.</em>
</p>

<p align="center">
  <a href="https://ayuguard-ui-118454190848.asia-south1.run.app"><strong>🌐 Live Demo →</strong></a>
</p>

---

## 🌿 What is AyuGuard?

**AyuGuard (आयुगार्ड)** is an ambient multi-agent caregiver assistant designed for family caregivers managing elderly or chronically ill patients.

### The Core Problem
Caregivers often ask isolated health questions — *"Is his fatigue normal today?"*, *"Can he eat this with his diabetes?"*. Taken individually, each symptom looks harmless, and reactive chatbots usually offer generic advice ("monitor it"). 

However, **the true clinical risk lies in pattern progression over time**:
> *Mild fatigue + increased thirst + blurry vision over 10 days is a classic early warning sign of metabolic decompensation.*

AyuGuard acts as an intelligent, ambient safety net. It tracks symptoms across a 14-day rolling window, matches patterns against clinical datasets, detects multi-condition conflicts (e.g., Pre-diabetes + Diarrhoea), and orchestrates specialized AI subagents to update care plans in real-time.

---

## 🤖 Multi-Agent Subagent Architecture & Workflow

AyuGuard uses **Google ADK (Agent Development Kit)** to coordinate specialized AI subagents that collaborate and solve multi-condition clinical challenges.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ayuguard_orchestrator (Root Agent)                       │
└──────┬──────────────────────────────┬───────────────────────────────┬───────┘
       │                              │                               │
       ▼                              ▼                               ▼
┌──────────────┐             ┌────────────────┐              ┌────────────────┐
│ Extraction   │             │ Retrieval      │              │ Dietary        │
│ Subagent     │             │ Subagent       │              │ Reconciliation │
│ (Symptoms)   │             │ (Datasets)     │              │ Subagent       │
└──────────────┘             └────────────────┘              └───────┬────────┘
                                                                     │
                                                                     ▼
                                                             ┌────────────────┐
                                                             │ save_care_plan │
                                                             │ (Real-Time UI) │
                                                             └────────────────┘
```

### 1. `ayuguard_orchestrator` (Root Agent)
- **Model:** `gemini-2.5-flash-lite` (Vertex AI)
- Manages turn-by-turn dialogue, enforces medical safety gates, injects caregiver context (*Priya*) vs patient context (*Rajan ji*), and delegates complex tasks to specialized subagents.

### 2. `symptom_extraction_agent` (Extraction Subagent)
- Converts raw natural language text (in English, Hindi, or Hinglish) into structured JSON (`symptom`, `severity`, `date`, `source`, `notes`).
- Enforces strict current-year date resolution.

### 3. `condition_retrieval_agent` (Dataset Search Subagent)
- Performs weighted Jaccard similarity searches against a **4,921-row clinical dataset** when symptom persistence or composite urgency scores cross risk thresholds.

### 4. `dietary_reconciliation_agent` (Multi-Condition Reconciliation Subagent)
- **The Problem:** Chronic dietary guidelines often directly conflict with acute recovery needs. For instance, a **Pre-diabetes** diet requires high fiber (raw salad, legumes), while acute **Diarrhoea** requires a low-fiber, bland diet (BRAT / khichdi). High fiber during diarrhoea worsens gut motility.
- **The AI Collaboration Workflow:**
  1. **Acute Onset:** When acute symptoms (diarrhoea, vomiting, fever) occur in a patient with chronic conditions (pre-diabetes, hypertension), the subagent is invoked.
  2. **Dietary Reconciliation:** It formulates a temporary 2–3 day recovery meal plan (low-fiber, bland low-GI carbs like ripe bananas, soft white rice with light dal & curd, ORS hydration) that is safe for *both* conditions simultaneously.
  3. **Recovery Transition:** When the caregiver reports recovery (*"Dad has recovered from diarrhoea today"*), the subagent automatically de-escalates the acute diet and transitions the care plan back to the healthy baseline chronic management schedule (re-introducing high-fiber multigrain roti, legumes, and fresh salads).
  4. **Real-time Push:** Invokes `save_care_plan()` to update the database and push instant notifications to the UI.

---

## 🚀 Significant Technical & UI Modifications

### 🌐 Vertex AI Infrastructure
- Migrated the multi-agent pipeline to **Vertex AI** (`gemini-2.5-flash-lite`, `us-central1`).
- Unified Cloud Run deployment scripts (`deploy.ps1`, `deploy.sh`) to leverage Application Default Credentials (ADC) and Google Secret Manager.

### 🎨 Modular UI & Glassmorphism Design
- **Asset Separation:** Refactored the frontend into modular `index.html`, `ui/static/style.css`, and `ui/static/app.js` files to enable browser caching and optimize load speed.
- **Visual Overhaul:** Added glassmorphism (`backdrop-filter: blur(10px)`), smooth hover cards (`transform: translateY(-3px)`), and a modern color palette.
- **Real-time Sync:** Implemented smart background polling in `app.js` (3-second notification checks, 5-second dashboard updates) so Caregiver and Patient tabs stay synchronized in real-time.
- **Instant History Reset & Context Guard:** Added an instant "Clear History" action that clears local memory and forces a fresh ADK backend session. Context injection guarantees the caregiver is always addressed as **Priya** and the patient as **Rajan ji**.

---

## 📊 Deterministic Urgency Scoring Formula

> **Safety Rule:** The LLM never decides if a pattern is dangerous. The deterministic mathematical formula decides that — the LLM only explains it.

```
composite_score = (dataset_similarity × 0.50)
                + (persistence_days / 14 × 0.30)
                + (avg_severity / 3 × 0.20)
```

| Composite Score | Urgency Level | System Action |
|---|---|---|
| **≥ 0.65** | 🚨 `escalate` | Flagged for doctor referral. Home remedies suppressed. |
| **≥ 0.42** | 👀 `watch` | Emerging pattern. Watchful monitoring & dataset precautions shown. |
| **< 0.42** | 🟢 `low` | Log saved. Reassurance & general wellness guidance provided. |

*A **48-hour cooldown** per `(patient, disease)` pair prevents alert fatigue.*

---

## 🗂️ Real Clinical Datasets Integrated

| Dataset File | Rows / Entries | Function |
|---|---|---|
| `datasets/dataset.csv` | 4,921 rows, 41 diseases | Disease-to-symptom cluster mappings |
| `datasets/Symptom-severity.csv` | 133 symptoms | Clinical severity weights (1–7 scale) |
| `datasets/symptom_Description.csv` | 41 diseases | Plain-language medical summaries |
| `datasets/symptom_precaution.csv` | 41 diseases | Up to 4 actionable precautions per disease |
| `datasets/Symptom2Disease.csv` | 1,200 rows | Natural language symptom query training data |

---

## 🛠️ Project Structure

```
ayuguard-care-platform/
├── ayuguard/                         ← ADK Agent Package
│   ├── agent.py                      ← ayuguard_orchestrator (Root ADK Agent)
│   ├── sub_agents/
│   │   ├── extraction.py             ← symptom_extraction_agent
│   │   ├── retrieval.py              ← condition_retrieval_agent
│   │   └── dietary_reconciliation.py  ← dietary_reconciliation_agent (NEW!)
│   ├── tools/
│   │   ├── symptom_store.py          ← Persistent log store + real-time alerts
│   │   ├── urgency_scorer.py         ← Deterministic 14-day trend scorer
│   │   ├── care_plan.py              ← Care plan manager + notification engine
│   │   ├── patient_profile.py        ← Patient / caregiver profile store
│   │   ├── diagnosis.py              ← Non-critical home care gating
│   │   ├── medical_records.py        ← Gemini AI PDF/image document analyzer
│   │   └── dataset_search.py         ← Weighted Jaccard clinical dataset search
│   └── data/
│       ├── symptom_logs.json         ← Active 14-day patient log store
│       └── uploads/                  ← Uploaded lab reports & prescriptions
├── ui/
│   ├── index.html                    ← Clean SPA HTML structure
│   ├── server.py                     ← FastAPI UI Server & SSE Proxy
│   └── static/
│       ├── style.css                 ← Glassmorphism & layout design system
│       ├── app.js                    ← Real-time polling & client-side logic
│       └── Logo.png                  ← AyuGuard brand logo
├── datasets/                         ← Real clinical CSV datasets
├── Dockerfile.agent                  ← Cloud Run: ADK Agent container
├── Dockerfile.ui                     ← Cloud Run: UI Server container
├── deploy.ps1                        ← Automated Cloud Run deployment script
└── requirements.txt
```

---

## ⚡ Quick Start (Local Setup)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# ayuguard/.env
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=silken-dogfish-484814-g9
GOOGLE_CLOUD_LOCATION=us-central1
```
*(Ensure you have authenticated via `gcloud auth application-default login`)*

### 3. Start the ADK Agent (Terminal 1)
```bash
adk web
# Runs on http://127.0.0.1:8000
```

### 4. Start the UI Server (Terminal 2)
```bash
python ui/server.py
# Runs on http://127.0.0.1:8001
```

Open **http://127.0.0.1:8001** in your browser.

---

## 💬 Sample Demo Prompts

| User Input | AI Subagent Action & Output |
|---|---|
| *"Dad has developed diarrhoea today. What should we feed him considering his pre-diabetes?"* | **`dietary_reconciliation_agent`**: Recognizes conflict between Pre-diabetes (high fiber) and Diarrhoea (low fiber). Reconciles temporary low-fiber bland recovery diet (bananas, soft rice, ORS) and updates Care Plan in real-time. |
| *"Dad has completely recovered from diarrhoea today and feels great!"* | **`dietary_reconciliation_agent`**: Recognizes recovery, de-escalates acute diet, and transitions Care Plan back to healthy pre-diabetes baseline (oats, salads, multigrain roti). |
| *"Dad was tired again today and very thirsty"* | **`symptom_extraction_agent`** + **`urgency_scorer`**: Detects 10-day pattern → `ESCALATE` status → warm alert message for Priya. |
| Upload a blood test PDF | **`medical_records`**: Gemini AI analyzes document, extracts HbA1c / glucose values, and flags abnormal parameters. |

---

## 🌸 Tone & Philosophy

AyuGuard speaks like a **compassionate, medically informed family member** — never an impersonal bot. It respects patient dignity (*Rajan ji*), supports the caregiver (*Priya*), supports Indian languages (English, Hindi, Hinglish), and supplements — **never replaces** — professional medical advice.

---

*Built with Google ADK + Vertex AI Gemini 2.5 Flash + Real Clinical Datasets · Deployed on Google Cloud Run (asia-south1)*
