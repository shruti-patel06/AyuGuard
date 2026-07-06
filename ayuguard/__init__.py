"""
AyuGuard Agent Package
======================
Exports root_agent for ADK CLI discovery.

Architecture (upgraded with CareTrend AI's longitudinal pattern engine):
  - root_agent = ayuguard_orchestrator
  - Sub-agents via AgentTool: extraction, retrieval, communication
  - Deterministic scoring: trend_window + dataset_search + urgency_scorer
  - Real clinical datasets: datasets/ (41 diseases, 4,921 symptom-disease rows)
"""
from . import agent  # noqa: F401 — triggers root_agent binding
