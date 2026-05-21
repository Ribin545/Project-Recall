"""
Project Recall - Generalized Direct Memory Lookup

For direct memory questions, bypass vector retrieval and look up
remembered facts directly from extracted_memories_project_recall.json.

Supports arbitrary remembered phrases — not just demo-specific examples.
Detects questions like:
- "What was my grounding phrase?"
- "What sentence did I ask you to remember for my brother conversation?"
- "What did I plan to say to my friend?"
- "What was my review preparation plan?"

Canonical memories are preferred:
- is_canonical: true
- user_explicitly_asked_to_remember: true
- memory_source_kind: exact_user_request

Vector retrieval is only a fallback for direct questions.
"""
import json
import os
import re
import sys
from typing import Dict, Optional, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import active paths from central config
from app.paths import PROJECT_RECALL_MEMORIES_PATH

# --- Paths ---
MEMORIES_PATH = PROJECT_RECALL_MEMORIES_PATH

# --- Direct memory question detection ---
# General patterns that indicate ANY direct memory request
DIRECT_QUESTION_PATTERNS = [
    # Grounding phrases
    {"phrases": ["grounding phrase", "calming phrase", "anchor phrase", "phrase i used", "phrase i picked", "phrase i chose", "phrase to calm down"], "type_hint": "grounding_phrase"},
    # Communication scripts / remembered sentences
    {"phrases": ["sentence did i ask", "what sentence did i", "what did i ask you to remember", "what phrase did i", "what line did i", "what did i plan to say", "what did i want to say", "sentence i wanted to use", "sentence i wanted", "line i wanted to use", "phrase i wanted to use"], "type_hint": "communication_script"},
    # Generic remembered facts
    {"phrases": ["what did i ask you to remember", "what was the phrase", "what was the sentence", "what was the line", "what was my phrase", "what was my sentence", "tell me the phrase i picked", "tell me the phrase i chose", "tell me the sentence i wanted"], "type_hint": None},
    # Preparation / plans (allow any type since plans can be user_goal, follow_up_intent, or coping_strategy)
    {"phrases": ["preparation plan", "small plan", "plan before", "plan i made", "what was the plan", "what was my plan", "before the review"], "type_hint": None},
    # Generic memory questions
    {"phrases": ["what did i say", "what did i mention", "what did i tell you", "what did we talk about", "what did i ask"], "type_hint": None},
]

CANONICAL_SLOT_PATTERNS = {
    "grounding_phrase": [
        "grounding phrase", "calming phrase", "anchor phrase", "grounding line",
        "phrase i used", "phrase i picked", "phrase i chose",
    ],
    "communication_script": [
        "what exact sentence", "what sentence did i ask", "what did i ask you to remember",
        "what line did i ask", "what phrase did i ask", "performance review sentence",
        "sentence for my performance review", "tell me the sentence i wanted to use", "sentence i wanted to use for my performance review", "line i wanted to use with my manager",
    ],
    "prep_plan": [
        "preparation plan", "small preparation plan", "small plan", "plan before the review",
        "what was my plan", "what was the plan before the review", "calm bullet points",
    ],
}

# Topic hints to extract from query for filtering
TOPIC_HINT_PATTERNS = {
    "brother": ["brother", "sibling"],
    "sister": ["sister", "sibling"],
    "friend": ["friend", "friendship"],
    "manager": ["manager", "boss", "supervisor"],
    "review": ["review", "performance"],
    "sleep": ["sleep", "bedtime"],
    "family": ["family", "parent", "mother", "father"],
    "conversation": ["conversation", "talk", "discussion"],
}


def _is_direct_memory_question(message: str) -> bool:
    """Check if a message is asking for a specific remembered fact or topic."""
    msg_lower = message.lower()
    for pattern in DIRECT_QUESTION_PATTERNS:
        if any(p in msg_lower for p in pattern["phrases"]):
            return True
    # Generic "what was my X" pattern
    if re.search(r"what\s+(?:was|is)\s+my\s+\w+", msg_lower):
        return True
    # "Do you remember X" pattern — asking about a past topic/event
    if re.search(r"do\s+you\s+remember\s+(.+)", msg_lower):
        return True
    # "What about X" or "How about X" — topic follow-up
    if re.search(r"^(what|how)\s+about\s+(.+)", msg_lower):
        return True
    return False


def _extract_type_hint(message: str) -> Optional[str]:
    """Extract memory type hint from the question."""
    msg_lower = message.lower()
    for pattern in DIRECT_QUESTION_PATTERNS:
        if any(p in msg_lower for p in pattern["phrases"]):
            return pattern["type_hint"]
    return None


def _extract_canonical_slot(message: str) -> Optional[str]:
    """Extract a normalized canonical slot hint from user phrasing."""
    msg_lower = message.lower()
    for slot, phrases in CANONICAL_SLOT_PATTERNS.items():
        if any(p in msg_lower for p in phrases):
            return slot
    return None


def _extract_topic_hints(message: str) -> List[str]:
    """Extract topic hints from the question for filtering memories."""
    msg_lower = message.lower()
    hints = []
    for topic, keywords in TOPIC_HINT_PATTERNS.items():
        if any(kw in msg_lower for kw in keywords):
            hints.append(topic)
    return hints


def _score_memory_for_query(
    memory: Dict,
    type_hint: Optional[str],
    canonical_slot: Optional[str],
    topic_hints: List[str],
    message: str,
    session_context: Optional[Dict] = None,
) -> float:
    """
    Score how well a memory matches the direct question query.
    Higher score = better match.
    
    If session_context is provided (from recent conversation), boost memories
    from that session/theme to help with follow-up disambiguation.
    """
    score = 0.0

    # 1. Source kind bonus: exact_user_request is best for direct recall
    source_kind = memory.get("memory_source_kind", "key_moment")
    if source_kind == "exact_user_request":
        score += 0.50
    elif source_kind == "key_moment":
        score += 0.10

    # 2. Canonical / explicitly asked to remember
    if memory.get("is_canonical"):
        score += 0.30
    if memory.get("user_explicitly_asked_to_remember"):
        score += 0.20

    # 2b. Canonical slot match is a strong deterministic signal
    if canonical_slot and memory.get("canonical_slot") == canonical_slot:
        score += 0.90

    # 3. Memory type match
    mem_type = memory.get("memory_type", "")
    if type_hint and mem_type == type_hint:
        score += 0.40
    # Backward compatibility: review_preparation maps to communication_script
    if type_hint == "communication_script" and mem_type == "review_preparation":
        score += 0.40

    # 4. Topic tag overlap
    mem_tags = set(t.lower() for t in memory.get("topic_tags", []))
    for hint in topic_hints:
        if any(hint in tag for tag in mem_tags):
            score += 0.25

    # 5. Content match: specific content words in query vs exact_value
    # This helps distinguish between multiple canonical memories
    exact_val = (memory.get("exact_value") or "").lower()
    query_lower = message.lower()
    # Extract content words (skip common stop words)
    stop_words = {"what", "was", "my", "the", "did", "i", "you", "to", "for", "a", "an", "is", "your", "small", "me", "remember", "ask", "asked", "sentence", "phrase", "line", "plan", "preparation", "grounding", "calming", "exact"}
    query_words = set(w for w in re.findall(r'\b\w+\b', query_lower) if len(w) > 2 and w not in stop_words)
    exact_words = set(re.findall(r'\b\w+\b', exact_val))
    content_overlap = len(query_words & exact_words)
    score += content_overlap * 0.30

    # 6. Confidence
    score += memory.get("confidence", 0.5) * 0.10

    # 7. Has exact_value (critical for direct lookup)
    if memory.get("exact_value"):
        score += 0.15

    # 8. SESSION CONTEXT BOOST — if user recently discussed this session/theme
    if session_context:
        mem_session = memory.get("source_session_id", "")
        mem_theme = memory.get("theme", "").lower()
        
        # Check ALL recent sessions (up to 3), not just the current one
        recent_sessions = session_context.get("recent_sessions", [])
        if recent_sessions and mem_session in recent_sessions:
            score += 1.0  # Strong boost: same session
        
        # Also check current session_id as fallback
        if not recent_sessions:
            context_session = session_context.get("session_id", "")
            if context_session and mem_session == context_session:
                score += 1.0
        
        # Check ALL recent themes (up to 3)
        recent_themes = session_context.get("recent_themes", [])
        matched_theme = False
        for context_theme in recent_themes:
            context_theme = context_theme.lower()
            if context_theme and mem_theme:
                context_words = set(context_theme.split())
                mem_words = set(mem_theme.split())
                shared_words = context_words & mem_words
                if shared_words:
                    score += 0.5  # Theme overlap boost
                    matched_theme = True
                    break  # Only boost once
        
        # Also check current theme as fallback
        if not matched_theme:
            context_theme = session_context.get("theme", "").lower()
            if context_theme and mem_theme:
                context_words = set(context_theme.split())
                mem_words = set(mem_theme.split())
                shared_words = context_words & mem_words
                if shared_words:
                    score += 0.5

    return score


def lookup_direct_memory(
    user_id: str,
    message: str,
    memories_path: Optional[str] = None,
    session_context: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    Look up a remembered fact or topic for the user based on their question.

    Supports:
    - Exact phrase questions ("What was my grounding phrase?")
    - Topic questions ("Do you remember panic before bedtime?")
    - Follow-up topic questions ("What about my sleep routine?")

    Args:
        user_id: User whose memories should be searched.
        message: Raw user message.
        memories_path: Path to extracted memories JSON.
        session_context: Optional dict with recent session context (session_id, theme, memory_id).

    Returns:
        Raw memory dict if found, otherwise None.
    """
    if not _is_direct_memory_question(message):
        return None

    # Resolve path
    path = memories_path or MEMORIES_PATH
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        memories = json.load(f)

    # Filter by user
    user_memories = [m for m in memories if m.get("user_id") == user_id]

    # Extract query hints
    type_hint = _extract_type_hint(message)
    canonical_slot = _extract_canonical_slot(message)
    topic_hints = _extract_topic_hints(message)

    # Determine if this is an exact-phrase question or topic question
    msg_lower = message.lower()
    is_exact_phrase_question = any(
        p in msg_lower for p in [
            "what was my", "what did i ask", "what exact", "what sentence",
            "what phrase", "what line", "what did i plan to say"
        ]
    )
    is_topic_question = (
        "do you remember" in msg_lower or
        re.search(r"^(what|how)\s+about\s+(.+)", msg_lower) is not None
    )

    # For exact phrase questions, prefer canonical exact memories first
    canonical_pool = [
        m for m in user_memories
        if m.get("exact_value")
        and m.get("is_canonical")
        and m.get("user_explicitly_asked_to_remember")
    ]
    if canonical_slot:
        slot_pool = [m for m in canonical_pool if m.get("canonical_slot") == canonical_slot]
        if slot_pool:
            user_memories = slot_pool
        elif canonical_pool:
            user_memories = canonical_pool

    # If topic hints exist, narrow canonical pool to candidates whose tags/theme match the topic
    if canonical_slot and topic_hints and user_memories:
        narrowed = []
        for mem in user_memories:
            text = " ".join([
                mem.get("theme", ""),
                mem.get("summary", ""),
                " ".join(mem.get("topic_tags", [])),
            ]).lower()
            if any(hint in text for hint in topic_hints):
                narrowed.append(mem)
        if narrowed:
            user_memories = narrowed

    # Score all eligible memories
    scored = []
    for mem in user_memories:
        # For exact phrase questions, require exact_value
        if is_exact_phrase_question and not mem.get("exact_value"):
            continue

        score = _score_memory_for_query(mem, type_hint, canonical_slot, topic_hints, message, session_context)

        # For topic questions, boost memories whose summary contains query content words
        if is_topic_question:
            summary = mem.get("summary", "").lower()
            exact_val = (mem.get("exact_value") or "").lower()
            query_words = set(w for w in re.findall(r'\b\w+\b', msg_lower) if len(w) > 3 and w not in {"remember", "about", "what", "how", "does", "did", "you", "have", "there", "with", "from", "that", "this", "about"})
            for qw in query_words:
                if qw in summary or qw in exact_val:
                    score += 0.35  # Strong content match bonus for topic questions

        scored.append((score, mem))

    if not scored:
        return None

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Ambiguity handling for canonical slots
    if canonical_slot and len(scored) >= 2:
        top_score, top_mem = scored[0]
        second_score, second_mem = scored[1]
        if abs(top_score - second_score) < 0.20:
            return {
                "memory_id": "AMBIGUOUS_DIRECT_MEMORY",
                "memory_type": "ambiguity_prompt",
                "memory_source_kind": "exact_user_request",
                "summary": f"Ambiguous canonical lookup for slot {canonical_slot}",
                "exact_value": None,
                "canonical_slot": canonical_slot,
                "ambiguity_candidates": [top_mem, second_mem],
                "is_canonical": True,
                "confidence": 0.4,
            }

    # Return best match if score is reasonable
    best_score, best_mem = scored[0]
    if best_score >= 0.5:
        return best_mem

    # No good match found
    return None


def get_canonical_candidates(
    user_id: str,
    message: str,
    memories_path: Optional[str] = None,
    top_k: int = 3,
    session_context: Optional[Dict] = None,
) -> List[Dict]:
    """
    Return top canonical exact-memory candidates for a message without requiring
    the message to match a rule-based 'direct question' pattern.

    This is intended for candidate augmentation: broad retrieval + canonical options.
    
    Args:
        session_context: Optional dict with recent session context to boost matching memories.
    """
    path = memories_path or MEMORIES_PATH
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        memories = json.load(f)

    canonical_pool = [
        m for m in memories
        if m.get("user_id") == user_id
        and m.get("exact_value")
        and m.get("is_canonical")
        and m.get("user_explicitly_asked_to_remember")
    ]

    if not canonical_pool:
        return []

    type_hint = _extract_type_hint(message)
    canonical_slot = _extract_canonical_slot(message)
    topic_hints = _extract_topic_hints(message)

    scored = []
    for mem in canonical_pool:
        score = _score_memory_for_query(mem, type_hint, canonical_slot, topic_hints, message, session_context)
        # small base score so semantically nearby canonical options still surface
        score += 0.10
        scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for score, m in scored[:top_k] if score >= 0.35]


def _build_selected_memory_dict(mem: Dict) -> Dict:
    """
    Convert a raw memory dict to the format expected by the chat pipeline.

    Args:
        mem: Raw extracted-memory dict.

    Returns:
        Normalized selected-memory dict.
    """
    return {
        "memory_id": mem.get("memory_id"),
        "source_session_id": mem.get("source_session_id"),
        "memory_type": mem.get("memory_type"),
        "memory_source_kind": mem.get("memory_source_kind", "key_moment"),
        "summary": mem.get("summary", ""),
        "exact_value": mem.get("exact_value"),
        "canonical_slot": mem.get("canonical_slot"),
        "emotion_primary": mem.get("emotion", {}).get("primary", "neutral"),
        "emotion_intensity": mem.get("emotion", {}).get("intensity", 0.5),
        "importance": mem.get("importance", 0.5),
        "sensitivity": mem.get("sensitivity", 0.0),
        "resolved_status": mem.get("resolved_status", "unknown"),
        "safe_to_reference_in_opener": mem.get("safe_to_reference_in_opener", True),
        "follow_up_recommended": mem.get("follow_up_recommended", False),
        "is_distractor": mem.get("is_distractor", False),
        "is_canonical": mem.get("is_canonical", False),
        "confidence": mem.get("confidence", 0.5),
        "semantic_similarity": 1.0,  # Direct lookup is treated as exact match
        "final_score": 1.0,
        "reason_selected": "Direct memory lookup (generalized exact match)",
    }


def resolve_direct_memory(
    user_id: str,
    message: str,
    memories_path: Optional[str] = None,
    session_context: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    Detect a direct memory request and return a pipeline-compatible memory.

    Args:
        user_id: User whose memories should be searched.
        message: Raw user message.
        memories_path: Path to extracted memories JSON.
        session_context: Optional dict with recent session context to boost matching memories.

    Returns:
        Selected-memory dict compatible with the pipeline, or None.
    """
    mem = lookup_direct_memory(user_id, message, memories_path, session_context)
    if mem:
        if mem.get("memory_id") == "AMBIGUOUS_DIRECT_MEMORY":
            candidates = mem.get("ambiguity_candidates", [])
            options = []
            for c in candidates[:2]:
                label = c.get("theme") or c.get("source_session_id") or c.get("memory_id")
                exact = c.get("exact_value")
                if exact:
                    label = f"{label}: {exact}"
                options.append(label)
            clarification = "I found more than one matching remembered phrase. Do you mean " + " or ".join(options) + "?"
            return {
                "memory_id": "AMBIGUOUS_DIRECT_MEMORY",
                "source_session_id": None,
                "memory_type": "ambiguity_prompt",
                "memory_source_kind": "exact_user_request",
                "summary": clarification,
                "exact_value": None,
                "canonical_slot": mem.get("canonical_slot"),
                "emotion_primary": "neutral",
                "emotion_intensity": 0.0,
                "importance": 1.0,
                "sensitivity": 0.0,
                "resolved_status": "unknown",
                "safe_to_reference_in_opener": True,
                "follow_up_recommended": False,
                "is_distractor": False,
                "is_canonical": True,
                "confidence": 0.4,
                "semantic_similarity": 1.0,
                "final_score": 1.0,
                "reason_selected": "Direct memory lookup found multiple canonical matches",
            }
        return _build_selected_memory_dict(mem)
    return None


if __name__ == "__main__":
    # Quick self-test
    test_messages = [
        "What was my grounding phrase?",
        "What exact sentence did I ask you to remember for my performance review?",
        "What was the small preparation plan I made before the review?",
        "What sentence did I ask you to remember for my brother conversation?",
        "I'm feeling anxious today",  # Not a direct memory question
    ]

    for msg in test_messages:
        result = resolve_direct_memory("demo_user", msg)
        if result:
            print(f'"{msg}"')
            print(f'  -> FOUND: {result["memory_id"]}')
            print(f'  -> Type: {result["memory_type"]}')
            print(f'  -> Exact: {result["exact_value"]}')
            print()
        else:
            print(f'"{msg}"')
            print("  -> No direct memory found (fallback to vector retrieval)")
            print()