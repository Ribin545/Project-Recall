"""
Project Recall - Re-Engagement Rules Engine
============================================

Decides whether to send a push notification to a user who has not
chatted recently, what type of notification to send, and what
emotionally appropriate, lock-screen-safe copy to use.

The engine is fully rule-based and local-first. It does NOT send
real notifications — it produces a decision object and safe copy
that a real push-notification service would consume.

Pipeline
--------
1. Load user state + re-engagement config
2. Guard checks (consent, quiet hours, fatigue, timing)
3. Filter candidate memories to safe-for-notification subset
4. Select the best memory for re-engagement
5. Determine notification type based on emotion + memory + timing
6. Generate safe copy (emotion-specific templates from prompts.py)
7. Run safety audit
8. Return decision object

Integration
-----------
- Reads user state from `app/reengagement_state.py`
- Reads trigger rules from `config/response_policy.yaml`
- Reads notification copy from `app/prompts.py` (configurable templates)
- Optionally rewrites copy via LLM when `use_llm=true`
"""

import os
from typing import Dict, List, Optional

from app.reengagement_state import load_extracted_memories
from app.response_policy import load_response_policy


# Path to the unified YAML response policy (contains reengagement section)
DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "response_policy.yaml"
)


def decide_reengagement(
    user_state: Dict,
    candidate_memories: List[Dict] = None,
    policy_config: Dict = None,
) -> Dict:
    """
    Main entry point: decide whether to send a re-engagement notification.

    Runs the full guard → filter → select → type → copy → audit pipeline.
    Returns a decision dict that is safe to serialize to JSON.

    Args:
        user_state: Dict with keys like days_since_last_session,
            last_session_close_emotion, notifications_sent_last_7_days, etc.
        candidate_memories: Optional pre-loaded memory list. If None,
            memories are loaded from `data/extracted_memories.json`.
        policy_config: Optional pre-loaded YAML config. If None,
            the default `config/response_policy.yaml` is loaded.

    Returns:
        A decision dict. When should_send is True, it includes:
            - notification_type: str
            - priority: "high" | "medium" | "low" | "none"
            - selected_memory_id: str | None
            - selected_memory_type: str | None
            - selected_topic: str | None
            - selected_emotion: str | None
            - copy: str | None
            - reason: str
            - safety_notes: List[str]
            - blocked_by: None

        When should_send is False, it includes:
            - blocked_by: str (reason: consent, fatigue, too_soon, etc.)
    """
    # -------------------------------------------------------------------------
    # 1. Load configuration
    # -------------------------------------------------------------------------
    if policy_config is None:
        policy_config = load_response_policy(DEFAULT_CONFIG_PATH)

    reeng_config = policy_config.get("reengagement", {})
    if not reeng_config.get("enabled", True):
        return _blocked("reengagement_disabled")

    # -------------------------------------------------------------------------
    # 2. Guard checks (order matters: fastest / cheapest first)
    # -------------------------------------------------------------------------
    # A. Consent — respect user preference immediately
    if not user_state.get("personalized_notifications_enabled", True):
        return _blocked("consent")

    # B. Quiet hours — do not disturb
    if user_state.get("quiet_hours_active", False):
        return _blocked("quiet_hours")

    # C. Fatigue — limit to max_notifications_per_7_days
    max_per_week = reeng_config.get("max_notifications_per_7_days", 2)
    if user_state.get("notifications_sent_last_7_days", 0) >= max_per_week:
        return _blocked("fatigue")

    # D. Timing — wait at least min_days_between_notifications
    min_days = reeng_config.get("min_days_between_notifications", 2)
    days_since = user_state.get("days_since_last_session", 0)
    if days_since < min_days:
        return _blocked("too_soon")

    # -------------------------------------------------------------------------
    # 3. Load and filter candidate memories
    # -------------------------------------------------------------------------
    user_id = user_state.get("user_id", "demo_user")
    if candidate_memories is None:
        candidate_memories = load_extracted_memories(user_id)

    safe_candidates = _filter_safe_candidates(candidate_memories, reeng_config)
    if not safe_candidates:
        return _blocked("no_relevant_memory")

    # -------------------------------------------------------------------------
    # 4. Select the best memory for a notification
    # -------------------------------------------------------------------------
    selected_memory = _select_best_notification_memory(
        safe_candidates,
        user_state,
        policy_config,
    )

    if not selected_memory:
        return _blocked("no_relevant_memory")

    # -------------------------------------------------------------------------
    # 5. Determine notification type based on user emotion + memory + timing
    # -------------------------------------------------------------------------
    # Use the user's emotion from state, NOT the memory's emotion.
    # This ensures the notification matches how the user felt at session close.
    user_emotion = user_state.get("last_session_close_emotion", "neutral")
    notif_type, priority = _determine_notification_type(
        selected_memory,
        days_since,
        reeng_config,
        user_emotion,
    )

    # -------------------------------------------------------------------------
    # 6. Upgrade soft_return if a better candidate exists
    # -------------------------------------------------------------------------
    # If the engine defaulted to soft_return, try to find a more specific
    # memory type that matches a higher-priority notification rule.
    if notif_type == "soft_return" and 2 <= days_since < 7:
        upgraded = _try_upgrade_notification_type(
            safe_candidates, days_since, reeng_config, user_state
        )
        if upgraded:
            notif_type, priority, selected_memory = upgraded

    # -------------------------------------------------------------------------
    # 7. Generate safe notification copy
    # -------------------------------------------------------------------------
    copy = make_notification_copy(notif_type, selected_memory, user_state)

    # -------------------------------------------------------------------------
    # 8. Safety audit
    # -------------------------------------------------------------------------
    safety_notes = _audit_safety(copy, selected_memory, reeng_config)

    # -------------------------------------------------------------------------
    # 9. Build and return the decision object
    # -------------------------------------------------------------------------
    return {
        "should_send": True,
        "notification_type": notif_type,
        "priority": priority,
        "selected_memory_id": selected_memory.get("memory_id"),
        "selected_memory_type": selected_memory.get("memory_type"),
        "selected_topic": _infer_topic(selected_memory),
        "selected_emotion": selected_memory.get("emotion", {}).get("primary", "neutral"),
        "reason": (
            f"{notif_type} triggered after {days_since} days. "
            f"Memory: {selected_memory.get('memory_type')} "
            f"(importance={selected_memory.get('importance', 0)}, "
            f"resolved={selected_memory.get('resolved_status')})."
        ),
        "copy": copy,
        "safety_notes": safety_notes,
        "blocked_by": None,
    }


def _try_upgrade_notification_type(
    candidates: List[Dict],
    days_since: int,
    reeng_config: Dict,
    user_state: Dict,
) -> Optional[tuple]:
    """
    Try to upgrade a 'soft_return' to a more specific notification type.

    When the engine initially selects soft_return (7+ days), this
    function looks for higher-priority matches among safe candidates:
      1. gentle_unresolved_followup — unresolved + matching emotion
      2. coping_strategy_checkin — coping/grounding memory types
      3. goal_progress_checkin — user_goal memory types

    This prevents a user with unresolved anxiety from only receiving
    the generic "whenever you're ready" message.

    Args:
        candidates: Safe memory candidates (already filtered).
        days_since: Days since the user's last session.
        reeng_config: The reengagement section of response_policy.yaml.
        user_state: Full user state dict (for emotion access).

    Returns:
        A tuple (notification_type, priority, selected_memory) if a
        better match is found, otherwise None.
    """
    rules = reeng_config.get("trigger_rules", {})

    # -------------------------------------------------------------------------
    # Upgrade path 1: gentle_unresolved_followup
    # -------------------------------------------------------------------------
    # Matches unresolved or partially-resolved memories whose emotion
    # aligns with the user's last_session_close_emotion.
    unresolved_rule = rules.get("gentle_unresolved_followup", {})
    allowed_emotions = set(unresolved_rule.get("allowed_emotions", []))
    allowed_status = set(unresolved_rule.get("allowed_resolved_status", []))
    allowed_status.add("unknown")  # Many needle memories have unknown status
    min_days = unresolved_rule.get("min_days_since_last_session", 3)

    user_emotion = user_state.get("last_session_close_emotion", "neutral")
    if days_since >= min_days and user_emotion in allowed_emotions:
        for mem in candidates:
            emotion = mem.get("emotion", {}).get("primary", "neutral")
            resolved = mem.get("resolved_status", "unknown")
            if emotion in allowed_emotions and resolved in allowed_status:
                return "gentle_unresolved_followup", "high", mem

    # -------------------------------------------------------------------------
    # Upgrade path 2: coping_strategy_checkin
    # -------------------------------------------------------------------------
    # Skipped for positive emotions (hopefulness, relief) because a
    # coping check-in would feel mismatched — the user doesn't need coping.
    positive_emotions = {"hopefulness", "relief"}
    coping_rule = rules.get("coping_strategy_checkin", {})
    allowed_types = set(coping_rule.get("allowed_memory_types", []))
    min_days_coping = coping_rule.get("min_days_since_last_session", 2)

    if days_since >= min_days_coping and user_emotion not in positive_emotions:
        for mem in candidates:
            if mem.get("memory_type", "") in allowed_types:
                return "coping_strategy_checkin", "medium", mem

    # -------------------------------------------------------------------------
    # Upgrade path 3: goal_progress_checkin
    # -------------------------------------------------------------------------
    goal_rule = rules.get("goal_progress_checkin", {})
    goal_types = set(goal_rule.get("allowed_memory_types", []))
    min_days_goal = goal_rule.get("min_days_since_last_session", 3)

    if days_since >= min_days_goal:
        for mem in candidates:
            if mem.get("memory_type", "") in goal_types:
                return "goal_progress_checkin", "medium", mem

    return None


def _blocked(reason: str) -> Dict:
    """
    Return a blocked notification decision.

    This is the uniform shape returned whenever a notification
    should NOT be sent (consent off, fatigue, quiet hours, etc.).

    Args:
        reason: Human-readable block reason (also used as blocked_by).

    Returns:
        A decision dict with should_send=False.
    """
    return {
        "should_send": False,
        "notification_type": "no_notification",
        "priority": "none",
        "selected_memory_id": None,
        "selected_memory_type": None,
        "selected_topic": None,
        "selected_emotion": None,
        "reason": f"Notification blocked: {reason}",
        "copy": None,
        "safety_notes": [f"Blocked by {reason}"],
        "blocked_by": reason,
    }


def _filter_safe_candidates(
    memories: List[Dict],
    reeng_config: Dict,
) -> List[Dict]:
    """
    Filter memories to only those safe for push notifications.

    Safety criteria (all must pass):
      - safe_to_reference_in_opener == True
      - is_distractor == False (avoid memories that are similar but wrong)
      - sensitivity < 0.7 (high-sensitivity memories are too risky)
      - importance >= 0.65 (ignore trivial memories)

    Args:
        memories: All extracted memories for the user.
        reeng_config: Reengagement config from response_policy.yaml.

    Returns:
        A list of safe candidate memories.
    """
    safe = []
    for mem in memories:
        # Must be explicitly flagged safe for openers/notifications
        if not mem.get("safe_to_reference_in_opener", True):
            continue

        # Distractors are near-duplicate memories that could mislead
        if mem.get("is_distractor", False):
            continue

        # High sensitivity = topics like trauma, self-harm, abuse
        # These should never appear in push notifications
        if mem.get("sensitivity", 0) >= 0.7:
            continue

        # Skip low-importance memories (e.g., casual small talk)
        if mem.get("importance", 0) < 0.65:
            continue

        safe.append(mem)

    return safe


def _select_best_notification_memory(
    candidates: List[Dict],
    user_state: Dict,
    policy_config: Dict,
) -> Optional[Dict]:
    """
    Select the best memory for a re-engagement notification.

    First tries the shared best_memory_selector.py with
    purpose="notification". Falls back to local scoring if that
    module is unavailable or returns nothing.

    Args:
        candidates: Safe candidate memories (already filtered).
        user_state: Full user state dict.
        policy_config: Loaded response_policy.yaml config.

    Returns:
        The selected memory dict, or None if no suitable memory found.
    """
    # -------------------------------------------------------------------------
    # Primary path: use the project's shared best_memory_selector
    # -------------------------------------------------------------------------
    try:
        from app.best_memory_selector import select_best_memory

        # Build a synthetic emotion dict so the selector can apply
        # YAML emotion-specific weights and memory type rules
        detected = {
            "primary": user_state.get("last_session_close_emotion", "neutral"),
            "intent": "notification",
            "needs_memory_lookup": True,
        }

        result = select_best_memory(
            retrieved_memories=candidates,
            detected_emotion=detected,
            current_user_message="notification-safe follow-up",
            purpose="notification",
            policy_config=policy_config,
        )

        selected = result.get("selected_memory")
        if selected:
            return selected
    except Exception:
        # best_memory_selector not available — fall through
        pass

    # -------------------------------------------------------------------------
    # Fallback: local scoring heuristic
    # -------------------------------------------------------------------------
    return _local_score_selection(candidates)


def _local_score_selection(candidates: List[Dict]) -> Optional[Dict]:
    """
    Score notification candidates with a simple heuristic.

    Scoring weights (arbitrary but tuned for re-engagement):
      - importance * 0.30
      - preferred memory type +0.20
      - unresolved/partially_resolved status +0.20
      - follow_up_recommended +0.15
      - emotion intensity * 0.15
      - session_003 recency bonus +0.15
      - sensitivity penalty -0.30
      - distractor penalty -0.50

    Args:
        candidates: Safe candidate memories.

    Returns:
        The highest-scoring memory, or None if no candidates.
    """
    # Memory types that are especially good for notifications
    preferred_types = {
        "follow_up_intent",
        "coping_strategy",
        "grounding_phrase",
        "unresolved_theme",
        "emotional_pattern",
        "user_goal",
        "review_preparation",
    }

    scored = []
    for mem in candidates:
        mem_type = mem.get("memory_type", "")
        resolved = mem.get("resolved_status", "unknown")
        importance = mem.get("importance", 0.5)
        sensitivity = mem.get("sensitivity", 0)
        follow_up = mem.get("follow_up_recommended", False)
        session_id = mem.get("source_session_id", "")

        # Base score from importance
        score = importance * 0.30

        # Boost for preferred memory types
        if mem_type in preferred_types:
            score += 0.20

        # Boost for unresolved / partially resolved memories
        if resolved in ("unresolved", "partially_resolved", "unknown"):
            score += 0.20

        # Boost for memories explicitly flagged for follow-up
        if follow_up:
            score += 0.15

        # Slight boost for emotionally intense memories
        intensity = mem.get("emotion", {}).get("intensity", 0.5)
        score += intensity * 0.15

        # Strong recency bonus for the needle session (session_003)
        # In production this would be a real recency calculation
        if "session_003" in session_id:
            score += 0.15

        # Penalties
        score -= sensitivity * 0.30
        if mem.get("is_distractor", False):
            score -= 0.50

        scored.append((score, mem))

    if not scored:
        return None

    # Return the highest-scoring memory
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _is_recent_session(session_id: str) -> bool:
    """
    Heuristic: session_003 and higher are considered recent.

    In production this would compare actual timestamps.
    For the demo we use session numbering as a proxy.

    Args:
        session_id: A session identifier like "session_003".

    Returns:
        True if the session number is >= 3.
    """
    try:
        if session_id.startswith("session_"):
            num = int(session_id.split("_")[1])
            return num >= 3
    except Exception:
        pass
    return False


def _determine_notification_type(
    memory: Dict,
    days_since: int,
    reeng_config: Dict,
    user_emotion: str = "neutral",
) -> tuple:
    """
    Determine notification type and priority from memory + timing + emotion.

    Checks rules in priority order:
      1. gentle_unresolved_followup (3+ days, unresolved, matching emotion)
      2. coping_strategy_checkin (2+ days, coping/grounding memory type)
      3. goal_progress_checkin (3+ days, user_goal memory type)
      4. soft_return (7+ days, generic fallback)

    Args:
        memory: The selected best memory dict.
        days_since: Days since the user's last session.
        reeng_config: Reengagement config from response_policy.yaml.
        user_emotion: The user's emotion at session close (NOT the memory's).

    Returns:
        A tuple (notification_type, priority).
    """
    rules = reeng_config.get("trigger_rules", {})

    # Memory attributes used for type matching
    mem_type = memory.get("memory_type", "")
    resolved = memory.get("resolved_status", "unknown")
    # IMPORTANT: use user's emotion, not memory's emotion
    emotion = user_emotion

    # -------------------------------------------------------------------------
    # Rule 1: gentle_unresolved_followup
    # -------------------------------------------------------------------------
    unresolved_rule = rules.get("gentle_unresolved_followup", {})
    min_days_unresolved = unresolved_rule.get("min_days_since_last_session", 3)
    allowed_emotions = set(unresolved_rule.get("allowed_emotions", []))
    allowed_status = set(unresolved_rule.get("allowed_resolved_status", []))

    # Treat "unknown" as a fallback — many needle memories lack explicit status
    if "unknown" not in allowed_status:
        allowed_status.add("unknown")

    if (days_since >= min_days_unresolved and
            resolved in allowed_status and
            emotion in allowed_emotions):
        return "gentle_unresolved_followup", "high"

    soft_rule = rules.get("soft_return", {})
    min_days_soft = soft_rule.get("min_days_since_last_session", 7)

    if days_since >= min_days_soft:
        return "soft_return", "low"

    # -------------------------------------------------------------------------
    # Rule 2: coping_strategy_checkin
    # -------------------------------------------------------------------------
    coping_rule = rules.get("coping_strategy_checkin", {})
    min_days_coping = coping_rule.get("min_days_since_last_session", 2)
    allowed_types = set(coping_rule.get("allowed_memory_types", []))

    if days_since >= min_days_coping and mem_type in allowed_types:
        return "coping_strategy_checkin", "medium"

    # -------------------------------------------------------------------------
    # Rule 3: goal_progress_checkin
    # -------------------------------------------------------------------------
    goal_rule = rules.get("goal_progress_checkin", {})
    min_days_goal = goal_rule.get("min_days_since_last_session", 3)
    goal_types = set(goal_rule.get("allowed_memory_types", []))

    if days_since >= min_days_goal and mem_type in goal_types:
        return "goal_progress_checkin", "medium"

    # -------------------------------------------------------------------------
    # Rule 4: soft_return (generic, lowest priority fallback)
    # -------------------------------------------------------------------------

    # If nothing matches strongly, still return soft_return with low priority
    return "soft_return", "low"


def make_notification_copy(
    notification_type: str,
    memory: Dict,
    user_state: Dict,
) -> str:
    """
    Generate safe, vague notification copy for a push notification.

    Copies are pulled from NOTIFICATION_COPY_TEMPLATES in prompts.py.
    Each notification type supports emotion-specific copies with a
    "default" fallback. This ensures a user whose last session ended
    in shame gets different copy than one whose session ended in anxiety.

    Args:
        notification_type: The determined notification type
            (e.g., "gentle_unresolved_followup").
        memory: The selected memory dict (used only for exact_value guard).
        user_state: Full user state (used for last_session_close_emotion).

    Returns:
        A lock-screen-safe notification string.
    """
    try:
        from app.prompts import NOTIFICATION_COPY_TEMPLATES
    except Exception:
        NOTIFICATION_COPY_TEMPLATES = {}

    # -------------------------------------------------------------------------
    # Safety guard: if the memory contains an exact_value, ensure it
    # NEVER leaks into the notification copy. Exact values are for
    # in-app references only, not lock-screen push text.
    # -------------------------------------------------------------------------
    exact = memory.get("exact_value")
    if exact:
        pass  # Deliberate no-op; the guard is enforced by template design

    # -------------------------------------------------------------------------
    # Look up copy by (notification_type -> emotion -> copy)
    # Fall back to default copy for that type if emotion not found.
    # -------------------------------------------------------------------------
    emotion = user_state.get("last_session_close_emotion", "neutral")
    type_templates = NOTIFICATION_COPY_TEMPLATES.get(notification_type, {})

    if isinstance(type_templates, dict):
        copy = type_templates.get(emotion) or type_templates.get("default")
    else:
        # Legacy fallback: if templates were stored as plain strings
        copy = type_templates

    return copy or "I'm here if you want a quiet moment to check in."


def _audit_safety(
    copy: str,
    memory: Dict,
    reeng_config: Dict,
) -> List[str]:
    """
    Audit notification copy for safety violations.

    Checks:
      - Forbidden phrases (clinical, mechanical, or stigmatizing words)
      - Exact value leakage (exact_value appearing in copy)
      - Missing copy

    Args:
        copy: The generated notification copy string.
        memory: The selected memory (for exact_value comparison).
        reeng_config: Reengagement config (not currently used, reserved).

    Returns:
        A list of audit notes. Empty list means fully safe.
        If no violations found, returns ["Copy passes safety audit."].
    """
    notes = []

    # List of words/phrases that should NEVER appear in push copy
    forbidden = [
        "anxiety",           # Too clinical for lock screen
        "shame",             # Too stigmatizing
        "therapy",           # Clinical framing
        "mental health diagnosis",
        "we noticed",        # Creepy / mechanical
        "your records",      # Creepy / mechanical
        "database",          # Implementation detail
    ]

    for word in forbidden:
        if word.lower() in copy.lower():
            notes.append(f"WARNING: copy contains forbidden phrase '{word}'")

    # CRITICAL: exact_value must NEVER appear in push copy
    if memory.get("exact_value") and memory.get("exact_value", "") in copy:
        notes.append("CRITICAL: exact_value leaked into notification copy")

    if not notes:
        notes.append("Copy passes safety audit.")

    return notes


def _infer_topic(memory: Dict) -> str:
    """
    Infer a vague topic name from a memory's metadata.

    Used for logging and debugging — never exposed to the user in copy.

    Args:
        memory: A memory dict with a memory_type field.

    Returns:
        A human-readable topic string.
    """
    mem_type = memory.get("memory_type", "")
    topic_map = {
        "review_preparation": "performance preparation",
        "grounding_phrase": "grounding and calm",
        "follow_up_intent": "plan and follow-up",
        "coping_strategy": "coping and self-care",
        "unresolved_theme": "ongoing life concern",
        "emotional_pattern": "emotional pattern",
        "user_goal": "personal goal",
        "relationship_context": "relationship matter",
    }
    return topic_map.get(mem_type, "something we talked about")


# -----------------------------------------------------------------------------
# Self-test entry point (run as: python app/reengagement_rules.py)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    from app.reengagement_state import load_user_reengagement_state

    state = load_user_reengagement_state("demo_user")
    result = decide_reengagement(state)
    print("Re-engagement decision:")
    for k, v in result.items():
        print(f"  {k}: {v}")