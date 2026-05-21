"""
Project Recall - Current Topic Extractor

Rule-based topic extraction from user messages to prevent irrelevant
memory injection. Extracts topic hints, topic family, and confidence
for use in memory selection scoring and relevance judging.
"""

import re
from typing import Dict, List


# --- Topic keyword maps ---
TOPIC_KEYWORDS = {
    "sleep": {
        "keywords": [
            "bedtime", "before bed", "sleep", "sleeping", "night", "nighttime",
            "insomnia", "wind-down", "phone before bed", "panic before bedtime",
            "can't sleep", "trouble sleeping", "wake up", "waking up", "rest",
            "tired", "exhausted", "sleep routine", "sleep hygiene", "bed",
        ],
        "topic_hints": ["sleep", "bedtime", "night anxiety", "wind-down", "sleep hygiene", "insomnia", "rest"],
    },
    "work": {
        "keywords": [
            "work", "working", "meeting", "meetings", "manager", "boss", "supervisor",
            "review", "performance review", "feedback", "coworker", "colleague",
            "office", "deadline", "project", "task", "workplace", "job",
            "career", "promotion", "evaluation", "annual review",
        ],
        "topic_hints": ["work stress", "meetings", "manager conversation", "performance review", "feedback", "deadline", "workplace"],
    },
    "relationship": {
        "keywords": [
            "friend", "friendship", "partner", "relationship", "ignored", "distant",
            "argument", "conversation with friend", "breakup", "dating", "spouse",
            "boyfriend", "girlfriend", "trust", "betrayed", "rejected",
        ],
        "topic_hints": ["friendship", "relationship conflict", "connection", "repair conversation", "trust", "rejection"],
    },
    "family": {
        "keywords": [
            "brother", "sister", "mother", "mom", "father", "dad", "parent",
            "parents", "family", "sibling", "cousin", "aunt", "uncle",
            "grandmother", "grandfather", "in-law", "home",
        ],
        "topic_hints": ["family boundaries", "family conversation", "relationship boundary", "home dynamics", "parent relationship"],
    },
    "self_criticism": {
        "keywords": [
            "ashamed", "embarrassed", "disappointed in myself", "replaying what i said",
            "self-critical", "self critical", "guilt", "guilty", "regret",
            "hate myself", "not good enough", "failure", "worthless",
            "should have", "shouldn't have", "messed up", "screwed up",
        ],
        "topic_hints": ["self-criticism", "shame", "replaying conversation", "embarrassment", "guilt", "regret"],
    },
    "loneliness": {
        "keywords": [
            "lonely", "alone", "disconnected", "isolated", "no one understands",
            "abandoned", "rejected", "left out", "invisible", "disconnected",
            "empty", "nobody cares", "no friends", "isolation",
        ],
        "topic_hints": ["loneliness", "disconnection", "social isolation", "rejection", "invisibility"],
    },
    "uncertainty": {
        "keywords": [
            "stuck", "don't know what to do", "confused", "unsure", "decision",
            "choose wrong", "what if i choose wrong", "adrift", "purposeless",
            "directionless", "lost", "wandering", "no direction", "crossroads",
        ],
        "topic_hints": ["uncertainty", "decision difficulty", "next step", "direction", "purpose", "crossroads"],
    },
    "grounding": {
        "keywords": [
            "grounding", "grounding phrase", "calming phrase", "anchor phrase",
            "calm me down", "settle me", "center me", "anchor me",
            "breathing", "breathe", "relaxation", "meditation", "mindfulness",
        ],
        "topic_hints": ["grounding", "grounding phrase", "calming phrase", "breathing", "relaxation", "mindfulness"],
    },
}


def _find_keyword_matches(text_lower: str, keywords: List[str]) -> List[str]:
    """Find which keywords from the list appear in the text."""
    matches = []
    for kw in keywords:
        if kw in text_lower:
            matches.append(kw)
    return matches


def _count_matches(text_lower: str, keywords: List[str]) -> int:
    """Count how many distinct keywords appear in the text."""
    return len(_find_keyword_matches(text_lower, keywords))


# --- Strong multi-word phrases for episode recall ---
STRONG_TOPIC_PHRASES = [
    "family dinner", "family gathering", "brother conversation", "brother talk",
    "friend conversation", "friend talk", "friendship repair", "friendship conflict",
    "bedtime panic", "sleep hygiene", "manager conversation", "manager talk",
    "work meeting", "performance review", "self-criticism", "grounding exercise",
    "loneliness check-in", "social outreach", "boundary setting",
    "decision next step", "small productivity step", "no-phone wind-down",
    "bedtime routine", "communication skills", "quiet exit", "calm bullet points",
]


def extract_current_topic_hints(message: str) -> Dict:
    """
    Extract topic hints from the user's current message.
    Updated with strong phrase extraction for specific episode recall.

    Args:
        message: Raw user message.

    Returns:
        Dict with:
        - topic_hints: list of specific topic keywords found
        - strong_topic_terms: list of high-confidence exact phrases
        - topic_family: primary topic category
        - confidence: 0.0 to 1.0
    """
    text_lower = message.lower().strip()

    # --- Extract strong multi-word phrases first ---
    strong_terms = []
    for phrase in STRONG_TOPIC_PHRASES:
        if phrase in text_lower:
            strong_terms.append(phrase)

    # Score each topic family
    topic_scores = {}
    for family, config in TOPIC_KEYWORDS.items():
        matches = _find_keyword_matches(text_lower, config["keywords"])
        score = len(matches)
        topic_scores[family] = {
            "matches": matches,
            "score": score,
        }

    # Find best topic family
    best_family = max(topic_scores, key=lambda f: topic_scores[f]["score"])
    best_score = topic_scores[best_family]["score"]

    # Build topic hints from best family
    if best_score > 0:
        topic_family = best_family
        topic_hints = TOPIC_KEYWORDS[best_family]["topic_hints"].copy()
        # Add matched keywords as additional hints
        for match in topic_scores[best_family]["matches"]:
            if match not in topic_hints:
                topic_hints.append(match)
        confidence = min(1.0, 0.3 + best_score * 0.25)
    else:
        topic_family = "general"
        topic_hints = []
        confidence = 0.0

    # Boost confidence significantly if strong phrases detected
    if strong_terms:
        confidence = max(confidence, 0.85)

    return {
        "topic_hints": topic_hints,
        "strong_topic_terms": strong_terms,
        "topic_family": topic_family,
        "confidence": round(confidence, 2),
    }


def get_topic_family_for_memory(memory: Dict) -> str:
    """
    Infer the topic family of a memory from its tags, summary, and type.

    Args:
        memory: Memory dict with topic_tags, summary, memory_type.

    Returns:
        Topic family string or "general".
    """
    tags = set(t.lower() for t in memory.get("topic_tags", []))
    summary = memory.get("summary", "").lower()
    mem_type = memory.get("memory_type", "").lower()

    combined = " ".join(tags) + " " + summary + " " + mem_type

    family_scores = {}
    for family, config in TOPIC_KEYWORDS.items():
        score = 0
        for kw in config["keywords"]:
            if kw in combined:
                score += 1
        family_scores[family] = score

    best = max(family_scores, key=family_scores.get)
    if family_scores[best] > 0:
        return best
    return "general"


def has_strong_topic_mismatch(topic_hints: Dict, memory: Dict) -> bool:
    """
    Check if a memory has a strong topic mismatch with the user's current message.

    Args:
        topic_hints: Result from extract_current_topic_hints.
        memory: Candidate memory dict.

    Returns:
        True if memory is clearly about a different topic.
    """
    user_family = topic_hints.get("topic_family", "general")
    user_confidence = topic_hints.get("confidence", 0.0)

    # If no clear topic or low confidence, don't block
    if user_family == "general" or user_confidence < 0.4:
        return False

    memory_family = get_topic_family_for_memory(memory)

    # Same family is not a mismatch
    if memory_family == user_family:
        return False

    # Check for partial overlap in topic hints
    user_hints = set(h.lower() for h in topic_hints.get("topic_hints", []))
    mem_tags = set(t.lower() for t in memory.get("topic_tags", []))
    mem_summary = memory.get("summary", "").lower()
    mem_exact = (memory.get("exact_value") or "").lower()

    # If any user hint appears in memory tags/summary/exact_value, it's related
    for hint in user_hints:
        if hint in mem_tags or hint in mem_summary or hint in mem_exact:
            return False

    # Strong mismatch: user has clear topic and memory is about a different family
    # with no keyword overlap
    return True


def compute_topic_overlap_score(topic_hints: Dict, memory: Dict) -> float:
    """
    Compute topic overlap score between user message topic hints and memory.

    Args:
        topic_hints: Result from extract_current_topic_hints.
        memory: Candidate memory dict.

    Returns:
        Score 0.0 to 1.0.
    """
    if not topic_hints.get("topic_hints"):
        return 0.5  # Neutral when no topic hints

    user_hints = set(h.lower() for h in topic_hints.get("topic_hints", []))
    user_family = topic_hints.get("topic_family", "general")
    user_strong = set(t.lower() for t in topic_hints.get("strong_topic_terms", []))

    mem_tags = set(t.lower() for t in memory.get("topic_tags", []))
    mem_summary = memory.get("summary", "").lower()
    mem_exact = (memory.get("exact_value") or "").lower()
    mem_family = get_topic_family_for_memory(memory)
    mem_type = memory.get("memory_type", "").lower()

    combined = " ".join(mem_tags) + " " + mem_summary + " " + mem_exact + " " + mem_type

    score = 0.0

    # Exact topic tag match
    for hint in user_hints:
        if hint in mem_tags:
            score += 1.0

    # Partial keyword match in summary/exact_value/type
    for hint in user_hints:
        if hint in combined and hint not in mem_tags:
            score += 0.5

    # Strong term match (shorter, more specific keywords)
    for term in user_strong:
        if term in combined:
            score += 0.7

    # Same topic family bonus
    if mem_family == user_family and user_family != "general":
        score += 0.5

    # Normalize
    max_possible = len(user_hints) * 1.0 + len(user_strong) * 0.7 + 0.5
    normalized = score / max(max_possible, 1.0)

    return min(1.0, normalized)


if __name__ == "__main__":
    test_messages = [
        "Do you remember panic before bedtime? I was anxious.",
        "I feel anxious about my manager meeting.",
        "I've been around people but still feel alone.",
        "What was my grounding phrase?",
        "I feel anxious about moving to a new city.",
    ]

    for msg in test_messages:
        result = extract_current_topic_hints(msg)
        print(f'"{msg}"')
        print(f"  family={result['topic_family']}, confidence={result['confidence']}")
        print(f"  hints={result['topic_hints']}")
        print(f"  strong_terms={result['strong_topic_terms']}")
        print()