"""
Project Recall - Prompts Module

Contains system prompts, notification copy templates, and message templates for the LLM.
All LLM prompts and notification copies are configurable here.
"""

# -----------------------------------------------------------------------------
# 1. SYSTEM PROMPT
# -----------------------------------------------------------------------------
# System prompt for Mentra, the AI emotional support companion.
# Tone: warm, grounded, human, non-clinical, not overly dramatic.
# Does not diagnose. Does not claim to be a licensed therapist.
# Encourages reflection. Avoids long lectures.

MENTRA_BASE_SYSTEM_PROMPT = (
    "You are Mentra, a warm emotional support companion. "
    "You help users reflect on stress, anxiety, relationships, self-growth, and difficult emotions. "
    "You are not a licensed therapist and you do not diagnose. "
    "IMPORTANT: Respond in a natural, warm, conversational tone. "
    "Do NOT use bullet points, markdown formatting, or analytical summaries. "
    "Write as if you are speaking directly to a friend — short sentences, gentle language, human warmth. "
    "Keep responses short, gentle, and conversational. "
    "Ask one thoughtful follow-up question when appropriate. "
    "Do not invent memories. "
    "Only reference past sessions when approved memory context is provided in the current turn. "
    "If no memory is approved, do not guess. Ask a gentle clarifying question instead."
)

# Legacy alias for backward compatibility
MENTRA_SYSTEM_PROMPT = MENTRA_BASE_SYSTEM_PROMPT

# -----------------------------------------------------------------------------
# 2. NOTIFICATION COPY TEMPLATES (Configurable)
# -----------------------------------------------------------------------------
# These are the lock-screen-safe push notification copies.
# Product/clinical teams can customize these without touching code.
# All copies must remain vague (no exact values, no names, no sensitive details).

NOTIFICATION_COPY_TEMPLATES = {
    # Emotion-specific copies for gentle_unresolved_followup
    "gentle_unresolved_followup": {
        "anxiety": (
            "I know last time felt heavy. I'm here when you're ready to talk."
        ),
        "sadness": (
            "I remember things felt hard last time. I'm here if you want company."
        ),
        "shame": (
            "I'm here. No judgment, just a quiet space whenever you're ready."
        ),
        "overwhelm": (
            "Things felt like a lot last time. I'm here if you want to slow down together."
        ),
        "loneliness": (
            "Last time felt quiet in a hard way. I'm here if you want to check in."
        ),
        "uncertainty": (
            "A lot felt unclear last time. I'm here if you want to sort through it gently."
        ),
        "default": (
            "Something you shared last time may still be on your mind. "
            "I'm here if you want to continue gently."
        ),
    },
    # Emotion-specific copies for coping_strategy_checkin
    "coping_strategy_checkin": {
        "anxiety": (
            "Want to check in on the small step that felt calming last time?"
        ),
        "overwhelm": (
            "The small plan you made last time — want to see how it's going?"
        ),
        "default": (
            "Want to check in on the small step you planned last time?"
        ),
    },
    # Emotion-specific copies for goal_progress_checkin
    "goal_progress_checkin": {
        "hopefulness": (
            "The goal you were excited about — want to celebrate one small step?"
        ),
        "default": (
            "Want to revisit the goal you were working toward, one small step at a time?"
        ),
    },
    # soft_return is generic — same for all emotions
    "soft_return": {
        "default": (
            "Whenever you're ready, we can pick up gently from where we left off."
        ),
    },
    "fallback": {
        "default": (
            "I'm here if you want a quiet moment to check in."
        ),
    },
}

# -----------------------------------------------------------------------------
# 3. LLM RE-ENGAGEMENT REWRITE PROMPT (Configurable)
# -----------------------------------------------------------------------------
# This prompt is sent to the LLM when use_llm=true on the reengagement endpoint.
# The LLM personalizes the notification copy based on the user's emotion.

NOTIFICATION_LLM_REWRITE_PROMPT_TEMPLATE = (
    "You are Mentra, a warm AI emotional support companion. "
    "Rewrite this notification copy to be more personalized and warm, "
    "based on the user's last session emotion being '{emotion}'. "
    "Keep it vague, lock-screen safe, short (under 100 characters), and optional in tone. "
    "Do not include exact values, names, or sensitive details. "
    "Do not diagnose. Do not use clinical language. "
    "Do not say 'we noticed' or 'your records'. "
    "Original copy: '{copy}'"
)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def build_memory_aware_prompt(base_prompt: str, memories_context: str) -> str:
    """
    Inject retrieved memory context into the system prompt.
    The memory context is a compact summary of relevant past session memories.
    The LLM is instructed to use this context naturally, not mechanically.
    """
    return (
        f"{base_prompt}\n\n"
        f"--- Past Session Context ---\n"
        f"The following relevant memories from previous sessions may help you respond warmly and naturally. "
        f"Reference them only if the user asks about them or if doing so feels genuinely helpful. "
        f"Do not list them mechanically. Do not say 'according to your records.'\n\n"
        f"{memories_context}\n"
        f"--- End Context ---"
    )


def format_memories_for_prompt(memories: list) -> str:
    """
    Format a list of retrieved memory objects into a compact context string.
    """
    if not memories:
        return ""

    lines = []
    for i, m in enumerate(memories[:5], 1):
        mem_type = m.get("memory_type", "memory")
        summary = m.get("summary", "")
        exact = m.get("exact_value")

        if exact:
            lines.append(f"{i}. [{mem_type}] \"{exact}\" — {summary[:100]}")
        else:
            lines.append(f"{i}. [{mem_type}] {summary[:120]}")

    return "\n".join(lines)


def build_direct_answer_prompt(base_prompt: str, selected_memory: dict) -> str:
    """
    Build a system prompt for DIRECT memory questions.
    The user is explicitly asking about a past memory.
    The LLM must answer using the exact value, not claim ignorance.
    """
    if not selected_memory:
        return base_prompt

    mem_type = selected_memory.get("memory_type", "memory")
    exact_value = selected_memory.get("exact_value")
    summary = selected_memory.get("summary", "")

    # Build memory context
    memory_context = ""
    if exact_value:
        memory_context = (
            f"Relevant memory (Type: {mem_type}):\n"
            f'Exact value: "{exact_value}"\n'
            f"Summary: {summary[:200]}\n"
        )
    else:
        memory_context = (
            f"Relevant memory (Type: {mem_type}):\n"
            f"Summary: {summary[:200]}\n"
        )

    instructions = (
        "The user is directly asking about a past memory from previous sessions. "
        "Answer using the memory context provided above. "
        "Be warm, brief, and direct. "
        "Do NOT say you don't have access to past conversations. "
        "Do NOT say 'I don't have a record' or 'I cannot recall'. "
        "Do NOT mention databases, retrieval, records, or internal memory systems. "
        "Simply answer what the user asked, using the exact value if available."
    )

    return (
        f"{base_prompt}\n\n"
        f"--- Memory Context Available ---\n"
        f"{memory_context}"
        f"---\n\n"
        f"--- Response Instruction ---\n"
        f"{instructions}\n"
        f"---"
    )


def build_no_memory_fallback_prompt(
    base_prompt: str,
    user_message: str,
    detected_emotion: dict,
) -> str:
    """
    Build a system prompt for when NO memory was judged clearly relevant.
    The assistant must NOT invent or guess a past memory.
    """
    emotion = detected_emotion.get("primary", "neutral") if detected_emotion else "neutral"
    intensity = detected_emotion.get("intensity", 0.5) if detected_emotion else 0.5

    instructions = (
        "No past memory was judged clearly relevant to the user's current message. "
        "Do NOT invent, guess, or simulate a past memory. "
        "Do NOT say 'we discussed this before' or 'I remember that' unless a memory was actually provided. "
        "Validate the user's current message and ask a gentle clarifying question. "
        "If the user seems to expect recall, gently say you don't want to guess from the wrong memory."
    )

    parts = [
        base_prompt,
        "\n--- Memory Status ---\nNo relevant past memory was found for this message.",
        "\n--- Response Instructions ---\n" + instructions,
        f"\n--- Current User State ---\nThe user is expressing {emotion} (intensity: {intensity}).\n--- End Instructions ---",
    ]

    return "\n".join(parts)


def extract_forbidden_topics_from_rejected_memories(
    rejected_memories: list,
    approved_memories: list,
    current_user_message: str,
) -> list:
    """
    Extract topic tags/themes from rejected memories to prevent leakage.
    Do not mark a topic as forbidden if it appears in approved memories or the user message.
    """
    approved_topics = set()
    for m in approved_memories:
        approved_topics.update(t.lower() for t in m.get("topic_tags", []))
        theme = (m.get("theme") or "").lower()
        if theme:
            approved_topics.add(theme)
        summary = (m.get("summary") or "").lower()
        if summary:
            approved_topics.update(w for w in summary.split() if len(w) > 3)

    user_lower = current_user_message.lower()

    forbidden = set()
    for m in rejected_memories:
        for tag in m.get("topic_tags", []):
            tag_lower = tag.lower()
            if tag_lower not in approved_topics and tag_lower not in user_lower:
                forbidden.add(tag)
        theme = (m.get("theme") or "").lower()
        if theme and theme not in approved_topics and theme not in user_lower:
            forbidden.add(theme)
        # Add keywords from summary
        summary = (m.get("summary") or "").lower()
        for kw in ["performance review", "manager", "calm bullet points", "bedtime panic", "quiet exit", "grounding anchor"]:
            if kw in summary and kw not in user_lower:
                # Only forbid if not in approved
                in_approved = any(kw in (a.get("summary") or "").lower() for a in approved_memories)
                if not in_approved:
                    forbidden.add(kw)

    return sorted(forbidden)


def build_current_turn_control_block(
    current_user_message: str,
    detected_emotion: dict,
    query_understanding: dict,
    relevance_judge_result: dict,
    approved_memories: list,
    policy_decision: dict,
    all_retrieved_memories: list = None,
    active_memory: dict = None,
) -> str:
    """
    Build the current turn control block that sits close to the user message.
    This is the primary anti-dilution mechanism: memory/policy instructions placed
    near the current turn so the LLM cannot ignore them.
    """
    lines = []

    # A. Intent and user state
    lines.append("CURRENT TURN CONTROL BLOCK — FOLLOW THESE INSTRUCTIONS FOR THE NEXT RESPONSE")
    lines.append("")
    lines.append("=== A. User State ===")
    emotion = detected_emotion.get("primary", "neutral") if detected_emotion else "neutral"
    intent = detected_emotion.get("intent", "general_chat") if detected_emotion else "general_chat"
    intensity = detected_emotion.get("intensity", 0.5) if detected_emotion else 0.5
    lines.append(f"Detected emotion: {emotion} (intensity: {intensity})")
    lines.append(f"Detected intent: {intent}")

    if query_understanding:
        lines.append(f"Query intent: {query_understanding.get('query_intent', 'general_chat')}")
        lines.append(f"Memory need: {query_understanding.get('memory_need', 'none')}")

    lines.append("")

    # NEW: Conversation Continuity
    if active_memory:
        lines.append("=== B. Conversation Continuity ===")
        lines.append("The previous response was about this memory:")
        mem_id = active_memory.get("memory_id", "unknown")
        theme = active_memory.get("theme", "")
        summary = active_memory.get("summary", "")
        exact = active_memory.get("exact_value")
        mem_type = active_memory.get("memory_type", "")
        session_id = active_memory.get("source_session_id", "")
        
        lines.append(f"  [{mem_id}] Session: {session_id} | Theme: {theme} | Type: {mem_type}")
        if exact:
            lines.append(f'  Exact value: "{exact}"')
        lines.append(f"  Summary: {summary[:150]}")
        lines.append("")
        lines.append("INSTRUCTION:")
        lines.append("- If the user's current message is a follow-up about this topic, continue using this memory.")
        lines.append("- If the user is asking about a DIFFERENT topic, use the approved memory from Section C instead.")
        lines.append("- You may also reference the additional context in Section D if relevant.")
        lines.append("- Be natural. Do not say 'according to the active memory' or similar meta-language.")
        lines.append("")

    # C. Memory candidates (ALL retrieved memories, let LLM decide)
    lines.append("=== C. Retrieved Memory Candidates ===")
    if all_retrieved_memories:
        lines.append("The following memories were retrieved for this query. Use the MOST RELEVANT one.")
        lines.append("If the user's message is a follow-up to the previous topic (Section B), prefer those memories.")
        lines.append("If the user switched topics, use a memory from a different session.")
        lines.append("")
        
        for m in all_retrieved_memories[:8]:
            mem_id = m.get("memory_id", "unknown")
            mem_type = m.get("memory_type", "unknown")
            theme = m.get("theme", "")
            summary = m.get("summary", "")
            exact = m.get("exact_value")
            session_id = ""
            parts = mem_id.split("_")
            if len(parts) >= 3 and parts[0] == "mem":
                session_id = f"{parts[1]}_{parts[2]}"
            
            lines.append(f"  [{mem_id}] Session: {session_id} | Type: {mem_type} | Theme: {theme}")
            if exact:
                lines.append(f'    Exact: "{exact}"')
            lines.append(f"    Summary: {summary[:120]}")
            lines.append("")

        lines.append("INSTRUCTION: Pick the single most relevant memory and answer using it.")
        lines.append("Do NOT mention memory IDs or session IDs in your response.")
        lines.append("Be natural and conversational.")
    else:
        lines.append("No memories retrieved for this query.")
        lines.append("INSTRUCTION: Do NOT invent past events. Ask a gentle clarifying question.")

    # B2. Additional context from all retrieved memories (for LLM to use naturally)
    if all_retrieved_memories:
        lines.append("")
        lines.append("=== B2. Additional Recent Session Context ===")
        lines.append("The following memories were retrieved but not formally approved by the judge.")
        lines.append("You may use them as conversational context if they help answer the user's question naturally.")
        lines.append("Do not list them mechanically. Only reference them if directly relevant.")
        lines.append("")
        for m in all_retrieved_memories[:6]:
            if m.get("memory_id") in {am.get("memory_id") for am in approved_memories}:
                continue  # Skip already-approved memories
            mem_id = m.get("memory_id", "unknown")
            summary = m.get("summary", "")
            exact = m.get("exact_value")
            theme = m.get("theme", "")
            if exact:
                lines.append(f"  [{mem_id}] ({theme}): \"{exact}\" — {summary[:80]}")
            else:
                lines.append(f"  [{mem_id}] ({theme}): {summary[:120]}")

    lines.append("")

    # C. Response policy
    lines.append("=== C. Response Policy ===")
    if policy_decision:
        mode = policy_decision.get("response_mode", "validate_only")
        mention = policy_decision.get("mention_memory", False)
        ask_q = policy_decision.get("ask_direct_question", False)
        tone = policy_decision.get("tone", "warm, calm, gently curious")
        lines.append(f"Response mode: {mode}")
        lines.append(f"Mention memory: {mention}")
        lines.append(f"Ask direct question: {ask_q}")
        lines.append(f"Tone: {tone}")

        avoid = policy_decision.get("avoid", [])
        if avoid:
            lines.append(f"Avoid: {' '.join(avoid)}")

    lines.append("")

    # D. Forbidden topics
    lines.append("=== D. Forbidden Topics ===")
    if relevance_judge_result:
        rejected = relevance_judge_result.get("rejected_memories", [])
        if rejected:
            forbidden = extract_forbidden_topics_from_rejected_memories(
                rejected,
                approved_memories,
                current_user_message,
            )
            if forbidden:
                lines.append("Do NOT mention these topics unless the user explicitly asks:")
                for f in forbidden:
                    lines.append(f"  - {f}")
            else:
                lines.append("(None)")
        else:
            lines.append("(None)")
    else:
        lines.append("(None)")

    lines.append("")

    # E. Response instructions
    lines.append("=== E. Response Instructions ===")
    lines.append("1. Pick the single most relevant memory from Section C.")
    lines.append("2. Answer the user's message using that memory.")
    lines.append("3. Do NOT mention memory IDs or session IDs in your response.")
    lines.append("4. Do NOT say 'according to your records', 'retrieved memory', 'database', or 'stored memory'.")
    lines.append("5. Do NOT diagnose.")
    lines.append("6. Ask at most one gentle follow-up question.")
    lines.append("7. Keep responses short, warm, and conversational.")
    lines.append("")
    lines.append("=== F. IMPORTANT: Memory Tracking JSON ===")
    lines.append("After your response, you MUST include a JSON block on its own line:")
    lines.append("")
    lines.append("```json")
    lines.append('{')
    lines.append('  "memory_id": "the_memory_id_you_used_or_null",')
    lines.append('  "reason": "brief reason why you picked this memory or skipped"')
    lines.append('}')
    lines.append("```")
    lines.append("")
    lines.append("Example 1: If you used mem_sess_002_km_0:")
    lines.append('  {"memory_id":"mem_sess_002_km_0","reason":"User asked about 2am thoughts"}')
    lines.append("")
    lines.append("Example 2: If no memory was relevant:")
    lines.append('  {"memory_id":null,"reason":"User switched to a new topic not in memories"}')
    lines.append("")
    lines.append("This JSON is required and will be stripped from the final user-facing message.")

    return "\n".join(lines)


def build_turn_local_messages(
    base_system_prompt: str,
    recent_history: list,
    current_user_message: str,
    detected_emotion: dict,
    query_understanding: dict,
    relevance_judge_result: dict,
    approved_memories: list,
    policy_decision: dict,
    max_history_messages: int = 6,
    all_retrieved_memories: list = None,
    active_memory: dict = None,
) -> list:
    """
    Build the final LLM message list with turn-local memory injection.

    Order:
    1. System: short base Mentra prompt
    2. Recent history: last N messages only
    3. Current turn control block: approved memory + policy + forbidden topics
    4. User message
    """
    messages = []

    # 1. Short base system prompt
    messages.append({
        "role": "system",
        "content": base_system_prompt,
    })

    # 2. Recent history (rolling window)
    if recent_history:
        # Ensure we only take the last N messages
        history_window = recent_history[-max_history_messages:]
        messages.extend(history_window)

    # 3. Current turn control block
    control_block = build_current_turn_control_block(
        current_user_message=current_user_message,
        detected_emotion=detected_emotion,
        query_understanding=query_understanding,
        relevance_judge_result=relevance_judge_result,
        approved_memories=approved_memories,
        policy_decision=policy_decision,
        all_retrieved_memories=all_retrieved_memories,
        active_memory=active_memory,
    )
    # Use user role with clear label for Ollama/local models that may ignore late system messages
    messages.append({
        "role": "user",
        "content": control_block,
    })

    # 4. Current user message
    messages.append({
        "role": "user",
        "content": f"USER MESSAGE:\n{current_user_message}",
    })

    return messages


def build_policy_injected_prompt(
    base_prompt: str,
    user_message: str,
    detected_emotion: dict,
    policy_decision: dict,
    selected_memory: dict = None,
) -> str:
    """
    Build a system prompt for the LLM based on the response policy decision.

    The policy controls HOW MUCH memory context to inject:
    - none: no memory context
    - vague: hint that something relevant exists, do not be specific
    - topic_only: mention the topic name
    - exact_value: include the exact memory value
    """
    if not policy_decision or not selected_memory:
        return base_prompt

    detail_level = policy_decision.get("allowed_memory_detail_level", "none")
    mention_memory = policy_decision.get("mention_memory", False)
    topic = policy_decision.get("selected_topic", "something from before")
    tone = policy_decision.get("tone", "warm, calm, gently curious")
    exact_value = selected_memory.get("exact_value") if selected_memory else None
    emotion = detected_emotion.get("primary", "neutral")
    intensity = detected_emotion.get("intensity", 0.5)
    mem_type = selected_memory.get("memory_type", "") if selected_memory else ""

    # Build the memory context string based on detail level.
    # If mention_memory is false, treat the response as a strict no-memory-reference
    # path even if a selected_memory exists internally for orchestration.
    memory_context = ""
    if not mention_memory or detail_level == "none":
        memory_context = ""
    elif detail_level == "exact_value" and exact_value:
        if mem_type == "grounding_phrase":
            memory_context = (
                f"The user previously found a grounding phrase that felt calming: "
                f'"{exact_value}". If the user seems activated, you may gently offer it.'
            )
        else:
            memory_context = (
                f'The user previously mentioned this: "{exact_value}". '
                f"It relates to {topic}. You may reference it gently if relevant."
            )

    elif detail_level == "topic_only":
        memory_context = (
            f"The user previously discussed {topic}. "
            f"You may gently ask if today's feeling is connected, but do not assume."
        )

    elif detail_level == "summary_level":
        # For episode recall: inject full source_text/summary so LLM can answer
        # "what did we explore" from the memory content
        source_text = selected_memory.get("source_text", "") if selected_memory else ""
        mem_summary = selected_memory.get("summary", "") if selected_memory else ""
        if source_text and source_text != mem_summary:
            memory_context = (
                f"Relevant past session context:\n"
                f"{source_text}\n"
            )
        elif mem_summary:
            memory_context = (
                f"Relevant past session context:\n"
                f"{mem_summary}\n"
            )
        else:
            memory_context = (
                f"The user previously discussed {topic}. "
                f"You may ask if today's feeling is connected."
            )
        memory_context += (
            "\nUse this context to answer the user's question directly and naturally. "
            "Summarize what was explored or discussed. "
            "Do not mention unrelated topics. "
            "Do not expose exact canonical values the user did not ask for. "
            "If the context does not fully answer the question, say so gently."
        )

    elif detail_level == "vague":
        memory_context = (
            f"The user has some emotionally relevant history. "
            f"Do NOT mention specific topics, events, or past conversations by name. "
            f"Do NOT say things like 'we talked about X before' or 'when we discussed Y'. "
            f"Only acknowledge that something relevant may exist if the user explicitly asks. "
            f"Stay with what they are feeling right now first."
        )

    # Build instruction based on response mode
    mode = policy_decision.get("response_mode", "validate_only")
    instructions = []

    if not mention_memory or detail_level == "none":
        instructions.append(
            "Respond only to the current message. Do NOT mention, imply, hint at, or allude to past conversations, "
            "previous themes, earlier sessions, recurring patterns, or anything that sounds like continuity or memory. "
            "Stay fully present-focused."
        )
        instructions.append(
            "Do not say things like 'we've talked about this before', 'something similar came up before', "
            "'in past conversations', or any equivalent continuity language."
        )

    elif mode == "ground_first_then_offer_memory":
        instructions.append(
            "The user is overwhelmed. FIRST validate their feeling and help them slow down. "
            "ONLY AFTER grounding, gently and optionally mention the relevant memory if it feels useful."
        )
    elif mode == "validate_then_offer_choice":
        instructions.append(
            "Validate their emotion first. Then gently mention that something relevant came up before, "
            "but give the user a choice whether to explore it or stay with the present feeling."
        )
    elif mode == "validate_then_gentle_optional_reference":
        instructions.append(
            "Validate their emotion first. If you mention a past topic, be vague and explicitly say "
            "you are not assuming it is connected to today. Stay gentle and optional."
        )
    elif mode == "direct_follow_up":
        instructions.append(
            "Validate their emotion first. Then gently ask if today might be connected to the past topic."
        )
    elif mode == "offer_grounding":
        instructions.append(
            "The user asked about a grounding phrase. Gently offer it if it still feels helpful."
        )
    elif mode == "gentle_follow_up":
        instructions.append(
            "The user asked about a specific past topic. Gently reference it and ask how they feel about it now."
        )
    elif mode == "soft_optional_reference":
        instructions.append(
            "The user asked about a specific past topic. Answer directly but keep it warm and optional."
        )
    else:
        instructions.append(
            "Validate their emotion. Do not proactively bring up past memories unless explicitly asked."
        )

    # Add avoid list
    avoid = policy_decision.get("avoid", [])
    if avoid:
        instructions.append("IMPORTANT: " + " ".join(avoid))

    # Add memory relevance guard instruction
    instructions.append(
        "CRITICAL: Only use the provided memory context if it clearly matches what the user is asking about. "
        "If the memory is only emotionally similar but topically unrelated, ignore it completely. "
        "Never introduce unrelated topics such as performance reviews, work, managers, sleep, bedtime, "
        "family, or grounding phrases unless the user explicitly mentioned them or the memory is directly relevant."
    )

    # Combine into full prompt
    parts = [base_prompt]

    if memory_context:
        parts.append("\n--- Relevant Past Context ---\n" + memory_context)

    if instructions:
        parts.append("\n--- Response Instructions ---\n" + "\n".join(instructions))

    parts.append(f"\n--- Current User State ---\nThe user is expressing {emotion} (intensity: {intensity}). Adopt a {tone} tone.\n--- End Instructions ---")

    return "\n".join(parts)