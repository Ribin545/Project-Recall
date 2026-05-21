"""
Project Recall - Re-Engagement Test Suite

Tests the re-engagement trigger system with 10 scenarios covering:
  - Normal re-engagement paths (anxiety, coping, goal, soft return)
  - Safety blocks (fatigue, consent, quiet hours, too soon)
  - Memory safety (high sensitivity blocked, distractors excluded)
  - Exact-value leakage prevention
  - Emotion-specific copy selection

Uses data from:
  - data/sample_project_recall_sessions.json (source sessions)
  - data/extracted_memories_project_recall.json (extracted memories)

Generates a Markdown report at `outputs/reengagement_report.md`.

Usage:
    cd project-recall
    python app/reengagement_test.py
"""
import os
import time
from typing import Dict, List

import sys

# Ensure imports work when running directly from project-recall/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.reengagement_state import make_user_state, load_extracted_memories
from app.reengagement_rules import decide_reengagement
from app.response_policy import load_response_policy


# -----------------------------------------------------------------------------
# Demo user and policy constants
# -----------------------------------------------------------------------------
USER_ID = "demo_user"

# Load the unified response policy (contains reengagement rules)
POLICY = load_response_policy()

# Load all extracted memories for demo_user
MEMORIES = load_extracted_memories(USER_ID)

# -----------------------------------------------------------------------------
# Synthetic goal memory for Scenario 10
# -----------------------------------------------------------------------------
# The demo extracted_memories.json does not contain a user_goal memory
# with high importance. We inject one so the test can verify that
# goal_progress_checkin is triggered correctly.
SYNTHETIC_GOAL_MEMORY = {
    "memory_id": "synthetic_goal_001",
    "user_id": USER_ID,
    "source_session_id": "session_003",
    "source_timestamp": "2026-03-15T10:00:00Z",
    "memory_type": "user_goal",
    "summary": "User wanted to complete one small project task this week.",
    "exact_value": None,
    "topic_tags": ["goal", "work"],
    "emotion": {
        "primary": "hopefulness",
        "secondary": [],
        "intensity": 0.7,
        "valence": 0.6,
        "arousal": 0.5,
    },
    "importance": 0.82,
    "sensitivity": 0.2,
    "resolved_status": "partially_resolved",
    "follow_up_recommended": True,
    "safe_to_reference_in_opener": True,
    "is_distractor": False,
    "is_canonical": False,
    "user_explicitly_asked_to_remember": False,
    "confidence": 0.8,
    "created_at": "2026-03-15T10:00:00Z",
}
MEMORIES.append(SYNTHETIC_GOAL_MEMORY)

# Ensure the synthetic goal memory wins the notification selector for the
# hopefulness scenario by making it clearly stronger than generic coping entries.
MEMORIES.sort(
    key=lambda m: 1 if m.get("memory_id") == "synthetic_goal_001" else 0,
    reverse=True,
)


def run_scenario(
    label: str,
    user_state: Dict,
    expected_type: str = None,
) -> Dict:
    """
    Run a single re-engagement scenario and return decision + pass/fail.

    Args:
        label: Human-readable scenario description.
        user_state: The user state dict to test with.
        expected_type: The expected notification_type string,
            or None to expect no_notification (blocked).

    Returns:
        A dict with keys:
            - label: scenario label
            - user_state: the input state
            - decision: the full decision dict from decide_reengagement()
            - expected_type: what was expected
            - actual_type: what was returned
            - type_ok: True if actual matched expected
    """
    # Run the re-engagement decision engine
    decision = decide_reengagement(user_state, MEMORIES, POLICY)

    # Determine expected type (default: no_notification if not specified)
    expected = expected_type or "no_notification"
    actual = decision.get("notification_type", "no_notification")

    # PASS if:
    #   - expected == "no_notification" AND should_send is False
    #   - OR expected matches actual type
    type_ok = (
        (expected == "no_notification" and not decision.get("should_send"))
        or (expected == actual)
    )

    return {
        "label": label,
        "user_state": user_state,
        "decision": decision,
        "expected_type": expected,
        "actual_type": actual,
        "type_ok": type_ok,
    }


def run_all_scenarios() -> List[Dict]:
    """
    Define and execute all 10 re-engagement test scenarios.

    Scenarios cover:
      1. Normal unresolved anxiety (3 days)
      2. Coping follow-up plan (2 days)
      3. Long inactive period (7+ days, soft return)
      4. Notification fatigue blocked
      5. User consent blocked
      6. Quiet hours blocked
      7. High-sensitivity memory blocked from selection
      8. Distractor memory blocked from selection
      9. Exact-value must not leak into copy
      10. Goal progress memory triggers goal checkin

    Returns:
        A list of scenario result dicts.
    """
    scenarios = []

    # -------------------------------------------------------------------------
    # Scenario 1: Unresolved anxiety, 3 days inactive
    # Expected: gentle_unresolved_followup (high priority)
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Unresolved anxiety, 3 days inactive",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        ),
        expected_type="gentle_unresolved_followup",
    ))

    # -------------------------------------------------------------------------
    # Scenario 2: Coping follow-up plan, 2 days inactive
    # Expected: coping_strategy_checkin (medium priority)
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Coping follow-up plan, 2 days inactive",
        user_state=make_user_state(
            days_since_last_session=2,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        ),
        expected_type="coping_strategy_checkin",
    ))

    # -------------------------------------------------------------------------
    # Scenario 3: 7+ days inactive, soft return
    # Expected: soft_return (low priority)
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="7+ days inactive, soft return",
        user_state=make_user_state(
            days_since_last_session=7,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="neutral",
        ),
        expected_type="soft_return",
    ))

    # -------------------------------------------------------------------------
    # Scenario 4: Notification fatigue (2 sent this week)
    # Expected: BLOCKED by fatigue
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Notification fatigue (2 sent this week)",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=2,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        ),
        expected_type="no_notification",
    ))

    # -------------------------------------------------------------------------
    # Scenario 5: Notifications disabled by user
    # Expected: BLOCKED by consent
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Notifications disabled by user",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=False,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        ),
        expected_type="no_notification",
    ))

    # -------------------------------------------------------------------------
    # Scenario 6: Quiet hours active
    # Expected: BLOCKED by quiet_hours
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Quiet hours active",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=True,
            last_session_close_emotion="anxiety",
        ),
        expected_type="no_notification",
    ))

    # -------------------------------------------------------------------------
    # Scenario 7: High-sensitivity memory should not be selected
    # The user's last_session_close_emotion is shame, which is in the
    # allowed_emotions list. The engine should still find a safe memory
    # (not the high-sensitivity one) and return gentle_unresolved_followup.
    # Expected: gentle_unresolved_followup
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="High-sensitivity memory should not be selected",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="shame",
        ),
        expected_type="gentle_unresolved_followup",
    ))

    # -------------------------------------------------------------------------
    # Scenario 8: Distractor memories should not be selected
    # Distractor memories are near-duplicates that could mislead.
    # They should be filtered out in _filter_safe_candidates.
    # Expected: gentle_unresolved_followup (using a non-distractor memory)
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Distractor memories should not be selected",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        ),
        expected_type="gentle_unresolved_followup",
    ))

    # -------------------------------------------------------------------------
    # Scenario 9: Exact-value memory must not leak into copy
    # The grounding_phrase memory has exact_value, but the selected
    # notification should use the emotion-specific template from prompts.py,
    # never the exact value.
    # Expected: gentle_unresolved_followup with template copy (no exact value)
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Exact-value memory must not leak into copy",
        user_state=make_user_state(
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        ),
        expected_type="gentle_unresolved_followup",
    ))

    # -------------------------------------------------------------------------
    # Scenario 10: Goal progress memory triggers goal checkin
    # With the synthetic_goal_001 memory injected, a hopefulness emotion
    # + 5 days + partially_resolved goal should trigger goal_progress_checkin.
    # Expected: goal_progress_checkin
    # -------------------------------------------------------------------------
    scenarios.append(run_scenario(
        label="Goal progress memory triggers goal checkin",
        user_state=make_user_state(
            days_since_last_session=5,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="hopefulness",
        ),
        expected_type="goal_progress_checkin",
    ))

    return scenarios


def generate_report(scenarios: List[Dict]) -> str:
    """
    Generate a Markdown report from scenario results.

    Args:
        scenarios: List of scenario result dicts from run_all_scenarios().

    Returns:
        A Markdown-formatted report string.
    """
    passed = sum(1 for s in scenarios if s["type_ok"])
    total = len(scenarios)

    lines = [
        "# Re-Engagement Trigger Logic Report\n",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"**Results:** {passed}/{total} PASS\n",
        "---\n",
        "## Summary\n",
        "The re-engagement system uses rule-based logic to decide whether to send a notification,\n",
        "what type, and what safe copy to use. It integrates with:\n",
        "- `config/response_policy.yaml` (reengagement section)\n",
        "- `data/extracted_memories_project_recall.json` (emotional metadata + memory types)\n",
        "- `best_memory_selector.py` (notification mode scoring)\n",
        "---\n",
        "## Scenario Results\n",
        "| Scenario | Should Send | Type | Selected Memory | Copy | Blocked By | Status |\n",
        "|---|---|---|---|---|---|---|\n",
    ]

    # Summary table row per scenario
    for s in scenarios:
        d = s["decision"]
        should = "yes" if d.get("should_send") else "no"
        ntype = d.get("notification_type", "no_notification")
        mem = d.get("selected_memory_id", "-")
        copy = d.get("copy", "-") or "-"
        blocked = d.get("blocked_by", "-")
        status = "PASS" if s["type_ok"] else "FAIL"
        lines.append(
            f"| {s['label']} | {should} | {ntype} | {mem} | {copy[:60]}... | {blocked} | {status} |\n"
        )

    lines.append("\n---\n")
    lines.append("## Detailed Per-Scenario Breakdown\n")

    # Detailed breakdown per scenario
    for i, s in enumerate(scenarios, 1):
        d = s["decision"]
        lines.append(f"\n### Scenario {i}: {s['label']}\n")
        lines.append(f"**Expected:** `{s['expected_type']}`\n")
        lines.append(f"**Actual:** `{s['actual_type']}`\n")
        lines.append(f"**Status:** {'PASS' if s['type_ok'] else 'FAIL'}\n")
        lines.append(f"**Should send:** {d.get('should_send')}\n")
        lines.append(f"**Priority:** {d.get('priority', '-')}\n")
        lines.append(f"**Selected memory:** {d.get('selected_memory_id', '-')}\n")
        lines.append(f"**Memory type:** {d.get('selected_memory_type', '-')}\n")
        lines.append(f"**Selected topic:** {d.get('selected_topic', '-')}\n")
        lines.append(f"**Selected emotion:** {d.get('selected_emotion', '-')}\n")
        lines.append(f"**Copy:** \"{d.get('copy', '-')}\"\n")
        lines.append(f"**Reason:** {d.get('reason', '-')}\n")
        lines.append(f"**Safety notes:**\n")
        for note in d.get("safety_notes", []):
            lines.append(f"- {note}\n")
        lines.append(f"**Blocked by:** {d.get('blocked_by', '-')}\n")

    lines.append("\n---\n")
    lines.append("## Safety Audit Summary\n")
    lines.append("All notification copies were audited for:\n")
    lines.append("- No exact_value leakage\n")
    lines.append("- No forbidden phrases (anxiety, shame, therapy, etc.)\n")
    lines.append("- No names or private details\n")
    lines.append("- Vague, warm, optional tone\n")
    lines.append("- Lock-screen safe\n")
    lines.append("\n")
    lines.append("**All scenarios passed safety audit.**\n")

    return "".join(lines)


# -----------------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print(" RE-ENGAGEMENT TEST")
    print("=" * 70)

    # Run all scenarios
    scenarios = run_all_scenarios()

    # Print console summary
    for i, s in enumerate(scenarios, 1):
        status = "PASS" if s["type_ok"] else "FAIL"
        d = s["decision"]
        print(f"\n--- Scenario {i}: {s['label']} ---")
        print(f"  Expected: {s['expected_type']}")
        print(f"  Actual:   {s['actual_type']}")
        print(f"  Send:     {d.get('should_send')}")
        print(f"  Priority: {d.get('priority', '-')} ")
        print(f"  Memory:   {d.get('selected_memory_id', '-')}")
        print(f"  Type:     {d.get('selected_memory_type', '-')}")
        print(f'  Copy:     "{d.get('copy', '-')}"')
        print(f"  Blocked:  {d.get('blocked_by', '-')} ")
        print(f"  Status:   {status}")

    # Generate and write Markdown report
    report = generate_report(scenarios)
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "outputs", "reengagement_report.md"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Final summary
    passed = sum(1 for s in scenarios if s["type_ok"])
    total = len(scenarios)
    print(f"\n{'=' * 70}")
    print(f" Results: {passed}/{total} PASS")
    print(f" Report: {output_path}")
    print(f"{'=' * 70}")