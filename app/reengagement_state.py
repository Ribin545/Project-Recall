"""
Project Recall - Re-Engagement State Module
============================================

This module handles the loading and construction of user state
for the re-engagement (push notification) decision engine.

User state includes:
  - How many days since the last session
  - How many notifications were already sent recently
  - Whether the user has notifications enabled
  - Whether quiet hours are active
  - The emotional tone at session close

For the demo, most states are mock/constructed from query parameters.
In production, this would pull from a persistent user-preferences store.
"""

import os
import json
from typing import Dict, Optional

# Import active paths from central config
from app.paths import PROJECT_RECALL_MEMORIES_PATH

# -----------------------------------------------------------------------------
# Default Mock State (used for demo_user when no real state exists)
# -----------------------------------------------------------------------------
DEFAULT_STATE = {
    "user_id": "demo_user",
    "days_since_last_session": 3,               # 3 days since last chat
    "notifications_sent_last_7_days": 0,        # No fatigue yet
    "personalized_notifications_enabled": True,   # User consents to notifications
    "quiet_hours_active": False,                # Not in DND mode
    "last_session_id": "session_003",            # Most recent session ID
    "last_session_close_emotion": "anxiety",     # Emotion at end of last session
    "last_session_close_tone": "nervous but more prepared",
}


def load_user_reengagement_state(user_id: str) -> Dict:
    """
    Load re-engagement state for a user.

    In the demo, this returns a mock state with sensible defaults.
    In production, this would query a user-preferences database.

    Args:
        user_id: The user identifier (e.g., "demo_user").

    Returns:
        A dict with keys: user_id, days_since_last_session,
        notifications_sent_last_7_days, personalized_notifications_enabled,
        quiet_hours_active, last_session_id, last_session_close_emotion,
        last_session_close_tone.
    """
    if user_id == "demo_user":
        # Return a shallow copy so callers can mutate safely
        return dict(DEFAULT_STATE)

    # Generic fallback for any non-demo user
    return {
        "user_id": user_id,
        "days_since_last_session": 5,
        "notifications_sent_last_7_days": 0,
        "personalized_notifications_enabled": True,
        "quiet_hours_active": False,
        "last_session_id": "unknown",
        "last_session_close_emotion": "neutral",
        "last_session_close_tone": "neutral",
    }


def make_user_state(
    user_id: str = "demo_user",
    days_since_last_session: int = 3,
    notifications_sent_last_7_days: int = 0,
    personalized_notifications_enabled: bool = True,
    quiet_hours_active: bool = False,
    last_session_close_emotion: str = "anxiety",
    **extra
) -> Dict:
    """
    Build a user state dict for testing scenarios.

    This helper lets test scenarios construct arbitrary user states
    without needing a real database. Extra keyword arguments are
    merged into the returned dict for future extensibility.

    Args:
        user_id: User identifier.
        days_since_last_session: Days since the user's last chat session.
        notifications_sent_last_7_days: How many push notifications
            were sent in the last 7 days (fatigue tracking).
        personalized_notifications_enabled: Whether the user has opted
            in to personalized re-engagement notifications.
        quiet_hours_active: Whether the user is currently in a
            do-not-disturb / quiet-hours window.
        last_session_close_emotion: The primary emotion detected at
            the end of the user's last session (e.g., "anxiety").
        **extra: Any additional key-value pairs to include.

    Returns:
        A fully populated user state dict.
    """
    return {
        "user_id": user_id,
        "days_since_last_session": days_since_last_session,
        "notifications_sent_last_7_days": notifications_sent_last_7_days,
        "personalized_notifications_enabled": personalized_notifications_enabled,
        "quiet_hours_active": quiet_hours_active,
        "last_session_id": extra.get("last_session_id", "session_003"),
        "last_session_close_emotion": last_session_close_emotion,
        "last_session_close_tone": extra.get("last_session_close_tone", ""),
        **extra,
    }


def load_extracted_memories(user_id: str) -> list:
    """
    Load extracted memories for a user from the local JSON file.

    The memories are produced by `app/memory_extractor.py` and stored
    in `data/extracted_memories.json`. Each memory contains emotional
    metadata (primary emotion, intensity, valence, etc.), resolution
    status, sensitivity score, and follow-up recommendation flags.

    Args:
        user_id: The user whose memories to load.

    Returns:
        A list of memory dicts for that user, or an empty list if the
        file does not exist or the user has no memories.
    """
    # Resolve path relative to project root
    path = PROJECT_RECALL_MEMORIES_PATH

    # If the memory extraction step hasn't been run yet, return empty
    if not os.path.exists(path):
        return []

    # Load and filter to this user's memories only
    with open(path, "r", encoding="utf-8") as f:
        all_memories = json.load(f)

    return [m for m in all_memories if m.get("user_id") == user_id]