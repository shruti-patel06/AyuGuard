# 🛠️ AyuGuard Intelligent Caregiver Platform — Custom AI & Logic Skills

This file provides a comprehensive reference of all custom **AI Agentic Skills**, **Deterministic Analysis Systems**, and **Multimodal Processing Pipelines** implemented in AyuGuard. These skills are powered by **Google ADK (Agent Development Kit)** and the **Gemini 2.5 Flash** models, integrated seamlessly with a real-time Fast API SPA dashboard.

---

## 🧭 Core Architectural Pipeline

Every caregiver observations, symptom log, and medical record runs through a structured, multi-agent pipeline:

```
[ Caregiver Upload / Message ]
              │
              ▼
    [ root_agent (ADK) ]
              │
              ├──► 1. Symptom Extraction Agent (Sub-Agent)
              │       ├─ AI-driven NLP parser (Gemini 2.5 Flash)
              │       └─ Normalizes free text (English/Hindi/Hinglish) → Structured JSON
              │
              ├──► 2. Deterministic Urgency Scorer (Python Core)
              │       ├─ NO LLM Gating (Safety Guarantee)
              │       ├─ 14-Day Decay-Weighted rolling Jaccard Search
              │       └─ Cross-references 4,921-row symptom/disease dataset
              │
              ├──► 3. Medical Record Parsing & Storage (Python/GCS)
              │       ├─ Dual-writes records to Firestore & Google Cloud Storage
              │       └─ Extracts parameters, flags anomalies, synthesizes clinical reports
              │
              └──► 4. Localized Caregiver Communicator (Sub-Agent)
                      ├─ Patient-personal language translation
                      └─ Warm, compassionate, non-diagnostic guidance
```

---

## 🧠 Core Agent & Technical Skills

### 1. `symptom_extraction_agent` (AI Sub-Agent)
*   **Purpose**: Parses informal caregiver free-text notes into highly-structured clinical data.
*   **Language Support**: Fully fluent in **Hindi**, **English**, and **Hinglish** (Roman-script Hindi).
*   **Skill Action**: Extracts the symptom name, severity (mild, moderate, severe), date, source, and extra qualitative notes, outputting a Firestore-compatible JSON array.
*   **Location**: `ayuguard/sub_agents/extraction.py`

### 2. `compute_trend_score` (Deterministic Mathematical Logic)
*   **Purpose**: Ensures absolute clinical safety. No language model determines patient risk.
*   **Algorithm**: Computes a decay-weighted similarity score against our **4,921-row symptom-to-disease clinical corpus**.
*   **Formula**:
    $$\text{Composite Score} = (\text{Jaccard Similarity} \times 0.50) + \left(\frac{\text{Persistence Days}}{14} \times 0.30\right) + \left(\frac{\text{Avg Severity}}{3} \times 0.20\right)$$
*   **Alert Escalation**:
    *   `composite >= 0.65` $\rightarrow$ **Escalate** (Pattern matches severe clusters, doctor visit recommended).
    *   `composite >= 0.42` $\rightarrow$ **Watch** (Emerging patterns detected, monitor closely).
    *   `composite < 0.42` $\rightarrow$ **Low** (Quiet log saved, background patterns inactive).
*   **Cooldown Gate**: Hardcoded 48-hour cooldown per patient-disease pair to prevent alert fatigue.
*   **Location**: `ayuguard/tools/urgency_scorer.py`

### 3. `medical_records_agent` (Multimodal Extraction & Dual-Persist)
*   **Purpose**: Processes caregiver-uploaded medical records, lab reports, and prescriptions.
*   **Core Logic**:
    1.  Dual-writes files locally and to secure **Google Cloud Storage** buckets (`gs://ayuguard-uploads-...`) for high durability.
    2.  Uses multimodal Gemini processing to parse lab results, extract vital statistics, compile summaries, and flag anomalous parameters against standard clinical ranges.
    3.  Links abnormalities directly with the patient's ongoing 14-day rolling symptom history.
*   **Location**: `ayuguard/tools/medical_records.py`

### 4. `caregiver_communication_agent` (AI Sub-Agent)
*   **Purpose**: Formulates the user-facing response.
*   **Behavioral Constraints**: 
    *   Never makes a definitive medical diagnosis.
    *   Maintains a warm, empathetic, clinical-assistant voice.
    *   Always addresses both the patient and caregiver by their names retrieved from their `patient_profile.json`.
    *   Matches the caregiver's spoken language seamlessly.
*   **Location**: `ayuguard/tools/communication.py`

---

## 📂 Clinical Reference Corpus (Datasets)

AyuGuard executes matches using actual medical reference datasets stored locally and loaded at runtime:

1.  **`datasets/dataset.csv`** (4,921 Rows): Maps symptom clusters to 41 primary chronic and acute diseases.
2.  **`datasets/Symptom-severity.csv`** (133 Symptoms): Clinical weights graded 1–7 used to normalize avg severity.
3.  **`datasets/symptom_Description.csv`**: Contains strict plain-text explanations of mapped conditions.
4.  **`datasets/symptom_precaution.csv`**: 4 clinically validated preventive tips per condition, retrieved verbatim.

---

## ⚡ Deployment & Cloud Operations

AyuGuard is completely Dockerized and deployed onto **Google Cloud Run** using a fully automated multi-service topology:

*   **Internal Service (`ayuguard-agent`)**: Internal-only ADK orchestrator that handles secure AI agent pipelines and communicates directly with GCP Secret Manager for API keys.
*   **Public Service (`ayuguard-ui`)**: Fast API SPA serving the caregiver console, dynamically integrated with the secure backend.
