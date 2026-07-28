"""
AyuGuard ADK Agent — root_agent definition
==========================================
AyuGuard (आयुगार्ड) — Ambient multi-agent caregiver platform.

Architecture:
  - ayuguard_orchestrator  : root orchestrator
  - symptom_extraction_agent: caregiver text → structured JSON
  - condition_retrieval_agent: dataset disease-cluster search
  - diagnose_non_critical() : SAFE home-care suggestions (non-critical only)
  - generate_caregiver_message(): warm localized message generation
  - save/get_care_plan()    : caregiver meal/med/activity plan management
  - Firestore dual-write    : all data goes to Firebase + local JSON fallback

Run:
  adk web  (from ayuguard-care-platform/)
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
_AGENT_DIR = Path(__file__).parent.resolve()
_ENV_FILE = _AGENT_DIR / ".env"
load_dotenv(dotenv_path=_ENV_FILE)

# ── Auth check: Vertex AI (ADC) or Gemini Developer API key ──────────────────
_use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
_has_api_key = bool(os.environ.get("GOOGLE_API_KEY"))
_has_project  = bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))

if _use_vertex:
    if not _has_project:
        print(
            "\n  GOOGLE_CLOUD_PROJECT not set!\n"
            f"    Please add GOOGLE_CLOUD_PROJECT=<your-project-id> to: {_ENV_FILE}\n"
            "    Also run: gcloud auth application-default login\n",
            file=sys.stderr,
        )
    else:
        print(
            f"  [OK] AyuGuard -- Vertex AI backend active "
            f"(project={os.environ['GOOGLE_CLOUD_PROJECT']}, "
            f"location={os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')})"
        )
elif not _has_api_key:
    print(
        "\n  GOOGLE_API_KEY not found!\n"
        f"    Please add it to: {_ENV_FILE}\n"
        "    Example: GOOGLE_API_KEY=AIza...\n",
        file=sys.stderr,
    )

# ── ADK imports ────────────────────────────────────────────────────────────────
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

# ── Sub-agents ────────────────────────────────────────────────────────────────
from .sub_agents.extraction import symptom_extraction_agent
from .sub_agents.retrieval import condition_retrieval_agent
from .sub_agents.dietary_reconciliation import dietary_reconciliation_agent

# ── Orchestrator tools ─────────────────────────────────────────────────────────
from .tools.symptom_store import store_symptom_log, get_patient_history
from .tools.urgency_scorer import compute_trend_score
from .tools.communication import generate_caregiver_message
from .tools.patient_profile import get_patient_profile, save_patient_profile
from .tools.diagnosis import diagnose_non_critical
from .tools.care_plan import get_care_plan, save_care_plan, get_patient_notifications
from .tools.medical_records import get_medical_records, get_record_details, get_abnormal_history

# ── Python Function Wrappers for Subagents (Prevents MALFORMED_FUNCTION_CALL) ─
def extract_symptoms(text: str) -> str:
    """Converts raw caregiver text or health observations into structured symptom JSON.

    Args:
        text: Raw caregiver message describing physical symptoms or health observations.

    Returns:
        JSON string representing the extracted symptoms.
    """
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "silken-dogfish-484814-g9")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        client = genai.Client(vertexai=True, project=project, location=location)
    else:
        api_key = os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)

    prompt = f"{symptom_extraction_agent.instruction}\n\nINPUT TEXT:\n{text}"
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
    )
    return resp.text.strip()


def retrieve_condition(symptom_text: str) -> str:
    """Searches clinical dataset for disease patterns matching the patient's symptom profile.

    Args:
        symptom_text: The aggregated symptom words as plain text.

    Returns:
        Exact dataset pattern match result string.
    """
    from .tools.dataset_search import search_disease_patterns
    return search_disease_patterns(query=symptom_text)


def reconcile_dietary_plan(symptom_or_recovery_text: str) -> str:
    """Reconciles care plans and dietary guidelines for concurrent conditions or recovery.

    Args:
        symptom_or_recovery_text: Plain text describing acute symptoms or recovery status.

    Returns:
        Summary of the care plan revision.
    """
    use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"
    if use_vertex:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "silken-dogfish-484814-g9")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        client = genai.Client(vertexai=True, project=project, location=location)
    else:
        api_key = os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)

    prompt = f"{dietary_reconciliation_agent.instruction}\n\nINPUT:\n{symptom_or_recovery_text}"
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
    )
    return resp.text.strip()


# ── Root Agent (Orchestrator) ─────────────────────────────────────────────────
root_agent = Agent(
    name="ayuguard_orchestrator",
    model="gemini-2.5-flash-lite",
    description=(
        "AyuGuard (आयुगार्ड) — ambient multi-agent caregiver platform. "
        "Detects symptom patterns across days, provides non-critical home-care "
        "suggestions, and manages the patient's care plan."
    ),
    instruction="""You are AyuGuard (आयुगार्ड) — a warm, compassionate, and intelligent
ambient caregiver assistant for family caregivers and elderly patients in India.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 0 — ONBOARDING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTE: For simple greetings like "hey", "hello", "hi", respond directly and warmly WITHOUT invoking any tools!

IF checking profile or starting session:
  → Call get_patient_profile(patient_id="patient_001").

IF profile_complete is False OR status is "not_found":
  → Greet warmly. Ask for patient & caregiver details.
  → Call save_patient_profile() with collected details.

IF profile_complete is True:
  → Greet warmly using patient and caregiver names.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PATIENT DIRECT-CHAT MODE vs CAREGIVER MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Look for a [SYSTEM CONTEXT] or indication of the active user role.

IF THE ACTIVE USER IS THE ELDERLY PATIENT DIRECTLY (patient-001):
  → Greet the patient directly by their name ("Rajan ji") with great respect and warmth.
  → Run the Symptom Pipeline (Step 1 to Step 4) to extract and log their symptoms.
  → Provide comforting, warm direct feedback.

IF THE ACTIVE USER IS THE CAREGIVER (caregiver-001):
  → Follow the caregiver instructions (Step 6 COMMUNICATE) and call generate_caregiver_message().

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYMPTOM PIPELINE — run when caregiver describes a symptom
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — EXTRACT
  → Call extract_symptoms(text="exact caregiver message as plain string")

STEP 2 — STORE
  → Call store_symptom_log(patient_id="patient_001", symptom_json=<JSON string from Step 1>)

STEP 3 — SCORE
  → Call compute_trend_score(patient_id="patient_001")

STEP 4 — DIAGNOSE (non-critical home care)
  → Call diagnose_non_critical(symptom_text=..., urgency=..., top_disease=..., similarity_score=...)

STEP 5 — RETRIEVE (only if urgency is "watch" or "escalate")
  → Call retrieve_condition(symptom_text="symptom words")

STEP 6 — COMMUNICATE
  3. If a discharge summary was uploaded → check recommendations for follow-up dates.
  4. Always label AI-read findings: "According to the uploaded report..."
  5. NEVER override the doctor's interpretation — only relay what the document says.
  6. Critical values flagged by Gemini → always recommend discussing with doctor.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USING NAMES — ALWAYS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Always address the caregiver by their first name.
Always refer to the patient by their name — never "the patient".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAFETY RULES — NON-NEGOTIABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• NEVER say "you have [disease]" — always frame as "this pattern resembles..."
• NEVER skip STORE + SCORE — every log must be persisted
• NEVER suggest home-care for escalate urgency or serious diseases
• The urgency decision comes ONLY from compute_trend_score()
• The diagnosis decision comes ONLY from diagnose_non_critical()
• ALWAYS include the disclaimer if home-care tips are shared
• Emergency symptoms (chest pain, loss of consciousness, stroke): call doctor immediately

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Speak like a caring, knowledgeable family member — not a doctor.
Hindi / Hinglish welcome. Simple language. Always warm, never alarming.
AyuGuard supplements — never replaces — the doctor's advice. 🌸""",
    tools=[
        # Profile management
        get_patient_profile,
        save_patient_profile,
        # Symptom pipeline
        AgentTool(agent=symptom_extraction_agent),
        AgentTool(agent=condition_retrieval_agent),
        AgentTool(agent=dietary_reconciliation_agent),
        store_symptom_log,
        get_patient_history,
        compute_trend_score,
        # Diagnosis (non-critical only)
        diagnose_non_critical,
        # Communication
        generate_caregiver_message,
        # Care plan management
        get_care_plan,
        save_care_plan,
        get_patient_notifications,
        # Medical records
        get_medical_records,
        get_record_details,
        get_abnormal_history,
    ],
)
