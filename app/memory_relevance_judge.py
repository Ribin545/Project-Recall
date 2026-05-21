"""
Project Recall — LLM Memory Relevance Judge

The vector DB retrieves plausible candidate memories, but does not
make the final decision. The LLM relevance judge reads the top
candidate memories and chooses the one that best matches the user's
current message. It can also reject all memories.

Architecture:
  User message
    ↓
  Emotion + intent detection
    ↓
  Topic hint extraction
    ↓
  Vector DB retrieves top 12 candidate memories
    ↓
  Safety filtering (sensitivity, distractors)
    ↓
  LLM Memory Relevance Judge chooses best / supporting / none
    ↓
  Response Policy YAML controls detail level
    ↓
  Final LLM response generation

Direct memory questions bypass the judge and use canonical direct lookup.
"""
import json
import os
import re
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm_client
from app.current_topic_extractor import extract_current_topic_hints

# ---------------------------------------------------------------------------
# 1. Candidate formatting for judge prompt
# ---------------------------------------------------------------------------

def format_candidate_memories_for_judge(candidate_memories: List[dict]) -> str:
    """
    Format candidate memories into a compact, readable list for the LLM judge.

    Args:
        candidate_memories: List of memory dicts (already safety-filtered).

    Returns:
        A formatted string with numbered candidate memories.
    """
    lines = []
    for i, mem in enumerate(candidate_memories, 1):
        mem_id = mem.get("memory_id", "unknown")
        mem_type = mem.get("memory_type", "unknown")
        source_kind = mem.get("memory_source_kind", "key_moment")
        theme = mem.get("theme", "")
        source_text = mem.get("source_text", "")
        summary = mem.get("summary", "")
        topic_tags = mem.get("topic_tags", [])
        emotion = mem.get("emotion", {})
        resolved_status = mem.get("resolved_status", "unknown")
        follow_up = mem.get("follow_up_topics", [])
        sensitivity = mem.get("sensitivity", 0.0)
        is_canonical = mem.get("is_canonical", False)
        user_explicit = mem.get("user_explicitly_asked_to_remember", False)
        exact_value = mem.get("exact_value")

        source_session = mem.get("source_session_id", "")
        lines.append(f"[{i}] memory_id: {mem_id}")
        if source_session:
            lines.append(f"    source_session: {source_session}")
        lines.append(f"    type: {mem_type} | source_kind: {source_kind}")
        if theme:
            lines.append(f"    theme: {theme}")
        if source_text:
            lines.append(f"    source_text: {source_text}")
        if summary:
            lines.append(f"    summary: {summary}")
        if topic_tags:
            lines.append(f"    topic_tags: {', '.join(topic_tags)}")
        if emotion:
            emo_parts = []
            if emotion.get("primary"):
                emo_parts.append(f"primary={emotion['primary']}")
            if emotion.get("secondary"):
                emo_parts.append(f"secondary={', '.join(emotion['secondary'])}")
            if emo_parts:
                lines.append(f"    emotion: {' | '.join(emo_parts)}")
        if resolved_status:
            lines.append(f"    resolved_status: {resolved_status}")
        if follow_up:
            lines.append(f"    follow_up_topics: {', '.join(follow_up)}")
        lines.append(f"    sensitivity: {sensitivity}")
        lines.append(f"    canonical: {is_canonical} | user_asked_remember: {user_explicit}")
        if exact_value:
            # Include the actual exact value so judge can disambiguate
            # This is critical for follow-up questions like "what was my grounding phrase?"
            lines.append(f'    exact_value: "{exact_value}"')
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Judge prompt builder
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """You are a Memory Relevance Judge for a mental-health support assistant.

Your task:
Given a user's current message and a list of candidate memories, decide which memory, if any, is actually relevant.

You are NOT writing the final assistant response.
You are only selecting memory context.

Selection rules:
1. Specific topic match beats broad emotional similarity.
2. Do not choose a memory just because the emotion matches.
3. If the user asks "what did we explore/discuss/talk about", choose a memory that contains what was explored/discussed/talked about.
4. If the user mentions a specific event like "family dinner", "bedtime panic", "manager conversation", or "friendship repair", choose only memories that explicitly match that event or clearly equivalent wording.
5. If no memory clearly matches, return use_memory=false.
6. Do not choose high-sensitivity memories (sensitivity >= 0.7).
7. Do not choose distractors.
8. Do not expose exact values unless the user directly asks for exact recall.
9. If multiple memories are complementary and safe, choose one primary and at most two supporting memories.
10. If the selected memory is only broadly related, set relevance=medium or low.
11. If the memory is topically unrelated, reject it even if emotion matches.
12. If the user asks "how did we manage" or "what strategy did we use" or "what was the plan", prefer memories that describe the actual strategy, action, steps, or plan over memories that only mention commitment or intention without the actual method.
13. For broad recall questions ("what did we explore/discuss/talk about", "what happened during", "do you remember when"), prefer session_summary cards if they directly answer the question. Key moment cards may support the summary. Do not choose a nearby key moment if a summary card directly answers the question.
14. CRITICAL — Ambiguity rule: If the user's message is vague or broad (e.g., "that time when...", "do you remember when...", "that thing we talked about") AND two or more candidate memories could both plausibly match, you MUST return use_memory=false. Do NOT guess.
15. CRITICAL — Follow-up disambiguation: If the user is asking a follow-up question like "what was my grounding phrase?" or "what was that sentence?" AND there is a "Recently discussed sessions" section, you MUST prefer the memory from the most recently discussed session that matches the question type. This is not ambiguous — the conversation context makes it clear which memory the user means.

Output JSON only. No markdown, no code fences, no extra text."""


def _build_judge_prompt(
    user_message: str,
    detected_emotion: Dict,
    topic_hints: Dict,
    candidate_memories: List[Dict],
    policy_config: Dict,
    conversation_context: Optional[Dict] = None,
) -> str:
    """Build the full judge prompt."""
    emotion_str = json.dumps(detected_emotion, indent=2)
    topic_str = json.dumps(topic_hints, indent=2)
    candidates_str = format_candidate_memories_for_judge(candidate_memories)

    # Build conversation context section
    context_section = ""
    if conversation_context:
        recent_sessions = conversation_context.get("recent_sessions", [])
        recent_themes = conversation_context.get("recent_themes", [])
        if recent_sessions or recent_themes:
            context_section = "\nRecently discussed sessions:\n"
            for i, (sess, theme) in enumerate(zip(recent_sessions, recent_themes)):
                context_section += f"  {i+1}. Session: {sess} (Theme: {theme})\n"
            context_section += "\nWhen the user's message is ambiguous, prefer memories from recently discussed sessions.\n"

    prompt = f"""User message:
{user_message}

Detected emotion:
{emotion_str}

Topic hints:
{topic_str}{context_section}

Candidate memories:
{candidates_str}

Required JSON output:
{{
  "use_memory": true or false,
  "selected_memory_id": "memory_id string or null",
  "selected_memory_ids": ["memory_id_1", ...],
  "supporting_memory_ids": ["memory_id_2", ...],
  "relevance": "high" | "medium" | "low" | "none",
  "confidence": 0.0 to 1.0,
  "detail_level_recommendation": "none" | "vague" | "topic_only" | "summary_level" | "exact_value",
  "answer_basis": "short explanation of what should be answered from memory",
  "reason": "why selected memory matches user message",
  "rejected_memories": [
    {{
      "memory_id": "memory_id",
      "reason": "why rejected"
    }}
  ]
}}

Examples:

Example 1:
User: "During that family dinner what did we explore?"
Candidate A: source_text mentions family dinner, communication styles, "I feel... when... because..." practice.
Candidate B: source_text mentions quiet exit plan for family conversations.
Correct: Choose A. Reject B because it is family-related but not specifically about the family dinner exploration.

Example 2:
User: "Do you remember panic before bedtime? I was anxious."
Candidate A: source_text mentions panic before bedtime and no-phone wind-down.
Candidate B: source_text mentions anxiety about performance review.
Correct: Choose A. Reject B because it is anxiety-related but topically about performance review, not bedtime.

Example 3:
User: "I feel anxious but I don't know why."
Candidates are all specific and unrelated.
Correct: Either choose a broad unresolved anxiety memory with medium relevance or return use_memory=false. Do not force unrelated specific memories.

Example 4:
User: "How did we manage emotional regulation before important events?"
Candidate A: source_text mentions "committed to try the preparation plan" — a commitment, but does not describe the actual preparation plan.
Candidate B: source_text mentions "walk for ten minutes, then write three calm bullet points before the review" — the actual strategy and steps.
Correct: Choose B as primary. Reject A because the user asks HOW it was managed, so the actual strategy/steps memory is more relevant than a commitment-only memory.

Example 5:
User: "During that family dinner what did we explore?"
Candidate A: type=session_summary, source_kind=summary, contains "User described tension that escalated during a family dinner. They felt unheard and withdrew. We explored communication styles and practiced 'I feel... when... because...' language. They committed to one gentle conversation before the next gathering."
Candidate B: type=relationship_context, source_kind=key_moment, source_text="User felt unheard and withdrew during the family dinner."
Candidate C: type=coping_strategy, source_kind=key_moment, source_text="User explored a quiet exit plan when family conversations become too intense."
Correct: Choose A as primary (summary directly answers "what did we explore"). Choose B as supporting (confirms the feeling of being unheard). Reject C because quiet exit is family-related but not specifically about the family dinner exploration.

Example 6:
User: "Do you remember what that sentence was?"
Recently discussed sessions:
  1. Session: sess_004 (Theme: friendship conflict)
  2. Session: sess_011 (Theme: sleep hygiene)
Candidate A: memory_id=mem_sleep_001, source_session=sess_011, type=grounding_phrase, exact_value="Quiet room, soft blanket, slow breath."
Candidate B: memory_id=mem_friend_001, source_session=sess_004, type=communication_script, exact_value="I felt hurt, but I want to understand what happened."
Candidate C: memory_id=mem_review_001, source_session=sess_007, type=communication_script, exact_value="I'd like to understand how I can grow from here."
Correct: Choose B as primary. The user just discussed sess_004 (friendship conflict) and asked "what was that sentence" — they mean the sentence from the friendship conversation. Reject A because it's from a different session (sleep). Reject C because it's from an even older session (review).

Your JSON:"""

    return prompt


# ---------------------------------------------------------------------------
# 3. JSON response parser with repair
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[dict]:
    """
    Extract a JSON object from text that may contain markdown fences,
    extra prose, or other content.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    fence_pattern = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL)
    for match in fence_pattern.finditer(text):
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding the first JSON object {...}
    obj_pattern = re.compile(r'\{.*\}', re.DOTALL)
    for match in obj_pattern.finditer(text):
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _parse_judge_response(raw: str) -> Optional[Dict]:
    """
    Parse the LLM judge's raw text output into a structured dict.

    Returns:
        Parsed dict with validated fields, or None if parsing fails.
    """
    parsed = _extract_json(raw)
    if not parsed or not isinstance(parsed, dict):
        return None

    # Ensure required fields exist with sensible defaults
    result = {
        "use_memory": bool(parsed.get("use_memory", False)),
        "selected_memory_id": parsed.get("selected_memory_id") or None,
        "selected_memory_ids": list(parsed.get("selected_memory_ids", [])),
        "supporting_memory_ids": list(parsed.get("supporting_memory_ids", [])),
        "relevance": str(parsed.get("relevance", "none")).lower(),
        "confidence": float(parsed.get("confidence", 0.5)),
        "detail_level_recommendation": str(parsed.get("detail_level_recommendation", "none")).lower(),
        "answer_basis": str(parsed.get("answer_basis", "")),
        "reason": str(parsed.get("reason", "")),
        "rejected_memories": [],
        "judge_status": "success",
        "fallback_used": False,
        "raw_model_output": raw[:1000],
    }

    # Parse rejected memories
    raw_rejected = parsed.get("rejected_memories", [])
    if isinstance(raw_rejected, list):
        for item in raw_rejected:
            if isinstance(item, dict):
                result["rejected_memories"].append({
                    "memory_id": str(item.get("memory_id", "unknown")),
                    "reason": str(item.get("reason", "rejected")),
                })

    # Validate relevance
    if result["relevance"] not in ("high", "medium", "low", "none"):
        result["relevance"] = "none"

    # Validate detail level
    if result["detail_level_recommendation"] not in ("none", "vague", "topic_only", "summary_level", "exact_value"):
        result["detail_level_recommendation"] = "none"

    # Validate confidence
    if result["confidence"] < 0 or result["confidence"] > 1:
        result["confidence"] = 0.5

    # If selected_memory_id exists but not in selected_memory_ids, add it
    if result["selected_memory_id"] and result["selected_memory_id"] not in result["selected_memory_ids"]:
        result["selected_memory_ids"].insert(0, result["selected_memory_id"])

    # If no selected_memory_ids but use_memory is true, downgrade
    if not result["selected_memory_ids"] and result["use_memory"]:
        result["use_memory"] = False
        result["relevance"] = "none"

    return result


# ---------------------------------------------------------------------------
# 4. Deterministic fallback
# ---------------------------------------------------------------------------

def _compute_topic_overlap_score(
    topic_hints: Dict,
    memory: Dict,
) -> float:
    """Compute topic overlap between user topic hints and memory tags."""
    user_topic = topic_hints.get("topic_family", "unknown")
    mem_tags = [t.lower() for t in memory.get("topic_tags", [])]
    mem_type = memory.get("memory_type", "unknown")

    if user_topic == "unknown":
        return 0.0

    user_topic_lower = user_topic.lower()

    # Direct topic match in tags
    if user_topic_lower in mem_tags:
        return 1.0

    # Topic family mapping
    FAMILY_MAP = {
        "sleep": ["sleep", "bedtime", "insomnia", "night", "wind-down", "rest"],
        "anxiety": ["anxiety", "panic", "worry", "stress", "nervousness"],
        "work": ["work", "job", "career", "manager", "performance review", "colleague"],
        "relationship": ["relationship", "friend", "family", "partner", "conversation", "conflict"],
        "health": ["health", "exercise", "sleep", "routine", "self-care"],
        "self_improvement": ["goal", "plan", "progress", "growth", "commitment"],
    }

    user_family_keywords = FAMILY_MAP.get(user_topic_lower, [user_topic_lower])
    matching = sum(1 for kw in user_family_keywords if kw in mem_tags)
    return min(1.0, matching / max(len(user_family_keywords), 1))


def _deterministic_fallback(
    user_message: str,
    topic_hints: Dict,
    candidate_memories: List[Dict],
    detected_emotion: Dict,
) -> Dict:
    """
    Deterministic fallback when LLM judge is unavailable or returns invalid JSON.
    """
    user_topic = topic_hints.get("topic_family", "unknown")
    is_episode_recall = detected_emotion.get("intent") == "specific_episode_recall"
    strong_terms = set(t.lower() for t in topic_hints.get("strong_topic_terms", []))

    # Detect ambiguous/vague queries
    user_lower = user_message.lower()
    vague_phrases = ["that time when", "do you remember when", "that thing we talked about", "that time", "that thing", "that one time"]
    is_vague = any(vp in user_lower for vp in vague_phrases)

    best_memory = None
    best_score = -1.0
    rejected = []

    # Track top-scoring memories for ambiguity detection
    scored_memories = []

    for mem in candidate_memories:
        mem_id = mem.get("memory_id", "unknown")
        mem_type = mem.get("memory_type", "unknown")
        mem_tags = [t.lower() for t in mem.get("topic_tags", [])]
        summary = mem.get("summary", "").lower()
        source_text = (mem.get("source_text", "") or "").lower()

        # Skip high sensitivity and distractors
        if mem.get("sensitivity", 0) >= 0.7:
            rejected.append({"memory_id": mem_id, "reason": "High sensitivity"})
            continue
        if mem.get("is_distractor", False):
            rejected.append({"memory_id": mem_id, "reason": "Distractor"})
            continue

        score = 0.0
        is_mismatch = False

        # Topic overlap
        topic_score = _compute_topic_overlap_score(topic_hints, mem)
        score += topic_score * 0.35

        # Source text match
        if strong_terms:
            mem_text = " ".join(mem_tags) + " " + summary + " " + source_text
            for term in strong_terms:
                if term in mem_text:
                    score += 0.25
                    break

        # Semantic similarity from retrieval
        score += mem.get("semantic_similarity", 0.5) * 0.20

        # Emotion match
        mem_emotion = mem.get("emotion", {}).get("primary", "neutral")
        user_emotion = detected_emotion.get("primary", "neutral")
        if mem_emotion == user_emotion:
            score += 0.10

        # Key moment bonus
        if mem.get("memory_source_kind") == "key_moment":
            score += 0.10

        # Episode recall: require strong term match
        if is_episode_recall and strong_terms:
            has_strong_match = any(term in mem_text for term in strong_terms)
            if has_strong_match:
                score += 0.5
            else:
                score -= 0.4
                rejected.append({
                    "memory_id": mem_id,
                    "reason": f"Missing exact phrase match for episode recall: {strong_terms}",
                })

        if score > best_score:
            best_score = score
            best_memory = mem

        scored_memories.append({"memory": mem, "score": score})

    # Ambiguity check: if query is vague and multiple memories are close, reject
    if is_vague and len(scored_memories) >= 2:
        # Sort by score descending
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        top_score = scored_memories[0]["score"]
        second_score = scored_memories[1]["score"] if len(scored_memories) > 1 else 0.0
        # If second-best is within 70% of top score, consider ambiguous
        if second_score >= top_score * 0.7 and top_score >= 0.4:
            return {
                "use_memory": False,
                "selected_memory_id": None,
                "selected_memory_ids": [],
                "supporting_memory_ids": [],
                "relevance": "none",
                "confidence": 0.0,
                "detail_level_recommendation": "none",
                "answer_basis": "",
                "reason": f"Query is vague/ambiguous and multiple memories could match (top scores: {top_score:.2f}, {second_score:.2f}). Ask user to clarify.",
                "rejected_memories": [{"memory_id": m["memory"].get("memory_id"), "reason": "Ambiguous match — ask user to clarify"} for m in scored_memories],
                "raw_model_output": "[deterministic_fallback_ambiguity_detected]",
            }

    threshold = 0.5 if is_episode_recall else 0.3

    if best_memory and best_score >= threshold:
        return {
            "use_memory": True,
            "selected_memory_id": best_memory.get("memory_id"),
            "selected_memory_ids": [best_memory.get("memory_id")],
            "supporting_memory_ids": [],
            "relevance": "medium" if best_score < 0.7 else "high",
            "detail_level_recommendation": "topic_only",
            "answer_basis": "Topic-matched memory selected via deterministic fallback.",
            "reason": f"Topic overlap score={best_score:.2f}. Best matching memory selected via deterministic fallback.",
            "rejected_memories": rejected,
            "raw_model_output": "[deterministic_fallback]",
        }
    else:
        return {
            "use_memory": False,
            "selected_memory_id": None,
            "selected_memory_ids": [],
            "supporting_memory_ids": [],
            "relevance": "none",
            "detail_level_recommendation": "none",
            "answer_basis": "",
            "reason": f"No memory with sufficient topic overlap (best score={best_score:.2f}, threshold={threshold}).",
            "rejected_memories": rejected,
            "raw_model_output": "[deterministic_fallback]",
        }


# ---------------------------------------------------------------------------
# 5. Main judge function
# ---------------------------------------------------------------------------

def judge_memory_relevance(
    user_message: str,
    detected_emotion: Dict,
    topic_hints: Dict,
    candidate_memories: List[Dict],
    policy_config: Dict,
    provider: str = None,
    model: str = None,
    max_candidates: int = 8,
    conversation_context: Optional[Dict] = None,
) -> Dict:
    """
    Judge whether retrieved memories are relevant to the user's current message.

    Architecture:
    1. Safety-filter candidates (sensitivity, distractors).
    2. Call LLM judge with top max_candidates.
    3. Parse JSON response.
    4. If LLM fails or returns invalid JSON, fall back to deterministic scoring.
    5. Return structured result.

    Args:
        user_message: Raw user message.
        detected_emotion: Detected emotion/intent dict.
        topic_hints: Topic hints from extract_current_topic_hints.
        candidate_memories: Retrieved candidate memories.
        policy_config: Loaded response policy config.
        provider: LLM provider ("ollama" or "gemini"). If None, uses configured provider.
        model: Model name override.
        max_candidates: Max candidates to send to LLM judge.

    Returns:
        Dict with use_memory, selected_memory_id(s), relevance, detail_level, etc.
    """
    # 1. Safety filtering
    safe_memories = []
    pre_rejected = []
    for mem in candidate_memories:
        mem_id = mem.get("memory_id", "unknown")
        if mem.get("sensitivity", 0) >= 0.7:
            pre_rejected.append({
                "memory_id": mem_id,
                "reason": "High sensitivity memory blocked",
            })
            continue
        if mem.get("is_distractor", False):
            pre_rejected.append({
                "memory_id": mem_id,
                "reason": "Distractor memory blocked",
            })
            continue
        safe_memories.append(mem)

    if not safe_memories:
        return {
            "use_memory": False,
            "selected_memory_id": None,
            "selected_memory_ids": [],
            "supporting_memory_ids": [],
            "relevance": "none",
            "detail_level_recommendation": "none",
            "answer_basis": "",
            "reason": "No safe memories available (all high-sensitivity or distractors).",
            "rejected_memories": pre_rejected,
            "raw_model_output": "[safety_filter_blocked_all]",
        }

    # Limit to top max_candidates for LLM judge
    judge_candidates = safe_memories[:max_candidates]

    # 2. Try LLM judge
    llm_result = None
    if llm_client:
        try:
            prompt = _build_judge_prompt(
                user_message=user_message,
                detected_emotion=detected_emotion,
                topic_hints=topic_hints,
                candidate_memories=judge_candidates,
                policy_config=policy_config,
                conversation_context=conversation_context,
            )

            messages = [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            raw = llm_client.chat(messages, model=model)
            parsed = _parse_judge_response(raw)

            if parsed and isinstance(parsed, dict) and "use_memory" in parsed:
                # Merge pre-filtered rejections with LLM rejections
                parsed["rejected_memories"] = pre_rejected + parsed.get("rejected_memories", [])
                llm_result = parsed

        except Exception:
            # LLM judge failed — fall through to deterministic
            pass

    # 3. Use LLM result if valid
    if llm_result:
        return llm_result

    # 4. Deterministic fallback
    fallback = _deterministic_fallback(user_message, topic_hints, safe_memories, detected_emotion)
    fallback["rejected_memories"] = pre_rejected + fallback.get("rejected_memories", [])
    return fallback


# ---------------------------------------------------------------------------
# 6. Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Self-test with synthetic candidates
    test_candidates = [
        {
            "memory_id": "mem_family_dinner",
            "memory_type": "relationship_context",
            "memory_source_kind": "key_moment",
            "theme": "family boundaries",
            "source_text": "User described tension that escalated during a family dinner. They felt unheard and withdrew. We explored communication styles and practiced 'I feel... when... because...' language. They committed to one gentle conversation before the next gathering.",
            "summary": "Family dinner tension, communication practice, and gentle conversation plan.",
            "topic_tags": ["family dinner", "family gathering", "family tension", "communication styles", "gentle conversation"],
            "emotion": {"primary": "sadness", "secondary": ["hurt", "uncertainty", "hopefulness"]},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.45,
            "is_distractor": False,
            "is_canonical": False,
            "user_explicitly_asked_to_remember": False,
        },
        {
            "memory_id": "mem_quiet_exit",
            "memory_type": "coping_strategy",
            "memory_source_kind": "key_moment",
            "theme": "family boundaries",
            "source_text": "User explored a quiet exit plan when family conversations become too intense. They identified early warning signs in their body and practiced stepping away physically and mentally.",
            "summary": "Quiet exit strategy for intense family conversations.",
            "topic_tags": ["family boundaries", "quiet exit", "grounding anchor", "physically disengage", "mentally disengage"],
            "emotion": {"primary": "sadness", "secondary": ["overwhelm"]},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
            "is_canonical": False,
            "user_explicitly_asked_to_remember": False,
        },
        {
            "memory_id": "mem_performance_review",
            "memory_type": "coping_strategy",
            "memory_source_kind": "key_moment",
            "theme": "work stress",
            "source_text": "User planned to walk ten minutes and write calm bullet points before a performance review. They wanted to feel prepared rather than anxious.",
            "summary": "Pre-review preparation plan with walking and bullet points.",
            "topic_tags": ["performance review", "work stress", "calm bullet points", "preparation"],
            "emotion": {"primary": "anxiety", "secondary": ["uncertainty"]},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
            "is_canonical": False,
            "user_explicitly_asked_to_remember": False,
        },
    ]

    print("=" * 60)
    print("LLM MEMORY RELEVANCE JUDGE — Self Test")
    print("=" * 60)

    # Test A: Family dinner episode recall
    msg = "During that family dinner what did we explore? do you remember it?"
    detected = {"primary": "sadness", "intent": "specific_episode_recall", "intensity": 0.7}
    topic = extract_current_topic_hints(msg)

    result = judge_memory_relevance(
        user_message=msg,
        detected_emotion=detected,
        topic_hints=topic,
        candidate_memories=test_candidates,
        policy_config={},
        max_candidates=8,
    )

    print(f"\nTest A: '{msg}'")
    print(f"  use_memory: {result['use_memory']}")
    print(f"  selected: {result['selected_memory_id']}")
    print(f"  relevance: {result['relevance']}")
    print(f"  detail: {result['detail_level_recommendation']}")
    print(f"  reason: {result['reason']}")
    print(f"  rejected: {[r['memory_id'] for r in result['rejected_memories']]}")

    # Test B: Bedtime panic
    msg2 = "Do you remember panic before bedtime? I was anxious."
    detected2 = {"primary": "anxiety", "intent": "emotional_disclosure", "intensity": 0.8}
    topic2 = extract_current_topic_hints(msg2)

    # Add a bedtime memory
    bedtime_candidates = test_candidates + [{
        "memory_id": "mem_bedtime_panic",
        "memory_type": "coping_strategy",
        "memory_source_kind": "key_moment",
        "theme": "sleep anxiety",
        "source_text": "User discussed panic before bedtime and a no-phone wind-down routine. They committed to putting the phone away by 9:30 PM.",
        "summary": "Bedtime panic and no-phone wind-down routine.",
        "topic_tags": ["bedtime", "sleep", "panic", "no-phone", "wind-down"],
        "emotion": {"primary": "anxiety", "secondary": ["sadness"]},
        "resolved_status": "partially_resolved",
        "sensitivity": 0.3,
        "is_distractor": False,
    }]

    result2 = judge_memory_relevance(
        user_message=msg2,
        detected_emotion=detected2,
        topic_hints=topic2,
        candidate_memories=bedtime_candidates,
        policy_config={},
        max_candidates=8,
    )

    print(f"\nTest B: '{msg2}'")
    print(f"  use_memory: {result2['use_memory']}")
    print(f"  selected: {result2['selected_memory_id']}")
    print(f"  relevance: {result2['relevance']}")
    print(f"  reason: {result2['reason']}")
    print(f"  rejected: {[r['memory_id'] for r in result2['rejected_memories']]}")

    # Test C: Unrelated topic
    msg3 = "I feel anxious about moving to a new city."
    detected3 = {"primary": "anxiety", "intent": "emotional_disclosure", "intensity": 0.6}
    topic3 = extract_current_topic_hints(msg3)

    result3 = judge_memory_relevance(
        user_message=msg3,
        detected_emotion=detected3,
        topic_hints=topic3,
        candidate_memories=test_candidates,
        policy_config={},
        max_candidates=8,
    )

    print(f"\nTest C: '{msg3}'")
    print(f"  use_memory: {result3['use_memory']}")
    print(f"  selected: {result3['selected_memory_id']}")
    print(f"  relevance: {result3['relevance']}")
    print(f"  reason: {result3['reason']}")

    print(f"\n{'=' * 60}")