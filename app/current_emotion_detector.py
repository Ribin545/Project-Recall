"""
Project Recall — Current Emotion Detector

Rule-based detector that classifies the user's current message
into an emotional state and decides whether memory lookup is needed.

This is a lightweight deterministic front-end classifier used before
retrieval. It identifies both emotional tone and conversational intent.
"""
from typing import Dict


# --- Keyword maps for emotion detection ---
EMOTION_KEYWORDS = {
    "anxiety": [
        "anxious", "nervous", "worried", "panic", "stress", "stressed",
        "on edge", "tense", "uneasy", "dread", "fear", "scared",
        "butterflies", "restless", "racing thoughts", "can't stop thinking",
        "overthinking", "what if", "afraid", "tension",
    ],
    "sadness": [
        "sad", "down", "depressed", "empty", "numb", "hopeless",
        "blue", "low", "crying", "cried", "tears", "grief", "loss",
        "disappointed", "let down", "heartbroken", "lonely",
        "not okay", "not good", "feel bad", "feeling bad",
    ],
    "overwhelm": [
        "overwhelmed", "too much", "can't handle", "drowning",
        "buried", "swamped", "everything at once", "burned out",
        "exhausted", "tired of", "no energy", "shut down",
        "paralyzed", "frozen", "can't cope", "too many things",
    ],
    "anger": [
        "angry", "mad", "furious", "rage", "irritated", "annoyed",
        "frustrated", "pissed", "resentful", "bitter", "hostile",
        "hate", "can't stand", "fed up", "had enough",
    ],
    "shame": [
        "ashamed", "embarrassed", "humiliated", "guilty", "failure",
        "worthless", "not enough", "disgusted with myself", "hate myself",
        "should have", "shouldn't have", "messed up", "screwed up",
    ],
    "loneliness": [
        "lonely", "alone", "isolated", "no one understands", "empty",
        "abandoned", "rejected", "left out", "invisible", " disconnected",
    ],
    "uncertainty": [
        "confused", "unsure", "don't know", "lost", "directionless",
        "stuck", "don't know what to do", "paralyzed by choice",
        "indecisive", "wandering", "adrift", "purposeless",
    ],
    "hopefulness": [
        "hopeful", "optimistic", "excited", "looking forward",
        "better", "improving", "turning around", "light at the end",
    ],
    "relief": [
        "relieved", "calmer", "lighter", "peaceful", "settled",
        "breathing easier", "weight lifted", "glad that's over",
    ],
}


INTENT_KEYWORDS = {
    "emotional_disclosure": [
        "i'm feeling", "i feel", "feeling", "i am feeling",
        "i've been feeling", "i am anxious", "i am sad",
        "i am overwhelmed", "i am lonely", "i feel hurt",
    ],
    "direct_memory_question": [
        "what was", "what is", "what did i", "what sentence",
        "what phrase", "what exact", "what grounding", "do you remember",
        "what preparation", "what plan", "what line",
        "what did you remember", "what did we agree", "what did i ask",
    ],
    "specific_episode_recall": [
        "what did we explore", "what did we talk about",
        "what did we discuss", "what did we decide",
        "what happened during", "during that", "about that",
        "what was the plan for", "what did we practice",
        "what did i commit to", "what happened at",
        "what did we work on", "what came up about",
    ],
    "grounding_request": [
        "ground me", "help me ground", "grounding phrase",
        "calm me down", "something to hold onto",
    ],
    "session_opener": [
        "hi", "hello", "hey", "good morning", "good evening",
    ],
}


MEMORY_TYPE_HINTS = {
    "grounding phrase": "grounding_phrase",
    "grounding": "grounding_phrase",
    "review sentence": "review_preparation",
    "performance review": "review_preparation",
    "review": "review_preparation",
    "preparation plan": "follow_up_intent",
    "plan before": "follow_up_intent",
    "plan i made": "follow_up_intent",
    "exact sentence": "review_preparation",
    "exact phrase": "grounding_phrase",
}


def _score_emotion(text_lower: str) -> Dict[str, float]:
    """
    Score each emotion by keyword match count.

    Uses word-aware matching:
    - Single-word keywords must match as whole words.
    - Multi-word keywords use substring matching.

    Args:
        text_lower: Lower-cased user text.

    Returns:
        Dict mapping emotion name to keyword-match score.
    """
    import re
    scores = {}
    
    for emotion, keywords in EMOTION_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if " " in kw:
                # Multi-word keyword: use substring match
                if kw in text_lower:
                    score += 1
            else:
                # Single-word keyword: require word boundary
                pattern = r'(?:^|\s|[.,;!?])' + re.escape(kw) + r'(?:$|\s|[.,;!?])'
                if re.search(pattern, text_lower):
                    score += 1
        scores[emotion] = score
    return scores


def detect_current_emotion(message: str) -> Dict:
    """
    Detect the user's current emotional state and intent from a message.

    Args:
        message: Raw user message.

    Returns:
        Dict with keys:
        - primary
        - intensity
        - intent
        - needs_memory_lookup
        - preferred_memory_type (optional)
    """
    text_lower = message.lower().strip()

    # Default
    result = {
        "primary": "neutral",
        "intensity": 0.0,
        "intent": "general_chat",
        "needs_memory_lookup": False,
    }

    # --- Detect intent first ---
    # PRIORITY: specific_episode_recall > direct_memory_question > emotional_disclosure
    # Episode recall ("do you remember when...", "how did we manage...") is MORE
    # specific than generic "do you remember" and should win when both match.

    text_lower = message.lower().strip()

    # A. Check for specific_episode_recall FIRST (most nuanced)
    episode_indicators = INTENT_KEYWORDS.get("specific_episode_recall", [])
    has_episode_indicator = any(kw in text_lower for kw in episode_indicators)

    # "do you remember when/that/how" + narrative question = episode recall
    episode_do_you_remember = (
        "do you remember when" in text_lower or
        "do you remember that" in text_lower or
        "do you remember how" in text_lower or
        "how did we" in text_lower or
        "what did we" in text_lower
    )

    # "what about" + past event reference = episode recall
    # Examples: "what about that family dinner", "what about the time when"
    what_about_past = (
        "what about" in text_lower and
        any(p in text_lower for p in [
            "family", "dinner", "gathering", "conversation", "time", "meeting",
            "review", "bedtime", "sleep", "panic", "situation", "event",
            "incident", "moment", "day", "night", "week", "last",
        ])
    )

    # "tell me about" + past event = episode recall
    tell_me_about = (
        "tell me about" in text_lower and
        any(p in text_lower for p in [
            "the time", "that", "when", "how", "what happened", "family",
            "dinner", "meeting", "conversation", "bedtime", "panic",
        ])
    )

    # "that time when" / "the other day" / "remember that"
    that_time_when = (
        "that time when" in text_lower or
        "the other day" in text_lower or
        "remember that" in text_lower or
        "the time when" in text_lower
    )

    # Check for specific topic phrases that indicate episode recall
    EPISODE_TOPIC_PHRASES = [
        "family dinner", "family gathering", "brother conversation",
        "friend conversation", "bedtime", "sleep hygiene", "manager conversation",
        "work meeting", "performance review", "friendship repair",
        "loneliness", "self-criticism", "grounding exercise",
        "emotional regulation", "important events", "preparation plan",
        "before the review", "before meetings", "before bedtime",
    ]
    has_episode_topic = any(p in text_lower for p in EPISODE_TOPIC_PHRASES)

    # Episode recall if:
    # - explicit indicator, OR
    # - (do_you_remember_when + any topic), OR
    # - "what about" + past event, OR
    # - "tell me about" + past event, OR
    # - "that time when" / "the other day"
    is_episode_recall = (
        has_episode_indicator or
        (episode_do_you_remember and has_episode_topic) or
        what_about_past or
        tell_me_about or
        that_time_when
    )

    if is_episode_recall:
        result["intent"] = "specific_episode_recall"
        result["needs_memory_lookup"] = True
    else:
        # B. Check for direct memory questions
        direct_keywords = INTENT_KEYWORDS.get("direct_memory_question", [])
        has_direct_question = any(kw in text_lower for kw in direct_keywords)

        if has_direct_question:
            result["intent"] = "direct_memory_question"
            result["needs_memory_lookup"] = True
            # Still detect memory type hint
            msg_lower = text_lower
            for hint, mem_type in MEMORY_TYPE_HINTS.items():
                if hint in msg_lower:
                    result["preferred_memory_type"] = mem_type
                    break
        else:
            # C. Other intents
            for intent_type, keywords in INTENT_KEYWORDS.items():
                if intent_type in ("specific_episode_recall", "direct_memory_question"):
                    continue
                if any(kw in text_lower for kw in keywords):
                    result["intent"] = intent_type
                    if intent_type == "grounding_request":
                        result["needs_memory_lookup"] = True
                    break

            # Fallback: episode topic + plain "do you remember" (without when/that/how)
            if result["intent"] == "general_chat" and has_episode_topic and "do you remember" in text_lower:
                result["intent"] = "specific_episode_recall"
                result["needs_memory_lookup"] = True

    # Add memory type hint for direct questions
    if result["intent"] == "direct_memory_question":
        msg_lower = message.lower()
        for hint, mem_type in MEMORY_TYPE_HINTS.items():
            if hint in msg_lower:
                result["preferred_memory_type"] = mem_type
                break

    # --- Detect emotion ---
    scores = _score_emotion(text_lower)

    # Check for emotional disclosure patterns
    disclosure_patterns = [
        "i'm", "i am", "i feel", "feeling", "i've been",
        "i have been", "today i", "lately i", "recently",
    ]
    is_disclosure = any(p in text_lower for p in disclosure_patterns)

    if is_disclosure or max(scores.values(), default=0) > 0:
        primary = max(scores, key=scores.get)
        score = scores[primary]

        if score == 0:
            primary = "sadness"
            score = 0.5

        intensity = min(1.0, 0.3 + (score * 0.2) + (1.0 / max(len(text_lower) / 20, 1)) * 0.2)

        result["primary"] = primary
        result["intensity"] = round(intensity, 2)

        if is_disclosure and result["intent"] == "general_chat":
            result["intent"] = "emotional_disclosure"

        if result["intent"] == "emotional_disclosure":
            lookup_emotions = {"anxiety", "sadness", "overwhelm", "uncertainty", "loneliness"}
            if primary in lookup_emotions:
                result["needs_memory_lookup"] = True

    # Direct memory questions always need lookup
    if result["intent"] == "direct_memory_question":
        result["needs_memory_lookup"] = True

    # Specific episode recall always needs lookup
    if result["intent"] == "specific_episode_recall":
        result["needs_memory_lookup"] = True
        result["preferred_detail_level"] = "topic_only"

    # Grounding requests
    if result["intent"] == "grounding_request":
        result["needs_memory_lookup"] = True
        result["primary"] = "overwhelm"

    return result


if __name__ == "__main__":
    test_messages = [
        "I'm feeling down",
        "I'm anxious today",
        "What was my grounding phrase?",
        "What exact sentence did I ask you to remember for my performance review?",
        "What was the small preparation plan I made before the review?",
    ]

    for msg in test_messages:
        r = detect_current_emotion(msg)
        print(f'"{msg}"')
        print(f"  → emotion={r['primary']}, intent={r['intent']}, lookup={r['needs_memory_lookup']}, preferred={r.get('preferred_memory_type', 'none')}")
        print()