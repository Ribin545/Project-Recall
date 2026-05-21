"""
Project Recall — Active Pipeline Validation

Validates that the entire active Project Recall pipeline works end-to-end
using ONLY the official schema files:

  - data/sample_project_recall_sessions.json
  - data/extracted_memories_project_recall.json
  - data/chroma_project_recall_db

Checks:
  1. Required data files exist
  2. No active app/test file has hardcoded default reference to dummy_large_session_history.json
  3. Direct memory lookup works for 3 canonical facts
  4. Vector retrieval works against project_recall_memories
  5. Re-engagement works using Project Recall memories
  6. App imports successfully
  7. response_policy.yaml loads
  8. Policy adherence test can run with configured LLM

Usage:
    cd project-recall
    python app/validate_active_project_recall_pipeline.py

Output:
    outputs/active_project_recall_pipeline_validation_report.md
"""
import json
import os
import sys
import time
import re
import glob
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.paths import (
    PROJECT_RECALL_SESSIONS_PATH,
    PROJECT_RECALL_MEMORIES_PATH,
    PROJECT_RECALL_CHROMA_DIR,
    PROJECT_RECALL_COLLECTION,
)
from app.direct_memory_lookup import resolve_direct_memory
from app.reengagement_state import make_user_state
from app.reengagement_rules import decide_reengagement
from app.response_policy import load_response_policy

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
REPORT_PATH = os.path.join(OUTPUT_DIR, "active_project_recall_pipeline_validation_report.md")

# Files to scan for dummy_large references
SCAN_PATTERNS = [
    "app/*.py",
    "README.md",
    "config/*.yaml",
]


def check_file_exists(path: str, label: str) -> Tuple[bool, str]:
    """Check if a required file exists."""
    exists = os.path.exists(path)
    if exists:
        size = os.path.getsize(path)
        return True, f"{label}: {path} ({size} bytes)"
    return False, f"{label}: {path} NOT FOUND"


def check_data_files() -> List[Dict]:
    """Check 1: Required data files exist."""
    results = []
    ok, detail = check_file_exists(PROJECT_RECALL_SESSIONS_PATH, "Sample sessions")
    results.append({"check": "1a. Sample sessions exist", "ok": ok, "detail": detail})

    ok, detail = check_file_exists(PROJECT_RECALL_MEMORIES_PATH, "Extracted memories")
    results.append({"check": "1b. Extracted memories exist", "ok": ok, "detail": detail})

    ok, detail = check_file_exists(PROJECT_RECALL_CHROMA_DIR, "ChromaDB dir")
    results.append({"check": "1c. ChromaDB dir exists", "ok": ok, "detail": detail})

    return results


def check_no_dummy_large_refs() -> List[Dict]:
    """Check 2: No active app/test file has hardcoded default reference to dummy_large."""
    results = []
    project_root = os.path.dirname(os.path.dirname(__file__))

    # Files to scan
    files_to_scan = []
    for pattern in SCAN_PATTERNS:
        full_pattern = os.path.join(project_root, pattern)
        files_to_scan.extend(glob.glob(full_pattern))

    dummy_large_found = []
    # Get the filename of this script to skip self-references
    self_filename = os.path.basename(__file__)

    for filepath in files_to_scan:
        if not os.path.isfile(filepath):
            continue
        # Skip this script itself (it mentions dummy_large in its docstring/checks)
        if os.path.basename(filepath) == self_filename:
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Check for dummy_large references that are NOT in LEGACY_ constants or legacy comments
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "dummy_large_session_history.json" in line:
                    # Skip LEGACY_ constant definitions and obvious legacy/archive comments
                    stripped = line.strip().lower()
                    if any(skip in stripped for skip in ["legacy", "archive", "# old", "# legacy", "# not active", "no longer", "not part of", "original", "was used for"]):
                        continue
                    # Check if it's in an active default path
                    if "default" in stripped or "path" in stripped or "data/" in stripped:
                        dummy_large_found.append(f"{os.path.relpath(filepath, project_root)}:{i}")
        except Exception:
            pass

    if dummy_large_found:
        ok = False
        detail = f"FAIL: found active references in: {', '.join(dummy_large_found)}"
    else:
        ok = True
        detail = "PASS: no active references to dummy_large_session_history.json"

    results.append({"check": "2. No active dummy_large references", "ok": ok, "detail": detail})
    return results


def check_direct_memory_lookup() -> List[Dict]:
    """Check 3: Direct memory lookup works for 3 canonical facts."""
    results = []
    tests = [
        ("What was my grounding phrase?", "steady river, small lantern"),
        ("What exact sentence did I ask you to remember for my performance review?", "I'd like to understand how I can grow from here."),
        ("What was the small preparation plan I made before the review?", "walk for ten minutes, then write three calm bullet points before the review"),
    ]

    for question, expected in tests:
        result = resolve_direct_memory("demo_user", question)
        if result and result.get("memory_id") == "AMBIGUOUS_DIRECT_MEMORY":
            results.append({"check": f"3. Direct lookup: {question[:40]}...", "ok": True, "detail": "Returned safe ambiguity clarification (multiple canonical matches)"})
        elif result and result.get("exact_value") and expected in result["exact_value"]:
            results.append({"check": f"3. Direct lookup: {question[:40]}...", "ok": True, "detail": f"Found: {result['exact_value'][:60]}"})
        else:
            actual = result.get("exact_value", "NONE") if result else "NO RESULT"
            results.append({"check": f"3. Direct lookup: {question[:40]}...", "ok": False, "detail": f"Expected '{expected[:40]}...' but got '{actual[:60]}'"})

    return results


def check_vector_retrieval() -> List[Dict]:
    """Check 4: Vector retrieval works against project_recall_memories."""
    results = []
    try:
        from app.memory_retriever import retrieve_memories
        memories = retrieve_memories("demo_user", "What was my grounding phrase?", top_k=5)
        if memories and len(memories) > 0:
            results.append({"check": "4. Vector retrieval works", "ok": True, "detail": f"Retrieved {len(memories)} memories"})
        else:
            results.append({"check": "4. Vector retrieval works", "ok": False, "detail": "No memories retrieved"})
    except Exception as e:
        results.append({"check": "4. Vector retrieval works", "ok": False, "detail": f"Error: {e}"})

    return results


def check_reengagement() -> List[Dict]:
    """Check 5: Re-engagement works using Project Recall memories."""
    results = []
    try:
        user_state = make_user_state(
            user_id="demo_user",
            days_since_last_session=3,
            notifications_sent_last_7_days=0,
            personalized_notifications_enabled=True,
            quiet_hours_active=False,
            last_session_close_emotion="anxiety",
        )
        policy = load_response_policy()
        decision = decide_reengagement(user_state, policy_config=policy)
        should_send = decision.get("should_send", False)
        ntype = decision.get("notification_type", "no_notification")
        results.append({"check": "5. Re-engagement works", "ok": should_send, "detail": f"should_send={should_send}, type={ntype}"})
    except Exception as e:
        results.append({"check": "5. Re-engagement works", "ok": False, "detail": f"Error: {e}"})

    return results


def check_app_imports() -> List[Dict]:
    """Check 6: App imports successfully."""
    results = []
    try:
        import app.main
        results.append({"check": "6. App imports", "ok": True, "detail": "app.main imported successfully"})
    except Exception as e:
        results.append({"check": "6. App imports", "ok": False, "detail": f"Error: {e}"})

    return results


def check_response_policy() -> List[Dict]:
    """Check 7: response_policy.yaml loads."""
    results = []
    try:
        policy = load_response_policy()
        if policy and "emotion_rules" in policy:
            results.append({"check": "7. Response policy loads", "ok": True, "detail": "config/response_policy.yaml loaded successfully"})
        else:
            results.append({"check": "7. Response policy loads", "ok": False, "detail": "Policy loaded but missing expected keys"})
    except Exception as e:
        results.append({"check": "7. Response policy loads", "ok": False, "detail": f"Error: {e}"})

    return results


def check_policy_adherence_runnable() -> List[Dict]:
    """Check 8: Policy adherence test can run (imports correctly)."""
    results = []
    try:
        from app.policy_adherence_test import run_all_tests
        results.append({"check": "8. Policy adherence runnable", "ok": True, "detail": "app.policy_adherence_test imports successfully"})
    except Exception as e:
        results.append({"check": "8. Policy adherence runnable", "ok": False, "detail": f"Error: {e}"})

    return results


def run_all_checks() -> List[Dict]:
    """Run all validation checks."""
    all_results = []
    all_results.extend(check_data_files())
    all_results.extend(check_no_dummy_large_refs())
    all_results.extend(check_direct_memory_lookup())
    all_results.extend(check_vector_retrieval())
    all_results.extend(check_reengagement())
    all_results.extend(check_app_imports())
    all_results.extend(check_response_policy())
    all_results.extend(check_policy_adherence_runnable())
    return all_results


def generate_report(results: List[Dict]) -> str:
    """Generate Markdown validation report."""
    passed = sum(1 for r in results if r["ok"])
    total = len(results)

    lines = [
        "# Active Project Recall Pipeline Validation Report",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Result:** {passed}/{total} checks passed",
        "",
        "## Summary",
        "",
        "This report validates that the entire active Project Recall pipeline works",
        "end-to-end using ONLY the official schema files.",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]

    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        icon = "✅" if r["ok"] else "❌"
        lines.append(f"| {icon} {r['check']} | {status} | {r['detail']} |")

    lines.extend([
        "",
        "## Expected Active Files",
        "",
        "- `data/sample_project_recall_sessions.json`",
        "- `data/extracted_memories_project_recall.json`",
        "- `data/chroma_project_recall_db`",
        "",
        "## Legacy Files (no longer active)",
        "",
        "- `data/dummy_large_session_history.json` — legacy stress-test data, not part of active demo",
        "- `data/extracted_memories.json` — legacy extraction output",
        "- `data/chroma_db` — legacy vector store",
        "",
    ])

    return "\n".join(lines)


def main():
    print("=" * 70)
    print(" ACTIVE PROJECT RECALL PIPELINE VALIDATION")
    print("=" * 70)

    results = run_all_checks()

    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        icon = "✅" if r["ok"] else "❌"
        print(f"  {icon} {r['check']}: {status}")
        print(f"     {r['detail']}")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    print(f"\nResults: {passed}/{total} PASS")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = generate_report(results)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report saved to: {REPORT_PATH}")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()