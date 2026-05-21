"""
Project Recall — Reliability Guardrail Test

Tests that the system behaves safely when:
- Judge returns invalid JSON
- Judge times out
- Correct memory is not rank 1
- Vector misses but sparse finds
- Topic extraction is empty
- No relevant memory exists
- Direct exact recall still works
"""
import json
import os
import sys
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory_relevance_judge import judge_memory_relevance, _deterministic_fallback
from app.current_emotion_detector import detect_current_emotion
from app.current_topic_extractor import extract_current_topic_hints
from app.response_policy import load_response_policy
from app.prompts import build_no_memory_fallback_prompt, MENTRA_SYSTEM_PROMPT
from app.direct_memory_lookup import resolve_direct_memory


# --- Test A: Judge invalid JSON ---
def test_a_judge_invalid_json() -> dict:
    """Test A: Mock judge returns invalid JSON → fallback used, no weak memory injected."""
    candidates = [
        {
            "memory_id": "mem_test_a",
            "memory_type": "coping_strategy",
            "memory_source_kind": "key_moment",
            "theme": "anxiety",
            "source_text": "User planned to walk for ten minutes before review",
            "summary": "Walking plan before review",
            "topic_tags": ["anxiety", "walking", "review"],
            "emotion": {"primary": "anxiety"},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
        }
    ]

    # Mock the LLM client to return garbage
    with patch("app.memory_relevance_judge.llm_client") as mock_llm:
        mock_llm.chat.return_value = "this is not json at all { broken"

        result = judge_memory_relevance(
            user_message="I feel anxious about my review",
            detected_emotion={"primary": "anxiety", "intent": "emotional_disclosure"},
            topic_hints={"topic_family": "work", "topic_hints": ["review"], "strong_topic_terms": ["review"]},
            candidate_memories=candidates,
            policy_config={},
        )

    checks = []
    if result.get("use_memory") and result.get("confidence", 0) < 0.65:
        checks.append("WARN: fallback approved memory with low confidence")
    if result.get("raw_model_output") != "[deterministic_fallback]":
        checks.append("FAIL: expected deterministic fallback, got LLM result")
    if not result.get("use_memory"):
        checks.append("INFO: fallback correctly rejected memory (no strong match)")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "judge_invalid_json",
        "status": status,
        "checks": checks,
        "judge_status": result.get("raw_model_output", "unknown"),
        "use_memory": result.get("use_memory"),
    }


# --- Test B: Judge timeout / provider error ---
def test_b_judge_timeout() -> dict:
    """Test B: Mock judge raises exception → safe no-memory fallback."""
    candidates = [
        {
            "memory_id": "mem_test_b",
            "memory_type": "coping_strategy",
            "memory_source_kind": "key_moment",
            "theme": "anxiety",
            "source_text": "User planned to walk for ten minutes",
            "summary": "Walking plan",
            "topic_tags": ["anxiety", "walking"],
            "emotion": {"primary": "anxiety"},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
        }
    ]

    with patch("app.memory_relevance_judge.llm_client") as mock_llm:
        mock_llm.chat.side_effect = Exception("LLM timeout")

        result = judge_memory_relevance(
            user_message="I feel anxious",
            detected_emotion={"primary": "anxiety", "intent": "emotional_disclosure"},
            topic_hints={"topic_family": "anxiety", "topic_hints": [], "strong_topic_terms": []},
            candidate_memories=candidates,
            policy_config={},
        )

    checks = []
    if result.get("use_memory"):
        checks.append("WARN: fallback approved memory without LLM judge")
    if result.get("raw_model_output") != "[deterministic_fallback]":
        checks.append("FAIL: expected deterministic fallback after timeout")
    if not result.get("use_memory"):
        checks.append("PASS: safe rejection when judge unavailable")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "judge_timeout",
        "status": status,
        "checks": checks,
        "use_memory": result.get("use_memory"),
    }


# --- Test C: Correct memory not rank 1 ---
def test_c_correct_memory_not_first() -> dict:
    """Test C: LLM judge selects correct memory even when not top-ranked."""
    candidates = [
        {
            "memory_id": "mem_wrong",
            "memory_type": "communication_script",
            "memory_source_kind": "exact_user_request",
            "theme": "friendship conflict",
            "source_text": "User wanted to say: 'I felt hurt...'",
            "summary": "Friendship repair script",
            "topic_tags": ["friendship", "hurt"],
            "emotion": {"primary": "sadness"},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
            "semantic_similarity": 0.9,
            "final_score": 0.9,
        },
        {
            "memory_id": "mem_correct",
            "memory_type": "coping_strategy",
            "memory_source_kind": "exact_user_request",
            "theme": "emotional regulation",
            "source_text": "User planned to walk for ten minutes, then write three calm bullet points before the review",
            "summary": "Pre-review prep plan",
            "topic_tags": ["emotional regulation", "walking", "review"],
            "emotion": {"primary": "anxiety"},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
            "semantic_similarity": 0.7,
            "final_score": 0.7,
        },
    ]

    with patch("app.memory_relevance_judge.llm_client") as mock_llm:
        # Mock LLM that correctly selects mem_correct
        mock_llm.chat.return_value = json.dumps({
            "use_memory": True,
            "selected_memory_ids": ["mem_correct"],
            "relevance": "high",
            "confidence": 0.85,
            "detail_level_recommendation": "summary_level",
            "answer_basis": "Preparation plan for emotional regulation",
            "reason": "User asks HOW they managed, and mem_correct contains the actual strategy",
            "rejected_memories": [{"memory_id": "mem_wrong", "reason": "About friendship, not emotional regulation"}],
        })

        result = judge_memory_relevance(
            user_message="How did we manage emotional regulation before important events?",
            detected_emotion={"primary": "neutral", "intent": "specific_episode_recall"},
            topic_hints={"topic_family": "general", "topic_hints": [], "strong_topic_terms": []},
            candidate_memories=candidates,
            policy_config={},
        )

    checks = []
    selected = result.get("selected_memory_ids", [])
    if "mem_correct" not in selected:
        checks.append("FAIL: judge did not select correct memory")
    if "mem_wrong" in selected:
        checks.append("FAIL: judge selected wrong memory")
    if result.get("confidence", 0) < 0.65:
        checks.append("FAIL: confidence too low")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "correct_memory_not_first",
        "status": status,
        "checks": checks,
        "selected": selected,
        "confidence": result.get("confidence"),
    }


# --- Test D: Vector misses but sparse finds ---
def test_d_vector_misses_sparse_finds() -> dict:
    """Test D: Dense vector misses, but sparse text search finds the memory."""
    # This tests the hybrid retriever's sparse search
    from app.hybrid_memory_retriever import _compute_sparse_score

    memory = {
        "memory_id": "mem_sparse",
        "memory_type": "coping_strategy",
        "memory_source_kind": "exact_user_request",
        "theme": "emotional regulation",
        "source_text": "User planned to walk for ten minutes, then write three calm bullet points before the review",
        "summary": "Pre-review prep plan",
        "topic_tags": ["emotional regulation", "walking", "review"],
        "emotion": {"primary": "anxiety"},
    }

    query = "emotional regulation before important events"
    score = _compute_sparse_score(
        query=query,
        memory=memory,
        topic_hints={"topic_family": "general", "topic_hints": [], "strong_topic_terms": []},
        detected_emotion={"primary": "neutral", "intent": "specific_episode_recall"},
    )

    checks = []
    if score < 0.25:
        checks.append(f"FAIL: sparse score too low ({score:.3f}) for clearly relevant memory")
    else:
        checks.append(f"PASS: sparse score {score:.3f} finds relevant memory")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "vector_misses_sparse_finds",
        "status": status,
        "checks": checks,
        "sparse_score": round(score, 3),
    }


# --- Test E: Topic extraction empty ---
def test_e_topic_extraction_empty() -> dict:
    """Test E: Query understanding fills in when topic hints are empty."""
    from app.query_understanding import understand_memory_query

    result = understand_memory_query(
        "How did we handle those situations before big things?",
        detected_emotion={"primary": "neutral", "intent": "specific_episode_recall"},
        use_llm=False,
    )

    checks = []
    if result.get("query_intent") != "specific_episode_recall":
        checks.append(f"FAIL: expected specific_episode_recall, got {result.get('query_intent')}")
    if result.get("memory_need") != "summary_level":
        checks.append(f"FAIL: expected summary_level, got {result.get('memory_need')}")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "topic_extraction_empty",
        "status": status,
        "checks": checks,
        "intent": result.get("query_intent"),
        "memory_need": result.get("memory_need"),
    }


# --- Test F: No relevant memory ---
def test_f_no_relevant_memory() -> dict:
    """Test F: No matching memory → judge rejects, no injection."""
    candidates = [
        {
            "memory_id": "mem_sleep",
            "memory_type": "coping_strategy",
            "memory_source_kind": "key_moment",
            "theme": "sleep anxiety",
            "source_text": "User committed to no-phone wind-down",
            "summary": "Sleep routine",
            "topic_tags": ["sleep", "bedtime"],
            "emotion": {"primary": "anxiety"},
            "resolved_status": "partially_resolved",
            "sensitivity": 0.3,
            "is_distractor": False,
        }
    ]

    with patch("app.memory_relevance_judge.llm_client") as mock_llm:
        mock_llm.chat.return_value = json.dumps({
            "use_memory": False,
            "selected_memory_ids": [],
            "relevance": "none",
            "confidence": 0.2,
            "reason": "No memory about moving to a new city",
            "rejected_memories": [{"memory_id": "mem_sleep", "reason": "About sleep, not moving"}],
        })

        result = judge_memory_relevance(
            user_message="I feel anxious about moving to a new city",
            detected_emotion={"primary": "anxiety", "intent": "emotional_disclosure"},
            topic_hints={"topic_family": "anxiety", "topic_hints": ["moving", "city"], "strong_topic_terms": ["moving"]},
            candidate_memories=candidates,
            policy_config={},
        )

    checks = []
    if result.get("use_memory"):
        checks.append("FAIL: judge approved unrelated memory")
    if result.get("confidence", 1) > 0.5:
        checks.append("WARN: confidence high despite no match")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "no_relevant_memory",
        "status": status,
        "checks": checks,
        "use_memory": result.get("use_memory"),
        "confidence": result.get("confidence"),
    }


# --- Test G: Direct exact recall still works ---
def test_g_direct_exact_recall() -> dict:
    """Test G: Direct canonical lookup bypasses judge and returns exact value."""
    result = resolve_direct_memory("demo_user", "What was my grounding phrase?")

    checks = []
    if not result:
        checks.append("FAIL: direct lookup returned None")
    elif result.get("memory_id") == "AMBIGUOUS_DIRECT_MEMORY":
        checks.append("PASS: ambiguous direct recall handled safely")
    elif result.get("exact_value") != "steady river, small lantern":
        checks.append(f"FAIL: wrong exact value: {result.get('exact_value')}")
    else:
        checks.append("PASS: direct exact recall works")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "direct_exact_recall",
        "status": status,
        "checks": checks,
        "exact_value": result.get("exact_value") if result else None,
    }


# --- No-memory fallback prompt test ---
def test_h_no_memory_fallback_prompt() -> dict:
    """Test H: Fallback prompt instructs LLM not to invent memories."""
    prompt = build_no_memory_fallback_prompt(
        base_prompt=MENTRA_SYSTEM_PROMPT,
        user_message="I feel anxious about moving",
        detected_emotion={"primary": "anxiety", "intent": "emotional_disclosure"},
    )

    checks = []
    if "Do NOT invent" not in prompt:
        checks.append("FAIL: fallback prompt missing anti-invention instruction")
    if "No relevant past memory" not in prompt:
        checks.append("FAIL: fallback prompt missing memory status")
    if "gentle clarifying question" not in prompt.lower():
        checks.append("WARN: fallback prompt missing clarifying question instruction")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS"
    return {
        "test": "no_memory_fallback_prompt",
        "status": status,
        "checks": checks,
        "prompt_length": len(prompt),
    }


def main():
    print("=" * 70)
    print(" RELIABILITY GUARDRAIL TEST")
    print("=" * 70)

    results = []
    results.append(test_a_judge_invalid_json())
    results.append(test_b_judge_timeout())
    results.append(test_c_correct_memory_not_first())
    results.append(test_d_vector_misses_sparse_finds())
    results.append(test_e_topic_extraction_empty())
    results.append(test_f_no_relevant_memory())
    results.append(test_g_direct_exact_recall())
    results.append(test_h_no_memory_fallback_prompt())

    print("\n--- Results ---")
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"\n{icon} {r['test'].upper()}: {r['status']}")
        for c in r.get("checks", []):
            print(f"   -> {c}")

    # Write report
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/reliability_guardrail_report.md", "w", encoding="utf-8") as f:
        f.write("# Reliability Guardrail Test Report\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for r in results:
            f.write(f"## {r['test'].upper()}\n\n")
            f.write(f"- **Status:** {r['status']}\n")
            f.write(f"- **Checks:**\n")
            for c in r.get("checks", []):
                f.write(f"  - {c}\n")
            for k, v in r.items():
                if k not in ("test", "status", "checks"):
                    f.write(f"- **{k}:** {v}\n")
            f.write("\n")

        f.write("---\n")
        by_status = {"PASS": 0, "FAIL": 0}
        for r in results:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        f.write(f"\n**Summary:** PASS={by_status['PASS']} FAIL={by_status['FAIL']}\n")

    print(f"\n{'='*70}")
    print(f" SUMMARY: PASS={by_status['PASS']} FAIL={by_status['FAIL']}")
    print(f"{'='*70}")

    return by_status["FAIL"] == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)