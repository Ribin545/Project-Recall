"""
Project Recall — Memory-Aware Session Opener

Uses emotional memory planner to generate warm, natural session-opening greetings.

This module runs a small multi-query retrieval pass to gather emotionally
relevant memories, then turns the resulting plan into a session opener.
"""
import os
import sys
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory_retriever import retrieve_memories
from app.emotional_memory_planner import (
    plan_memory_response,
    generate_opener_from_plan,
)


def generate_opener(user_id: str, user_message: Optional[str] = None) -> str:
    """
    Generate a warm, memory-aware session opening message.

    Steps:
    1. Retrieve memories with several broad continuity queries.
    2. Deduplicate the results.
    3. Pass them through the emotional planner.
    4. Turn the plan into a natural opener.

    Args:
        user_id: User to generate the opener for.
        user_message: Optional current message context.

    Returns:
        Opening message string.
    """
    # Query for unresolved themes, follow-ups, and emotional context
    queries = [
        "upcoming events unresolved follow up",
        "emotional state recent session",
        "coping strategy grounding technique",
    ]

    all_memories: List[Dict] = []
    for q in queries:
        results = retrieve_memories(
            user_id=user_id,
            query=q,
            top_k=3,
            only_safe_for_opener=True,
        )
        all_memories.extend(results)

    # Deduplicate by memory_id
    seen = set()
    unique_memories = []
    for m in all_memories:
        mid = m.get("memory_id")
        if mid and mid not in seen:
            seen.add(mid)
            unique_memories.append(m)

    # Plan the response
    plan = plan_memory_response(
        retrieved_memories=unique_memories,
        current_user_message=user_message,
        purpose="session_opener",
    )

    # Generate opener from plan
    return _generate_opener_from_plan(plan)


def _generate_opener_from_plan(plan: Dict) -> str:
    """
    Build a warm opener from the emotional plan.

    Args:
        plan: Emotional plan dict.

    Returns:
        Generated opener string.
    """
    strategy = plan.get("response_strategy", "supportive_reference")
    topic = plan.get("selected_topic", "something")
    exact_value = None
    safe = plan.get("safe_to_reference", False)

    # Get exact_value from primary if safe
    supporting = plan.get("supporting_memories", [])
    if supporting and safe:
        exact_value = supporting[0].get("exact_value")

    # Fallback if no usable plan
    if strategy == "do_not_use" or not safe:
        return "Hi, I'm glad you're here. What would you like to talk about today?"

    # Template-based generation
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

    if strategy == "only_if_user_mentions":
        return (
            f"Hi, I'm glad you're here. What would you like to talk about today?"
        )

    # Default
    return "Hi, I'm glad you're here. What would you like to talk about today?"


def generate_opener_with_plan(user_id: str = "demo_user") -> Dict:
    """
    Generate a memory-aware opener and return the full emotional plan.

    Useful for testing and debugging because it exposes both the final opener
    and the planner internals.

    Args:
        user_id: User to generate the opener for.

    Returns:
        Dict with opener text, plan, and retrieval count.
    """
    queries = [
        "upcoming events unresolved follow up",
        "emotional state recent session",
        "coping strategy grounding technique",
    ]

    all_memories: List[Dict] = []
    for q in queries:
        results = retrieve_memories(
            user_id=user_id,
            query=q,
            top_k=3,
            only_safe_for_opener=True,
        )
        all_memories.extend(results)

    # Deduplicate
    seen = set()
    unique_memories = []
    for m in all_memories:
        mid = m.get("memory_id")
        if mid and mid not in seen:
            seen.add(mid)
            unique_memories.append(m)

    plan = plan_memory_response(unique_memories, purpose="session_opener")
    opener = _generate_opener_from_plan(plan)

    return {
        "opener": opener,
        "plan": plan,
        "retrieved_count": len(unique_memories),
    }


def main():
    """
    Run a small CLI demo of the session opener pipeline.
    """
    print("=" * 60)
    print(" MEMORY-AWARE SESSION OPENER (with Emotional Planner)")
    print("=" * 60)

    result = generate_opener_with_plan("demo_user")

    print(f"\n--- Retrieved {result['retrieved_count']} unique memories ---")

    plan = result["plan"]
    print(f"\n--- Emotional Plan ---")
    print(f"  Selected memory: {plan['selected_memory_id']}")
    print(f"  Topic: {plan['selected_topic']}")
    print(f"  Strategy: {plan['response_strategy']}")
    print(f"  Tone: {plan['tone']}")
    print(f"  Safe: {plan['safe_to_reference']}")
    print(f"  Reason: {plan['reason_selected']}")

    if plan['supporting_memories']:
        print(f"\n  Supporting memories:")
        for sm in plan['supporting_memories']:
            print(f"    - {sm['memory_type']}: {sm.get('exact_value', 'N/A')[:50]}...")

    print(f"\n  Avoid:")
    for a in plan['avoid']:
        print(f"    - {a}")

    print(f"\n  Prompt guidance:")
    print(f"    {plan['prompt_guidance']}")

    print(f"\n--- Generated Opener ---")
    print(f"\"{result['opener']}\"")
    print(f"\nDone.")


if __name__ == "__main__":
    main()