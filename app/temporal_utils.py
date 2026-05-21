"""
Project Recall — Temporal Utilities

Lightweight temporal metadata support.
Does NOT implement full temporal reasoning yet.

Provides:
- Basic time reference parsing from user messages
- Recency scoring for memories
- Time phrase recognition
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Optional


# --- Time phrase patterns ---
TIME_PHRASES = {
    "last session": "last_session",
    "last time": "last_session",
    "recently": "recent",
    "last week": "last_week",
    "this week": "this_week",
    "before": "before",
    "after": "after",
    "yesterday": "yesterday",
    "today": "today",
    "last month": "last_month",
    "a few days ago": "recent",
    "earlier": "before",
    "previously": "before",
    "last conversation": "last_session",
}


def parse_time_reference(user_message: str) -> Optional[str]:
    """
    Parse basic time references from user messages.
    Returns a simple time descriptor or None.
    """
    text_lower = user_message.lower()

    for phrase, descriptor in TIME_PHRASES.items():
        if phrase in text_lower:
            return descriptor

    return None


def compute_recency_score(memory: Dict, now: datetime = None) -> float:
    """
    Compute a recency score for a memory (0.0 = very old, 1.0 = most recent).

    Simple implementation: memories from exact_user_request/key_moment get
    a slight boost over summary memories, but no true temporal ranking yet.
    """
    if not memory:
        return 0.0

    score = 0.0

    # Source kind preference (exact/key_moment > follow_up > summary)
    source_kind = memory.get("memory_source_kind", "")
    if source_kind == "exact_user_request":
        score += 0.3
    elif source_kind == "key_moment":
        score += 0.25
    elif source_kind == "follow_up_topic":
        score += 0.15
    elif source_kind == "summary":
        score += 0.1

    # Has timestamp
    timestamp = memory.get("source_timestamp", "")
    if timestamp:
        score += 0.05

    # Follow-up recommended = more relevant for continuity
    if memory.get("follow_up_recommended", False):
        score += 0.1

    # Unresolved status = may need follow-up
    if memory.get("resolved_status") in ("unresolved", "partially_resolved"):
        score += 0.05

    return min(1.0, score)


def time_reference_to_days(time_ref: str) -> Optional[int]:
    """
    Convert a time reference to approximate days.
    Returns None if unknown.
    """
    mapping = {
        "today": 0,
        "yesterday": 1,
        "recent": 3,
        "this_week": 3,
        "last_week": 7,
        "last_month": 30,
        "last_session": None,  # special: needs context
        "before": None,
        "after": None,
    }
    return mapping.get(time_ref)


def should_boost_by_time(memory: Dict, time_ref: str, now: datetime = None) -> float:
    """
    Return a boost score if memory should be boosted for this time reference.
    Currently simple: only boosts if time_ref is None (no time preference = neutral).

    Future: could filter by actual timestamps.
    """
    if not time_ref:
        return 0.0

    # If user said "last session", boost anything with source_session_id
    if time_ref == "last_session" and memory.get("source_session_id"):
        return 0.1

    # If user said "recently", boost unresolved/partially resolved
    if time_ref in ("recent", "this_week") and memory.get("resolved_status") in ("unresolved", "partially_resolved"):
        return 0.05

    return 0.0


if __name__ == "__main__":
    print("=" * 50)
    print("TEMPORAL UTILS — Self Test")
    print("=" * 50)

    tests = [
        "How did we handle that last week?",
        "What did we discuss last time?",
        "I feel anxious today",
        "Do you remember what happened before?",
    ]

    for msg in tests:
        time_ref = parse_time_reference(msg)
        days = time_reference_to_days(time_ref) if time_ref else None
        print(f"  '{msg[:40]}...' -> time_ref={time_ref}, days={days}")

    print("\nRecency score test:")
    test_mem = {
        "memory_source_kind": "exact_user_request",
        "source_timestamp": "2026-05-19T09:00:00Z",
        "follow_up_recommended": True,
        "resolved_status": "partially_resolved",
    }
    print(f"  exact_user_request + follow_up + unresolved: {compute_recency_score(test_mem):.2f}")