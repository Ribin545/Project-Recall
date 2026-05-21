"""
Project Recall — Chat Storage Module

Manages local JSON chat history for active sessions.

Design:
- Thread-safe file I/O using a file-level lock.
- Each user has a session record with messages[] and a memory_enabled flag.
- clear_user_history preserves the memory setting so the user doesn't lose
  their preference when starting a new session.
"""
import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional

from app.config import CHAT_HISTORY_PATH

# Simple file-level lock to prevent concurrent read/write corruption
_file_lock = threading.Lock()


def _ensure_data_dir() -> None:
    """
    Create the data directory if it doesn't exist.
    
    Called automatically by save_history before writing.
    """
    dir_path = os.path.dirname(CHAT_HISTORY_PATH)
    os.makedirs(dir_path, exist_ok=True)


def load_history() -> Dict:
    """
    Load chat history from local JSON file.
    
    Returns:
        Dict mapping user_id -> session data, or empty dict on error.
    """
    if not os.path.exists(CHAT_HISTORY_PATH):
        return {}
    try:
        with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_history(history: Dict) -> None:
    """
    Save chat history to local JSON file safely.
    
    Uses a threading lock to prevent corruption from concurrent writes.
    
    Args:
        history: The full chat history dict to persist.
    """
    _ensure_data_dir()
    with _file_lock:
        with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)


def get_user_history(user_id: str) -> List[Dict[str, str]]:
    """
    Return the message list for a given user, or an empty list.
    
    Args:
        user_id: Unique user identifier.
    
    Returns:
        List of message dicts with keys "role" and "content".
    """
    history = load_history()
    user_data = history.get(user_id, {})
    return user_data.get("messages", [])


def append_message(user_id: str, role: str, content: str) -> None:
    """
    Append a message to the user's current session.
    
    Creates a new session record for the user if one doesn't exist.
    
    Args:
        user_id: Unique user identifier.
        role: "user" or "assistant".
        content: The message text.
    """
    history = load_history()

    if user_id not in history:
        history[user_id] = {
            "session_id": "session_current",
            "messages": []
        }

    history[user_id]["messages"].append({
        "role": role,
        "content": content
    })

    save_history(history)


def clear_user_history(user_id: str) -> None:
    """
    Remove a user's chat history entirely, but preserve memory setting.
    
    This is used at the start of a new session so the user keeps their
    memory preference but gets a fresh conversation.
    
    Args:
        user_id: Unique user identifier.
    """
    history = load_history()
    memory_setting = get_user_memory_setting(user_id)
    if user_id in history:
        del history[user_id]
        save_history(history)
    # Restore memory setting
    set_user_memory_setting(user_id, memory_setting)


def get_user_memory_setting(user_id: str) -> bool:
    """
    Get whether memory mode is enabled for this user.
    
    Args:
        user_id: Unique user identifier.
    
    Returns:
        True if memory mode is enabled, False otherwise.
    """
    history = load_history()
    user_data = history.get(user_id, {})
    return user_data.get("memory_enabled", False)


def set_user_memory_setting(user_id: str, enabled: bool) -> None:
    """
    Set memory mode for this user.
    
    Creates a new session record if the user doesn't have one yet.
    
    Args:
        user_id: Unique user identifier.
        enabled: True to enable memory mode, False to disable.
    """
    history = load_history()

    if user_id not in history:
        history[user_id] = {
            "session_id": "session_current",
            "messages": [],
            "memory_enabled": enabled,
        }
    else:
        history[user_id]["memory_enabled"] = enabled

    save_history(history)


def get_recent_session_context(user_id: str, lookback_turns: int = 4) -> Dict:
    """
    Retrieve the recently discussed session context for a user.
    
    This tracks which session_id/theme was last discussed so that
    follow-up questions like 'what was my grounding phrase?' can
    be scoped to the right session instead of matching globally.
    
    Args:
        user_id: Unique user identifier.
        lookback_turns: How many recent turns to check.
    
    Returns:
        Dict with keys: session_id, theme, memory_id (or empty dict).
    """
    history = load_history()
    user_data = history.get(user_id, {})
    
    # Get the active context stored directly
    context = user_data.get("active_context", {})
    
    # Also check recent messages for any system context blocks
    messages = user_data.get("messages", [])
    if not context and messages:
        # Look at recent assistant messages for context clues
        recent = messages[-lookback_turns * 2:] if len(messages) > lookback_turns * 2 else messages
        for msg in reversed(recent):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # Extract session references from assistant replies
                # This is a lightweight heuristic
                if "bedtime" in content.lower() or "sleep" in content.lower():
                    context["inferred_topic"] = "sleep"
                elif "performance review" in content.lower() or "review" in content.lower():
                    context["inferred_topic"] = "performance_review"
                elif "family dinner" in content.lower() or "family" in content.lower():
                    context["inferred_topic"] = "family"
                break
    
    return context


def set_session_context(user_id: str, session_id: str = None, theme: str = None, memory_id: str = None) -> None:
    """
    Store the current session context for a user.
    
    Called after a memory is successfully selected so follow-up
    questions can be scoped correctly.
    
    Maintains a list of recently discussed sessions (up to 3) for
    better follow-up disambiguation.
    
    Args:
        user_id: Unique user identifier.
        session_id: The session_id of the most recently discussed memory.
        theme: The theme/topic of the most recent discussion.
        memory_id: The specific memory_id that was used.
    """
    history = load_history()
    
    if user_id not in history:
        history[user_id] = {
            "session_id": "session_current",
            "messages": [],
            "memory_enabled": False,
        }
    
    if "active_context" not in history[user_id]:
        history[user_id]["active_context"] = {}
    
    # Track current values
    if session_id:
        history[user_id]["active_context"]["session_id"] = session_id
    if theme:
        history[user_id]["active_context"]["theme"] = theme
    if memory_id:
        history[user_id]["active_context"]["memory_id"] = memory_id
    
    # Track recent sessions (up to 3) for better disambiguation
    if session_id:
        recent_sessions = history[user_id]["active_context"].get("recent_sessions", [])
        # Remove if already exists (move to front)
        recent_sessions = [s for s in recent_sessions if s != session_id]
        recent_sessions.insert(0, session_id)
        history[user_id]["active_context"]["recent_sessions"] = recent_sessions[:3]
    
    # Track recent themes (up to 3)
    if theme:
        recent_themes = history[user_id]["active_context"].get("recent_themes", [])
        # Remove if already exists (move to front)
        recent_themes = [t for t in recent_themes if t != theme]
        recent_themes.insert(0, theme)
        history[user_id]["active_context"]["recent_themes"] = recent_themes[:3]
    
    save_history(history)


def clear_session_context(user_id: str) -> None:
    """
    Clear the active session context.
    
    Call this when starting a completely new topic.
    
    Args:
        user_id: Unique user identifier.
    """
    history = load_history()
    if user_id in history and "active_context" in history[user_id]:
        del history[user_id]["active_context"]
        save_history(history)


# --- Active memory tracking (conversation continuity) ---
_ACTIVE_MEMORY_FILE = os.path.join("data", "active_memories.json")


def set_active_memory(user_id: str, memory_id: str, memory_data: Dict) -> None:
    """
    Store the currently active memory for conversation continuity.
    The active memory is the memory the LLM was most recently responding about.
    """
    try:
        data = {}
        if os.path.exists(_ACTIVE_MEMORY_FILE):
            with open(_ACTIVE_MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        
        data[user_id] = {
            "memory_id": memory_id,
            "memory_data": memory_data,
            "timestamp": datetime.now().isoformat(),
        }
        
        with open(_ACTIVE_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_active_memory(user_id: str) -> Optional[Dict]:
    """
    Retrieve the currently active memory for conversation continuity.
    """
    try:
        if not os.path.exists(_ACTIVE_MEMORY_FILE):
            return None
        
        with open(_ACTIVE_MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        entry = data.get(user_id)
        if not entry:
            return None
        
        return entry.get("memory_data")
    except Exception:
        return None


def is_message_related_to_memory(user_message: str, memory: Dict) -> bool:
    """
    Check if user's message is related to a specific memory.
    Uses keyword matching and semantic similarity heuristics.
    """
    import re
    
    if not memory:
        return False
    
    user_lower = user_message.lower()
    
    # Check if user message contains keywords from the memory
    memory_text = " ".join([
        memory.get("summary", ""),
        memory.get("theme", ""),
        memory.get("source_text", ""),
        " ".join(memory.get("topic_tags", [])),
    ]).lower()
    
    # Extract key nouns/phrases from user message
    user_words = set(re.findall(r'\b\w{3,}\b', user_lower))
    memory_words = set(re.findall(r'\b\w{3,}\b', memory_text))
    
    # Check overlap
    overlap = user_words & memory_words
    overlap_ratio = len(overlap) / max(len(user_words), 1)
    
    # Special cases for exact-value questions
    exact_value = memory.get("exact_value", "")
    if exact_value:
        # If user asks about "grounding phrase" and memory has grounding_phrase type
        if "grounding phrase" in user_lower and memory.get("memory_type") == "grounding_phrase":
            return True
        if "sentence" in user_lower and memory.get("memory_type") == "communication_script":
            return True
        if "preparation" in user_lower or "plan" in user_lower:
            if memory.get("memory_type") in ("coping_strategy", "review_preparation"):
                return True
    
    # General overlap threshold
    if overlap_ratio >= 0.3:
        return True
    
    # Check for session-related keywords
    session_keywords = {
        "2 am": ["2am", "2 am", "late night", "early morning", "insomnia"],
        "bedtime": ["bedtime", "sleep", "night", "bed"],
        "friendship": ["friend", "conversation", "hurt", "unheard"],
        "family": ["family", "dinner", "gathering"],
        "work": ["work", "review", "performance", "manager"],
    }
    
    theme = memory.get("theme", "").lower()
    for keyword_group, related_words in session_keywords.items():
        if any(kw in theme for kw in related_words):
            if any(kw in user_lower for kw in related_words):
                return True
    
    return False
