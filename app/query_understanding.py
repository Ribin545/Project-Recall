"""
Project Recall — Query Understanding

Uses LLM to extract intent, topic phrases, related terms, and memory needs
from user messages. Falls back to rule-based if LLM unavailable.

Output:
{
  "query_intent": "direct_exact_recall | specific_episode_recall | emotional_disclosure | general_chat | reengagement_context",
  "topic_phrases": [],
  "related_terms": [],
  "time_reference": null,
  "requires_exact_value": false,
  "memory_need": "none | vague | topic_only | summary_level | exact_value",
  "confidence": 0.0,
  "reason": "..."
}
"""
import json
import os
import re
import sys
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm_client


# --- Rule-based fallback ---

RULE_INTENT_PATTERNS = {
    "direct_exact_recall": [
        "what was my", "what did i ask", "what exact", "what sentence",
        "what phrase", "what line", "what did i plan to say", "what grounding",
        "what preparation", "what plan", "what did i want to say",
    ],
    "specific_episode_recall": [
        "do you remember when", "do you remember that", "do you remember how",
        "what did we explore", "what did we talk about", "what did we discuss",
        "what did we decide", "what happened during", "what was the plan for",
        "what did we practice", "what did i commit to", "what did we work on",
        "how did we manage", "how did we handle", "what strategy did we use",
    ],
    "reengagement_context": [
        "follow up", "check in", "how is it going", "any update",
        "did you try", "what happened with",
    ],
}


def _rule_based_understanding(user_message: str) -> Dict:
    """Deterministic fallback for query understanding."""
    text_lower = user_message.lower().strip()

    # Detect intent
    intent = "general_chat"
    for intent_name, patterns in RULE_INTENT_PATTERNS.items():
        if any(p in text_lower for p in patterns):
            intent = intent_name
            break

    # Check for emotional disclosure
    disclosure_patterns = [
        "i'm feeling", "i feel", "feeling", "i am feeling",
        "i've been", "lately i", "recently", "today i",
    ]
    if any(p in text_lower for p in disclosure_patterns):
        if intent == "general_chat":
            intent = "emotional_disclosure"

    # Extract topic phrases (simple keyword extraction)
    topic_phrases = []
    # Look for quoted phrases
    quotes = re.findall(r'"([^"]+)"', user_message)
    topic_phrases.extend(quotes)

    # Look for "about X" or "regarding X"
    about_matches = re.findall(r'(?:about|regarding|on|with)\s+([a-zA-Z\s]+?)(?:\?|\.)', text_lower)
    topic_phrases.extend(about_matches)

    # Check for exact value need
    requires_exact = intent == "direct_exact_recall"

    # Memory need
    if intent == "direct_exact_recall":
        memory_need = "exact_value"
    elif intent == "specific_episode_recall":
        memory_need = "summary_level"
    elif intent == "emotional_disclosure":
        memory_need = "vague"
    else:
        memory_need = "none"

    return {
        "query_intent": intent,
        "topic_phrases": list(set(topic_phrases))[:5],
        "related_terms": [],
        "time_reference": None,
        "requires_exact_value": requires_exact,
        "memory_need": memory_need,
        "confidence": 0.5,
        "reason": "rule-based fallback",
    }


# ---------------------------------------------------------------------------
# LLM-based query understanding
# ---------------------------------------------------------------------------

QUERY_UNDERSTANDING_PROMPT = """You are a query understanding component for a memory-aware emotional support assistant.

Given the user's message, extract:
- what kind of memory request this is
- important topic phrases
- related search terms
- whether exact value is needed
- whether this is a specific episode recall
- whether there is a time reference

User message:
"{user_message}"

Return JSON only:
{{
  "query_intent": "direct_exact_recall | specific_episode_recall | emotional_disclosure | general_chat | reengagement_context",
  "topic_phrases": [],
  "related_terms": [],
  "time_reference": null or "...",
  "requires_exact_value": true or false,
  "memory_need": "none | vague | topic_only | summary_level | exact_value",
  "confidence": 0.0 to 1.0,
  "reason": "short explanation"
}}

Examples:

User: "Do you remember when I reported emotional regulation before important events? How did we manage those situations?"
Expected:
{{
  "query_intent": "specific_episode_recall",
  "topic_phrases": ["emotional regulation before important events", "important events"],
  "related_terms": ["preparation", "coping with pressure", "grounding", "calm plan", "before events"],
  "time_reference": null,
  "requires_exact_value": false,
  "memory_need": "summary_level",
  "confidence": 0.9,
  "reason": "User asks for a specific past episode and how it was managed."
}}

User: "What was my grounding phrase?"
Expected:
{{
  "query_intent": "direct_exact_recall",
  "topic_phrases": ["grounding phrase"],
  "related_terms": ["calming phrase", "anchor phrase", "steadying phrase"],
  "time_reference": null,
  "requires_exact_value": true,
  "memory_need": "exact_value",
  "confidence": 0.95,
  "reason": "Direct question asking for exact remembered phrase."
}}

User: "I feel anxious about moving to a new city."
Expected:
{{
  "query_intent": "emotional_disclosure",
  "topic_phrases": ["moving to a new city"],
  "related_terms": ["change", "uncertainty", "transition", "new environment"],
  "time_reference": null,
  "requires_exact_value": false,
  "memory_need": "vague",
  "confidence": 0.85,
  "reason": "User shares current emotional state without asking for memory."
}}

Your JSON:"""


def _llm_understanding(user_message: str, provider: str = None, model: str = None) -> Optional[Dict]:
    """Use LLM for query understanding."""
    if not llm_client:
        return None

    prompt = QUERY_UNDERSTANDING_PROMPT.format(user_message=user_message)

    try:
        raw = llm_client.chat([
            {"role": "system", "content": "You are a helpful assistant that extracts structured information from user messages."},
            {"role": "user", "content": prompt},
        ], model=model)

        # Parse JSON
        text = raw.strip()
        # Try direct parse
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            # Try extracting from fences
            import re
            fences = re.findall(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
            for fence in fences:
                try:
                    result = json.loads(fence.strip())
                    break
                except json.JSONDecodeError:
                    continue
            else:
                # Try first JSON object
                objs = re.findall(r'\{.*\}', text, re.DOTALL)
                for obj in objs:
                    try:
                        result = json.loads(obj)
                        break
                    except json.JSONDecodeError:
                        continue
                else:
                    return None

        # Validate fields
        if not isinstance(result, dict):
            return None

        # Ensure required fields
        validated = {
            "query_intent": result.get("query_intent", "general_chat"),
            "topic_phrases": list(result.get("topic_phrases", [])),
            "related_terms": list(result.get("related_terms", [])),
            "time_reference": result.get("time_reference"),
            "requires_exact_value": bool(result.get("requires_exact_value", False)),
            "memory_need": result.get("memory_need", "none"),
            "confidence": float(result.get("confidence", 0.5)),
            "reason": str(result.get("reason", "LLM extraction")),
        }

        return validated

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def understand_memory_query(
    user_message: str,
    detected_emotion: Dict = None,
    provider: str = None,
    model: str = None,
    use_llm: bool = True,
) -> Dict:
    """
    Understand user query intent and memory needs.

    Args:
        user_message: Raw user message.
        detected_emotion: Optional pre-detected emotion dict.
        provider: LLM provider.
        model: Model name.
        use_llm: Whether to try LLM extraction (falls back to rules if LLM fails).

    Returns:
        Dict with query_intent, topic_phrases, related_terms, time_reference,
        requires_exact_value, memory_need, confidence, reason.
    """
    # Try LLM first if requested
    llm_result = None
    if use_llm and llm_client:
        llm_result = _llm_understanding(user_message, provider, model)

    if llm_result and llm_result.get("confidence", 0) >= 0.6:
        llm_result["query_understanding_status"] = "llm_success"
        # Merge with detected emotion if available
        if detected_emotion:
            if detected_emotion.get("intent"):
                # Trust detected emotion intent if LLM didn't detect well
                if llm_result["query_intent"] == "general_chat" and detected_emotion["intent"] != "general_chat":
                    llm_result["query_intent"] = detected_emotion["intent"]
                    llm_result["reason"] += f" (merged with detected intent: {detected_emotion['intent']})"
        return llm_result

    # Fallback to rule-based
    rule_result = _rule_based_understanding(user_message)

    # Merge with detected emotion
    if detected_emotion:
        if detected_emotion.get("intent") and rule_result["query_intent"] == "general_chat":
            rule_result["query_intent"] = detected_emotion["intent"]
        if detected_emotion.get("primary"):
            # Add emotion as related term
            rule_result["related_terms"].append(detected_emotion["primary"])

    rule_result["query_understanding_status"] = "fallback_used"
    return rule_result


if __name__ == "__main__":
    import re

    print("=" * 60)
    print("QUERY UNDERSTANDING — Self Test")
    print("=" * 60)

    test_cases = [
        "Do you remember when I reported emotional regulation before important events? How did we manage those situations?",
        "What was my grounding phrase?",
        "I feel anxious about moving to a new city.",
        "What did we discuss about bedtime panic?",
    ]

    for msg in test_cases:
        result = understand_memory_query(msg, use_llm=False)
        print(f"\nMessage: {msg[:60]}...")
        print(f"  Intent: {result['query_intent']}")
        print(f"  Topic phrases: {result['topic_phrases']}")
        print(f"  Related terms: {result['related_terms']}")
        print(f"  Memory need: {result['memory_need']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Status: {result['query_understanding_status']}")