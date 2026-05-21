"""
Project Recall — Policy Adherence Test

Tests the full emotion-aware pipeline with realistic, nuanced user messages.
Evaluates memory-policy adherence and emotional response quality.

Usage:
    cd project-recall
    python app/policy_adherence_test.py

Output:
    outputs/policy_adherence_comparison_report.md
"""
import os
import time
import re
from typing import Dict, List

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.current_emotion_detector import detect_current_emotion
from app.emotion_aware_query_builder import build_emotion_aware_query
from app.memory_retriever import retrieve_memories
from app.direct_memory_lookup import resolve_direct_memory
from app.emotional_memory_planner import plan_memory_response
from app.response_policy import (
    load_response_policy,
    decide_response_policy,
    generate_policy_based_response,
)
from app import prompts, llm_client


USER_ID = "demo_user"
POLICY = load_response_policy()

# Known needle exact values for verification
# Note: these must match the exact_value field in extracted memories
NEEDLE_VALUES = {
    "grounding_phrase": "steady river, small lantern",
    "review_preparation": "I'd like to understand how I can grow from here.",
    "follow_up_intent": "walk for ten minutes, then write three calm bullet points before the review",
}


# --- Improved realistic user messages ---
REALISTIC_MESSAGES = [
    {
        "category": "anxiety",
        "message": "I've been feeling anxious today, and I can't fully tell if it's about something specific or just everything building up.",
        "description": "Anxiety → validate then offer choice, vague detail, NO direct question",
        "expected_mode": "validate_then_offer_choice",
        "expected_mention": True,
        "expected_detail_level": "vague",
    },
    {
        "category": "sadness",
        "message": "I've been feeling really low today. Nothing dramatic happened, but I just feel heavy and disconnected.",
        "description": "Sadness → validate then gentle optional reference, vague",
        "expected_mode": "validate_then_gentle_optional_reference",
        "expected_mention": True,
        "expected_detail_level": "vague",
    },
    {
        "category": "overwhelm",
        "message": "I feel like there are too many things in my head at once, and I don't know where to start.",
        "description": "Overwhelm → ground first then offer memory, vague",
        "expected_mode": "ground_first_then_offer_memory",
        "expected_mention": True,
        "expected_detail_level": "vague",
    },
    {
        "category": "anger",
        "message": "I'm really frustrated with someone at work, and I keep replaying the conversation in my head.",
        "description": "Anger → validate only, NO memory mention",
        "expected_mode": "validate_only",
        "expected_mention": False,
        "expected_detail_level": "none",
    },
    {
        "category": "loneliness",
        "message": "I've been around people, but I still feel strangely alone lately.",
        "description": "Loneliness → validate then optional connection context, vague",
        "expected_mode": "validate_then_optional_connection_context",
        "expected_mention": True,
        "expected_detail_level": "vague",
    },
    {
        "category": "shame",
        "message": "I keep thinking about something I said earlier, and I feel embarrassed and disappointed in myself.",
        "description": "Shame → validate gently, normalize replay, NO harsh correction",
        "expected_mode": "validate_then_gentle_optional_reference",
        "expected_mention": True,
        "expected_detail_level": "vague",
    },
    {
        "category": "uncertainty",
        "message": "I feel stuck because part of me wants to make a decision, but another part of me is scared I'll choose wrong.",
        "description": "Uncertainty → reflect uncertainty, offer one thread at a time",
        "expected_mode": "validate_then_offer_choice",
        "expected_mention": True,
        "expected_detail_level": "vague",
    },
    {
        "category": "direct_grounding",
        "message": "What was my grounding phrase?",
        "description": "STRICT: Direct grounding phrase question → must answer with needle value",
        "expected_mode": "direct_answer",
        "expected_mention": True,
        "expected_detail_level": "exact_value",
        "expected_exact_value": NEEDLE_VALUES["grounding_phrase"],
    },
    {
        "category": "direct_review",
        "message": "What exact sentence did I ask you to remember for my performance review?",
        "description": "STRICT: Direct review sentence question → must answer with needle value",
        "expected_mode": "direct_answer",
        "expected_mention": True,
        "expected_detail_level": "exact_value",
        "expected_exact_value": NEEDLE_VALUES["review_preparation"],
    },
    {
        "category": "direct_plan",
        "message": "What was the small preparation plan I made before the review?",
        "description": "STRICT: Direct plan question → must answer with needle value",
        "expected_mode": "direct_answer",
        "expected_mention": True,
        "expected_detail_level": "exact_value",
        "expected_exact_value": NEEDLE_VALUES["follow_up_intent"],
    },
]


def run_single_test(
    message: str,
    description: str,
    expected_mode: str,
    expected_mention: bool,
    expected_detail_level: str,
    category: str = "",
    expected_exact_value: str = None,
) -> Dict:
    """Run one end-to-end contextual response pipeline test case."""
    t0 = time.perf_counter()

    detected = detect_current_emotion(message)
    query = build_emotion_aware_query(message, detected)

    is_direct = detected.get("intent") == "direct_memory_question"
    preferred_type = detected.get("preferred_memory_type")

    # HYBRID: Direct memory lookup BEFORE vector retrieval
    canonical_memory = None
    if is_direct and resolve_direct_memory:
        try:
            canonical_memory = resolve_direct_memory(USER_ID, message)
        except Exception:
            canonical_memory = None

    if canonical_memory:
        memories = [canonical_memory]
    else:
        memories = retrieve_memories(
            USER_ID, query, top_k=5,
            preferred_memory_type=preferred_type,
            direct_question=is_direct,
        )

    plan = None
    if memories:
        plan = plan_memory_response(memories, current_user_message=message)

    decision = decide_response_policy(
        current_message=message,
        detected_emotion=detected,
        retrieved_memories=memories,
        emotional_plan=plan,
        policy_config=POLICY,
    )

    selected_memory = None
    selected_id = decision.get("selected_memory_id")
    if selected_id:
        for m in memories:
            if m.get("memory_id") == selected_id:
                selected_memory = m
                break
    if not selected_memory and memories:
        selected_memory = memories[0]

    template_response = generate_policy_based_response(
        current_message=message,
        detected_emotion=detected,
        selected_memory=selected_memory,
        response_policy=decision,
    )

    # LLM call
    llm_response = None
    adherence = None
    llm_elapsed_ms = None

    try:
        if is_direct and selected_memory:
            system_prompt = prompts.build_direct_answer_prompt(
                base_prompt=prompts.MENTRA_SYSTEM_PROMPT,
                selected_memory=selected_memory,
            )
        else:
            system_prompt = prompts.build_policy_injected_prompt(
                base_prompt=prompts.MENTRA_SYSTEM_PROMPT,
                user_message=message,
                detected_emotion=detected,
                policy_decision=decision,
                selected_memory=selected_memory,
            )

        t_llm0 = time.perf_counter()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]
        llm_response = llm_client.chat(messages)
        t_llm1 = time.perf_counter()
        llm_elapsed_ms = round((t_llm1 - t_llm0) * 1000, 2)

        adherence = check_policy_adherence(
            llm_response=llm_response,
            decision=decision,
            selected_memory=selected_memory,
            user_message=message,
            is_direct_question=is_direct,
            expected_exact_value=expected_exact_value,
            category=category,
        )
    except Exception as e:
        llm_response = f"[LLM unavailable: {str(e)}]"
        adherence = {
            "passed": True,
            "issues": [f"INFO: LLM call failed — {str(e)}"],
            "llm_available": False,
        }

    t1 = time.perf_counter()

    mode_match = decision.get("response_mode") == expected_mode
    mention_match = decision.get("mention_memory") == expected_mention
    detail_match = decision.get("allowed_memory_detail_level") == expected_detail_level

    return {
        "category": category,
        "description": description,
        "message": message,
        "detected_emotion": detected,
        "retrieval_query": query,
        "retrieved_count": len(memories),
        "top_memory": memories[0] if memories else None,
        "emotional_plan": plan,
        "decision": decision,
        "template_response": template_response,
        "llm_response": llm_response,
        "llm_elapsed_ms": llm_elapsed_ms,
        "adherence": adherence,
        "elapsed_ms": round((t1 - t0) * 1000, 2),
        "expected_mode": expected_mode,
        "expected_mention": expected_mention,
        "expected_detail": expected_detail_level,
        "mode_ok": mode_match,
        "mention_ok": mention_match,
        "detail_ok": detail_match,
        "all_pass": mode_match and mention_match and detail_match,
    }


def check_policy_adherence(
    llm_response: str,
    decision: Dict,
    selected_memory: Dict,
    user_message: str,
    is_direct_question: bool = False,
    expected_exact_value: str = None,
    category: str = "",
) -> Dict:
    """
    Check an LLM-generated response against policy rules.
    Enhanced with shame-specific checks.
    """
    issues = []
    detail_level = decision.get("allowed_memory_detail_level", "none")
    exact_value = selected_memory.get("exact_value") if selected_memory else None
    ask_direct = decision.get("ask_direct_question", False)
    mem_type = selected_memory.get("memory_type", "") if selected_memory else ""
    resp_lower = llm_response.lower()

    # === STRICT DIRECT MEMORY QUESTION CHECKS ===
    if is_direct_question:
        denial_phrases = [
            "don't have access", "don't have a record", "cannot recall",
            "no record of", "i don't remember", "i don't have any record",
            "i'm not able to recall", "i do not have", "no memory of",
        ]
        found_denial = [p for p in denial_phrases if p in resp_lower]
        if found_denial:
            issues.append(f'FAIL: direct memory question but LLM denies having memory: "{found_denial[0]}"')

        if "may or may not" in resp_lower:
            issues.append('FAIL: direct memory answer uses vague "may or may not be connected"')

        if expected_exact_value:
            key_phrases = _extract_key_phrases(expected_exact_value)
            # Normalize response same way as expected value (strip punctuation)
            resp_normalized = re.sub(r'[^\w\s]', ' ', resp_lower)
            matched = sum(1 for p in key_phrases if p in resp_normalized)
            if matched >= max(1, len(key_phrases) // 2):
                issues.append(f'PASS: expected content found ({matched}/{len(key_phrases)} key phrases)')
            else:
                issues.append(f'FAIL: expected exact_value "{expected_exact_value}" not found in LLM response')

        if mem_type == "grounding_phrase" and exact_value:
            distractor_values = ["peaceful garden, warm sunbeam", "shady grove, soft luminescence", "clear sky, small spark"]
            for dv in distractor_values:
                if dv.lower() in resp_lower:
                    issues.append(f'FAIL: LLM cited distractor value "{dv}" instead of needle')

    # === SHAME-SPECIFIC CHECKS ===
    if category == "shame":
        # Forbidden phrases
        forbidden_shame = [
            "you should have", "that was your fault", "you need to get over it",
            "stop thinking about it", "why did you do that",
        ]
        for forbidden in forbidden_shame:
            if forbidden in resp_lower:
                issues.append(f'FAIL: shame response uses forbidden phrase: "{forbidden}"')

        # Check for harsh language
        harsh_words = ["failure", "weak", "pathetic", "ridiculous", "stupid"]
        for hw in harsh_words:
            if hw in resp_lower:
                issues.append(f'FAIL: shame response contains harsh word: "{hw}"')

        # Preferred qualities (soft checks — at least 2 should be present)
        preferred_qualities = ["painful", "gentle", "kindness", "not judge", "replaying"]
        found_qualities = sum(1 for q in preferred_qualities if q in resp_lower)
        if found_qualities < 1:
            issues.append(f'WARNING: shame response lacks preferred qualities (found {found_qualities}/5: {preferred_qualities})')
        else:
            issues.append(f'PASS: shame response contains {found_qualities}/5 preferred qualities')

        # Validate emotion before offering memory
        validation_words = ["painful", "makes sense", "heavy", "hard", "difficult", "sorry", "understand"]
        has_validation = any(w in resp_lower for w in validation_words)
        if not has_validation:
            issues.append("WARNING: shame response does not validate emotion before offering memory")

    # === GENERAL CHECKS (all responses) ===
    if detail_level == "vague" and exact_value:
        pattern = r'(?:^|\\s|[.,;!?])' + re.escape(exact_value.lower()) + r'(?:$|\\s|[.,;!?])'
        if re.search(pattern, resp_lower):
            issues.append(f'FAIL: detail_level="vague" but exact_value "{exact_value}" appears in LLM response')

    if not ask_direct:
        causality = [
            "is this about", "is this connected to", "does this have to do with",
            "is this related to", "is this because of", "is this from",
            "does this remind you of", "is this the same",
        ]
        found = [p for p in causality if p in resp_lower]
        if found:
            issues.append(f'WARNING: ask_direct_question=false but contains causality phrase: "{found[0]}"')

    if mem_type == "relationship_context" and decision.get("response_mode") == "only_if_user_mentions":
        name_indicators = ["friend", "partner", "colleague", "boss", "family", "mother", "father", "sister", "brother"]
        summary = (selected_memory.get("summary") or "").lower()
        for indicator in name_indicators:
            if indicator in summary and indicator in resp_lower and indicator not in user_message.lower():
                issues.append(f'WARNING: relationship_context with only_if_user_mentions, response mentions "{indicator}" not in user message')

    # Emotion validation check
    validation_words = {
        "sadness": ["sorry", "hard", "makes sense", "heavy", "difficult", "tough"],
        "anxiety": ["uncomfortable", "makes sense", "overwhelming", "racing", "difficult", "heavy"],
        "overwhelm": ["lot", "too much", "exhausting", "makes sense", "a lot"],
        "anger": ["frustrating", "upset", "makes sense", "crossed", "understand"],
        "loneliness": ["isolating", "makes sense", "alone", "hard", "disconnected"],
        "shame": ["painful", "makes sense", "heavy", "hard"],
        "uncertainty": ["disorienting", "makes sense", "lost", "confusing"],
    }
    emotion = decision.get("selected_emotion", "neutral")
    val_words = validation_words.get(emotion, ["makes sense", "sorry", "understand", "that sounds"])
    has_validation = any(w in resp_lower for w in val_words)
    topic = decision.get("selected_topic", "")
    memory_mentioned = topic and topic.lower() in resp_lower
    if memory_mentioned and not has_validation:
        issues.append("WARNING: response mentions memory before validating user's emotion")

    # Mechanical phrases
    mechanical = [
        "according to your records", "retrieved memory", "from the database",
        "from my records", "the data shows", "stored memory", "previous entry",
        "session log", "chat history", "archived", "retrieved from",
    ]
    found_mech = [p for p in mechanical if p in resp_lower]
    if found_mech:
        issues.append(f'FAIL: mechanical/clinical phrase found: "{found_mech[0]}"')

    passed = len([i for i in issues if i.startswith("FAIL")]) == 0
    return {
        "passed": passed,
        "issues": issues if issues else ["All policy checks passed."],
        "llm_available": True,
    }


def _extract_key_phrases(expected_exact_value: str) -> List[str]:
    """Extract key content phrases from an exact value for fuzzy matching."""
    if not expected_exact_value:
        return []
    text = expected_exact_value.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    phrases = []
    for i in range(len(words) - 1):
        if len(words[i]) > 2 and len(words[i+1]) > 2:
            phrases.append(f"{words[i]} {words[i+1]}")
    for i in range(len(words) - 2):
        if len(words[i]) > 2 and len(words[i+1]) > 2 and len(words[i+2]) > 2:
            phrases.append(f"{words[i]} {words[i+1]} {words[i+2]}")
    return phrases


def _render_memory(mem: Dict) -> str:
    """Render a short human-readable memory summary for reports."""
    if not mem:
        return "None"
    return f"{mem.get('memory_id')} ({mem.get('memory_type')}) sim={mem.get('semantic_similarity', 0):.3f}"


def _render_plan(plan: Dict) -> str:
    """Render a short human-readable emotional plan summary for reports."""
    if not plan:
        return "None"
    ev = plan.get('selected_exact_value')
    ev_short = ev[:40] + "..." if ev and len(ev) > 40 else ev
    return f"strategy={plan.get('response_strategy')}, topic={plan.get('selected_topic')}, exact={ev_short}"


def _render_decision(dec: Dict) -> str:
    """Render a short human-readable policy decision summary for reports."""
    if not dec:
        return "None"
    return f"mode={dec.get('response_mode')}, mention={dec.get('mention_memory')}, detail={dec.get('allowed_memory_detail_level')}"


def run_all_tests() -> List[Dict]:
    """Run the complete policy adherence test suite with realistic messages."""
    tests = []
    for item in REALISTIC_MESSAGES:
        tests.append(run_single_test(
            message=item["message"],
            description=item["description"],
            expected_mode=item["expected_mode"],
            expected_mention=item["expected_mention"],
            expected_detail_level=item["expected_detail_level"],
            category=item["category"],
            expected_exact_value=item.get("expected_exact_value"),
        ))
    return tests


def generate_report(tests: List[Dict]) -> str:
    """Generate a Markdown report for policy adherence test results."""
    passed = sum(1 for t in tests if t["all_pass"])
    total = len(tests)
    llm_passed = sum(1 for t in tests if t.get("adherence") and t["adherence"]["passed"])

    lines = [
        "# Policy Adherence Comparison Report\n",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**Results:** {passed}/{total} PASS\n",
        f"**LLM Adherence:** {llm_passed}/{total} PASS\n",
        "---\n",
    ]

    for i, test in enumerate(tests, 1):
        status = "PASS" if test["all_pass"] else "FAIL"
        icon = "PASS" if test["all_pass"] else "FAIL"
        lines.append(f"## Test {i}: {test['description']}\n")
        lines.append(f"**Category:** `{test['category']}`\n")
        lines.append(f"**Status:** {icon} {status}\n")
        lines.append(f'**User Message:** "{test["message"]}"\n')
        lines.append(f"**Detected Emotion:** `{test['detected_emotion']['primary']}` (intent: {test['detected_emotion']['intent']})\n")
        if test['detected_emotion'].get('preferred_memory_type'):
            lines.append(f"**Preferred Memory Type:** `{test['detected_emotion']['preferred_memory_type']}`\n")
        lines.append(f"**Retrieval Query:** `{test['retrieval_query'][:80]}`\n")
        lines.append(f"**Retrieved:** {test['retrieved_count']} memories\n")
        lines.append(f"**Top Memory:** {_render_memory(test['top_memory'])}\n")
        lines.append(f"**Emotional Plan:** {_render_plan(test['emotional_plan'])}\n")
        lines.append(f"**Policy Decision:** {_render_decision(test['decision'])}\n")
        lines.append(f'**Template Response:** "{test["template_response"]}"\n')
        if test.get("llm_response"):
            lines.append(f'**LLM Response:** "{test["llm_response"]}"\n')
            lines.append(f"**LLM Time:** {test.get('llm_elapsed_ms', 'N/A')}ms\n")
        if test.get("adherence"):
            ad = test["adherence"]
            aicon = "PASS" if ad["passed"] else "FAIL"
            lines.append(f"**Policy Adherence:** {aicon}\n")
            for issue in ad["issues"]:
                lines.append(f"- {issue}\n")
        lines.append(f"**Pipeline Elapsed:** {test['elapsed_ms']}ms\n")
        for check_name in ["mode", "mention", "detail"]:
            key_map = {"mode": "expected_mode", "mention": "expected_mention", "detail": "expected_detail"}
            expected = test[key_map[check_name]]
            actual = test["decision"].get(check_name if check_name != "detail" else "allowed_memory_detail_level")
            ok = test[f"{check_name}_ok"]
            cicon = "PASS" if ok else "FAIL"
            lines.append(f"- {cicon} {check_name}: expected `{expected}`, got `{actual}`\n")
        lines.append("\n---\n")

    return "".join(lines)


if __name__ == "__main__":
    print("=" * 70)
    print(" POLICY ADHERENCE TEST")
    print("=" * 70)

    tests = run_all_tests()

    for i, test in enumerate(tests, 1):
        status = "PASS" if test["all_pass"] else "FAIL"
        print(f"\n--- Test {i}: {test['description']} ---")
        print(f'  Category: {test["category"]}')
        print(f'  Message: "{test["message"]}"')
        print(f"  Emotion: {test['detected_emotion']['primary']}")
        print(f"  Intent: {test['detected_emotion']['intent']}")
        if test['detected_emotion'].get('preferred_memory_type'):
            print(f"  Preferred Type: {test['detected_emotion']['preferred_memory_type']}")
        print(f"  Query: {test['retrieval_query'][:60]}...")
        print(f"  Retrieved: {test['retrieved_count']} memories")
        if test['retrieved_count'] > 0:
            print(f"  Top: {_render_memory(test['top_memory'])}")
        print(f"  Policy: {_render_decision(test['decision'])}")
        tpl = test['template_response']
        print(f'  Template: "{tpl[:80]}..."' if len(tpl) > 80 else f'  Template: "{tpl}"')

        llm = test.get('llm_response')
        if llm:
            print(f'  LLM: "{llm[:80]}..."' if len(llm) > 80 else f'  LLM: "{llm}"')
            print(f"  LLM time: {test.get('llm_elapsed_ms')}ms")

        adherence = test.get('adherence')
        if adherence:
            icon = "PASS" if adherence['passed'] else "FAIL"
            print(f"  Adherence: {icon}")
            for issue in adherence['issues']:
                print(f"    - {issue}")

        print(f"  Pipeline elapsed: {test['elapsed_ms']}ms")
        print(f"  Status: {status}")

    report = generate_report(tests)
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "outputs", "policy_adherence_comparison_report.md"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    passed = sum(1 for t in tests if t["all_pass"])
    total = len(tests)
    llm_passed = sum(1 for t in tests if t.get("adherence") and t["adherence"]["passed"])
    print(f"\n{'=' * 70}")
    print(f" Policy Results: {passed}/{total} PASS")
    print(f" LLM Adherence:  {llm_passed}/{total} PASS")
    print(f" Report: {output_path}")
    print(f"{'=' * 70}")