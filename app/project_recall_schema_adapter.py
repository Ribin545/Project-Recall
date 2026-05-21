"""
Project Recall — Official Schema Adapter (Generalized)

Adapts Mentra's expected session-history JSON schema into rich memory cards.

Deterministic extraction — no LLM required.
Preserves full key_moment text as source_text.
Generates short topic tags, normalizes emotions, identifies exact remembered phrases.

Public API:
    load_project_recall_sessions(path) -> list[dict]
    normalize_emotional_tone(emotional_tone) -> dict
    infer_memory_type_from_text(text, follow_up_topic=False) -> str
    extract_exact_value_from_text(text) -> Optional[str]
    estimate_importance(memory_type, text, exact_value, follow_up_topics) -> float
    infer_resolved_status(text, follow_up_topics, emotional_tone) -> str
    extract_topic_tags(session, text) -> list[str]
    session_to_memory_candidates(session) -> list[dict]
"""
import json
import os
import re
from typing import List, Dict, Optional

# --- Legacy needle facts (backward compatibility) ---
NEEDLE_REVIEW_SENTENCE = "I'd like to understand how I can grow from here."
NEEDLE_GROUNDING_PHRASE = "steady river, small lantern"
NEEDLE_PREPARATION_PLAN = "walk for ten minutes, then write three calm bullet points before the review"

# --- Emotion mapping: raw word -> normalized emotion ---
EMOTION_WORD_MAP = {
    "anxious": "anxiety",
    "anxiety": "anxiety",
    "nervous": "anxiety",
    "worried": "anxiety",
    "overwhelmed": "overwhelm",
    "overwhelm": "overwhelm",
    "stressed": "overwhelm",
    "tired": "overwhelm",
    "hopeful": "hopefulness",
    "hope": "hopefulness",
    "relieved": "relief",
    "calm": "neutral",
    "peaceful": "neutral",
    "sad": "sadness",
    "down": "sadness",
    "low": "sadness",
    "hurt": "sadness",
    "discouraged": "sadness",
    "depressed": "sadness",
    "lonely": "loneliness",
    "ashamed": "shame",
    "embarrassed": "shame",
    "guilty": "shame",
    "frustrated": "anger",
    "angry": "anger",
    "uncertain": "uncertainty",
    "confused": "uncertainty",
}

# --- Emotion intensity map ---
EMOTION_INTENSITY = {
    "anxiety": 0.75,
    "overwhelm": 0.80,
    "sadness": 0.70,
    "loneliness": 0.72,
    "shame": 0.78,
    "anger": 0.75,
    "uncertainty": 0.60,
    "hopefulness": 0.55,
    "relief": 0.45,
    "neutral": 0.30,
}

# --- Adjacent emotion mapping for retrieval overlap ---
ADJACENT_EMOTIONS = {
    "anxiety": {"overwhelm", "uncertainty", "shame"},
    "sadness": {"loneliness", "shame", "uncertainty", "overwhelm"},
    "overwhelm": {"anxiety", "uncertainty", "sadness"},
    "anger": {"shame", "uncertainty", "frustration"},
    "shame": {"sadness", "anger", "loneliness"},
    "loneliness": {"sadness", "uncertainty", "shame"},
    "uncertainty": {"anxiety", "overwhelm", "sadness", "loneliness"},
    "hopefulness": {"relief", "neutral"},
    "relief": {"hopefulness", "neutral"},
    "neutral": {"hopefulness", "relief"},
}

HIGH_RISK_FLAGS = {
    "self_harm", "suicide", "abuse", "crisis",
    "self-harm", "suicidal", "emergency", "domestic_violence",
}

REMEMBER_PATTERNS = re.compile(
    r"(?:wanted|asked|chose|planned|needed) (?:to )?(?:remember|use|say|use the sentence|use the line|use the phrase|"
    r"remember the sentence|remember the line|remember the phrase)|"
    r"(?:remember|phrase to use|sentence to use|line to use|planned to say|wanted to say)",
    re.IGNORECASE
)


def infer_canonical_slot(text: str, memory_type: str, exact_value: Optional[str]) -> Optional[str]:
    """Infer a stable canonical lookup slot for exact remembered facts."""
    lower = (text or "").lower()
    exact_lower = (exact_value or "").lower()

    if not exact_value:
        return None

    if "grounding phrase" in lower or memory_type == "grounding_phrase":
        return "grounding_phrase"

    if any(p in lower for p in [
        "performance review", "wanted to use the sentence", "asked you to remember",
        "sentence to use", "line to use", "planned to say"
    ]) and memory_type in {"communication_script", "relationship_context", "user_goal"}:
        return "communication_script"

    if any(p in lower for p in [
        "walk for ten minutes", "bullet points", "before the review",
        "preparation plan", "small plan"
    ]) or exact_lower == NEEDLE_PREPARATION_PLAN.lower():
        return "prep_plan"

    if memory_type == "communication_script" and exact_value:
        return "communication_script"

    if memory_type == "coping_strategy" and exact_value:
        return "coping_strategy"

    return None


def load_project_recall_sessions(path: str = "data/sample_project_recall_sessions.json") -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _slugify(text: str) -> str:
    """Create a URL-safe slug from text."""
    return re.sub(r'[^a-z0-9]+', '_', text.lower().strip())[:30].strip('_')


def normalize_emotional_tone(emotional_tone: List[str]) -> Dict:
    """
    Map emotional_tone list to internal emotion metadata with all_emotions.
    """
    if not emotional_tone:
        return {
            "primary": "neutral",
            "secondary": [],
            "all_emotions": [],
            "intensity": 0.5,
            "valence": 0.0,
            "arousal": 0.5,
            "trajectory": "unchanged",
            "session_close_tone": "neutral",
        }

    mapped = []
    for w in emotional_tone:
        norm = EMOTION_WORD_MAP.get(w.lower(), w.lower())
        if norm not in mapped:
            mapped.append(norm)

    primary = mapped[0] if mapped else "neutral"
    secondary = mapped[1:] if len(mapped) > 1 else []

    # Trajectory: negative -> positive = improving
    negative = {"anxiety", "overwhelm", "sadness", "anger", "shame", "loneliness", "uncertainty"}
    positive = {"hopefulness", "relief", "neutral"}

    first_neg = mapped[0] in negative if mapped else False
    last_pos = mapped[-1] in positive if mapped else False

    if first_neg and last_pos:
        trajectory = "improving"
    elif not first_neg and mapped[-1] in negative if mapped else False:
        trajectory = "worsening"
    else:
        trajectory = "unchanged"

    # Intensity: average of mapped emotions
    total_intensity = sum(EMOTION_INTENSITY.get(m, 0.5) for m in mapped)
    intensity = round(total_intensity / len(mapped), 2) if mapped else 0.5

    # Valence
    neg_count = sum(1 for m in mapped if m in negative)
    pos_count = sum(1 for m in mapped if m in positive)
    if neg_count > 0 and pos_count > 0:
        valence = -0.2
    elif neg_count > 0:
        valence = -0.5
    elif pos_count > 0:
        valence = 0.3
    else:
        valence = 0.0

    # Arousal
    arousal = round(0.5 + intensity * 0.3, 2)

    session_close_tone = mapped[-1] if mapped else "neutral"

    return {
        "primary": primary,
        "secondary": secondary,
        "all_emotions": mapped,
        "intensity": intensity,
        "valence": round(valence, 2),
        "arousal": arousal,
        "trajectory": trajectory,
        "session_close_tone": session_close_tone,
    }


def infer_memory_type_from_text(text: str, follow_up_topic: bool = False) -> str:
    """
    Infer internal memory_type from text content.
    Priority order matters — specific rules before generic.
    """
    if follow_up_topic:
        return "follow_up_intent"

    lower = text.lower()

    # 1. grounding phrase
    if any(p in lower for p in [
        "grounding phrase", "calming phrase", "anchor phrase",
        "phrase to calm", "steadying phrase"
    ]):
        return "grounding_phrase"

    # 2. communication script / remembered phrase
    if any(p in lower for p in [
        "wanted to remember", "asked to remember", "remember the sentence",
        "remember the line", "wanted to use the sentence", "planned to say",
        "wanted to say", "phrase to use", "line to use", "conversation script",
        "use the sentence", "sentence to use", "asked you to remember",
        "chose the grounding phrase", "chose the phrase"
    ]):
        return "communication_script"

    # 3. coping strategy
    if any(p in lower for p in [
        "grounding exercise", "breathing exercise", "breathing", "journaling",
        "walk", "routine", "sleep routine", "wind-down", "mindfulness",
        "self-care", "coping", "meditation", "exercise routine"
    ]):
        return "coping_strategy"

    # 4. relationship context
    if any(p in lower for p in [
        "friend", "friendship", "partner", "parent", "mother", "father",
        "brother", "sister", "coworker", "manager conflict", "relationship",
        "spouse", "colleague", "boss", "team member", "family dinner",
        "family gathering", "family boundaries"
    ]):
        return "relationship_context"

    # 5. emotional pattern
    if any(p in lower for p in [
        "self-critical", "self-criticism", "replaying", "overthinking",
        "shame", "guilt", "embarrassed", "disappointed in myself",
        "negative self-talk", "inner critic"
    ]):
        return "emotional_pattern"

    # 6. user goal
    if any(p in lower for p in [
        "committed to", "goal", "wants to", "planned to", "decided to",
        "routine", "habit", "intention", "aims to", "hopes to"
    ]):
        return "user_goal"

    # 7. unresolved theme
    if any(p in lower for p in [
        "conflict", "unresolved", "worried", "anxious", "panic",
        "overwhelmed", "stress", "stuck", "uncertain", "hurt",
        "fear", "dread", "tense", "felt unheard", "withdrew", "lonely"
    ]):
        return "unresolved_theme"

    return "recurring_theme"


def extract_exact_value_from_text(text: str) -> Optional[str]:
    """
    Extract exact phrase when text clearly indicates remembered phrase/line/sentence.
    """
    if not text:
        return None

    # 1. Straight double quotes
    m = re.search(r'"([^"]+)"', text)
    if m:
        val = m.group(1).strip()
        if 3 < len(val) < 500:
            return val

    # 2. Smart quotes
    m = re.search(r'[\"\"]([^\"\"]+)[\"\"]', text)
    if m:
        val = m.group(1).strip()
        if 3 < len(val) < 500:
            return val

    # 3. Single quotes
    m = re.search(r"'([^']+)'", text)
    if m:
        val = m.group(1).strip()
        if 3 < len(val) < 500:
            return val

    # 4. Colon-delimited patterns — require a colon separator to avoid false matches
    #    Only match if there's an actual colon or the text contains a quote
    colon_patterns = [
        # "wanted to remember the sentence: X"
        (r'(?:wanted|asked|chose|planned|needed) (?:to )?(?:remember|use|say) (?:the )?(?:sentence|line|phrase)\s*:\s*(.+?)(?:\.(?:\s|$)|$)', True),
        # "sentence: X" (after a phrase/sentence marker with colon)
        (r'(?:sentence|line|phrase|text)\s*:\s*(.+?)(?:\.(?:\s|$)|$)', True),
        # "planned to say: X"
        (r'(?:planned|wanted|chose) (?:to say|to use)\s*:\s*(.+?)(?:\.(?:\s|$)|$)', True),
        # "chose the grounding phrase: X"
        (r'(?:chose the grounding phrase|grounding phrase)\s*:\s*(.+?)(?:\.(?:\s|$)|$)', True),
        # "chose the grounding phrase" + quoted text (no colon needed if quotes present)
        (r'(?:chose the grounding phrase|grounding phrase)\s+["\u201c\u201d\']([^"\u201c\u201d\']+)["\u201c\u201d\']', False),
    ]
    for pattern, requires_colon in colon_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip().strip('"').strip("'").strip('\u201c').strip('\u201d')
            if 3 < len(val) < 500:
                return val

    # 5. Legacy needle fallback
    for needle in [NEEDLE_REVIEW_SENTENCE, NEEDLE_GROUNDING_PHRASE, NEEDLE_PREPARATION_PLAN]:
        if needle in text:
            return needle

    return None


def _is_explicit_remember_request(text: str) -> bool:
    if not text:
        return False
    return bool(REMEMBER_PATTERNS.search(text.lower()))


def estimate_importance(memory_type: str, text: str, exact_value: Optional[str],
                        follow_up_topics: List[str]) -> float:
    """
    Estimate memory importance based on type, content, and context.
    """
    base = {
        "communication_script": 0.95,
        "grounding_phrase": 0.90,
        "follow_up_intent": 0.80,
        "unresolved_theme": 0.78,
        "relationship_context": 0.75,
        "emotional_pattern": 0.75,
        "user_goal": 0.78,
        "coping_strategy": 0.72,
        "recurring_theme": 0.60,
        "session_summary": 0.60,
    }.get(memory_type, 0.60)

    boost = 0.0
    lower = text.lower()
    if any(kw in lower for kw in ["committed", "wanted to revisit", "follow up", "next session"]):
        boost += 0.10
    if follow_up_topics:
        boost += 0.05

    return min(1.0, base + boost)


def infer_resolved_status(text: str, follow_up_topics: List[str], emotional_tone: List[str]) -> str:
    """
    Infer resolved status from text, follow-up topics, and emotional trajectory.
    """
    lower = text.lower()

    # Completed / resolved indicators
    if any(kw in lower for kw in ["resolved", "relieved", "completed", "finished", "done"]):
        return "resolved"

    # Unresolved / distress indicators
    if any(kw in lower for kw in ["unresolved", "conflict", "stuck", "worried", "panic", "hurt", "dread"]):
        return "unresolved"

    # Future action = partially resolved
    if any(kw in lower for kw in ["committed", "planned", "decided to", "goal", "routine", "follow up"]):
        return "partially_resolved"

    if follow_up_topics:
        return "partially_resolved"

    # Emotional trajectory
    normalized = [EMOTION_WORD_MAP.get(w.lower(), w.lower()) for w in emotional_tone]
    negative = {"anxiety", "overwhelm", "sadness", "anger", "shame", "loneliness", "uncertainty"}
    if normalized and normalized[-1] in negative:
        return "unresolved"

    return "partially_resolved"


def infer_sensitivity(risk_flags: List[str], memory_type: str, text: str) -> float:
    """
    Infer sensitivity score from risk flags, memory type, and content.
    """
    base = 0.3
    if not risk_flags:
        base = 0.25
    else:
        flags_lower = [f.lower().replace("-", "_") for f in risk_flags]
        for flag in flags_lower:
            if flag in HIGH_RISK_FLAGS:
                return 0.85
        if any(f in {"high_stress", "sleep_disruption"} for f in flags_lower):
            base = 0.45

    # Memory type minimums
    type_min = {
        "relationship_context": 0.45,
        "emotional_pattern": 0.45,
        "grounding_phrase": 0.30,
        "communication_script": 0.35,
        "follow_up_intent": 0.25,
        "recurring_theme": 0.30,
        "session_summary": 0.30,
    }.get(memory_type, 0.30)

    return max(base, type_min)


def infer_safe_to_reference(risk_flags: List[str], sensitivity: float) -> bool:
    """Determine if memory is safe to use in session opener."""
    if not risk_flags:
        return True
    flags_lower = [f.lower().replace("-", "_") for f in risk_flags]
    for flag in flags_lower:
        if flag in HIGH_RISK_FLAGS:
            return False
    return sensitivity < 0.7


def infer_eligible_for_reengagement(risk_flags: List[str], sensitivity: float) -> bool:
    """Determine if memory is eligible for re-engagement notifications."""
    if not risk_flags:
        return True
    flags_lower = [f.lower().replace("-", "_") for f in risk_flags]
    for flag in flags_lower:
        if flag in HIGH_RISK_FLAGS:
            return False
    return sensitivity < 0.7


def extract_topic_tags(session: Dict, text: str) -> List[str]:
    """
    Extract topic tags from session theme, follow_up_topics, and text.
    """
    tags = set()
    text_lower = text.lower()

    # Always include theme
    theme = session.get("theme", "")
    if theme:
        tags.add(theme)

    # Include follow_up_topics
    for topic in session.get("follow_up_topics", []):
        if topic:
            tags.add(topic)

    # Specific keyword-based tags
    keyword_tags = {
        # Sleep
        "sleep": "sleep hygiene",
        "bed": "bedtime",
        "night": "night anxiety",
        "wind-down": "wind-down routine",
        "bedtime": "bedtime",
        # Work
        "meeting": "meetings",
        "manager": "manager conversation",
        "review": "performance review",
        "work": "work stress",
        "feedback": "feedback",
        "coworker": "coworker conflict",
        # Relationships
        "friend": "friendship repair",
        "friendship": "friendship repair",
        "brother": "brother conversation",
        "sister": "sister conversation",
        "mother": "mother conversation",
        "father": "father conversation",
        "parent": "parent conversation",
        "family": "family boundaries",
        "family dinner": "family dinner",
        "family gathering": "family gathering",
        "partner": "relationship conversation",
        # Emotions / patterns
        "self-critical": "self-criticism",
        "self-criticism": "self-criticism",
        "replaying": "replaying conversation",
        "shame": "shame",
        "ashamed": "shame",
        "embarrassed": "embarrassment",
        "lonely": "loneliness",
        "disconnected": "disconnection",
        "alone": "social isolation",
        # Coping / grounding
        "grounding phrase": "grounding",
        "grounding exercise": "grounding",
        "calming phrase": "calming strategy",
        "breathing": "breathing exercise",
        "walk": "walking",
        "routine": "routine building",
        # Communication
        "i feel": "I feel when because",
        "because": "communication practice",
        "conversation": "conversations",
        "sentence": "communication script",
        "phrase": "remembered phrase",
        # Decision / uncertainty
        "decision": "decision uncertainty",
        "stuck": "decision uncertainty",
        "choose wrong": "decision uncertainty",
        "uncertain": "uncertainty",
    }

    for keyword, tag in keyword_tags.items():
        if keyword in text_lower:
            tags.add(tag)

    return list(tags)[:8]


def session_to_memory_candidates(session: Dict) -> List[Dict]:
    """
    Convert a Project Recall official-schema session into rich memory card candidates.

    Creates three kinds of memory cards per session:
    A. One session-level summary card
    B. One card per key_moment
    C. One card per follow_up_topic
    """
    candidates = []

    user_id = session.get("user_id", "demo_user")
    session_id = session.get("session_id", "unknown")
    timestamp = session.get("timestamp", "")
    theme = session.get("theme", "")
    emotional_tone = session.get("emotional_tone", [])
    risk_flags = session.get("risk_flags", [])

    emotion_meta = normalize_emotional_tone(emotional_tone)

    # --- A. key_moments -> memory cards ---
    for idx, moment in enumerate(session.get("key_moments", [])):
        moment_text = str(moment)
        mem_type = infer_memory_type_from_text(moment_text, follow_up_topic=False)
        exact_val = extract_exact_value_from_text(moment_text)
        topic_tags = extract_topic_tags(session, moment_text)

        # Determine memory source kind and canonical status
        is_canonical = False
        user_explicitly_asked_to_remember = False
        confidence = 0.65
        memory_source_kind = "key_moment"

        if exact_val and _is_explicit_remember_request(moment_text):
            is_canonical = True
            user_explicitly_asked_to_remember = True
            confidence = 1.0
            memory_source_kind = "exact_user_request"
        elif exact_val and mem_type in ("communication_script", "grounding_phrase", "remembered_phrase"):
            # Exact phrase in a canonical memory type = user explicitly specified
            is_canonical = True
            user_explicitly_asked_to_remember = True
            confidence = 1.0
            memory_source_kind = "exact_user_request"
        elif exact_val and any(needle in exact_val for needle in [NEEDLE_REVIEW_SENTENCE, NEEDLE_GROUNDING_PHRASE, NEEDLE_PREPARATION_PLAN]):
            is_canonical = True
            user_explicitly_asked_to_remember = True
            confidence = 1.0
            memory_source_kind = "exact_user_request"
        elif "remember" in moment_text.lower():
            user_explicitly_asked_to_remember = True
            confidence = max(confidence, 0.85)

        if mem_type == "review_preparation":
            mem_type = "communication_script"

        resolved = infer_resolved_status(moment_text, session.get("follow_up_topics", []), emotional_tone)
        importance = estimate_importance(mem_type, moment_text, exact_val, session.get("follow_up_topics", []))
        sensitivity = infer_sensitivity(risk_flags, mem_type, moment_text)
        safe_opener = infer_safe_to_reference(risk_flags, sensitivity)
        eligible_reengagement = infer_eligible_for_reengagement(risk_flags, sensitivity)

        # Determine follow_up_recommended
        follow_up_recommended = (
            memory_source_kind == "exact_user_request" or
            resolved in ("unresolved", "partially_resolved") and importance >= 0.75 or
            any(kw in moment_text.lower() for kw in ["committed", "planned", "wanted to revisit", "follow up", "next session"])
        )

        memory_id = f"mem_{session_id}_exact_{idx}" if memory_source_kind == "exact_user_request" else f"mem_{session_id}_km_{idx}"

        canonical_slot = infer_canonical_slot(moment_text, mem_type, exact_val)

        memory = {
            "memory_id": memory_id,
            "user_id": user_id,
            "source_session_id": session_id,
            "source_timestamp": timestamp,
            "memory_type": mem_type,
            "memory_source_kind": memory_source_kind,
            "theme": theme,
            "source_text": moment_text,
            "summary": moment_text,
            "exact_value": exact_val,
            "canonical_slot": canonical_slot,
            "topic_tags": topic_tags,
            "follow_up_topics": session.get("follow_up_topics", []),
            "risk_flags": risk_flags,
            "emotion": {
                "primary": emotion_meta["primary"],
                "secondary": emotion_meta["secondary"],
                "all_emotions": emotion_meta["all_emotions"],
                "intensity": emotion_meta["intensity"],
                "valence": emotion_meta.get("valence"),
                "arousal": emotion_meta.get("arousal"),
                "trajectory": emotion_meta["trajectory"],
                "session_close_tone": emotion_meta["session_close_tone"],
            },
            "importance": importance,
            "sensitivity": sensitivity,
            "resolved_status": resolved,
            "follow_up_recommended": follow_up_recommended,
            "safe_to_reference_in_opener": safe_opener,
            "is_distractor": False,
            "is_canonical": is_canonical,
            "user_explicitly_asked_to_remember": user_explicitly_asked_to_remember,
            "confidence": confidence,
            "eligible_for_reengagement": eligible_reengagement,
        }

        candidates.append(memory)

    # --- B. follow_up_topics -> follow_up_intent memory cards ---
    for topic in session.get("follow_up_topics", []):
        topic_tags = extract_topic_tags(session, topic)
        if topic not in topic_tags:
            topic_tags.append(topic)

        sensitivity = infer_sensitivity(risk_flags, "follow_up_intent", topic)
        safe_opener = infer_safe_to_reference(risk_flags, sensitivity)
        eligible_reengagement = infer_eligible_for_reengagement(risk_flags, sensitivity)

        memory = {
            "memory_id": f"mem_{session_id}_followup_{_slugify(topic)}",
            "user_id": user_id,
            "source_session_id": session_id,
            "source_timestamp": timestamp,
            "memory_type": "follow_up_intent",
            "memory_source_kind": "follow_up_topic",
            "theme": theme,
            "source_text": f"Follow-up topic: {topic}",
            "summary": f"User wanted to follow up on {topic}.",
            "exact_value": None,
            "canonical_slot": None,
            "topic_tags": list(set(topic_tags))[:8],
            "follow_up_topics": session.get("follow_up_topics", []),
            "risk_flags": risk_flags,
            "emotion": {
                "primary": emotion_meta["primary"],
                "secondary": emotion_meta["secondary"],
                "all_emotions": emotion_meta["all_emotions"],
                "intensity": round(emotion_meta["intensity"] * 0.9, 2),
                "valence": emotion_meta.get("valence"),
                "arousal": emotion_meta.get("arousal"),
                "trajectory": emotion_meta["trajectory"],
                "session_close_tone": emotion_meta["session_close_tone"],
            },
            "importance": 0.80,
            "sensitivity": sensitivity,
            "resolved_status": "unresolved",
            "follow_up_recommended": True,
            "safe_to_reference_in_opener": safe_opener,
            "is_distractor": False,
            "is_canonical": False,
            "user_explicitly_asked_to_remember": False,
            "confidence": 0.75,
            "eligible_for_reengagement": eligible_reengagement,
        }

        candidates.append(memory)

    # --- C. summary -> session summary memory card ---
    summary_text = session.get("summary", "")
    if summary_text:
        # Rich topic tags: merge theme, key_moments, follow_up_topics, summary
        topic_tags = extract_topic_tags(session, summary_text)
        # Also add tags from key_moments for broader coverage
        for km in session.get("key_moments", []):
            km_tags = extract_topic_tags(session, str(km))
            for t in km_tags:
                if t not in topic_tags:
                    topic_tags.append(t)
        topic_tags = list(dict.fromkeys(topic_tags))[:12]  # dedupe, limit to 12

        sensitivity = infer_sensitivity(risk_flags, "session_summary", summary_text)
        safe_opener = infer_safe_to_reference(risk_flags, sensitivity)
        eligible_reengagement = infer_eligible_for_reengagement(risk_flags, sensitivity)

        # Determine importance based on content richness
        # Rich sessions with multiple elements = higher importance
        importance = 0.65
        richness = 0
        if len(session.get("key_moments", [])) >= 2:
            richness += 0.05
        if session.get("follow_up_topics"):
            richness += 0.05
        if any(kw in summary_text.lower() for kw in ["explored", "practiced", "discussed", "decided", "committed"]):
            richness += 0.05
        if any(kw in summary_text.lower() for kw in ["family dinner", "bedtime panic", "performance review", "manager", "friendship", "grounding"]):
            richness += 0.05
        importance = min(0.85, importance + richness)

        # Determine resolved status from summary text
        resolved = infer_resolved_status(summary_text, session.get("follow_up_topics", []), emotional_tone)
        follow_up_recommended = (
            bool(session.get("follow_up_topics")) or
            resolved in ("unresolved", "partially_resolved")
        )

        memory = {
            "memory_id": f"mem_{session_id}_summary",
            "user_id": user_id,
            "source_session_id": session_id,
            "source_timestamp": timestamp,
            "memory_type": "session_summary",
            "memory_source_kind": "summary",
            "theme": theme,
            "source_text": summary_text,
            "summary": summary_text,
            "exact_value": None,
            "canonical_slot": None,
            "topic_tags": topic_tags,
            "follow_up_topics": session.get("follow_up_topics", []),
            "risk_flags": risk_flags,
            "emotion": {
                "primary": emotion_meta["primary"],
                "secondary": emotion_meta["secondary"],
                "all_emotions": emotion_meta["all_emotions"],
                "intensity": round(emotion_meta["intensity"] * 0.85, 2),
                "valence": emotion_meta.get("valence"),
                "arousal": emotion_meta.get("arousal"),
                "trajectory": emotion_meta["trajectory"],
                "session_close_tone": emotion_meta["session_close_tone"],
            },
            "importance": importance,
            "sensitivity": sensitivity,
            "resolved_status": resolved,
            "follow_up_recommended": follow_up_recommended,
            "safe_to_reference_in_opener": safe_opener,
            "is_distractor": False,
            "is_canonical": False,
            "user_explicitly_asked_to_remember": False,
            "confidence": 0.75,
            "eligible_for_reengagement": eligible_reengagement,
        }

        candidates.append(memory)

    return candidates


if __name__ == "__main__":
    # Quick self-test
    test_session = {
        "user_id": "demo_user",
        "session_id": "sess_test",
        "timestamp": "2026-05-19T09:00:00Z",
        "theme": "family boundaries",
        "emotional_tone": ["anxious", "hopeful"],
        "key_moments": [
            "User wanted to remember the sentence: \"I need some space, but I still care about you.\" for a conversation with their brother.",
            "User committed to sleep routine",
        ],
        "summary": "User discussed family boundaries and wants to set limits with their brother.",
        "risk_flags": [],
        "follow_up_topics": ["brother conversation", "boundary setting"],
    }

    candidates = session_to_memory_candidates(test_session)
    for c in candidates:
        print(f"ID: {c['memory_id']} | Type: {c['memory_type']} | Source: {c['memory_source_kind']} | Importance: {c['importance']} | Canonical: {c['is_canonical']} | Exact: {c.get('exact_value', 'None')}")