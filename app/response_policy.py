"""
Project Recall — Response Policy Engine

Loads configurable response policy from YAML and decides:
- Whether to mention a memory
- Whether to ask a direct question
- How vague or specific the reference should be
- What tone and avoid-list to use

All behavior is configurable through config/response_policy.yaml.
This module is the main policy layer that converts detected emotion,
retrieved memories, and safety rules into a response plan.
"""
import os
from typing import Dict, List, Optional
import yaml


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "response_policy.yaml"
)


def load_response_policy(config_path: str = DEFAULT_CONFIG_PATH) -> Dict:
    """
    Load response policy from YAML file.

    Args:
        config_path: Path to response_policy.yaml.

    Returns:
        Parsed YAML policy dict.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_emotion_rule(policy: Dict, emotion: str) -> Dict:
    """
    Get the emotion-specific rule, falling back to neutral.

    Args:
        policy: Loaded policy dict.
        emotion: Detected primary emotion.

    Returns:
        Emotion rule dict.
    """
    rules = policy.get("emotion_rules", {})
    return rules.get(emotion, rules.get("neutral", {}))


def _get_memory_type_rule(policy: Dict, memory_type: str) -> Dict:
    """
    Get the memory-type-specific rule, falling back to a generic default.

    Args:
        policy: Loaded policy dict.
        memory_type: Retrieved memory type.

    Returns:
        Memory-type rule dict.
    """
    rules = policy.get("memory_type_rules", {})
    return rules.get(memory_type, {
        "can_reference_directly": False,
        "ask_direct_question": False,
        "preferred_strategy": "only_if_user_mentions",
    })


def decide_response_policy(
    current_message: str,
    detected_emotion: Dict,
    retrieved_memories: List[Dict],
    emotional_plan: Optional[Dict] = None,
    policy_config: Optional[Dict] = None,
) -> Dict:
    """
    Decide the response policy based on emotion, memory, and configuration.

    This function is the central behavior controller for memory usage. It
    applies emotion rules, memory-type rules, direct-question overrides, and
    global safety restrictions to produce a response plan.

    Args:
        current_message: Raw user message.
        detected_emotion: Output from detect_current_emotion().
        retrieved_memories: Candidate memories from retrieval.
        emotional_plan: Optional planner output.
        policy_config: Optional loaded YAML config.

    Returns:
        Dict containing response_mode, memory mention flags, detail level,
        tone, prompt guidance, selected topic, and debug rule information.
    """
    if policy_config is None:
        policy_config = load_response_policy()

    primary_emotion = detected_emotion.get("primary", "neutral")
    intent = detected_emotion.get("intent", "general_chat")
    needs_lookup = detected_emotion.get("needs_memory_lookup", False)

    emotion_rule = _get_emotion_rule(policy_config, primary_emotion)
    global_safety = policy_config.get("global_safety", {})

    # Load emotion rule
    emotion_rules = policy_config.get("emotion_rules", {})
    emotion_rule = emotion_rules.get(primary_emotion, emotion_rules.get("neutral", {}))

    # Default response: no memory mention
    result = {
        "response_mode": "validate_only",
        "mention_memory": False,
        "ask_direct_question": False,
        "selected_memory_id": None,
        "selected_topic": None,
        "allowed_memory_detail_level": "none",
        "tone": "warm, calm, gently curious",
        "policy_reason": "Default: no memory lookup triggered or no relevant memories found.",
        "avoid": [],
        "prompt_guidance": "",
        "effective_emotion_rule": {},
        "effective_memory_type_rule": {},
    }

    # --- Case 1: No memory lookup needed ---
    if not needs_lookup or not retrieved_memories:
        if intent == "emotional_disclosure":
            result["response_mode"] = "validate_only"
            result["policy_reason"] = f"Emotion detected ({primary_emotion}) but no relevant memories found or lookup disabled by policy."
        elif intent == "direct_memory_question":
            result["response_mode"] = "validate_only"
            result["policy_reason"] = "Direct memory question asked but no matching memories found."
        return result

    # --- Case 2: We have memories and lookup is needed ---
    # Select the top memory from the emotional plan or first retrieved
    selected_memory = None
    if emotional_plan and emotional_plan.get("selected_memory_id"):
        # Find the memory in retrieved list
        for m in retrieved_memories:
            if m.get("memory_id") == emotional_plan["selected_memory_id"]:
                selected_memory = m
                break
    if not selected_memory:
        selected_memory = retrieved_memories[0]

    mem_type = selected_memory.get("memory_type", "unknown")
    mem_rule = _get_memory_type_rule(policy_config, mem_type)
    sensitivity = selected_memory.get("sensitivity", 0.0)

    # Check global safety
    high_sensitivity = sensitivity >= 0.7
    max_memories = global_safety.get("max_memories_in_response", 1)
    use_uncertainty = global_safety.get("use_uncertainty_language", True)

    # --- Decide based on emotion rule + memory type rule ---

    # Can we mention this memory at all?
    can_mention = emotion_rule.get("mention_related_memory", False)
    can_mention = can_mention and mem_rule.get("can_reference_directly", False)

    # High sensitivity override
    if high_sensitivity and global_safety.get("never_reference_high_sensitivity_in_opener", True):
        can_mention = False

    # Can we ask a direct question?
    can_ask_direct = emotion_rule.get("ask_direct_question", False)
    can_ask_direct = can_ask_direct and mem_rule.get("ask_direct_question", False)

    # High sensitivity override for questions too
    if high_sensitivity and global_safety.get("never_ask_directly_about_sensitive_memory_unless_user_mentions", True):
        can_ask_direct = False

    # For direct memory questions, use strict direct-answer mode
    dmq_config = policy_config.get("direct_memory_questions", {})
    if intent == "direct_memory_question":
        can_mention = True
        can_ask_direct = False
        exact_val = selected_memory.get("exact_value")
        mem_type_rule = policy_config.get("memory_type_rules", {}).get(mem_type, {})
        if exact_val and mem_type_rule.get("can_reference_directly"):
            result["allowed_memory_detail_level"] = "exact_value"
            result["response_mode"] = "direct_answer"
        else:
            result["allowed_memory_detail_level"] = "topic_only"
            result["response_mode"] = "direct_answer_topic"
        result["policy_reason"] = f"Direct memory question -> direct_answer with {mem_type} memory."
        result["prompt_guidance"] = dmq_config.get("prompt_guidance", "")
        result["avoid"] = list(global_safety.get("avoid_mechanical_phrases", []))
    else:
        # Emotional disclosure: use emotion rule from YAML
        can_mention = emotion_rule.get("mention_related_memory", False)
        can_mention = can_mention and mem_rule.get("can_reference_directly", False)

        # High sensitivity override
        if high_sensitivity and global_safety.get("never_reference_high_sensitivity_in_opener", True):
            can_mention = False

        # Ask direct question?
        can_ask_direct = emotion_rule.get("ask_direct_question", False)
        can_ask_direct = can_ask_direct and mem_rule.get("ask_direct_question", False)
        if high_sensitivity and global_safety.get("never_ask_directly_about_sensitive_memory_unless_user_mentions", True):
            can_ask_direct = False

        # Never expose exact value for emotional disclosure
        if global_safety.get("never_expose_exact_value_for_emotional_disclosure", True):
            exact_val = None

        if can_mention:
            if can_ask_direct:
                result["allowed_memory_detail_level"] = emotion_rule.get("allowed_detail_level", "topic_only")
                result["response_mode"] = emotion_rule.get("preferred_strategy", "direct_follow_up")
                result["policy_reason"] = f"Emotion ({primary_emotion}) + memory ({mem_type}) allows direct follow-up."
            else:
                # Vague by default for emotional disclosures
                detail = emotion_rule.get("allowed_detail_level", "vague")
                result["allowed_memory_detail_level"] = detail
                result["response_mode"] = emotion_rule.get("preferred_strategy", "soft_optional_reference")
                result["policy_reason"] = f"Emotion ({primary_emotion}) detected, memory ({mem_type}) found. Using {detail} reference."
        else:
            result["allowed_memory_detail_level"] = "none"
            result["response_mode"] = emotion_rule.get("preferred_strategy", "validate_only")
            result["policy_reason"] = f"Emotion ({primary_emotion}) detected but memory mention blocked by policy."

        result["prompt_guidance"] = emotion_rule.get("prompt_guidance", "")
        result["avoid"] = list(emotion_rule.get("avoid", []))
        result["tone"] = emotion_rule.get("tone", "warm, calm, gently curious")

    # Effective rules for debug
    result["effective_emotion_rule"] = {
        "emotion": primary_emotion,
        "mention_related_memory": emotion_rule.get("mention_related_memory"),
        "ask_direct_question": emotion_rule.get("ask_direct_question"),
        "preferred_strategy": emotion_rule.get("preferred_strategy"),
        "allowed_detail_level": emotion_rule.get("allowed_detail_level"),
    }
    result["effective_memory_type_rule"] = {
        "memory_type": mem_type,
        "can_reference_directly": mem_rule.get("can_reference_directly"),
        "sensitivity_threshold": mem_rule.get("sensitivity_threshold"),
    }

    # Set mention and question flags
    result["mention_memory"] = can_mention
    result["ask_direct_question"] = can_ask_direct

    # Set selected memory info
    result["selected_memory_id"] = selected_memory.get("memory_id")
    result["selected_topic"] = _infer_topic(selected_memory)

    # Set tone based on emotion
    result["tone"] = _select_tone(primary_emotion, selected_memory)

    # Set avoid list (combine emotion + global)
    avoid_list = list(emotion_rule.get("avoid", []))
    if use_uncertainty and not can_ask_direct:
        avoid_list.append("Avoid stating causality. Use language like 'I remember something came up recently, but it may or may not be connected.'")
    result["avoid"] = avoid_list

    return result


def _infer_topic(memory: Dict) -> str:
    """
    Infer a human-readable topic from memory metadata.

    Args:
        memory: Selected memory dict.

    Returns:
        Human-readable topic string.
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
        "relationship_context": "relationship matter",
    }
    return topic_map.get(mem_type, "something from our previous session")


def _select_tone(emotion: str, memory: Dict) -> str:
    """
    Select a response tone based on emotion and memory metadata.

    Args:
        emotion: Detected primary emotion.
        memory: Selected memory dict.

    Returns:
        Tone description for generation.
    """
    intensity = memory.get("emotion_intensity", 0.5)

    if emotion in ("anxiety", "overwhelm"):
        if intensity > 0.7:
            return "warm, grounding, gently curious"
        return "warm, calm, gently curious"

    if emotion in ("sadness", "loneliness"):
        return "warm, soft, gently curious"

    if emotion == "anger":
        return "warm, calm, non-defensive"

    if emotion == "shame":
        return "warm, soft, non-judgmental"

    if emotion in ("hopefulness", "relief"):
        return "warm, quietly celebratory, gently curious"

    return "warm, calm, gently curious"


def generate_policy_based_response(
    current_message: str,
    detected_emotion: Dict,
    selected_memory: Optional[Dict],
    response_policy: Dict,
) -> str:
    """
    Generate a human-like response based on the decided policy.

    Uses templates for different response modes. This is primarily a debug
    and fallback generator; the main app usually uses policy-injected LLM
    prompts instead of these direct templates.

    Args:
        current_message: Raw user message.
        detected_emotion: Detected emotion dict.
        selected_memory: Selected memory dict, if any.
        response_policy: Output from decide_response_policy().

    Returns:
        Template-generated response string.
    """
    emotion = detected_emotion.get("primary", "neutral")
    intensity = detected_emotion.get("intensity", 0.5)
    mode = response_policy.get("response_mode", "validate_only")
    mention = response_policy.get("mention_memory", False)
    topic = response_policy.get("selected_topic", "something")
    detail_level = response_policy.get("allowed_memory_detail_level", "none")
    exact_value = selected_memory.get("exact_value") if selected_memory else None

    # --- Validation line based on emotion ---
    validation = _validation_line(emotion, intensity)

    # --- Case A: No memory mention ---
    if not mention or not selected_memory:
        if mode == "ground_first_then_offer_memory":
            return (
                f"Let's slow it down first. {validation} "
                f"You don't have to solve everything right now. What feels most urgent?"
            )
        if mode == "validate_only":
            return f"{validation} What feels most present right now?"
        return f"{validation} Would you like to talk about what's going on?"

    # --- Case B: Vague / optional reference ---
    if detail_level == "vague":
        if mode == "validate_then_offer_choice":
            return (
                f"{validation} I remember a few things recently felt emotionally unresolved, "
                f"but we don't have to jump into any of them unless it feels useful. "
                f"What feels most present right now?"
            )
        if mode == "validate_then_gentle_optional_reference":
            return (
                f"{validation} I remember {topic} came up before, "
                f"but I'm not assuming that's what's happening today. "
                f"What feels most present right now?"
            )
        if mode == "ground_first_then_offer_memory":
            return (
                f"Let's slow it down first. {validation} "
                f"If it helps, I remember {topic} was something we touched on before. "
                f"But we can stay right here with what you're feeling now. What feels most urgent?"
            )
        return (
            f"{validation} I remember {topic} was something that felt important before. "
            f"Would it help to pick that up, or is something else on your mind?"
        )

    # --- Case C: Topic-only reference ---
    if detail_level == "topic_only":
        if mode == "direct_follow_up":
            return (
                f"{validation} I remember {topic} had come up recently. "
                f"Is this connected to that, or does it feel like something different today?"
            )
        return (
            f"{validation} {topic} came up before. "
            f"Would it help to talk about that, or is something else going on?"
        )

    # --- Case D: Exact value reference (direct memory questions only) ---
    if detail_level == "exact_value" and exact_value:
        if mode == "offer_grounding":
            return (
                f"{validation} I remember you found a phrase that felt calming: "
                f'"{exact_value}". Is that still something that helps?'
            )
        return (
            f"{validation} You asked me to remember this: "
            f'"{exact_value}". How are you feeling about that today?'
        )

    # Fallback
    return f"{validation} What would you like to talk about today?"


def _validation_line(emotion: str, intensity: float) -> str:
    """
    Generate an emotion-appropriate validation line.

    Args:
        emotion: Primary emotion.
        intensity: Emotion intensity score.

    Returns:
        Short empathetic validation sentence.
    """
    lines = {
        "sadness": [
            "I'm sorry today feels heavy.",
            "That sounds really hard.",
            "It makes sense that things feel low right now.",
        ],
        "anxiety": [
            "That sounds really uncomfortable.",
            "It makes sense that your mind is racing.",
            "That sounds really overwhelming.",
        ],
        "overwhelm": [
            "That sounds like a lot.",
            "It makes sense that everything feels too much right now.",
            "That sounds exhausting.",
        ],
        "anger": [
            "That sounds really frustrating.",
            "It makes sense that you're upset.",
            "That sounds like something important was crossed.",
        ],
        "shame": [
            "That sounds really painful.",
            "It makes sense that you're being hard on yourself.",
            "That sounds heavy to carry.",
        ],
        "loneliness": [
            "That sounds really isolating.",
            "It makes sense that you feel disconnected right now.",
            "That sounds really hard to hold alone.",
        ],
        "uncertainty": [
            "That sounds really disorienting.",
            "It makes sense that you feel lost right now.",
            "That sounds really uncomfortable.",
        ],
        "hopefulness": [
            "That sounds like a positive shift.",
            "It's good to hear something feels better.",
            "That sounds encouraging.",
        ],
        "relief": [
            "I'm glad something feels lighter.",
            "That sounds like a weight lifted.",
            "It's good to hear you're breathing easier.",
        ],
        "neutral": [
            "I'm glad you're here.",
            "I'm listening.",
            "Thanks for sharing that.",
        ],
    }

    import random
    # Seed with emotion + intensity to be consistent for same inputs
    random.seed(hash(emotion) + int(intensity * 10))
    return random.choice(lines.get(emotion, lines["neutral"]))


if __name__ == "__main__":
    # Quick self-test
    policy = load_response_policy()
    print("Loaded policy keys:", list(policy.keys()))

    # Test with a sadness example
    from app.current_emotion_detector import detect_current_emotion
    msg = "I'm feeling down"
    emotion = detect_current_emotion(msg)
    print(f"\nMessage: '{msg}'")
    print(f"Detected: {emotion}")

    # Simulate a retrieved memory
    mock_memory = {
        "memory_id": "test_mem",
        "memory_type": "unresolved_theme",
        "topic_tags": ["friendship conflict", "hurt feelings"],
        "sensitivity": 0.4,
        "emotion_intensity": 0.7,
    }

    decision = decide_response_policy(
        current_message=msg,
        detected_emotion=emotion,
        retrieved_memories=[mock_memory],
        policy_config=policy,
    )
    print(f"\nPolicy decision:")
    for k, v in decision.items():
        print(f"  {k}: {v}")

    response = generate_policy_based_response(msg, emotion, mock_memory, decision)
    print(f"\nGenerated response:")
    print(f'  "{response}"')