# Active Project Recall Pipeline Validation Report

**Date:** 2026-05-21 16:41:47
**Result:** 12/12 checks passed

## Summary

This report validates that the entire active Project Recall pipeline works
end-to-end using ONLY the official schema files.

| Check | Status | Detail |
|-------|--------|--------|
| ✅ 1a. Sample sessions exist | PASS | Sample sessions: E:\Projects\HealthApp\project-recall\data\sample_project_recall_sessions.json (9698 bytes) |
| ✅ 1b. Extracted memories exist | PASS | Extracted memories: E:\Projects\HealthApp\project-recall\data\extracted_memories_project_recall.json (105971 bytes) |
| ✅ 1c. ChromaDB dir exists | PASS | ChromaDB dir: E:\Projects\HealthApp\project-recall\data\chroma_project_recall_db (4096 bytes) |
| ✅ 2. No active dummy_large references | PASS | PASS: no active references to dummy_large_session_history.json |
| ✅ 3. Direct lookup: What was my grounding phrase?... | PASS | Returned safe ambiguity clarification (multiple canonical matches) |
| ✅ 3. Direct lookup: What exact sentence did I ask you to rem... | PASS | Found: I'd like to understand how I can grow from here. |
| ✅ 3. Direct lookup: What was the small preparation plan I ma... | PASS | Found: walk for ten minutes, then write three calm bullet points be |
| ✅ 4. Vector retrieval works | PASS | Retrieved 5 memories |
| ✅ 5. Re-engagement works | PASS | should_send=True, type=gentle_unresolved_followup |
| ✅ 6. App imports | PASS | app.main imported successfully |
| ✅ 7. Response policy loads | PASS | config/response_policy.yaml loaded successfully |
| ✅ 8. Policy adherence runnable | PASS | app.policy_adherence_test imports successfully |

## Expected Active Files

- `data/sample_project_recall_sessions.json`
- `data/extracted_memories_project_recall.json`
- `data/chroma_project_recall_db`

## Legacy Files (no longer active)

- `data/dummy_large_session_history.json` — legacy stress-test data, not part of active demo
- `data/extracted_memories.json` — legacy extraction output
- `data/chroma_db` — legacy vector store
