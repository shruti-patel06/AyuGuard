"""
Vector Search — Gemini text-embedding-004 + Cosine Similarity
==============================================================
Simulates Firestore Vector Search for the hackathon prototype.

Pipeline:
  1. Load clinical reference clusters from condition_clusters.json
  2. On first use: embed each cluster's symptom text via Gemini text-embedding-004
     and cache results to embeddings_cache.json
  3. At query time: embed the patient's pattern text, compute cosine similarity
     against all cached embeddings, return top-k matches
  4. Fallback: if the API is unavailable, use Jaccard keyword similarity

Replacing this with real Firestore Vector Search requires only modifying
_ensure_cluster_embeddings() and the search loop below.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent.parent / "data"
_CLUSTERS_FILE = _DATA_DIR / "condition_clusters.json"
_CACHE_FILE = _DATA_DIR / "embeddings_cache.json"

# ── In-memory caches ────────────────────────────────────────────────────────────
_clusters_cache: list[dict] | None = None
_embeddings_cache: dict[str, list[float]] | None = None


# ── Data loading ────────────────────────────────────────────────────────────────

def _load_clusters() -> list[dict]:
    global _clusters_cache
    if _clusters_cache is None:
        with _CLUSTERS_FILE.open("r", encoding="utf-8") as f:
            _clusters_cache = json.load(f)
    return _clusters_cache


def _load_embedding_cache() -> dict[str, list[float]]:
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    if _CACHE_FILE.exists():
        with _CACHE_FILE.open("r", encoding="utf-8") as f:
            _embeddings_cache = json.load(f)
    else:
        _embeddings_cache = {}
    return _embeddings_cache


def _save_embedding_cache(cache: dict[str, list[float]]) -> None:
    global _embeddings_cache
    with _CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cache, f)
    _embeddings_cache = cache


# ── Gemini Embedding API ────────────────────────────────────────────────────────

def _embed_text(text: str) -> list[float] | None:
    """
    Embed a text string using Gemini text-embedding-004.
    Returns a list of 768 floats, or None if the API call fails.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=genai_types.EmbedContentConfig(output_dimensionality=768),
        )
        return list(result.embeddings[0].values)
    except Exception as exc:  # noqa: BLE001
        print(f"[VectorSearch] Embedding API error: {exc} — using keyword fallback", flush=True)
        return None


# ── Math helpers ────────────────────────────────────────────────────────────────

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length float vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


_STOP_WORDS = {"a", "an", "the", "and", "or", "of", "in", "on", "is", "was", "has", "with"}


def _keyword_similarity(query_text: str, cluster_symptoms: list[str]) -> float:
    """
    Jaccard + coverage hybrid fallback when Gemini API is unavailable.
    Handles partial matches (e.g., 'thirst' overlaps 'increased thirst').
    """
    query_tokens = set(re.findall(r"\b\w+\b", query_text.lower())) - _STOP_WORDS
    cluster_tokens: set[str] = set()
    for sym in cluster_symptoms:
        cluster_tokens.update(re.findall(r"\b\w+\b", sym.lower()))
    cluster_tokens -= _STOP_WORDS

    if not query_tokens or not cluster_tokens:
        return 0.0

    intersection = query_tokens & cluster_tokens
    union = query_tokens | cluster_tokens
    jaccard = len(intersection) / len(union)

    # Coverage: what fraction of cluster symptom *strings* contain a query word
    matched_symptoms = sum(
        1 for sym in cluster_symptoms
        if any(q in sym.lower() or sym.lower() in q for q in query_tokens)
    )
    coverage = matched_symptoms / max(len(cluster_symptoms), 1)

    return min(1.0, jaccard * 0.55 + coverage * 0.45)


# ── Embedding bootstrap ─────────────────────────────────────────────────────────

def _ensure_cluster_embeddings() -> dict[str, list[float]]:
    """
    Ensure all reference clusters have cached embeddings.
    Computes missing ones via Gemini API and saves to embeddings_cache.json.
    Returns the full cache (may be partial if API is unavailable).
    """
    clusters = _load_clusters()
    cache = _load_embedding_cache()
    changed = False

    for cluster in clusters:
        cid = cluster["id"]
        if cid not in cache:
            # Build embedding text: symptom list is most semantically rich
            text = " ".join(cluster["symptoms"])
            embedding = _embed_text(text)
            if embedding:
                cache[cid] = embedding
                changed = True

    if changed:
        _save_embedding_cache(cache)

    return cache


# ── Public ADK Tool ─────────────────────────────────────────────────────────────

def search_condition_patterns(symptom_list: str, top_k: int = 3) -> dict:
    """
    Search the clinical reference corpus for condition clusters matching the
    given symptom pattern. Uses Gemini text-embedding-004 + cosine similarity
    when available; falls back to Jaccard keyword similarity otherwise.

    This tool is intentionally retrieval-only: it never generates or infers
    medical information. It only returns what is stored in condition_clusters.json.

    Args:
        symptom_list: Space- or comma-separated observed symptoms, e.g.
                     "fatigue increased thirst frequent urination blurry vision".
        top_k: Number of top-matching clusters to return (default: 3, max: 15).

    Returns:
        A dict with:
          - status: "success" or "error"
          - matches: list of {id, name, similarity_score, description, severity_weight}
          - search_method: "embedding" or "keyword"
          - query: the input symptom_list
    """
    clusters = _load_clusters()
    if not clusters:
        return {"status": "error", "message": "No reference clusters found.", "matches": []}

    top_k = min(top_k, len(clusters))

    # Try embedding-based search first
    cache = _ensure_cluster_embeddings()
    query_embedding = _embed_text(symptom_list) if cache else None

    scores: list[tuple[float, dict]] = []

    if query_embedding:
        for cluster in clusters:
            cid = cluster["id"]
            if cid in cache:
                sim = _cosine_similarity(query_embedding, cache[cid])
            else:
                sim = _keyword_similarity(symptom_list, cluster["symptoms"])
            scores.append((sim, cluster))
        method = "embedding"
    else:
        # Full keyword fallback
        for cluster in clusters:
            sim = _keyword_similarity(symptom_list, cluster["symptoms"])
            scores.append((sim, cluster))
        method = "keyword"

    scores.sort(key=lambda x: -x[0])

    return {
        "status": "success",
        "matches": [
            {
                "id": c["id"],
                "name": c["name"],
                "similarity_score": round(sim, 4),
                "description": c["description"],
                "severity_weight": c.get("severity_weight", 1),
            }
            for sim, c in scores[:top_k]
        ],
        "search_method": method,
        "query": symptom_list,
    }
