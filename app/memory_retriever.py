"""
Project Recall — Memory Retriever

Retrieves and reranks memories from the vector database.

This module is the semantic search layer between user queries and the
stored memory archive. It embeds the incoming query, fetches candidates
from ChromaDB, then reranks them using a weighted scoring formula that
combines semantic similarity with emotional and safety signals.
"""
import os
import sys
from typing import List, Dict, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.vector_store import query_index

# --- Embedding model ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_model = None


def get_model():
    """
    Lazy-load the sentence-transformer embedding model.

    Returns:
        SentenceTransformer model instance.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_query(text: str) -> List[float]:
    """
    Embed a user query string into a vector.

    Args:
        text: Query text.

    Returns:
        Embedding vector as a Python list.
    """
    model = get_model()
    return model.encode(text).tolist()


def retrieve_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
    only_safe_for_opener: bool = False,
    min_importance: float = 0.0,
    preferred_memory_type: str = None,
    direct_question: bool = False,
) -> List[Dict]:
    """
    Retrieve and rerank memories for a user query.

    For direct memory questions (`direct_question=True`), the reranker:
    - boosts memories that contain exact values,
    - boosts preferred memory type matches,
    - increases distractor penalties,
    - prefers non-distractors when scores are close.

    Scoring formula:
        final_score =
            semantic_similarity * 0.45
            + importance * 0.20
            + emotion_intensity * 0.10
            + follow_up_bonus * 0.10
            + unresolved_or_partial_bonus * 0.10
            + exact_value_bonus * 0.05 (or 0.25 for direct questions)
            + type_match_bonus (direct questions only)
            - sensitivity_penalty
            - distractor_penalty

    Args:
        user_id: User whose memories should be searched.
        query: Natural-language retrieval query.
        top_k: Number of final reranked memories to return.
        only_safe_for_opener: If True, filter to opener-safe memories only.
        min_importance: Reserved threshold for future filtering.
        preferred_memory_type: Optional retrieval hint.
        direct_question: Whether the user is asking an exact recall question.

    Returns:
        A list of reranked memory dicts with scores and selection reasons.
    """
    query_embedding = embed_query(query)

    # Build filter
    where_filter = {}
    if only_safe_for_opener:
        where_filter["safe_to_reference_in_opener"] = True

    results = query_index(
        query_embedding=query_embedding,
        user_id=user_id,
        top_k=max(top_k * 3, 20),  # Retrieve more for reranking
        where_filter=where_filter if where_filter else None,
    )

    if not results or not results.get("ids") or not results["ids"][0]:
        return []

    # Flatten results
    memories = []
    for i in range(len(results["ids"][0])):
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]  # cosine distance
        document = results["documents"][0][i]

        # Convert cosine distance to similarity (1 - distance for cosine space)
        semantic_similarity = 1.0 - float(distance)

        importance = float(metadata.get("importance", 0.5))
        emotion_intensity = float(metadata.get("emotion_intensity", 0.5))
        sensitivity = float(metadata.get("sensitivity", 0.0))
        resolved_status = metadata.get("resolved_status", "unknown")
        exact_value = metadata.get("exact_value", "")
        follow_up_recommended = metadata.get("follow_up_recommended", False)
        is_distractor = metadata.get("is_distractor", False)

        # Bonuses
        follow_up_bonus = 0.10 if follow_up_recommended else 0.0

        unresolved_bonus = 0.0
        if resolved_status in ("unresolved", "partially_resolved"):
            unresolved_bonus = 0.10

        # Direct question: strongly boost exact_value memories
        if direct_question:
            exact_value_bonus = 0.25 if exact_value else 0.0
        else:
            exact_value_bonus = 0.05 if exact_value else 0.0

        # Direct question: boost preferred memory type match
        type_match_bonus = 0.0
        if direct_question and preferred_memory_type:
            if metadata.get("memory_type") == preferred_memory_type:
                type_match_bonus = 0.15

        # Penalties
        # Sensitivity: high sensitivity = 0.15, medium = 0.10, low = 0.05
        sensitivity_penalty = sensitivity * 0.15

        # Distractor penalty
        if direct_question:
            # Stronger penalty for distractors on direct questions
            distractor_penalty = 0.20 if is_distractor else 0.0
        else:
            distractor_penalty = 0.10 if is_distractor else 0.0

        # Final score
        final_score = (
            semantic_similarity * 0.45
            + importance * 0.20
            + emotion_intensity * 0.10
            + follow_up_bonus
            + unresolved_bonus
            + exact_value_bonus
            + type_match_bonus
            - sensitivity_penalty
            - distractor_penalty
        )

        # Clamp to 0-1
        final_score = max(0.0, min(1.0, final_score))

        # Reconstruct rich memory card from metadata
        import json as _json
        def _json_loads(val, default=None):
            try:
                return _json.loads(val) if val else default
            except Exception:
                return default

        memory_card = {
            # Core IDs
            "memory_id": metadata.get("memory_id"),
            "user_id": metadata.get("user_id"),
            "source_session_id": metadata.get("source_session_id"),
            "source_timestamp": metadata.get("source_timestamp"),
            # Memory type
            "memory_type": metadata.get("memory_type"),
            "memory_source_kind": metadata.get("memory_source_kind", "key_moment"),
            "theme": metadata.get("theme", ""),
            # Rich text content
            "source_text": metadata.get("source_text", ""),
            "summary": document,
            "exact_value": exact_value or None,
            # Topic/flags
            "topic_tags": _json_loads(metadata.get("topic_tags_json"), []),
            "follow_up_topics": _json_loads(metadata.get("follow_up_topics_json"), []),
            "risk_flags": _json_loads(metadata.get("risk_flags_json"), []),
            # Emotion
            "emotion": {
                "primary": metadata.get("emotion_primary", "neutral"),
                "secondary": _json_loads(metadata.get("emotion_secondary_json"), []),
                "all_emotions": _json_loads(metadata.get("emotion_all_json"), []),
                "intensity": emotion_intensity,
                "trajectory": metadata.get("emotion_trajectory", "unknown"),
            },
            # Safety
            "resolved_status": resolved_status,
            "importance": importance,
            "sensitivity": sensitivity,
            "safe_to_reference_in_opener": metadata.get("safe_to_reference_in_opener", True),
            "follow_up_recommended": follow_up_recommended,
            "is_canonical": metadata.get("is_canonical", False),
            "user_explicitly_asked_to_remember": metadata.get("user_explicitly_asked_to_remember", False),
            "is_distractor": is_distractor,
            "confidence": float(metadata.get("confidence", 0.5)),
            # Retrieval metadata
            "semantic_similarity": round(semantic_similarity, 4),
            "final_score": round(final_score, 4),
            "reason_selected": (
                f"semantic_similarity={round(semantic_similarity, 2)}, "
                f"importance={round(importance, 2)}, "
                f"exact_value={'yes' if exact_value else 'no'}, "
                f"follow_up={'yes' if follow_up_recommended else 'no'}, "
                f"distractor={'yes' if is_distractor else 'no'}, "
                f"resolved={resolved_status}"
            ),
        }
        memories.append(memory_card)

    # Sort by final score descending
    memories.sort(key=lambda x: x["final_score"], reverse=True)

    # Direct question: ensure top result is not a distractor if non-distractor exists
    if direct_question and memories and memories[0].get("is_distractor", False):
        # Find first non-distractor with reasonable score
        for i in range(1, len(memories)):
            if not memories[i].get("is_distractor", False):
                # Only promote if non-distractor is close enough (within 0.15 of top)
                if memories[i]["final_score"] >= memories[0]["final_score"] - 0.15:
                    memories.insert(0, memories.pop(i))
                    break

    # Return top_k
    return memories[:top_k]
