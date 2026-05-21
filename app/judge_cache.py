"""
Project Recall — LLM Judge Response Cache

Simple file-based cache to avoid repeated LLM judge calls for identical
(user_message + candidate_ids + model) combinations.

Cache file: data/judge_cache.json
"""
import hashlib
import json
import os
from typing import Dict, Optional

CACHE_PATH = os.path.join("data", "judge_cache.json")


def _make_key(user_message: str, candidate_ids: list, provider: str = None, model: str = None) -> str:
    """Create a deterministic cache key."""
    content = "|".join([
        user_message.strip().lower(),
        ",".join(sorted(candidate_ids)),
        provider or "default",
        model or "default",
    ])
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def get_cached_judge_result(user_message: str, candidate_ids: list, provider: str = None, model: str = None) -> Optional[Dict]:
    """Retrieve cached judge result if available."""
    if not os.path.exists(CACHE_PATH):
        return None

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        return None

    key = _make_key(user_message, candidate_ids, provider, model)
    entry = cache.get(key)
    if not entry:
        return None

    # Validate entry has required fields
    if not isinstance(entry, dict) or "use_memory" not in entry:
        return None

    return entry


def save_cached_judge_result(user_message: str, candidate_ids: list, result: Dict, provider: str = None, model: str = None) -> None:
    """Save judge result to cache."""
    # Don't cache failed/invalid results
    if not result or not isinstance(result, dict):
        return

    # Don't cache low-confidence results
    if result.get("confidence", 1.0) < 0.5:
        return

    # Don't cache fallback results
    if result.get("judge_status") in ("fallback_used", "invalid_json", "timeout", "provider_error"):
        return

    try:
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        else:
            cache = {}
    except Exception:
        cache = {}

    key = _make_key(user_message, candidate_ids, provider, model)
    cache[key] = result

    # Limit cache size
    if len(cache) > 500:
        # Remove oldest entries (simple: clear half)
        keys = list(cache.keys())
        for k in keys[:250]:
            del cache[k]

    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def clear_judge_cache() -> None:
    """Clear the judge cache."""
    if os.path.exists(CACHE_PATH):
        try:
            os.remove(CACHE_PATH)
        except Exception:
            pass


if __name__ == "__main__":
    print("Judge cache self-test")
    clear_judge_cache()

    test_result = {
        "use_memory": True,
        "selected_memory_ids": ["mem_test"],
        "relevance": "high",
        "confidence": 0.85,
        "judge_status": "success",
    }

    save_cached_judge_result(
        "What was my grounding phrase?",
        ["mem_test", "mem_other"],
        test_result,
        provider="ollama",
        model="llama3.1",
    )

    cached = get_cached_judge_result(
        "What was my grounding phrase?",
        ["mem_test", "mem_other"],
        provider="ollama",
        model="llama3.1",
    )

    print(f"Cached: {cached}")
    assert cached is not None
    assert cached["use_memory"] is True
    print("PASS")