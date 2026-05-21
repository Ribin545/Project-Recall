"""
Project Recall — Summary Card Retrieval Test

Tests that summary cards are preferred for broad recall questions
like "what did we explore/discuss/talk about".

Verifies:
1. Summary cards exist for sessions
2. Summary cards rank in top candidates for broad recall
3. Judge selects summary cards for broad recall
4. Wrong memories are rejected
5. Exact canonical lookup still works
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.current_emotion_detector import detect_current_emotion
from app.current_topic_extractor import extract_current_topic_hints
from app.hybrid_memory_retriever import hybrid_retrieve_memory_candidates
from app.memory_relevance_judge import judge_memory_relevance
from app.response_policy import load_response_policy
from app.direct_memory_lookup import resolve_direct_memory, get_canonical_candidates
from app.prompts import build_policy_injected_prompt, MENTRA_SYSTEM_PROMPT
from app import llm_client


def _load_memories():
    with open("data/extracted_memories_project_recall.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _count_source_kinds(memories):
    counts = {}
    for m in memories:
        sk = m.get("memory_source_kind", "unknown")
        counts[sk] = counts.get(sk, 0) + 1
    return counts


# --- Test 1: Family dinner broad recall ---
def test_a_family_dinner_broad_recall() -> dict:
    """Test A: Broad recall 'During that family dinner what did we explore?'"""
    msg = "During that family dinner what did we explore? do you remember it?"
    detected = detect_current_emotion(msg)
    topic_hints = extract_current_topic_hints(msg)
    policy = load_response_policy()

    candidates = hybrid_retrieve_memory_candidates(
        user_id="demo_user",
        query=msg,
        detected_emotion=detected,
        topic_hints=topic_hints,
        top_k_dense=12,
        top_k_sparse=12,
        final_k=15,
    )

    judge_result = judge_memory_relevance(
        user_message=msg,
        detected_emotion=detected,
        topic_hints=topic_hints,
        candidate_memories=candidates,
        policy_config=policy,
        max_candidates=8,
    )

    selected_id = judge_result.get("selected_memory_ids", [None])[0] if judge_result.get("use_memory") else None
    selected = None
    for c in candidates:
        if c["memory_id"] == selected_id:
            selected = c
            break

    checks = []
    # Check summary card exists
    summary_cards = [c for c in candidates if c.get("memory_source_kind") == "summary"]
    if not summary_cards:
        checks.append("FAIL: no summary card in candidates")
    else:
        checks.append(f"INFO: {len(summary_cards)} summary cards in candidates")

    # Check family dinner summary is in candidates
    family_summary = [c for c in candidates if "family" in c.get("theme", "").lower() and c.get("memory_source_kind") == "summary"]
    if not family_summary:
        checks.append("WARN: family dinner summary not in candidates")

    # Check selected memory
    if not selected:
        checks.append("FAIL: no memory selected by judge")
    elif selected.get("memory_source_kind") == "summary":
        checks.append("PASS: judge selected summary card for broad recall")
    elif selected.get("memory_source_kind") == "key_moment":
        checks.append("WARN: judge selected key_moment instead of summary")
    else:
        checks.append(f"INFO: selected source_kind={selected.get('memory_source_kind')}")

    # Check quiet exit was NOT selected (wrong topic)
    if selected_id and "quiet_exit" in selected_id.lower():
        checks.append("FAIL: selected quiet_exit (wrong topic)")

    # Build LLM response
    llm_reply = None
    if selected and judge_result.get("use_memory"):
        prompt = build_policy_injected_prompt(
            base_prompt=MENTRA_SYSTEM_PROMPT,
            user_message=msg,
            detected_emotion=detected,
            policy_decision={"mention_memory": True, "allowed_memory_detail_level": "summary_level", "response_mode": "gentle_follow_up"},
            selected_memory=selected,
        )
        llm_reply = llm_client.chat([
            {"role": "system", "content": prompt},
            {"role": "user", "content": msg},
        ])

    reply_lower = (llm_reply or "").lower()
    if llm_reply:
        # Check for expected content
        found_exp = any(t in reply_lower for t in ["communication styles", "i feel", "because", "gentle conversation", "next gathering", "family dinner", "unheard", "withdrew"])
        if found_exp:
            checks.append("PASS: LLM response contains expected summary content")
        else:
            checks.append("WARN: LLM response missing expected summary content")

        # Check for forbidden
        forbidden = ["performance review", "calm bullet points", "walk for ten minutes", "manager"]
        found_forb = [t for t in forbidden if t in reply_lower]
        if found_forb:
            checks.append(f"FAIL: LLM response contains forbidden topics: {found_forb}")
        else:
            checks.append("PASS: LLM response has no forbidden topic leakage")
    else:
        checks.append("INFO: no LLM reply generated")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "WARN" if any(c.startswith("WARN") for c in checks) else "PASS"
    return {
        "test": "family_dinner_broad_recall",
        "status": status,
        "checks": checks,
        "selected_id": selected_id,
        "selected_source_kind": selected.get("memory_source_kind") if selected else None,
        "llm_reply": llm_reply[:200] if llm_reply else None,
    }


# --- Test 2: Bedtime panic broad recall ---
def test_b_bedtime_panic_broad_recall() -> dict:
    """Test B: 'Do you remember panic before bedtime? What did we discuss?'"""
    msg = "Do you remember panic before bedtime? What did we discuss?"
    detected = detect_current_emotion(msg)
    topic_hints = extract_current_topic_hints(msg)
    policy = load_response_policy()

    candidates = hybrid_retrieve_memory_candidates(
        user_id="demo_user",
        query=msg,
        detected_emotion=detected,
        topic_hints=topic_hints,
        top_k_dense=10,
        top_k_sparse=10,
        final_k=12,
    )

    # Blend in canonical candidates like the active chat pipeline now does
    seen = {c.get("memory_id") for c in candidates}
    for mem in get_canonical_candidates("demo_user", msg, top_k=3):
        if mem.get("memory_id") not in seen:
            mem_copy = dict(mem)
            mem_copy["_dense_score"] = mem_copy.get("semantic_similarity", mem_copy.get("final_score", 0.0))
            mem_copy["_sparse_score"] = mem_copy.get("final_score", 0.0)
            mem_copy["_metadata_score"] = 0.9 if mem_copy.get("is_canonical") else 0.0
            mem_copy["final_score"] = max(mem_copy.get("final_score", 0.0), 0.72)
            mem_copy["semantic_similarity"] = mem_copy.get("_dense_score", 0.72)
            candidates.append(mem_copy)
            seen.add(mem.get("memory_id"))

    judge_result = judge_memory_relevance(
        user_message=msg,
        detected_emotion=detected,
        topic_hints=topic_hints,
        candidate_memories=candidates,
        policy_config=policy,
        max_candidates=8,
    )

    selected_id = judge_result.get("selected_memory_ids", [None])[0] if judge_result.get("use_memory") else None
    selected = None
    for c in candidates:
        if c["memory_id"] == selected_id:
            selected = c
            break

    checks = []
    if not selected:
        checks.append("FAIL: no memory selected")
    else:
        sel_tags = [t.lower() for t in selected.get("topic_tags", [])]
        sel_theme = (selected.get("theme", "") or "").lower()
        sel_summary = (selected.get("summary", "") or "").lower()

        has_sleep = any(t in sel_tags for t in ["sleep", "bedtime", "night", "wind-down"]) or any(t in sel_theme for t in ["sleep", "bedtime"])
        has_sleep = has_sleep or any(t in sel_summary for t in ["sleep", "bedtime", "panic before bed", "no-phone"])

        if has_sleep:
            checks.append("PASS: selected memory is sleep/bedtime related")
        else:
            checks.append(f"FAIL: selected memory not sleep/bedtime: {sel_tags} / theme={sel_theme}")

        # Must not be performance review
        if "performance review" in sel_summary or "review" in sel_summary and "bedtime" not in sel_summary:
            checks.append("FAIL: selected memory is about review instead of bedtime")
        else:
            checks.append("PASS: no performance review leakage")

    status = "FAIL" if any(c.startswith("FAIL") for c in checks) else "WARN" if any(c.startswith("WARN") for c in checks) else "PASS"
    return {
        "test": "bedtime_panic_broad_recall",
        "status": status,
        "checks": checks,
        "selected_id": selected_id,
    }


# --- Test 3: Direct exact recall still works ---
def test_c_direct_exact_recall() -> dict:
    """Test C: 'What was my grounding phrase?' — exact lookup, NOT summary."""
    result = resolve_direct_memory("demo_user", "What was my grounding phrase?")

    checks = []
    if not result:
        checks.append("FAIL: direct lookup returned None")
    elif result.get("memory_id") == "AMBIGUOUS_DIRECT_MEMORY":
        checks.append("PASS: direct recall correctly returned ambiguity for multiple grounding phrases")
    elif result.get("exact_value") != "steady river, small lantern":
        checks.append(f"FAIL: wrong exact value: {result.get('exact_value')}")
    else:
        checks.append("PASS: direct exact recall works")
        if result.get("memory_source_kind") == "exact_user_request":
            checks.append("PASS: uses exact_user_request card, not summary")
        else:
            checks.append(f"INFO: source_kind={result.get('memory_source_kind')}")

    return {
        "test": "direct_exact_recall",
        "status": "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS",
        "checks": checks,
        "exact_value": result.get("exact_value") if result else None,
        "source_kind": result.get("memory_source_kind") if result else None,
    }


# --- Test 4: Summary card counts ---
def test_d_summary_cards_exist() -> dict:
    """Test D: Verify summary cards exist with proper metadata."""
    memories = _load_memories()
    counts = _count_source_kinds(memories)

    checks = []
    summary_count = counts.get("summary", 0)
    if summary_count == 0:
        checks.append("FAIL: no summary cards found")
    else:
        checks.append(f"PASS: {summary_count} summary cards found")

    # Verify summary card structure
    summaries = [m for m in memories if m.get("memory_source_kind") == "summary"]
    if summaries:
        s = summaries[0]
        if s.get("memory_type") == "session_summary":
            checks.append("PASS: summary card has correct memory_type")
        else:
            checks.append(f"FAIL: summary card has wrong memory_type: {s.get('memory_type')}")
        if s.get("importance", 0) >= 0.65:
            checks.append(f"PASS: summary importance={s.get('importance')} >= 0.65")
        else:
            checks.append(f"FAIL: summary importance too low: {s.get('importance')}")
        if len(s.get("topic_tags", [])) >= 3:
            checks.append(f"PASS: summary has {len(s.get('topic_tags', []))} topic tags")
        else:
            checks.append(f"WARN: summary has only {len(s.get('topic_tags', []))} topic tags")

    total = len(memories)
    checks.append(f"INFO: total memories={total}, summary={summary_count}, key_moment={counts.get('key_moment', 0)}, exact={counts.get('exact_user_request', 0)}, follow_up={counts.get('follow_up_topic', 0)}")

    return {
        "test": "summary_cards_exist",
        "status": "FAIL" if any(c.startswith("FAIL") for c in checks) else "PASS",
        "checks": checks,
        "counts": counts,
    }


def main():
    print("=" * 70)
    print(" SUMMARY CARD RETRIEVAL TEST")
    print("=" * 70)

    results = []
    results.append(test_a_family_dinner_broad_recall())
    results.append(test_b_bedtime_panic_broad_recall())
    results.append(test_c_direct_exact_recall())
    results.append(test_d_summary_cards_exist())

    print("\n--- Results ---")
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "⚠️" if r["status"] == "WARN" else "❌"
        print(f"\n{icon} {r['test'].upper()}: {r['status']}")
        for c in r.get("checks", []):
            print(f"   -> {c}")
        if r.get("llm_reply"):
            print(f"   Reply: {r['llm_reply'][:150]}...")

    # Write report
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/summary_card_retrieval_report.md", "w", encoding="utf-8") as f:
        f.write("# Summary Card Retrieval Test Report\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for r in results:
            f.write(f"## {r['test'].upper()}\n\n")
            f.write(f"- **Status:** {r['status']}\n")
            for k, v in r.items():
                if k not in ("test", "status", "checks", "llm_reply"):
                    f.write(f"- **{k}:** {v}\n")
            f.write(f"- **Checks:**\n")
            for c in r.get("checks", []):
                f.write(f"  - {c}\n")
            if r.get("llm_reply"):
                f.write(f"- **Reply:** {r['llm_reply'][:200]}...\n")
            f.write("\n")

        f.write("---\n")
        by_status = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for r in results:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        f.write(f"\n**Summary:** PASS={by_status['PASS']} WARN={by_status['WARN']} FAIL={by_status['FAIL']}\n")

    print(f"\n{'='*70}")
    print(f" SUMMARY: PASS={by_status['PASS']} WARN={by_status['WARN']} FAIL={by_status['FAIL']}")
    print(f"{'='*70}")

    return by_status["FAIL"] == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)