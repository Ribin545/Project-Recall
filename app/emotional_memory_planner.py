"""
Project Recall — Emotional Memory Planner

A decision layer that sits on top of vector retrieval.

Answers:
- Which retrieved memory should be used?
- How should the assistant talk about it?
- What emotional tone should it adopt?
- What should it avoid?

The retriever answers "which memories are semantically relevant?"
The planner answers "which memory should be used, and how?"
"""
from typing import List, Dict, Optional


def classify_memory_use(memory: Dict) -> str:
    """
    Decide how a memory should be used in the assistant's response.

    Args:
        memory: Retrieved memory dict.

    Returns:
        One of:
        - direct_answer
        - gentle_follow_up
        - supportive_reference
        - offer_grounding
        - only_if_user_mentions
        - do_not_use
    """
    safe = memory.get("safe_to_reference_in_opener", True)
    sensitivity = memory.get("sensitivity", 0.0)
    mem_type = memory.get("memory_type", "")
    follow_up = memory.get("follow_up_recommended", False)
    resolved = memory.get("resolved_status", "unknown")
    importance = memory.get("importance", 0.5)

    # Hard rules first
    if not safe:
        return "do_not_use"

    if sensitivity >= 0.7:
        return "only_if_user_mentions"

    if mem_type == "grounding_phrase":
        return "offer_grounding"

    if follow_up and resolved in ("unresolved", "partially_resolved"):
        return "gentle_follow_up"

    if mem_type in ("review_preparation", "follow_up_intent") and importance >= 0.85:
        return "gentle_follow_up"

    if importance >= 0.75:
        return "supportive_reference"

    return "supportive_reference"


def compute_topic_priority(memory: Dict) -> float:
    """
    Score a memory for how much emotional/life-space it occupies.

    Higher scores indicate a better candidate for gentle follow-up.

    Args:
        memory: Retrieved memory dict.

    Returns:
        Priority score clamped to 0.0-1.0.
    """
    importance = float(memory.get("importance", 0.5))
    emotion_intensity = float(memory.get("emotion_intensity", 0.5))
    follow_up = memory.get("follow_up_recommended", False)
    resolved = memory.get("resolved_status", "unknown")
    exact_value = memory.get("exact_value")
    sensitivity = float(memory.get("sensitivity", 0.0))
    is_distractor = memory.get("is_distractor", False)

    follow_up_bonus = 1.0 if follow_up else 0.0

    unresolved_bonus = 0.0
    if resolved in ("unresolved", "partially_resolved"):
        unresolved_bonus = 1.0

    exact_value_bonus = 1.0 if exact_value else 0.0

    # Sensitivity penalty
    if sensitivity >= 0.7:
        sensitivity_penalty = 0.25
    elif sensitivity >= 0.3:
        sensitivity_penalty = 0.05
    else:
        sensitivity_penalty = 0.0

    distractor_penalty = 0.30 if is_distractor else 0.0

    score = (
        importance * 0.30
        + emotion_intensity * 0.20
        + follow_up_bonus * 0.20
        + unresolved_bonus * 0.20
        + exact_value_bonus * 0.05
        - sensitivity_penalty
        - distractor_penalty
    )

    return round(max(0.0, min(1.0, score)), 4)


def _normalize_key(memory: Dict) -> str:
    """
    Create a deduplication key from exact_value or summary.

    Args:
        memory: Retrieved memory dict.

    Returns:
        Normalized string key for de-duplication.
    """
    exact = memory.get("exact_value")
    if exact:
        return exact.lower().strip()
    return (memory.get("summary") or "").lower().strip()[:80]


def plan_memory_response(
    retrieved_memories: List[Dict],
    current_user_message: Optional[str] = None,
    purpose: str = "session_opener",
) -> Dict:
    """
    Build a structured emotional plan from retrieved memories.

    Steps:
    1. Deduplicate by normalized exact_value/summary
    2. Classify each memory by usage strategy
    3. Filter out do_not_use
    4. Select the primary safe memory
    5. Add 1-2 supporting memories (non-distractor, non-duplicate)
    6. Generate prompt guidance and avoid-list

    Args:
        retrieved_memories: Candidate memories from retrieval.
        current_user_message: Optional current message for downstream use.
        purpose: session_opener, chat, or another generation purpose.

    Returns:
        Structured planning dict consumed by opener/policy layers.
    """
    # --- 1. Deduplicate ---
    seen = set()
    unique_memories = []
    for m in retrieved_memories:
        key = _normalize_key(m)
        if key not in seen:
            seen.add(key)
            unique_memories.append(m)

    # --- 2. Classify each memory ---
    # Preserve retriever's ranking (final_score) as primary order
    for m in unique_memories:
        strategy = classify_memory_use(m)
        m["_strategy"] = strategy
        m["_priority"] = compute_topic_priority(m)

    # --- 3. Filter out do_not_use ---
    usable = [m for m in unique_memories if m["_strategy"] != "do_not_use"]

    if not usable:
        return {
            "selected_memory_id": None,
            "selected_topic": None,
            "response_strategy": "do_not_use",
            "tone": "neutral",
            "safe_to_reference": False,
            "reason_selected": "No usable memories found after filtering.",
            "supporting_memories": [],
            "avoid": [],
            "prompt_guidance": "Open with a generic warm greeting. Do not reference past sessions.",
            "fallback_opener": "Hi, I'm glad you're here. What would you like to talk about today?",
        }

    # --- 4. Select primary ---
    # Use the highest retriever-ranked memory that is usable.
    # The retriever already ranked by semantic similarity + emotion + importance.
    # The planner's job is to classify and generate, not to re-rank entirely.
    primary = usable[0]

    # --- 5. Select supporting (1-2) ---
    supporting = []
    for m in usable[1:]:
        if len(supporting) >= 2:
            break
        if m.get("is_distractor", False):
            continue
        # Avoid same strategy if possible
        if m["_strategy"] != primary["_strategy"]:
            supporting.append(m)
        elif len(supporting) < 1:
            supporting.append(m)

    # --- 6. Build the plan ---
    selected_id = primary.get("memory_id", "unknown")
    topic = _infer_topic(primary)
    strategy = primary["_strategy"]
    tone = _select_tone(primary)
    safe = primary.get("safe_to_reference_in_opener", True)
    exact_value = primary.get("exact_value")
    emotion_primary = primary.get("emotion_primary", "neutral")

    reason = (
        f"Priority={primary['_priority']}. "
        f"Memory type={primary.get('memory_type')}. "
        f"Emotion={emotion_primary} (intensity={primary.get('emotion_intensity', 0.5)}). "
        f"Importance={primary.get('importance', 0.5)}. "
        f"Resolved={primary.get('resolved_status', 'unknown')}. "
        f"Follow-up={primary.get('follow_up_recommended', False)}."
    )

    avoid_list = [
        "Do not list memories mechanically.",
        "Do not say 'according to your records.'",
        "Do not overstate certainty.",
        "Do not pressure the user to discuss this topic.",
        "Do not diagnose or label the user's feelings.",
    ]

    if primary.get("sensitivity", 0.0) >= 0.5:
        avoid_list.append("Do not expose sensitive details in the opener.")

    prompt_guidance = _build_prompt_guidance(primary, supporting, strategy, purpose)

    return {
        "selected_memory_id": selected_id,
        "selected_topic": topic,
        "selected_exact_value": exact_value,
        "selected_emotion": emotion_primary,
        "response_strategy": strategy,
        "tone": tone,
        "safe_to_reference": safe,
        "reason_selected": reason,
        "supporting_memories": [
            {
                "memory_id": m.get("memory_id"),
                "memory_type": m.get("memory_type"),
                "exact_value": m.get("exact_value"),
                "emotion_primary": m.get("emotion_primary"),
                "_priority": m.get("_priority"),
            }
            for m in supporting
        ],
        "avoid": avoid_list,
        "prompt_guidance": prompt_guidance,
    }


def _infer_topic(memory: Dict) -> str:
    """
    Infer a human-readable topic from memory metadata.

    Args:
        memory: Retrieved memory dict.

    Returns:
        Human-readable topic label.
    """
    tags = memory.get("topic_tags", [])
    if tags:
        return tags[0]

    mem_type = memory.get("memory_type", "")
    topic_map = {
        "review_preparation": "performance review preparation",
        "grounding_phrase": "grounding and self-regulation",
        "follow_up_intent": "preparation plan",
        "coping_strategy": "coping and self-care",
        "unresolved_theme": "ongoing life concern",
        "recurring_theme": "recurring theme",
        "emotional_pattern": "emotional pattern",
        "user_goal": "personal goal",
    }
    return topic_map.get(mem_type, "an important topic from our last session")


def _select_tone(memory: Dict) -> str:
    """
    Select an emotional tone based on the memory's emotion metadata.

    Args:
        memory: Retrieved memory dict.

    Returns:
        Tone description for prompt generation.
    """
    primary = memory.get("emotion_primary", "neutral")
    intensity = memory.get("emotion_intensity", 0.5)

    if primary in ("anxiety", "overwhelm", "uncertainty"):
        if intensity > 0.7:
            return "warm, grounding, gently curious"
        return "warm, calm, gently curious"

    if primary in ("sadness", "loneliness", "shame"):
        return "warm, soft, gently curious"

    if primary in ("anger", "frustration"):
        return "warm, calm, non-defensive"

    if primary in ("hopefulness", "relief"):
        return "warm, quietly celebratory, gently curious"

    return "warm, calm, gently curious"


def _build_prompt_guidance(
    primary: Dict,
    supporting: List[Dict],
    strategy: str,
    purpose: str
) -> str:
    """
    Build a concise instruction for how the LLM should use this memory.

    Args:
        primary: Primary selected memory.
        supporting: Supporting memory list.
        strategy: Chosen response strategy.
        purpose: Generation purpose such as session_opener.

    Returns:
        Short natural-language prompt guidance string.
    """
    topic = _infer_topic(primary)
    emotion = primary.get("emotion_primary", "neutral")
    exact = primary.get("exact_value")
    mem_type = primary.get("memory_type", "")

    if strategy == "gentle_follow_up":
        guidance = (
            f"Gently reference that {topic} seemed to be carrying some {emotion} "
            f"last time, then invite the user to continue or redirect. "
            f"Keep it short, warm, and one follow-up question only."
        )
    elif strategy == "offer_grounding":
        guidance = (
            f"If the user seems activated, gently offer the grounding phrase "
            f"as something that helped before. Do not force it."
        )
    elif strategy == "supportive_reference":
        guidance = (
            f"Briefly acknowledge {topic} as something that felt important, "
            f"then ask how things have shifted since then."
        )
    elif strategy == "only_if_user_mentions":
        guidance = (
            f"Do not proactively mention {topic}. Only respond if the user brings it up."
        )
    else:
        guidance = (
            "Open with a generic warm greeting. Do not reference past sessions."
        )

    return guidance


def generate_opener_from_plan(plan: Dict) -> str:
    """
    Generate a warm, natural session opener from the emotional plan.

    Uses the selected strategy plus any safe exact value information.

    Args:
        plan: Emotional plan dict from plan_memory_response.

    Returns:
        Session opening message.
    """
    strategy = plan.get("response_strategy", "supportive_reference")
    topic = plan.get("selected_topic", "something")
    primary_emotion = plan.get("selected_emotion", "anxiety")
    exact_value = plan.get("selected_exact_value")

    # Fallback if no plan or do_not_use
    if strategy == "do_not_use" or not plan.get("safe_to_reference"):
        return "Hi, I'm glad you're here. What would you like to talk about today?"

    # Template-based generation (no LLM required)
    if strategy == "gentle_follow_up" and exact_value:
        return (
            f"I'm glad you're back. Last time, {topic} seemed to be taking up a lot of space, "
            f"and you had found a way to approach it more calmly: \"{exact_value}\" "
            f"How are you feeling about that today?"
        )

    if strategy == "offer_grounding" and exact_value:
        return (
            f"Hi again. I remember you found a grounding phrase that felt calming — "
            f"\"{exact_value}.\" Is that still something that feels helpful when things get loud?"
        )

    if strategy == "supportive_reference":
        return (
            f"Good to see you. {topic} came up last time. "
            f"Would you like to pick up where we left off, or is something else on your mind today?"
        )

    # Default warm opener
    return "Hi, I'm glad you're here. What would you like to talk about today?"


if __name__ == "__main__":
    # Quick self-test
    test_mem = {
        "memory_id": "mem_test",
        "memory_type": "review_preparation",
        "exact_value": "I'd like to understand how I can grow from here.",
        "summary": "User wanted to remember review sentence.",
        "topic_tags": ["performance review", "work anxiety"],
        "emotion_primary": "anxiety",
        "emotion_intensity": 0.82,
        "importance": 0.95,
        "sensitivity": 0.4,
        "resolved_status": "partially_resolved",
        "follow_up_recommended": True,
        "safe_to_reference_in_opener": True,
        "is_distractor": False,
    }

    strategy = classify_memory_use(test_mem)
    priority = compute_topic_priority(test_mem)
    print(f"Strategy: {strategy}")
    print(f"Priority: {priority}")