"""
Project Recall — Hybrid Memory Retriever

Combines dense vector retrieval with lightweight sparse/text search and metadata
matching to generate a robust candidate pool for the LLM judge.

Architecture:
  dense (semantic vectors) ─┐
  sparse (text search) ────┼→ merge/dedupe ─→ rank ─→ final candidates
  metadata (user, topic) ──┘

When uncertain, prefer no memory over wrong memory.
"""
import json
import os
import re
from typing import Dict, List, Optional, Set
from datetime import datetime

from app.paths import PROJECT_RECALL_MEMORIES_PATH

# Legacy needle facts for backward compatibility
NEEDLE_GROUNDING_PHRASE = "steady river, small lantern"
NEEDLE_REVIEW_SENTENCE = "I'd like to understand how I can grow from here."
NEEDLE_PREPARATION_PLAN = "walk for ten minutes, then write three calm bullet points before the review"


# ---------------------------------------------------------------------------
# Sparse / text scoring helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> Set[str]:
    """Simple lowercase tokenization."""
    return set(re.findall(r'[a-zA-Z]+', text.lower()))


def _exact_phrase_score(query: str, text: str) -> float:
    """Score exact phrase matches in source text or summary."""
    if not text:
        return 0.0
    query_lower = query.lower()
    text_lower = text.lower()

    # Full phrase match
    if query_lower in text_lower:
        return 1.0

    # All query words present in order
    query_words = query_lower.split()
    if len(query_words) > 1:
        joined = " ".join(query_words)
        if joined in text_lower:
            return 1.0

    return 0.0


def _all_terms_score(query: str, text: str) -> float:
    """Score if all query terms appear across text/topic/summary."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    text_tokens = _tokenize(text)
    matched = query_tokens.intersection(text_tokens)
    if not matched:
        return 0.0
    return len(matched) / len(query_tokens) * 0.8


def _keyword_match_score(query: str, text: str) -> float:
    """Score partial keyword matches."""
    query_tokens = _tokenize(query)
    text_tokens = _tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0
    matched = query_tokens.intersection(text_tokens)
    if not matched:
        return 0.0
    # Partial match scoring
    ratio = len(matched) / len(query_tokens)
    if ratio >= 0.7:
        return 0.6
    elif ratio >= 0.4:
        return 0.4
    elif ratio >= 0.2:
        return 0.3
    return 0.0


def _topic_hint_score(topic_hints: Dict, memory: Dict) -> float:
    """Score topic hint matches in memory tags/follow_up/theme."""
    if not topic_hints or not isinstance(topic_hints, dict):
        return 0.0

    score = 0.0
    mem_tags = [t.lower() for t in memory.get("topic_tags", [])]
    follow_ups = [t.lower() for t in memory.get("follow_up_topics", [])]
    theme = (memory.get("theme", "") or "").lower()

    # Topic family match
    topic_family = topic_hints.get("topic_family", "").lower()
    if topic_family and topic_family != "general" and topic_family != "unknown":
        all_targets = mem_tags + follow_ups + [theme]
        # Direct family match
        if topic_family in all_targets:
            score += 0.7
        else:
            # Family keyword match
            family_keywords = {
                "sleep": ["sleep", "bedtime", "night", "insomnia", "wind-down"],
                "anxiety": ["anxiety", "panic", "worry", "stress", "nervous"],
                "work": ["work", "job", "career", "manager", "review", "coworker"],
                "relationship": ["relationship", "friend", "family", "partner", "conversation"],
                "health": ["health", "exercise", "routine", "self-care"],
                "self_improvement": ["goal", "plan", "progress", "growth", "commitment"],
            }
            related = family_keywords.get(topic_family, [])
            for kw in related:
                if any(kw in t for t in all_targets):
                    score += 0.5
                    break

    # Strong topic terms match
    strong_terms = [t.lower() for t in topic_hints.get("strong_topic_terms", [])]
    all_targets = mem_tags + follow_ups + [theme]
    for term in strong_terms:
        if any(term in t for t in all_targets):
            score += 0.7
            break

    # Topic hints list
    topic_hint_list = [t.lower() for t in topic_hints.get("topic_hints", [])]
    for hint in topic_hint_list:
        if any(hint in t for t in all_targets):
            score += 0.5

    return min(1.0, score)


def _emotion_match_score(detected_emotion: Dict, memory: Dict) -> float:
    """Score emotion match between detected emotion and memory emotions."""
    if not detected_emotion or not isinstance(detected_emotion, dict):
        return 0.0

    user_emotion = detected_emotion.get("primary", "").lower()
    if not user_emotion:
        return 0.0

    mem_emotions = memory.get("emotion", {})
    if not mem_emotions:
        return 0.0

    # Primary match
    primary = (mem_emotions.get("primary") or "").lower()
    if primary == user_emotion:
        return 0.3

    # Secondary match
    secondary = [e.lower() for e in mem_emotions.get("secondary", [])]
    if user_emotion in secondary:
        return 0.2

    # All emotions match
    all_emotions = [e.lower() for e in mem_emotions.get("all_emotions", [])]
    if user_emotion in all_emotions:
        return 0.25

    return 0.0


# --- Source kind weights by query intent ---
SOURCE_KIND_WEIGHTS = {
    "specific_episode_recall": {
        "summary": 0.25,
        "key_moment": 0.20,
        "exact_user_request": 0.05,
        "follow_up_topic": 0.05,
    },
    "broad_session_recall": {
        "summary": 0.30,
        "key_moment": 0.15,
        "exact_user_request": 0.00,
        "follow_up_topic": 0.05,
    },
    "emotional_context": {
        "summary": 0.15,
        "key_moment": 0.15,
        "exact_user_request": 0.03,
        "follow_up_topic": 0.05,
    },
    "direct_memory_question": {
        "exact_user_request": 0.50,
        "key_moment": 0.10,
        "summary": 0.00,
        "follow_up_topic": 0.00,
    },
    "session_continuity": {
        "follow_up_topic": 0.25,
        "summary": 0.15,
        "key_moment": 0.10,
        "exact_user_request": 0.00,
    },
    "notification": {
        "follow_up_topic": 0.25,
        "summary": 0.10,
        "key_moment": 0.10,
        "exact_user_request": 0.00,
    },
}


def _intent_to_query_type(detected_emotion: Dict, query_understanding: Dict = None) -> str:
    """Map detected emotion intent to query type for source kind weighting."""
    intent = detected_emotion.get("intent", "") if detected_emotion else ""
    query_intent = query_understanding.get("query_intent", "") if query_understanding else ""

    # Prefer query_understanding intent if available
    if query_intent == "direct_exact_recall":
        return "direct_memory_question"
    if query_intent == "specific_episode_recall":
        return "specific_episode_recall"
    if query_intent == "reengagement_context":
        return "session_continuity"

    # Fallback to detected emotion intent
    if intent == "direct_memory_question":
        return "direct_memory_question"
    if intent == "specific_episode_recall":
        # Check if broad recall language
        return "broad_session_recall"
    if intent == "emotional_disclosure":
        return "emotional_context"

    return "specific_episode_recall"  # default


def _metadata_score(
    detected_emotion: Dict,
    topic_hints: Dict,
    memory: Dict,
    query_understanding: Dict = None,
) -> float:
    """Score metadata matches (user, type, safety, source kind, recency)."""
    score = 0.0

    # Source kind boost based on intent and query type
    source_kind = memory.get("memory_source_kind", "")
    query_type = _intent_to_query_type(detected_emotion, query_understanding)
    weights = SOURCE_KIND_WEIGHTS.get(query_type, SOURCE_KIND_WEIGHTS["specific_episode_recall"])
    score += weights.get(source_kind, 0.0)

    # Intent-specific boosts
    intent = detected_emotion.get("intent", "") if detected_emotion else ""

    if intent == "specific_episode_recall" and source_kind == "summary":
        score += 0.15  # Extra boost for summary cards on episode recall
    elif intent == "specific_episode_recall" and source_kind == "key_moment":
        score += 0.10  # Supporting boost for key moments

    # Follow-up topic match
    follow_up_topics = memory.get("follow_up_topics", [])
    if follow_up_topics and topic_hints and topic_hints.get("topic_hints"):
        for fu in follow_up_topics:
            for hint in topic_hints.get("topic_hints", []):
                if hint.lower() in fu.lower() or fu.lower() in hint.lower():
                    score += 0.5
                    break

    # Safe for opener check
    if memory.get("safe_to_reference_in_opener", True):
        score += 0.1
    else:
        score -= 0.2

    # Canonical / user explicitly asked
    if memory.get("is_canonical", False):
        score += 0.3
    if memory.get("user_explicitly_asked_to_remember", False):
        score += 0.2

    # Resolved status boost for unresolved topics (more relevant for follow-up)
    if memory.get("resolved_status") in ("unresolved", "partially_resolved"):
        score += 0.1

    # Session summary gets small importance boost if it has high importance
    if source_kind == "summary" and memory.get("importance", 0) >= 0.75:
        score += 0.05

    return score


def _compute_sparse_score(
    query: str,
    memory: Dict,
    topic_hints: Dict = None,
    detected_emotion: Dict = None,
) -> float:
    """Compute sparse text search score for a memory."""
    if not query:
        return 0.0

    # Build searchable text from memory
    searchable_parts = []
    if memory.get("source_text"):
        searchable_parts.append(memory["source_text"])
    if memory.get("summary"):
        searchable_parts.append(memory["summary"])
    if memory.get("theme"):
        searchable_parts.append(memory["theme"])
    if memory.get("topic_tags"):
        searchable_parts.append(" ".join(memory["topic_tags"]))
    if memory.get("follow_up_topics"):
        searchable_parts.append(" ".join(memory["follow_up_topics"]))
    if memory.get("memory_type"):
        searchable_parts.append(memory["memory_type"])
    if memory.get("exact_value"):
        searchable_parts.append(memory["exact_value"])

    searchable_text = " ".join(searchable_parts)

    # Compute component scores
    exact_score = _exact_phrase_score(query, searchable_text)
    all_terms = _all_terms_score(query, searchable_text)
    keyword_score = _keyword_match_score(query, searchable_text)
    topic_score = _topic_hint_score(topic_hints, memory) if topic_hints else 0.0
    emotion_score = _emotion_match_score(detected_emotion, memory) if detected_emotion else 0.0
    meta_score = _metadata_score(detected_emotion, topic_hints, memory)

    # Combine: exact matches dominate, then keyword, then topic, then emotion, then metadata
    score = max(exact_score, all_terms, keyword_score) * 0.6
    score += topic_score * 0.25
    score += emotion_score * 0.1
    score += meta_score * 0.05

    return min(1.0, score)


# ---------------------------------------------------------------------------
# Main hybrid retrieval function
# ---------------------------------------------------------------------------

def hybrid_retrieve_memory_candidates(
    user_id: str,
    query: str,
    detected_emotion: Dict = None,
    topic_hints: Dict = None,
    top_k_dense: int = 12,
    top_k_sparse: int = 12,
    final_k: int = 15,
    memories_path: str = None,
    direct_question: bool = False,
) -> List[Dict]:
    """
    Hybrid memory candidate retrieval combining dense vectors, sparse text search,
    and metadata matching.

    Returns a deduplicated, ranked candidate list for the LLM judge.

    Pipeline:
    1. Dense vector retrieval (semantic similarity)
    2. Sparse text search over all memories
    3. Merge and deduplicate by memory_id
    4. Compute candidate_score = dense*0.45 + sparse*0.35 + metadata*0.20
    5. Rank by candidate_score
    6. Safety filter (sensitivity, distractors, wrong user)
    7. Return top final_k
    """
    memories_path = memories_path or PROJECT_RECALL_MEMORIES_PATH

    # --- Step 1: Dense retrieval ---
    dense_candidates = []
    try:
        from app.memory_retriever import retrieve_memories
        dense_candidates = retrieve_memories(
            user_id=user_id,
            query=query,
            top_k=top_k_dense,
            direct_question=direct_question,
        )
    except Exception:
        dense_candidates = []

    # Mark dense scores
    for c in dense_candidates:
        c["_dense_score"] = c.get("final_score", 0.0)
        c["_sparse_score"] = 0.0
        c["_metadata_score"] = 0.0

    # --- Step 2: Sparse retrieval ---
    # Load all memories for text search
    sparse_candidates = []
    try:
        with open(memories_path, "r", encoding="utf-8") as f:
            all_memories = json.load(f)
    except Exception:
        all_memories = []

    # Score all memories with sparse search
    sparse_scored = []
    for mem in all_memories:
        # Skip wrong user
        if mem.get("user_id") and mem["user_id"] != user_id:
            continue

        # Skip high sensitivity unless direct question
        if not direct_question and mem.get("sensitivity", 0) >= 0.7:
            continue

        # Skip distractors
        if mem.get("is_distractor", False):
            continue

        sparse_score = _compute_sparse_score(
            query=query,
            memory=mem,
            topic_hints=topic_hints,
            detected_emotion=detected_emotion,
        )

        if sparse_score > 0.0:
            mem_copy = dict(mem)
            mem_copy["_sparse_score"] = sparse_score
            mem_copy["_dense_score"] = 0.0
            mem_copy["_metadata_score"] = _metadata_score(detected_emotion, topic_hints, mem)
            sparse_scored.append(mem_copy)

    # Take top sparse
    sparse_scored.sort(key=lambda x: x["_sparse_score"], reverse=True)
    sparse_candidates = sparse_scored[:top_k_sparse]

    # --- Step 3: Merge and deduplicate ---
    # Index dense by memory_id
    all_candidates = {}
    for c in dense_candidates:
        mid = c.get("memory_id")
        if mid:
            all_candidates[mid] = c

    for c in sparse_candidates:
        mid = c.get("memory_id")
        if not mid:
            continue
        if mid in all_candidates:
            # Update sparse score on existing candidate
            all_candidates[mid]["_sparse_score"] = max(
                all_candidates[mid].get("_sparse_score", 0.0),
                c["_sparse_score"],
            )
            all_candidates[mid]["_metadata_score"] = max(
                all_candidates[mid].get("_metadata_score", 0.0),
                c["_metadata_score"],
            )
        else:
            all_candidates[mid] = c

    # --- Step 4: Compute candidate_score ---
    scored_candidates = []
    for mem in all_candidates.values():
        dense = mem.get("_dense_score", 0.0)
        sparse = mem.get("_sparse_score", 0.0)
        meta = mem.get("_metadata_score", 0.0)

        candidate_score = (
            dense * 0.45 +
            sparse * 0.35 +
            meta * 0.20
        )

        mem["final_score"] = round(candidate_score, 4)
        mem["semantic_similarity"] = round(dense, 4)  # preserve for judge
        scored_candidates.append(mem)

    # --- Step 5: Rank ---
    scored_candidates.sort(key=lambda x: x["final_score"], reverse=True)

    # --- Step 6: Return top final_k ---
    return scored_candidates[:final_k]


# ---------------------------------------------------------------------------
# Legacy adapter — provide retrieve_memories interface with hybrid
# ---------------------------------------------------------------------------

def retrieve_with_fallback(
    user_id: str,
    query: str,
    top_k: int = 12,
    detected_emotion: Dict = None,
    topic_hints: Dict = None,
    direct_question: bool = False,
) -> List[Dict]:
    """
    Wrapper that uses hybrid retrieval but falls back to pure dense
    if hybrid raises an exception.
    """
    try:
        return hybrid_retrieve_memory_candidates(
            user_id=user_id,
            query=query,
            detected_emotion=detected_emotion,
            topic_hints=topic_hints,
            top_k_dense=top_k,
            top_k_sparse=top_k,
            final_k=max(top_k, 15),
            direct_question=direct_question,
        )
    except Exception:
        # Fallback to pure dense retrieval
        from app.memory_retriever import retrieve_memories
        return retrieve_memories(
            user_id=user_id,
            query=query,
            top_k=top_k,
            direct_question=direct_question,
        )


if __name__ == "__main__":
    # Quick self-test
    print("=" * 60)
    print("HYBRID MEMORY RETRIEVER — Self Test")
    print("=" * 60)

    # Test 1: Episode recall query
    query = "emotional regulation before important events how did we manage"
    candidates = hybrid_retrieve_memory_candidates(
        user_id="demo_user",
        query=query,
        detected_emotion={"primary": "neutral", "intent": "specific_episode_recall"},
        topic_hints={"topic_family": "general", "topic_hints": [], "strong_topic_terms": []},
        top_k_dense=8,
        top_k_sparse=8,
        final_k=10,
    )

    print(f"\nQuery: {query}")
    print(f"Retrieved {len(candidates)} candidates")
    for i, c in enumerate(candidates[:5]):
        print(f"  [{i}] {c['memory_id']} | type={c['memory_type']} | score={c['final_score']:.3f}")
        print(f"       d={c['_dense_score']:.3f} s={c['_sparse_score']:.3f} m={c['_metadata_score']:.3f}")