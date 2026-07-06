"""
AyuGuard Dataset Search
========================
Searches the uploaded real clinical datasets for disease-symptom patterns
that match the patient's current aggregated symptom profile.

Datasets consumed:
  datasets/dataset.csv              — 4,921 rows × 41 diseases × up to 17 symptoms
  datasets/Symptom-severity.csv     — 133 symptoms × severity weights (1–7)
  datasets/symptom_Description.csv  — 41 diseases × plain-language descriptions
  datasets/symptom_precaution.csv   — 41 diseases × up to 4 precautions

Matching strategy: weighted Jaccard similarity
  - Each matched symptom is weighted by its clinical severity score (from the dataset)
  - High-severity matches (chest_pain=7, high_fever=7) count more than low ones (itching=1)
  - Normalized across the disease's full symptom burden to avoid bias toward
    diseases with many symptoms

This module is retrieval-only — it never generates medical claims.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

# ── Dataset paths ───────────────────────────────────────────────────────────────
# tools/ → ayuguard/ → ayuguard-care-platform/ → datasets/
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DS = _PROJECT_ROOT / "datasets"

# ── Stop words ──────────────────────────────────────────────────────────────────
_STOP = {
    "a", "an", "the", "and", "or", "of", "in", "on", "is", "was",
    "has", "with", "to", "for", "from", "my", "i", "he", "she", "they",
    "it", "be", "been", "have", "had", "do", "did",
}

# ── Caregiver language → dataset canonical tokens ───────────────────────────────
# Maps common informal/Hindi-adjacent symptom words to dataset token equivalents.
SYNONYM_MAP: dict[str, str] = {
    "tired": "fatigue",
    "tiredness": "fatigue",
    "exhausted": "fatigue",
    "exhaustion": "fatigue",
    "thirsty": "thirst",
    "thirst": "thirst",
    "pee": "urination",
    "peeing": "urination",
    "bathroom": "urination",
    "urinating": "urination",
    "urination": "urination",
    "blurry": "blurred",
    "blurred": "blurred",
    "dizzy": "dizziness",
    "dizziness": "dizziness",
    "shaky": "shivering",
    "shaking": "shivering",
    "breathless": "breathlessness",
    "breathing": "breathlessness",
    "swollen": "swelling",
    "swelling": "swelling",
    "aching": "pain",
    "hurting": "pain",
    "pale": "pallor",
    "paleness": "pallor",
    "numb": "numbness",
    "itching": "itching",
    "itchy": "itching",
    "rash": "skin_rash",
    "coughing": "cough",
    "vomit": "vomiting",
    "nauseous": "nausea",
    "constipated": "constipation",
    "diarrhea": "diarrhoea",
    "loose": "diarrhoea",
    "appetite": "appetite",
    "hungry": "hunger",
    "sweating": "sweating",
    "confused": "sensorium",
    "confusion": "sensorium",
    "palpitation": "palpitations",
    "heartbeat": "palpitations",
    "fever": "fever",
    "temperature": "fever",
    "chill": "chills",
    "cold": "chills",
    "weight": "weight",
    "gaining": "weight_gain",
    "losing": "weight_loss",
    "sleeping": "sleep",
    "sleepy": "lethargy",
    "lethargic": "lethargy",
    "headache": "headache",
    "head": "headache",
    "joint": "joint",
    "joints": "joint",
    "muscle": "muscle",
    "muscles": "muscle",
    "skin": "skin",
    "yellow": "yellowish",
    "yellowish": "yellowish",
    "urine": "urine",
    "dark": "dark_urine",
    "frequent": "polyuria",
    "urgency": "urination",
    "bloating": "distention",
    "stomach": "stomach",
    "abdominal": "abdominal",
    "chest": "chest",
    "back": "back",
    "neck": "neck",
    "knee": "knee",
    "ankle": "swollen_legs",
    "ankles": "swollen_legs",
    "vision": "vision",
    "eyesight": "vision",
    "eye": "eyes",
    "eyes": "eyes",
    "runny": "runny_nose",
    "nose": "nose",
    "sneezing": "sneezing",
    "phlegm": "phlegm",
    "mucus": "phlegm",
}


# ── Data loaders (cached for performance) ──────────────────────────────────────

@lru_cache(maxsize=1)
def _load_disease_clusters() -> dict[str, set[str]]:
    """
    Load dataset.csv and collapse 4,921 rows into 41 disease clusters.
    Each cluster is the UNION of all symptoms seen across all rows for that disease.
    Returns dict[disease_name -> set[canonical_symptom_names]].
    """
    clusters: dict[str, set[str]] = {}
    path = _DS / "dataset.csv"
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            disease = row.get("Disease", "").strip()
            if not disease:
                continue
            if disease not in clusters:
                clusters[disease] = set()
            for i in range(1, 18):
                sym = row.get(f"Symptom_{i}", "").strip().lower()
                if sym:
                    clusters[disease].add(sym)
    return clusters


@lru_cache(maxsize=1)
def _load_severity_weights() -> dict[str, int]:
    """Load Symptom-severity.csv → dict[symptom_name, weight (1–7)]."""
    weights: dict[str, int] = {}
    path = _DS / "Symptom-severity.csv"
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get("Symptom", "").strip().lower()
            try:
                w = int(row.get("weight", 3))
            except (ValueError, TypeError):
                w = 3
            if sym:
                weights[sym] = w
    return weights


@lru_cache(maxsize=1)
def _load_descriptions() -> dict[str, str]:
    """Load symptom_Description.csv → dict[disease_name, description]."""
    descs: dict[str, str] = {}
    path = _DS / "symptom_Description.csv"
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            disease = row.get("Disease", "").strip()
            desc = row.get("Description", "").strip()
            if disease:
                descs[disease] = desc
    return descs


@lru_cache(maxsize=1)
def _load_precautions() -> dict[str, list[str]]:
    """Load symptom_precaution.csv → dict[disease_name, [precaution_1..4]]."""
    precs: dict[str, list[str]] = {}
    path = _DS / "symptom_precaution.csv"
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            disease = row.get("Disease", "").strip()
            ps = [
                row.get(f"Precaution_{i}", "").strip()
                for i in range(1, 5)
                if row.get(f"Precaution_{i}", "").strip()
            ]
            if disease:
                precs[disease] = ps
    return precs


# ── Tokenisation ────────────────────────────────────────────────────────────────

def _tokenize_query(symptom_text: str) -> set[str]:
    """Convert caregiver symptom text to a normalised token set."""
    raw = set(re.findall(r"\b[a-z]+\b", symptom_text.lower())) - _STOP
    expanded: set[str] = set()
    for token in raw:
        mapped = SYNONYM_MAP.get(token, token)
        # Add both the mapped form and its underscore-free components
        expanded.add(mapped)
        expanded.update(re.findall(r"\b[a-z]+\b", mapped.replace("_", " ")))
    return expanded - _STOP


def _tokenize_symptom_set(symptoms: set[str]) -> set[str]:
    """Convert underscore-separated symptom names to word tokens."""
    tokens: set[str] = set()
    for sym in symptoms:
        tokens.update(re.findall(r"\b[a-z]+\b", sym.replace("_", " ")))
    return tokens - _STOP


# ── Scoring ─────────────────────────────────────────────────────────────────────

def _weighted_jaccard(
    query_tokens: set[str],
    disease_symptoms: set[str],
    severity: dict[str, int],
) -> tuple[float, list[str]]:
    """
    Compute weighted Jaccard similarity and return (score, matched_symptom_names).

    Each matched symptom is weighted by its clinical severity (1–7).
    High-severity symptom matches count proportionally more.
    """
    disease_tokens = _tokenize_symptom_set(disease_symptoms)
    matched_tokens = query_tokens & disease_tokens

    if not matched_tokens or not disease_tokens:
        return 0.0, []

    # For each matched token, find the highest-severity dataset symptom it maps to
    intersection_weight = 0.0
    matched_syms: list[str] = []
    for token in matched_tokens:
        best_w = 1
        best_sym = token
        for sym in disease_symptoms:
            if token in sym.replace("_", " ").split():
                w = severity.get(sym, 3)
                if w > best_w:
                    best_w = w
                    best_sym = sym
        intersection_weight += best_w
        matched_syms.append(best_sym)

    # Normalised denominator: total severity weight of the disease's symptom set
    total_disease_weight = sum(severity.get(s, 3) for s in disease_symptoms)

    # Coverage: fraction of query tokens that matched (how "complete" the pattern is)
    coverage = len(matched_tokens) / max(len(query_tokens), 1)

    # Combined: weighted precision (specificity) + coverage (recall)
    precision = intersection_weight / max(total_disease_weight, 1)
    score = precision * 0.45 + coverage * 0.55

    return min(1.0, score), matched_syms


# ── Public ADK tool ─────────────────────────────────────────────────────────────

def search_disease_patterns(symptom_list: str, top_k: int = 3) -> dict:
    """
    Search the AyuGuard clinical dataset for diseases matching the symptom pattern.

    Powered by the uploaded datasets:
      - dataset.csv  (4,921 rows, 41 diseases)
      - Symptom-severity.csv (severity weights 1–7)
      - symptom_Description.csv + symptom_precaution.csv (enrichment)

    This tool is retrieval-only: it reports what the dataset contains.
    It never generates new medical claims or inferences.

    Args:
        symptom_list: Space/comma-separated symptom text from the caregiver,
                     e.g. "fatigue increased thirst frequent urination blurry vision"
        top_k: Number of top matches to return (default: 3, max: 10).

    Returns:
        dict with:
          - status: "success" or "error"
          - matches: list of {disease, similarity_score, description,
                     precautions, matched_symptoms}
          - search_method: "dataset_weighted_jaccard"
          - query_tokens: list of tokens extracted from input
    """
    try:
        clusters = _load_disease_clusters()
        severity = _load_severity_weights()
        descriptions = _load_descriptions()
        precautions = _load_precautions()
    except FileNotFoundError as exc:
        return {"status": "error", "message": f"Dataset file missing: {exc}", "matches": []}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"Dataset load error: {exc}", "matches": []}

    query_tokens = _tokenize_query(symptom_list)

    if not query_tokens:
        return {
            "status": "success",
            "matches": [],
            "message": "No symptom tokens extracted. Please describe specific symptoms.",
            "search_method": "dataset_weighted_jaccard",
            "query_tokens": [],
        }

    # Score every disease cluster
    scored: list[tuple[float, str, list[str]]] = []
    for disease, syms in clusters.items():
        score, matched = _weighted_jaccard(query_tokens, syms, severity)
        scored.append((score, disease, matched))

    scored.sort(key=lambda x: -x[0])
    top = scored[: min(top_k, 10)]

    matches = []
    for sim, disease, matched in top:
        # Fuzzy-match description and precautions (dataset names may differ in case/spacing)
        disease_lower = disease.lower().strip()
        desc = next(
            (v for k, v in descriptions.items() if k.lower().strip() == disease_lower),
            "",
        )
        prec = next(
            (v for k, v in precautions.items() if k.lower().strip() == disease_lower),
            [],
        )
        # Clean matched symptoms for display
        display_matched = [s.replace("_", " ") for s in matched[:5]]

        matches.append({
            "disease": disease,
            "similarity_score": round(sim, 4),
            "description": desc,
            "precautions": prec,
            "matched_symptoms": display_matched,
        })

    return {
        "status": "success",
        "matches": matches,
        "search_method": "dataset_weighted_jaccard",
        "query_tokens": list(query_tokens),
    }


def get_symptom_severity_weight(symptom_name: str) -> int:
    """
    Look up the clinical severity weight for a symptom from the dataset.

    Args:
        symptom_name: A symptom name (caregiver language or dataset canonical form).

    Returns:
        An integer severity weight 1–7. Returns 3 (moderate default) if not found.
    """
    weights = _load_severity_weights()
    clean = symptom_name.lower().strip().replace(" ", "_")
    if clean in weights:
        return weights[clean]
    # Token overlap fallback
    tokens = set(re.findall(r"\b[a-z]+\b", symptom_name.lower()))
    for sym, w in weights.items():
        if tokens & set(sym.replace("_", " ").split()):
            return w
    return 3
