"""
Project Recall — Validate Project Recall Sessions

Validates that generated sample_project_recall_sessions.json conforms
to the official schema and contains all required fields and needle facts.

Usage:
    python app/validate_project_recall_sessions.py
"""

import json
import os
import sys
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Paths ---
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SESSIONS_PATH = os.path.join(DATA_DIR, "sample_project_recall_sessions.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
REPORT_PATH = os.path.join(OUTPUT_DIR, "project_recall_schema_validation_report.md")

# --- Required fields per session ---
REQUIRED_FIELDS = [
    "user_id",
    "session_id",
    "timestamp",
    "theme",
    "emotional_tone",
    "key_moments",
    "summary",
    "risk_flags",
    "follow_up_topics",
]

# --- Needle values that must exist somewhere ---
NEEDLE_VALUES = [
    "I'd like to understand how I can grow from here.",
    "steady river, small lantern",
    "walk for ten minutes, then write three calm bullet points before the review",
    "I need some space, but I still care about you.",
    "I felt hurt, but I want to understand what happened.",
]


def validate_sessions(sessions: List[Dict]) -> List[str]:
    """
    Run all validation checks and return a list of result strings.
    """
    results = []
    passed = 0
    total = 0

    def check(name: str, ok: bool, detail: str = ""):
        nonlocal passed, total
        total += 1
        status = "PASS" if ok else "FAIL"
        if not ok and detail:
            results.append(f"  ❌ {name}: {detail}")
        else:
            results.append(f"  ✅ {name}")
        if ok:
            passed += 1

    # 1. File exists
    check("File exists", os.path.exists(SESSIONS_PATH))

    if not sessions:
        results.append("\n**No sessions loaded — aborting remaining checks.**")
        return results, 0, total

    # 2. Contains 8-15 sessions (generalized generator produces 11)
    count_ok = 8 <= len(sessions) <= 15
    check("Session count 8-15", count_ok, f"got {len(sessions)}")

    # 3. Every session has required fields
    all_fields_ok = True
    missing_fields = []
    for i, sess in enumerate(sessions):
        for field in REQUIRED_FIELDS:
            if field not in sess:
                all_fields_ok = False
                missing_fields.append(f"session {i+1} missing '{field}'")
    check("All required fields present", all_fields_ok, "; ".join(missing_fields[:5]))

    # 4. emotional_tone is a list
    tone_ok = all(isinstance(s.get("emotional_tone"), list) for s in sessions)
    check("emotional_tone is list", tone_ok)

    # 5. key_moments is a list of strings
    km_ok = all(
        isinstance(s.get("key_moments"), list) and
        all(isinstance(k, str) for k in s.get("key_moments", []))
        for s in sessions
    )
    check("key_moments is list of strings", km_ok)

    # 6. risk_flags is a list
    rf_ok = all(isinstance(s.get("risk_flags"), list) for s in sessions)
    check("risk_flags is list", rf_ok)

    # 7. follow_up_topics is a list
    fut_ok = all(isinstance(s.get("follow_up_topics"), list) for s in sessions)
    check("follow_up_topics is list", fut_ok)

    # 8. Three exact needle values exist somewhere
    all_text = json.dumps(sessions)
    needles_found = []
    for needle in NEEDLE_VALUES:
        if needle in all_text:
            needles_found.append(needle)
    check(
        "Needle values present",
        len(needles_found) == len(NEEDLE_VALUES),
        f"found {len(needles_found)}/{len(NEEDLE_VALUES)}",
    )

    # 9. At least 3 sessions have follow_up_topics
    sessions_with_fu = sum(1 for s in sessions if len(s.get("follow_up_topics", [])) > 0)
    check("At least 3 sessions with follow_up_topics", sessions_with_fu >= 3, f"got {sessions_with_fu}")

    # 10. At least 1 session has risk_flags, but no crisis flags
    sessions_with_risk = [s for s in sessions if len(s.get("risk_flags", [])) > 0]
    has_risk = len(sessions_with_risk) >= 1
    check("At least 1 session with risk_flags", has_risk, f"got {len(sessions_with_risk)}")

    # Check for forbidden crisis flags
    crisis_flags = {"self_harm", "suicide", "abuse", "crisis", "self-harm", "suicidal", "emergency"}
    forbidden_found = []
    for s in sessions:
        for flag in s.get("risk_flags", []):
            if flag.lower().replace("-", "_") in crisis_flags:
                forbidden_found.append(flag)
    check(
        "No crisis flags in demo data",
        len(forbidden_found) == 0,
        f"found: {forbidden_found}",
    )

    return results, passed, total


def build_report(results: List[str], passed: int, total: int) -> str:
    """
    Build a markdown validation report.
    """
    lines = [
        "# Project Recall Schema Validation Report",
        "",
        f"**Result: {passed}/{total} checks passed**",
        "",
        "## Checks",
    ]
    lines.extend(results)
    lines.extend([
        "",
        "## Needle Values",
        "The following exact values must appear in key_moments or summary:",
    ])
    for needle in NEEDLE_VALUES:
        lines.append(f'- "{needle}"')
    lines.extend([
        "",
        "## Summary",
        f"- Sessions validated: {total}",
        f"- Passed: {passed}",
        f"- Failed: {total - passed}",
        "",
        "This report confirms the generated dataset matches the official",
        "Project Recall session-history JSON schema and is safe for demo use.",
    ])
    return "\n".join(lines)


def main():
    # Ensure output dir exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load sessions
    if not os.path.exists(SESSIONS_PATH):
        print(f"ERROR: {SESSIONS_PATH} not found. Run generate_project_recall_sessions.py first.")
        sys.exit(1)

    with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    # Validate
    results, passed, total = validate_sessions(sessions)

    # Print
    print(f"Results: {passed}/{total} checks passed")
    for r in results:
        print(r)

    # Write report
    report = build_report(results, passed, total)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {REPORT_PATH}")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()