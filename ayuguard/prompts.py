"""
AyuGuard prompts.py — SUPERSEDED
==================================
This module has been superseded by the multi-agent architecture.

The system instruction now lives in ayuguard/agent.py (root_agent.instruction).
The warm tone, paradigm-shift logic, and care protocols are distributed across:

  - ayuguard/agent.py              : orchestrator instruction (pipeline routing)
  - ayuguard/sub_agents/extraction.py  : structured symptom extraction
  - ayuguard/sub_agents/retrieval.py   : dataset retrieval (real clinical data)
  - ayuguard/sub_agents/communication.py : warm caregiver message generation

The original AyuGuard tone (caring grandchild to grandparent, Hindi/Hinglish)
is preserved in communication.py.

The paradigm shift (acute vs chronic mode) is now replaced by the longitudinal
pattern-detection model: urgency is determined by the deterministic scoring
formula in tools/urgency_scorer.py, not the LLM.

This file is kept for reference only. It is not imported by any active module.
"""

# Original AyuGuard prompts preserved below for reference.
# The active system instruction is in ayuguard/agent.py.

AYUGUARD_LEGACY_INSTRUCTION = """
[LEGACY — not active]

You are AyuGuard (आयुगार्ड) — a warm, compassionate, and intelligent
ambient caregiver assistant for elderly patients in India.

PARADIGM SHIFT LOGIC (replaced by deterministic scoring in upgraded system):
  - If acute_events is NON-EMPTY  → ACUTE CARE MODE
  - If acute_events is EMPTY       → CHRONIC MANAGEMENT MODE

This logic has been upgraded to a rolling 14-day trend window with
dataset-backed similarity scoring. The new system detects patterns
across days and weeks rather than reacting to isolated symptoms.
"""
