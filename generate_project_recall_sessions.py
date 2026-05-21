"""
Project Recall — Official Schema Session Generator (Generalized)

Generates 8–12 realistic sessions using Mentra's expected session-history JSON schema.
Uses controlled emotion vocabulary and clear remembered-phrase patterns for reliable extraction.

Usage:
    python generate_project_recall_sessions.py
"""

import json
import os
from datetime import datetime, timedelta

# --- Output path ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "data", "sample_project_recall_sessions.json")

# --- Canonical exact memories (must be findable by direct memory lookup) ---
NEEDLE_REVIEW_SENTENCE = "I'd like to understand how I can grow from here."
NEEDLE_GROUNDING_PHRASE = "steady river, small lantern"
NEEDLE_PREPARATION_PLAN = "walk for ten minutes, then write three calm bullet points before the review"
NEEDLE_FAMILY_SCRIPT = "I need some space, but I still care about you."
NEEDLE_FRIEND_SCRIPT = "I felt hurt, but I want to understand what happened."


# --- Session generators (each produces a complete session dict) ---

def _session_work_stress(idx: int, base_time: datetime) -> dict:
    """Session about work stress and burnout."""
    t = base_time + timedelta(days=idx * 2)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "work stress and burnout",
        "emotional_tone": ["anxious", "overwhelmed", "hopeful"],
        "key_moments": [
            "User reported panic before meetings",
            "User discussed a grounding exercise before stressful work calls",
            "User committed to a 10-minute no-phone wind-down routine",
        ],
        "summary": "User described increasing stress from back-to-back deadlines. They noticed heart racing before weekly stand-ups. We explored a breathing pattern and a short wind-down window after work. The session ended with a small commitment to try the routine.",
        "risk_flags": ["high_stress"],
        "follow_up_topics": ["sleep hygiene", "grounding exercise"],
    }


def _session_sleep(idx: int, base_time: datetime) -> dict:
    """Session about sleep and overthinking."""
    t = base_time + timedelta(days=idx * 2 + 1)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "sleep and overthinking",
        "emotional_tone": ["tired", "overwhelmed", "hopeful"],
        "key_moments": [
            "User has been waking at 2 AM with looping thoughts",
            "User discussed a dim-lights wind-down and writing tomorrow's top three tasks before bed",
            "User committed to try the routine for three nights and notice what happens",
        ],
        "summary": "User has been waking at 2 AM with looping thoughts about unfinished work. They feel frustrated because tiredness bleeds into the next day. We discussed a dim-lights wind-down and writing tomorrow's top three tasks before bed.",
        "risk_flags": ["sleep_disruption"],
        "follow_up_topics": ["no-phone wind-down", "sleep hygiene"],
    }


def _session_family_boundaries(idx: int, base_time: datetime) -> dict:
    """Session about family boundaries with canonical communication script."""
    t = base_time + timedelta(days=idx * 2 + 2)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "family boundaries",
        "emotional_tone": ["anxious", "uncertain", "hopeful"],
        "key_moments": [
            f'User wanted to remember the sentence: "{NEEDLE_FAMILY_SCRIPT}" for a conversation with their brother.',
            "User felt guilty about setting boundaries",
            "User committed to sleep routine",
        ],
        "summary": "User discussed family boundaries and wants to set limits with their brother. They feel guilty but also hopeful. They found a sentence that felt honest and kind and want to remember it.",
        "risk_flags": [],
        "follow_up_topics": ["brother conversation", "boundary setting"],
    }


def _session_friendship_conflict(idx: int, base_time: datetime) -> dict:
    """Session about friendship conflict with canonical communication script."""
    t = base_time + timedelta(days=idx * 2 + 3)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "friendship conflict",
        "emotional_tone": ["hurt", "uncertain", "hopeful"],
        "key_moments": [
            f'User planned to say: "{NEEDLE_FRIEND_SCRIPT}" to a friend.',
            "User is worried the friendship might end",
            "User wants to apologize but also explain their feelings",
        ],
        "summary": "User is navigating a difficult conversation with a friend after a misunderstanding. They found a sentence that feels honest and kind and want to remember it for when they feel ready to talk.",
        "risk_flags": [],
        "follow_up_topics": ["friendship repair", "apology script"],
    }


def _session_self_criticism(idx: int, base_time: datetime) -> dict:
    """Session about self-criticism and shame."""
    t = base_time + timedelta(days=idx * 2 + 4)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "self-criticism and shame",
        "emotional_tone": ["ashamed", "discouraged", "hopeful"],
        "key_moments": [
            "User described a spiral of self-criticism after seeing peers' updates online",
            "User feels ashamed for not finishing a project and frustrated that the shame makes it harder to start",
            "User committed to fifteen minutes of focused work with no outcome judgment",
        ],
        "summary": "User described a spiral of self-criticism after seeing peers' updates online. They feel ashamed for not finishing a project and frustrated that the shame itself makes it harder to start. We explored the pattern of comparison and one tiny next step.",
        "risk_flags": [],
        "follow_up_topics": ["self-critical thoughts", "small productivity step"],
    }


def _session_loneliness(idx: int, base_time: datetime) -> dict:
    """Session about loneliness and social disconnection."""
    t = base_time + timedelta(days=idx * 2 + 5)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "loneliness and social disconnection",
        "emotional_tone": ["lonely", "discouraged", "hopeful"],
        "key_moments": [
            "User described loneliness even after spending time around people",
            "User feels disconnected and wonders if something is wrong with them",
            "User committed to one vulnerable share with their partner this week",
        ],
        "summary": "User described loneliness even after spending time around people. They feel disconnected and wonder if something is wrong with them. We explored the difference between being alone and feeling alone. They chose one vulnerable share with their partner this week.",
        "risk_flags": [],
        "follow_up_topics": ["loneliness check-in", "social outreach"],
    }


def _session_manager_conversation(idx: int, base_time: datetime) -> dict:
    """Session about manager conversation with canonical review sentence."""
    t = base_time + timedelta(days=idx * 2 + 6)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "manager conversation",
        "emotional_tone": ["nervous", "overwhelmed", "relieved"],
        "key_moments": [
            f'User wanted to use the sentence: "{NEEDLE_REVIEW_SENTENCE}" in a performance review conversation.',
            "User rehearsed the sentence and reported that the grounding phrase helped during a practice conversation",
            "User updated their preparation plan slightly",
        ],
        "summary": "User came in nervous about the upcoming performance review. They had rehearsed the sentence they wanted to use and reported that the grounding phrase helped during a practice conversation with a trusted colleague. They updated their preparation plan slightly. The session ended with a sense of mild relief and readiness.",
        "risk_flags": ["high_stress"],
        "follow_up_topics": ["performance review", "grounding exercise"],
    }


def _session_productivity_pressure(idx: int, base_time: datetime) -> dict:
    """Session about productivity pressure with canonical grounding phrase."""
    t = base_time + timedelta(days=idx * 2 + 7)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "productivity pressure",
        "emotional_tone": ["discouraged", "frustrated", "hopeful"],
        "key_moments": [
            "User feels behind and inadequate compared to peers",
            f'User chose the grounding phrase: "{NEEDLE_GROUNDING_PHRASE}"',
            "User committed to curating their feed and setting app time limits",
        ],
        "summary": "User described comparing themselves to others online and feeling behind and inadequate. We explored curating their feed and setting app time limits. They committed to one unfollow of an account that triggers comparison.",
        "risk_flags": [],
        "follow_up_topics": ["self-critical thoughts", "small productivity step"],
    }


def _session_preparation_plan(idx: int, base_time: datetime) -> dict:
    """Session with canonical preparation plan."""
    t = base_time + timedelta(days=idx * 2 + 8)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "emotional regulation",
        "emotional_tone": ["anxious", "overwhelmed", "calm"],
        "key_moments": [
            "User reported difficulty with emotional regulation before important events",
            f"User planned to {NEEDLE_PREPARATION_PLAN}",
            "User committed to try the preparation plan before the next important event",
        ],
        "summary": "User reported difficulty with emotional regulation before important events. They planned to walk for ten minutes, then write three calm bullet points before the review. They committed to try the preparation plan before the next important event and notice what shifts.",
        "risk_flags": [],
        "follow_up_topics": ["decision next step", "small productivity step"],
    }


def _session_emotional_regulation(idx: int, base_time: datetime) -> dict:
    """Session about emotional regulation."""
    t = base_time + timedelta(days=idx * 2 + 9)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "emotional regulation",
        "emotional_tone": ["uncertain", "anxious", "calm"],
        "key_moments": [
            "User described tension that escalated during a family dinner",
            "User felt unheard and withdrew",
            "User committed to one gentle conversation before the next gathering",
        ],
        "summary": "User described tension that escalated during a family dinner. They felt unheard and withdrew. We explored communication styles and practiced 'I feel... when... because...' language. They committed to one gentle conversation before the next gathering.",
        "risk_flags": [],
        "follow_up_topics": ["boundary practice", "communication skills"],
    }


def _session_sleep_hygiene(idx: int, base_time: datetime) -> dict:
    """Session about sleep hygiene."""
    t = base_time + timedelta(days=idx * 2 + 10)
    return {
        "user_id": "demo_user",
        "session_id": f"sess_{idx + 1:03d}",
        "timestamp": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": "sleep hygiene",
        "emotional_tone": ["tired", "discouraged", "relieved"],
        "key_moments": [
            "User reported panic before bedtime",
            "User chose a grounding phrase: 'Quiet room, soft blanket, slow breath.'",
            "User wants to try a no-phone wind-down routine",
        ],
        "summary": "User struggles with sleep due to anxiety and wants to build a calming bedtime routine. They chose a grounding phrase and want to try a no-phone wind-down routine.",
        "risk_flags": ["sleep_disruption"],
        "follow_up_topics": ["no-phone wind-down", "bedtime routine"],
    }


# --- Build sessions ---

SESSION_GENERATORS = [
    _session_work_stress,
    _session_sleep,
    _session_family_boundaries,
    _session_friendship_conflict,
    _session_self_criticism,
    _session_loneliness,
    _session_manager_conversation,
    _session_productivity_pressure,
    _session_preparation_plan,
    _session_emotional_regulation,
    _session_sleep_hygiene,
]


def _build_sessions() -> list:
    """Build 11 realistic sessions using the official schema."""
    base_time = datetime(2026, 1, 3, 9, 0, 0)
    sessions = []
    for i, gen in enumerate(SESSION_GENERATORS):
        session = gen(i, base_time)
        sessions.append(session)
    return sessions


def main():
    sessions = _build_sessions()

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

    # Verification
    needle_checks = {
        "review_sentence": NEEDLE_REVIEW_SENTENCE,
        "grounding_phrase": NEEDLE_GROUNDING_PHRASE,
        "preparation_plan": NEEDLE_PREPARATION_PLAN,
        "family_script": NEEDLE_FAMILY_SCRIPT,
        "friend_script": NEEDLE_FRIEND_SCRIPT,
    }

    all_text = json.dumps(sessions)
    found = {}
    for name, value in needle_checks.items():
        found[name] = value in all_text

    print(f"Generated {len(sessions)} sessions")
    print(f"Saved to: {OUTPUT_PATH}")
    for name, ok in found.items():
        status = "✅" if ok else "❌"
        print(f"  {status} Needle '{name}': {'found' if ok else 'MISSING'}")
    print(f"  Total sessions: {len(sessions)}")


if __name__ == "__main__":
    main()