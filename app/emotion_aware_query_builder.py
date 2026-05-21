"""
Project Recall — Emotion-Aware Query Builder

Builds context-aware vector search queries based on detected emotion.
This retrieves memories that might be relevant to the user's current
emotional state, without being too specific or leading.
"""
from typing import Dict


EMOTION_QUERY_TEMPLATES = {
    "sadness": "recent unresolved sadness, feeling down, hurt, loneliness, disappointment, relationship conflict, self-criticism, emotional low, grief, loss",
    "anxiety": "recent unresolved anxiety, worry, nervousness, panic, performance pressure, uncertainty, coping plan, grounding strategy, upcoming event, review, interview",
    "overwhelm": "recent overwhelm, too much pressure, coping strategy, grounding, unfinished stressors, unresolved tasks, burnout, need support, reduce load",
    "loneliness": "recent loneliness, isolation, relationship difficulty, feeling unseen, disconnection, need support, social stress, belonging",
    "uncertainty": "recent uncertainty, confusion, life direction, stuck, paralyzed by choice, big decision, career doubt, purpose, identity, transition",
    "anger": "recent frustration, conflict, boundary crossed, unfair treatment, resentment, work stress, unmet needs, anger trigger",
    "shame": "recent self-criticism, shame, feeling not enough, failure, mistake, embarrassment, vulnerability, self-worth",
    "hopefulness": "recent progress, hope, improvement, positive shift, growth, new plan, better coping, forward movement",
    "relief": "recent resolution, relief, calmer moment, weight lifted, peaceful, settled, breathing easier",
    "neutral": "recent important topic, ongoing concern, recent session theme, unresolved matter, life event",
}


def build_emotion_aware_query(current_message: str, detected_emotion: Dict) -> str:
    """
    Build a vector search query tailored to the detected emotion or intent.

    For direct memory questions, use the original message plus memory-type
    hints to improve exact recall retrieval. For emotional disclosures,
    broaden the query with emotion-specific search language.

    Args:
        current_message: Raw user message.
        detected_emotion: Output of detect_current_emotion().

    Returns:
        Query string for vector retrieval.
    """
    intent = detected_emotion.get("intent", "general_chat")
    primary = detected_emotion.get("primary", "neutral")
    preferred_type = detected_emotion.get("preferred_memory_type")

    # Direct memory questions: use original message + memory type hints for better retrieval
    if intent == "direct_memory_question":
        query = current_message
        if preferred_type:
            # Add memory type hint to the query to steer retrieval
            type_hints = {
                "grounding_phrase": "grounding phrase",
                "review_preparation": "review preparation",
                "follow_up_intent": "preparation plan",
            }
            hint = type_hints.get(preferred_type, preferred_type)
            query = f"{query}. memory_type: {hint}"
        return query

    # Grounding requests: look for grounding phrases and coping strategies
    if intent == "grounding_request":
        return "grounding phrase, coping strategy, calming technique, breathing, self-regulation"

    # Specific episode recall: use original message with topic emphasis
    if intent == "specific_episode_recall":
        # Extract strong topic terms to boost retrieval
        from app.current_topic_extractor import extract_current_topic_hints
        hints = extract_current_topic_hints(current_message)
        strong_terms = hints.get("strong_topic_terms", [])
        topic_family = hints.get("topic_family", "")
        # Build query with strong terms repeated for emphasis
        topic_boost = ""
        if strong_terms:
            topic_boost = ", ".join(strong_terms * 2)  # Repeat for emphasis
        elif topic_family:
            topic_boost = topic_family
        return f"{current_message}. {topic_boost}. specific episode, topic memory, session exploration"

    # Emotional disclosures: use emotion-tailored query
    emotion_query = EMOTION_QUERY_TEMPLATES.get(primary, EMOTION_QUERY_TEMPLATES["neutral"])

    # Add user message context if it's short enough (gives specificity)
    if len(current_message) < 80:
        return f"{emotion_query}. User said: {current_message}"

    return emotion_query


if __name__ == "__main__":
    # Quick self-test
    from app.current_emotion_detector import detect_current_emotion

    test_messages = [
        "I'm feeling down",
        "I'm anxious today",
        "I feel overwhelmed",
        "What was my grounding phrase?",
        "I'm angry at my boss",
        "I don't know what to do anymore",
    ]

    for msg in test_messages:
        emotion = detect_current_emotion(msg)
        query = build_emotion_aware_query(msg, emotion)
        print(f"\"{msg}\"")
        print(f"  → emotion={emotion['primary']}, intent={emotion['intent']}")
        print(f"  → query: {query[:80]}...")
        print()