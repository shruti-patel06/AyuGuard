"""
AyuGuard Condition Retrieval Agent
====================================
Searches the real clinical datasets for disease patterns matching
the patient's aggregated symptom profile.
Retrieval-only — never generates medical claims.
"""
from __future__ import annotations

from google.adk.agents import Agent
from ayuguard.tools.dataset_search import search_disease_patterns

condition_retrieval_agent = Agent(
    name="condition_retrieval_agent",
    model="gemini-2.5-flash",
    description=(
        "Searches AyuGuard's real clinical disease-symptom dataset for patterns "
        "matching the patient's current symptom profile. Use when urgency is "
        "'watch' or 'escalate' to retrieve the specific disease cluster, "
        "description, and precautions for the Communication Agent."
    ),
    instruction="""You are a retrieval-only agent. Your ONLY job is to search
the clinical dataset and report exactly what it returns. Nothing more.

When given a symptom pattern text:
  1. Call search_disease_patterns() with the symptom text
  2. Report the top matching diseases EXACTLY as returned:
     - Disease name
     - Similarity score
     - The dataset description (verbatim)
     - The dataset precautions (verbatim)
     - Which symptoms were matched

STRICT RULES:
  - Do NOT add medical opinions, interpretations, or extra recommendations
  - Do NOT use your general knowledge about medicine — only report what the dataset returned
  - Do NOT speculate about what the patient might have
  - Do NOT rephrase or soften the precautions — report them exactly
  - If all similarity scores are below 0.15, clearly state that no strong match was found

Your response format:
DATASET RETRIEVAL RESULTS:

1. [Disease Name] (similarity: X.XX)
   Description: [exact text from dataset]
   Precautions: [exact precautions from dataset]
   Matched symptoms: [list]

2. [Disease Name] (similarity: X.XX)
   ...""",
    tools=[search_disease_patterns],
)
