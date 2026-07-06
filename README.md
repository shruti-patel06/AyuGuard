# AyuGuard — Ambient Multi-Agent Caregiver Platform

> *Early warning signals for disease progression, powered by real clinical datasets and Google ADK.*

---

## What is AyuGuard?

AyuGuard (आयुगार्ड) is an ambient multi-agent caregiver assistant for family caregivers looking after elderly or chronically ill patients.

**The core insight:** Caregivers answer individual questions one at a time — "is this headache serious?", "is this okay with his diabetes?" Each question looks mild. A reactive chatbot almost always says "monitor it." But the real risk lives in **patterns across days and weeks** — mild fatigue + increased thirst + blurry vision over 10 days is a classic early metabolic warning sign. No caregiver has the bandwidth to track and cross-reference sparse, irregular observations manually.

That is AyuGuard's job.

---

## Architecture

```
Caregiver input
     │
     ▼
[Orchestrator: ayuguard_orchestrator]   ← root_agent (ADK)
     │
     ├── AgentTool → symptom_extraction_agent
     │        Converts free text (Hindi / English / Hinglish)
     │        → structured symptom JSON
     │
     ├── Tool → store_symptom_log()
     │        Persists log to ayuguard/data/symptom_logs.json
     │        (Firestore-compatible schema)
     │
     ├── Tool → compute_trend_score()   ← DETERMINISTIC — no LLM
     │        14-day decay-weighted pattern window
     │        + weighted Jaccard search against 4,921-row dataset
     │        + urgency formula: similarity×0.5 + persistence×0.3 + severity×0.2
     │        + 48-hour cooldown gate
     │
     ├── AgentTool → condition_retrieval_agent   (only if watch/escalate)
     │        Searches real clinical dataset for matching disease cluster
     │        Returns dataset description + precautions verbatim
     │
     └── AgentTool → caregiver_communication_agent
              Writes warm, localized message in caregiver's language
              NEVER diagnoses — says "this pattern is sometimes associated with..."
```

### The Safety Rule
> **The LLM never decides what is dangerous. The deterministic scoring formula decides that. The LLM only explains it.**

---

## Real Clinical Datasets Used

| File | Size | What it provides |
|---|---|---|
| `datasets/dataset.csv` | 4,921 rows, 41 diseases | Disease → symptom clusters (reference corpus) |
| `datasets/Symptom-severity.csv` | 133 symptoms | Clinical severity weights 1–7 (used in scoring) |
| `datasets/symptom_Description.csv` | 41 diseases | Plain-language disease descriptions (retrieved, not generated) |
| `datasets/symptom_precaution.csv` | 41 diseases | Up to 4 actionable precautions per disease |
| `datasets/Symptom2Disease.csv` | 1,200 rows | NLP text → disease (future text-classifier use) |

---

## Urgency Formula

```
composite = similarity × 0.50
          + (persistence_days / 14) × 0.30
          + (avg_severity / 3) × 0.20

composite ≥ 0.65  →  "escalate"  (pattern worth a doctor visit)
composite ≥ 0.42  →  "watch"     (pattern emerging, monitor closely)
composite <  0.42  →  "low"       (log saved, nothing to flag yet)
```

**Severity** is a blend of:
- Caregiver-reported intensity (mild=1, moderate=2, severe=3)
- Dataset clinical weight from `Symptom-severity.csv` (1–7, normalised to 1–3)

**48-hour cooldown** per `(patient, disease)` pair prevents alert fatigue.

---

## Project Structure

```
ayuguard-care-platform/
├── ayuguard/                        ← ADK agent package (discovered by `adk web`)
│   ├── __init__.py
│   ├── agent.py                     ← root_agent orchestrator
│   ├── prompts.py                   ← legacy (superseded)
│   ├── .env                         ← GOOGLE_API_KEY goes here
│   ├── data/
│   │   └── symptom_logs.json        ← rolling patient log store
│   ├── tools/
│   │   ├── dataset_search.py        ← weighted Jaccard search vs real datasets
│   │   ├── symptom_store.py         ← Firestore-compatible JSON persistence
│   │   ├── trend_window.py          ← 14-day decay-weighted aggregation
│   │   └── urgency_scorer.py        ← deterministic scoring (NO LLM)
│   └── sub_agents/
│       ├── extraction.py            ← symptom_extraction_agent
│       ├── retrieval.py             ← condition_retrieval_agent
│       └── communication.py         ← caregiver_communication_agent
├── datasets/                        ← uploaded real clinical CSV datasets
├── mcp_server/                      ← legacy MCP server (original AyuGuard v1)
├── scripts/
│   └── seed_demo_logs.py            ← pre-seeds 14-day Diabetes demo pattern
└── requirements.txt
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your API key

```
# ayuguard/.env
GOOGLE_API_KEY=AIza...
```

### 3. Seed the demo

```bash
python scripts/seed_demo_logs.py
```

### 4. Run

```bash
adk web
```

Open **http://localhost:8000** → select `ayuguard` agent.

---

## Demo Prompts

| Input | Expected behaviour |
|---|---|
| `"Dad was tired again today and very thirsty"` | Full pipeline → ESCALATE → warm Diabetes-pattern message |
| `"He had a slight cough today"` | Log saved → LOW urgency → brief reassurance |
| `"Show me the history"` | Returns patient log summary |
| `"Papa bahut thake hue hai"` (Hindi) | Extracts fatigue → stores → scores → Hindi reply |

---

## Core Tone

AyuGuard speaks like a **caring, medically informed grandchild** — not a doctor.
Simple language. Hindi/Hinglish welcome. Always warm. Never alarming.
It supplements — never replaces — the doctor's advice.

---

*Built with Google ADK + Gemini 2.0 Flash + real clinical datasets*
