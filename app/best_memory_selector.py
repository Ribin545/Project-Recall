"""
Project Recall - Best Memory Selector

Reads selection mode weights from config/response_policy.yaml
and picks the best memory candidate using emotion-aware scoring.

This module sits between retrieval and policy. It decides which single
memory should be treated as the best candidate for the current purpose.
"""
import os
from typing import Dict, List, Optional
from datetime import datetime

from app.response_policy import load_response_policy
from app.current_topic_extractor import (
    compute_topic_overlap_score,
    has_strong_topic_mismatch,
)


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "response_policy.yaml"
)


def infer_selection_mode(
    detected_emotion: Dict,
    purpose: str = "chat",
    policy_config: Optional[Dict] = None,
) -> str:
    """
    Determine which selection mode to use based on emotion and purpose.

    Rules (from YAML selection_defaults):
    - direct_memory_question -> exact_recall
    - session_opener -> session_continuity
    - notification -> notification
    - emotion has rule -> use its selection_mode
    - otherwise -> default_mode

    Args:
        detected_emotion: Detected emotion/intent dict.
        purpose: chat, session_opener, notification, etc.
        policy_config: Optional loaded policy config.

    Returns:
        Selection mode name.
    """
    if policy_config is None:
        policy_config = load_response_policy(DEFAULT_CONFIG_PATH)

    defaults = policy_config.get("selection_defaults", {})
    intent = detected_emotion.get("intent", "general_chat")
    primary = detected_emotion.get("primary", "neutral")

    if intent == "direct_memory_question":
        return defaults.get("direct_memory_question_mode", "exact_recall")

    if intent == "specific_episode_recall":
        return defaults.get("specific_episode_recall_mode", "specific_episode_recall")

    if purpose == "session_opener":
        return defaults.get("session_opener_mode", "session_continuity")

    if purpose == "notification":
        return defaults.get("notification_mode", "notification")

    emotion_rules = policy_config.get("emotion_rules", {})
    if primary in emotion_rules:
        return emotion_rules[primary].get("selection_mode", defaults.get("default_mode", "emotional_context"))

    return defaults.get("default_mode", "emotional_context")


def select_best_memory(
    retrieved_memories: List[Dict],
    detected_emotion: Dict,
    current_user_message: str,
    purpose: str = "chat",
    policy_config: Optional[Dict] = None,
    referenced_memory_ids: Optional[set] = None,
) -> Dict:
    """
    Select the best memory using YAML-configured selection mode weights.

    Args:
        retrieved_memories: Candidate memories from the retriever.
        detected_emotion: Detected emotion/intent dict.
        current_user_message: Raw user message.
        purpose: chat, session_opener, notification, etc.
        policy_config: Optional loaded policy config.
        referenced_memory_ids: Optional set of previously-used memory IDs.

    Returns:
        Dict with selected memory, score breakdowns, backup memories, and
        recommended detail level.
    """
    if policy_config is None:
        policy_config = load_response_policy(DEFAULT_CONFIG_PATH)

    if not retrieved_memories:
        return {
            "selected_memory": None,
            "selection_mode": "none",
            "selection_confidence": 0.0,
            "recommended_detail_level": "none",
            "selection_reason": "No memories retrieved",
            "scored_candidates": [],
            "backup_memories": [],
        }

    mode_name = infer_selection_mode(detected_emotion, purpose, policy_config)
    selection_modes = policy_config.get("selection_modes", {})
    mode_config = selection_modes.get(mode_name, selection_modes.get("emotional_context", {}))

    # Get emotion hints
    primary_emotion = detected_emotion.get("primary", "neutral")
    emotion_rules = policy_config.get("emotion_rules", {})
    emotion_rule = emotion_rules.get(primary_emotion, {})
    hints = emotion_rule.get("memory_selection_hints", {})
    preferred_types = set(hints.get("prefer_memory_types", []))
    preferred_emotions = set(hints.get("prefer_emotions", []))
    prefer_unresolved = hints.get("prefer_unresolved", False)
    prefer_follow_up = hints.get("prefer_follow_up", False)

    # Direct memory question preferred type
    preferred_type_from_query = detected_emotion.get("preferred_memory_type")
    if detected_emotion.get("intent") == "direct_memory_question" and preferred_type_from_query:
        preferred_types = {preferred_type_from_query}

    # Global safety
    high_sensitivity_block = mode_config.get("high_sensitivity_block", False)

    # Extract topic hints from user message
    from app.current_topic_extractor import extract_current_topic_hints
    topic_hints = extract_current_topic_hints(current_user_message)

    # Score each memory
    scored = []
    for mem in retrieved_memories:
        score = _score_memory(
            memory=mem,
            mode_config=mode_config,
            primary_emotion=primary_emotion,
            preferred_types=preferred_types,
            preferred_emotions=preferred_emotions,
            prefer_unresolved=prefer_unresolved,
            prefer_follow_up=prefer_follow_up,
            referenced_memory_ids=referenced_memory_ids or set(),
            high_sensitivity_block=high_sensitivity_block,
            topic_hints=topic_hints,
            current_user_message=current_user_message,
        )
        scored.append({"memory": mem, "score": score})

    # Sort by total score descending
    scored.sort(key=lambda x: x["score"]["total"], reverse=True)

    # For exact_recall: check if top is distractor and non-distractor exists
    if mode_name == "exact_recall" and scored:
        top = scored[0]
        if top["memory"].get("is_distractor", False):
            for i in range(1, len(scored)):
                if not scored[i]["memory"].get("is_distractor", False):
                    if scored[i]["score"]["total"] >= top["score"]["total"] - 0.15:
                        scored.insert(0, scored.pop(i))
                    break

    selected = scored[0]["memory"] if scored else None
    top_score = scored[0]["score"]["total"] if scored else 0.0

    confidence = min(1.0, max(0.0, top_score))
    detail_level = mode_config.get("allowed_detail_level", "vague")

    if selected and selected.get("sensitivity", 0) >= 0.7 and high_sensitivity_block:
        detail_level = "none"

    reason = f"Mode={mode_name}. "
    if selected:
        reason += (
            f"Selected {selected.get('memory_id')} "
            f"({selected.get('memory_type')}) "
            f"score={top_score:.3f}. "
        )
        breakdown = scored[0]["score"].get("breakdown", {})
        reason += f"Breakdown: {breakdown}"
    else:
        reason = "No suitable memory found."

    return {
        "selected_memory": selected,
        "selection_mode": mode_name,
        "selection_confidence": round(confidence, 3),
        "recommended_detail_level": detail_level,
        "selection_reason": reason,
        "scored_candidates": scored[:5],
        "backup_memories": [s["memory"] for s in scored[1:3]],
    }


def _compute_source_text_match_score(query: str, memory: Dict, topic_hints: Dict = None) -> float:
    """
    Compute how strongly the query matches source text, summary, or topic_tags.
    For specific episode recall, exact phrase match is critical.
    """
    query_lower = query.lower()
    score = 0.0

    # Extract strong topic phrases from hints
    strong_phrases = []
    if topic_hints:
        strong_phrases = topic_hints.get("strong_topic_terms", [])
        # Also check topic family
        family = topic_hints.get("topic_family", "")
        if family:
            strong_phrases.append(family)

    # Score against topic_tags
    tags = " ".join(memory.get("topic_tags", [])).lower()
    for phrase in strong_phrases:
        p_lower = phrase.lower()
        if p_lower in tags:
            score = max(score, 1.0)
        elif any(word in tags for word in p_lower.split()):
            score = max(score, 0.5)

    # Score against summary
    summary = memory.get("summary", "").lower()
    for phrase in strong_phrases:
        p_lower = phrase.lower()
        if p_lower in summary:
            score = max(score, 0.9)
        elif any(word in summary for word in p_lower.split()):
            score = max(score, 0.4)

    # Score against source_text if available
    source = memory.get("source_text", "").lower()
    for phrase in strong_phrases:
        p_lower = phrase.lower()
        if p_lower in source:
            score = max(score, 0.9)
        elif any(word in source for word in p_lower.split()):
            score = max(score, 0.4)

    return score


def _score_memory(
    memory: Dict,
    mode_config: Dict,
    primary_emotion: str,
    preferred_types: set,
    preferred_emotions: set,
    prefer_unresolved: bool,
    prefer_follow_up: bool,
    referenced_memory_ids: set,
    high_sensitivity_block: bool,
    topic_hints: Dict = None,
    current_user_message: str = "",
) -> Dict:
    """
    Score a single memory using the active selection-mode weights.
    Updated with topic-aware scoring + source_text match for episode recall.

    Args:
        memory: Candidate memory dict.
        mode_config: Active selection mode config.
        primary_emotion: Detected primary emotion.
        preferred_types: Preferred memory types for this context.
        preferred_emotions: Preferred memory emotions for this context.
        prefer_unresolved: Whether unresolved memories are favored.
        prefer_follow_up: Whether follow-up memories are favored.
        referenced_memory_ids: Memory IDs already used recently.
        high_sensitivity_block: Whether sensitivity should strongly suppress.
        topic_hints: Topic hints extracted from user message.
        current_user_message: Raw user message for source text matching.

    Returns:
        Dict with total score and breakdown.
    """
    # Weights — updated for topic-aware scoring
    w_sem = mode_config.get("semantic_similarity_weight", 0.25)
    w_topic = mode_config.get("topic_overlap_weight", 0.25)
    w_emotion = mode_config.get("emotion_match_weight", 0.20)
    w_unresolved = mode_config.get("unresolved_weight", 0.07)
    w_recency = mode_config.get("recency_weight", 0.10)
    w_importance = mode_config.get("importance_weight", 0.05)
    w_follow = mode_config.get("follow_up_weight", 0.08)
    w_exact = mode_config.get("exact_value_weight", 0.00)
    w_type_match = mode_config.get("memory_type_match_weight", 0.00)
    w_emotion_intensity = mode_config.get("emotion_intensity_weight", 0.10)

    # Episode recall specific weights
    w_source_text = mode_config.get("source_text_match_weight", 0.0)
    w_key_moment = mode_config.get("key_moment_bonus", 0.0)
    w_summary = mode_config.get("summary_bonus", 0.0)

    pen_sensitivity = mode_config.get("sensitivity_penalty", 0.25)
    pen_distractor = mode_config.get("distractor_penalty", 0.40)
    pen_overuse = mode_config.get("overuse_penalty", 0.15)

    # Values from memory
    semantic_sim = memory.get("semantic_similarity", 0)
    emotion_primary = memory.get("emotion_primary", "neutral")
    emotion_intensity = memory.get("emotion_intensity", 0.5)
    importance = memory.get("importance", 0.5)
    sensitivity = memory.get("sensitivity", 0.0)
    resolved_status = memory.get("resolved_status", "unknown")
    exact_value = memory.get("exact_value", "")
    follow_up = memory.get("follow_up_recommended", False)
    is_distractor = memory.get("is_distractor", False)
    mem_type = memory.get("memory_type", "")
    mem_id = memory.get("memory_id", "")
    mem_source_kind = memory.get("memory_source_kind", "")

    # Emotion match
    emotion_match = 1.0 if emotion_primary == primary_emotion else 0.0
    if emotion_primary in preferred_emotions:
        emotion_match = 1.0
    elif emotion_primary == "neutral":
        emotion_match = 0.3

    # Unresolved bonus
    unresolved_score = 0.0
    if resolved_status in ("unresolved", "partially_resolved"):
        unresolved_score = 1.0
    elif resolved_status == "resolved":
        unresolved_score = 0.3

    # Follow up bonus
    follow_up_score = 1.0 if follow_up else 0.0

    # Exact value bonus
    exact_score = 1.0 if exact_value else 0.0

    # Memory type match
    type_match_score = 1.0 if mem_type in preferred_types else 0.0

    # Recency (simplified)
    recency_score = 0.5

    # Topic overlap scoring
    topic_overlap = 0.0
    topic_mismatch_penalty = 0.0
    topic_match_bonus = 0.0
    if topic_hints:
        topic_overlap = compute_topic_overlap_score(topic_hints, memory)
        if has_strong_topic_mismatch(topic_hints, memory):
            topic_mismatch_penalty = 0.35
        if topic_overlap >= 0.7:
            topic_match_bonus = 0.15

    # Source text match for episode recall
    source_text_score = 0.0
    if w_source_text > 0 and current_user_message:
        source_text_score = _compute_source_text_match_score(
            current_user_message, memory, topic_hints
        )

    # Key moment bonus
    key_moment_score = 1.0 if mem_source_kind == "key_moment" else 0.0

    # Summary bonus
    summary_score = 1.0 if memory.get("summary", "") else 0.0

    # Overuse penalty
    overuse_penalty = 1.0 if mem_id in referenced_memory_ids else 0.0

    total = (
        semantic_sim * w_sem
        + topic_overlap * w_topic
        + topic_match_bonus
        + emotion_match * w_emotion
        + unresolved_score * w_unresolved
        + recency_score * w_recency
        + importance * w_importance
        + follow_up_score * w_follow
        + exact_score * w_exact
        + type_match_score * w_type_match
        + emotion_intensity * w_emotion_intensity
        + source_text_score * w_source_text
        + key_moment_score * w_key_moment
        + summary_score * w_summary
        - sensitivity * pen_sensitivity
        - (1.0 if is_distractor else 0.0) * pen_distractor
        - overuse_penalty * pen_overuse
        - topic_mismatch_penalty
    )

    total = max(-1.0, min(2.0, total))

    breakdown = {
        "semantic": round(semantic_sim * w_sem, 3),
        "topic_overlap": round(topic_overlap * w_topic, 3),
        "topic_match_bonus": round(topic_match_bonus, 3),
        "emotion_match": round(emotion_match * w_emotion, 3),
        "unresolved": round(unresolved_score * w_unresolved, 3),
        "recency": round(recency_score * w_recency, 3),
        "importance": round(importance * w_importance, 3),
        "follow_up": round(follow_up_score * w_follow, 3),
        "exact": round(exact_score * w_exact, 3),
        "type_match": round(type_match_score * w_type_match, 3),
        "emotion_intensity": round(emotion_intensity * w_emotion_intensity, 3),
        "source_text": round(source_text_score * w_source_text, 3),
        "key_moment": round(key_moment_score * w_key_moment, 3),
        "summary": round(summary_score * w_summary, 3),
        "sensitivity_pen": round(-sensitivity * pen_sensitivity, 3),
        "distractor_pen": round(-(1.0 if is_distractor else 0.0) * pen_distractor, 3),
        "overuse_pen": round(-overuse_penalty * pen_overuse, 3),
        "topic_mismatch_pen": round(-topic_mismatch_penalty, 3),
    }

    return {"total": round(total, 4), "breakdown": breakdown}


if __name__ == "__main__":
    policy = load_response_policy(DEFAULT_CONFIG_PATH)
    print("Loaded policy sections:", list(policy.keys()))
    print("\nSelection modes:", list(policy.get("selection_modes", {}).keys()))
    print("\nEmotions:", list(policy.get("emotion_rules", {}).keys()))

    from app.current_emotion_detector import detect_current_emotion

    test_msgs = [
        "I'm anxious today",
        "What was my grounding phrase?",
        "I feel overwhelmed",
        "hello",
    ]

    for msg in test_msgs:
        emotion = detect_current_emotion(msg)
        mode = infer_selection_mode(emotion, policy_config=policy)
        print(f'"{msg}" -> emotion={emotion["primary"]}, intent={emotion["intent"]}, mode={mode}')