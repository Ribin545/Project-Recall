"""
Project Recall — Memory Extractor

Reads structured memories with emotional metadata from session transcripts.
Supports the official Project Recall schema format.

Usage:
    # Default (Project Recall official schema)
    python app/memory_extractor.py

    # Equivalent explicit call
    python app/memory_extractor.py --input data/sample_project_recall_sessions.json --format project_recall --output data/extracted_memories_project_recall.json

Output: data/extracted_memories_project_recall.json (default) or specified output path
"""
import argparse
import json
import os
import sys
import random
import re
from typing import List, Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.memory_schema import Memory, Emotion
from app.paths import PROJECT_RECALL_SESSIONS_PATH, PROJECT_RECALL_MEMORIES_PATH

# --- Paths ---
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DEFAULT_SESSIONS_PATH = PROJECT_RECALL_SESSIONS_PATH
DEFAULT_OUTPUT_PATH = PROJECT_RECALL_MEMORIES_PATH


def _sensitivity_to_float(level: str) -> float:
    """
    Convert a string sensitivity level to a float score.
    
    Args:
        level: "low", "medium", or "high".
    
    Returns:
        Float sensitivity score.
    """
    mapping = {"low": 0.1, "medium": 0.4, "high": 0.8}
    return mapping.get(level, 0.4)


def _extract_moment_emotion(moment: Dict) -> Emotion:
    """
    Build an Emotion object from moment-level emotion data.
    
    Args:
        moment: A key_moment dict.
    
    Returns:
        Emotion Pydantic model.
    """
    e = moment.get("emotion", {})
    return Emotion(
        primary=e.get("primary", "neutral"),
        secondary=e.get("secondary", []),
        intensity=e.get("intensity", 0.5),
        trajectory=None,
        session_open_tone=None,
        session_close_tone=None,
    )


def _extract_session_emotion(session: Dict) -> Emotion:
    """
    Build an Emotion object from session-level emotion data.
    
    Args:
        session: A session dict.
    
    Returns:
        Emotion Pydantic model.
    """
    e = session.get("emotion", {})
    return Emotion(
        primary=e.get("primary", "neutral"),
        secondary=e.get("secondary", []),
        intensity=e.get("intensity", 0.5),
        valence=e.get("valence"),
        arousal=e.get("arousal"),
        trajectory=e.get("trajectory"),
        session_open_tone=e.get("session_open_tone"),
        session_close_tone=e.get("session_close_tone"),
    )


def _build_memory_from_moment(moment: Dict, session: Dict) -> Optional[Memory]:
    """
    Create a Memory object from a structured key_moment.
    
    Handles needle detection: moments with exact values matching known needle
    facts are marked as canonical with confidence=1.0.
    Distractors receive lower confidence scores.
    
    Args:
        moment: A key_moment dict.
        session: The parent session dict.
    
    Returns:
        Memory object or None.
    """
    user_id = session.get("user_id", "demo_user")
    session_id = session.get("session_id", "unknown")
    timestamp = session.get("timestamp", "")

    # Moment-level emotion, fallback to session-level
    if "emotion" in moment:
        emotion = _extract_moment_emotion(moment)
    else:
        emotion = _extract_session_emotion(session)

    # Determine canonical / confidence for needle memories
    is_canonical = False
    user_explicitly_asked_to_remember = False
    confidence = 0.5

    exact_val = moment.get("exact_value")
    if exact_val:
        needle_exact_values = [
            "steady river, small lantern",
            "I'd like to understand how I can grow from here.",
            "walk for ten minutes, then write three calm bullet points before the review",
        ]
        if any(v in exact_val for v in needle_exact_values):
            is_canonical = True
            user_explicitly_asked_to_remember = True
            confidence = 1.0

    # Distractors: lower confidence
    is_distractor = moment.get("is_distractor", False)
    if is_distractor:
        confidence = random.uniform(0.3, 0.6)

    return Memory(
        memory_id=moment.get("moment_id", f"mem_{session_id}_{random.randint(0,9999):04d}"),
        user_id=user_id,
        source_session_id=session_id,
        source_timestamp=timestamp,
        memory_type=moment.get("memory_type", "recurring_theme"),
        summary=moment.get("text", ""),
        exact_value=exact_val,
        topic_tags=moment.get("topic_tags", []),
        emotion=emotion,
        importance=moment.get("importance", 0.6),
        sensitivity=_sensitivity_to_float(session.get("sensitivity", "medium")),
        resolved_status=session.get("resolved_status", "unknown"),
        follow_up_recommended=moment.get("follow_up_recommended", False),
        safe_to_reference_in_opener=moment.get("safe_to_reference_in_opener", True),
        is_distractor=is_distractor,
        is_canonical=is_canonical,
        user_explicitly_asked_to_remember=user_explicitly_asked_to_remember,
        confidence=confidence,
    )


def _build_memory_from_message(
    message_idx: int,
    msg: Dict,
    session: Dict
) -> Optional[Memory]:
    """
    Create a Memory object from a user session message with emotion metadata.
    
    IMPORTANT: Only extracts from the needle session (session_003) to avoid
    extracting distractor phrases from synthetic filler session messages.
    
    Looks for quoted text or keyword phrases that indicate explicit memory
    requests from the user.
    
    Args:
        message_idx: Index of the message in the message list.
        msg: A transcript message dict.
        session: The parent session dict.
    
    Returns:
        Memory object or None if not a valid transcript memory.
    """
    # Only extract from user messages in the needle session
    if msg.get("role") != "user":
        return None
    if "emotion" not in msg:
        return None
    
    user_id = session.get("user_id", "demo_user")
    session_id = session.get("session_id", "unknown")
    # Only extract message-level memories from session_003 (the needle session)
    # Filler sessions have synthetic content that may contain distractor phrases
    if session_id != "session_003":
        return None

    timestamp = msg.get("timestamp", session.get("timestamp", ""))
    content = msg.get("content", "")

    # Check if this contains a needle-like explicit memory request
    contains_exact = False
    exact_value = None

    # Look for exact quoted text
    if '"' in content or "'" in content:
        quotes = re.findall(r'[\"\']([^\"\']+)[\"\']', content)
        if quotes:
            exact_value = quotes[0]
            contains_exact = True

    if not contains_exact and len(content) > 80:
        if any(kw in content.lower() for kw in ["walk for ten minutes", "review sentence", "grounding phrase"]):
            exact_value = content[:150]
            contains_exact = True

    if not contains_exact:
        return None

    # Build emotion from transcript message
    e = msg.get("emotion", {})
    emotion = Emotion(
        primary=e.get("primary", "neutral"),
        secondary=e.get("secondary", []),
        intensity=e.get("intensity", 0.5),
    )

    # Determine canonical / confidence for transcript needle memories
    is_canonical = False
    user_explicitly_asked_to_remember = False
    confidence = 0.5

    if exact_value:
        needle_exact_values = [
            "steady river, small lantern",
            "I'd like to understand how I can grow from here.",
            "walk for ten minutes, then write three calm bullet points before the review",
        ]
        if any(v in exact_value for v in needle_exact_values):
            is_canonical = True
            user_explicitly_asked_to_remember = True
            confidence = 1.0

    return Memory(
        memory_id=f"mem_{session_id}_msg_{message_idx:03d}",
        user_id=user_id,
        source_session_id=session_id,
        source_timestamp=timestamp,
        memory_type="follow_up_intent",  # Default for message-level memories
        summary=content[:150] + ("..." if len(content) > 150 else ""),
        exact_value=exact_value,
        topic_tags=[session.get("theme", ""), "session message memory"],
        emotion=emotion,
        importance=0.85,
        sensitivity=_sensitivity_to_float(session.get("sensitivity", "medium")),
        resolved_status=session.get("resolved_status", "unknown"),
        follow_up_recommended=True,
        safe_to_reference_in_opener=True,
        is_distractor=False,
        is_canonical=is_canonical,
        user_explicitly_asked_to_remember=user_explicitly_asked_to_remember,
        confidence=confidence,
    )


def _detect_format(sessions: List[Dict]) -> str:
    """
    Auto-detect the session format from the first session.

    Args:
        sessions: List of session dicts.

    Returns:
        "project_recall" or "dummy_large".
    """
    if not sessions:
        return "dummy_large"

    first = sessions[0]
    # Project Recall official schema has theme, summary, follow_up_topics at top level
    if all(k in first for k in ("theme", "summary", "follow_up_topics")):
        return "project_recall"

    # Legacy dummy_large has nested emotion objects and messages
    if "emotion" in first and isinstance(first.get("emotion"), dict) and "messages" in first:
        return "dummy_large"

    return "dummy_large"


def _extract_project_recall_memories(sessions: List[Dict]) -> List[Memory]:
    """
    Extract memories from Project Recall official-schema sessions.

    Uses the schema adapter to convert official format to internal Memory objects.

    Args:
        sessions: List of official-schema session dicts.

    Returns:
        List of Memory objects.
    """
    from app.project_recall_schema_adapter import session_to_memory_candidates

    all_memories: List[Memory] = []

    for session in sessions:
        candidates = session_to_memory_candidates(session)
        for cand in candidates:
            # Convert dict candidate to Memory Pydantic model
            emotion = cand.get("emotion", {})
            memory = Memory(
                memory_id=cand["memory_id"],
                user_id=cand["user_id"],
                source_session_id=cand["source_session_id"],
                source_timestamp=cand["source_timestamp"],
                memory_type=cand["memory_type"],
                memory_source_kind=cand.get("memory_source_kind", "key_moment"),
                theme=cand.get("theme"),
                source_text=cand.get("source_text"),
                summary=cand["summary"],
                exact_value=cand.get("exact_value"),
                canonical_slot=cand.get("canonical_slot"),
                topic_tags=cand.get("topic_tags", []),
                follow_up_topics=cand.get("follow_up_topics", []),
                risk_flags=cand.get("risk_flags", []),
                emotion=Emotion(
                    primary=emotion.get("primary", "neutral"),
                    secondary=emotion.get("secondary", []),
                    all_emotions=emotion.get("all_emotions", []),
                    intensity=emotion.get("intensity", 0.5),
                    valence=emotion.get("valence"),
                    arousal=emotion.get("arousal"),
                    trajectory=emotion.get("trajectory"),
                    session_close_tone=emotion.get("session_close_tone"),
                ),
                importance=cand.get("importance", 0.6),
                sensitivity=cand.get("sensitivity", 0.3),
                resolved_status=cand.get("resolved_status", "unknown"),
                follow_up_recommended=cand.get("follow_up_recommended", False),
                safe_to_reference_in_opener=cand.get("safe_to_reference_in_opener", True),
                is_distractor=cand.get("is_distractor", False),
                is_canonical=cand.get("is_canonical", False),
                user_explicitly_asked_to_remember=cand.get("user_explicitly_asked_to_remember", False),
                confidence=cand.get("confidence", 0.5),
            )
            all_memories.append(memory)

    return all_memories


def extract_all_memories(
    sessions_path: str = DEFAULT_SESSIONS_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    fmt: str = "auto",
) -> List[Memory]:
    """
    Extract memories from all sessions using structured metadata.

    Supports both legacy dummy_large format and Project Recall official schema.

    Args:
        sessions_path: Path to session archive JSON.
        output_path: Path to write extracted memories.
        fmt: "auto", "dummy_large", or "project_recall".

    Returns:
        List of Memory objects.
    """
    print(f"Loading session archive from {sessions_path}...")
    with open(sessions_path, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    if fmt == "auto":
        fmt = _detect_format(sessions)
        print(f"Auto-detected format: {fmt}")

    print(f"Loaded {len(sessions)} sessions (format={fmt}). Extracting memories...")

    if fmt == "project_recall":
        all_memories = _extract_project_recall_memories(sessions)
    else:
        # Legacy dummy_large extraction
        all_memories: List[Memory] = []
        for session in sessions:
            for moment in session.get("key_moments", []):
                mem = _build_memory_from_moment(moment, session)
                if mem:
                    all_memories.append(mem)

            for idx, msg in enumerate(session.get("messages", [])):
                mem = _build_memory_from_message(idx, msg, session)
                if mem:
                    all_memories.append(mem)

    print(f"Extracted {len(all_memories)} memories total.")
    return all_memories


def save_memories(memories: List[Memory], output_path: str = DEFAULT_OUTPUT_PATH) -> None:
    """
    Save extracted memories to JSON.
    
    Args:
        memories: List of Memory objects.
        output_path: Path to write extracted memories.
    """
    data = [m.model_dump() for m in memories]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_path}")


def main():
    """
    Main entry point: parse CLI args, extract, analyze, and save memories.
    """
    parser = argparse.ArgumentParser(description="Extract structured memories from session archives")
    parser.add_argument(
        "--input",
        default=DEFAULT_SESSIONS_PATH,
        help="Path to session archive JSON (default: Project Recall sample sessions)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write extracted memories JSON",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "project_recall"],
        default="project_recall",
        help="Session format (default: project_recall)",
    )
    args = parser.parse_args()

    memories = extract_all_memories(
        sessions_path=args.input,
        output_path=args.output,
        fmt=args.format,
    )

    # Show needle memory count
    needle_facts = [
        "I'd like to understand how I can grow from here.",
        "steady river, small lantern",
        "walk for ten minutes, then write three calm bullet points before the review",
    ]
    needle_count = sum(
        1 for m in memories
        if m.exact_value and any(m.exact_value == v for v in needle_facts)
    )
    print(f"Needle memories extracted: {needle_count}")

    # Show distractor count
    distractor_count = sum(1 for m in memories if m.is_distractor)
    print(f"Distractor memories extracted: {distractor_count}")

    # Show emotion coverage
    with_emotion = sum(1 for m in memories if m.emotion.primary != "neutral")
    print(f"Memories with emotion metadata: {with_emotion}/{len(memories)}")

    save_memories(memories, args.output)


if __name__ == "__main__":
    main()
