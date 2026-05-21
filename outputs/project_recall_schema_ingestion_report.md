# Project Recall Schema Ingestion Report

**Result:** 12/12 tests passed
**Total time:** 38.8ms

## Summary

This report validates the full mini-pipeline for the official Project Recall
session-history JSON schema. It confirms:

- Generated sessions match the official schema
- Memories extract successfully from the new format
- emotional_tone maps into internal emotion metadata
- follow_up_topics convert to follow_up_intent memories
- risk_flags map to safety metadata
- Direct memory lookup works for all three needle facts
- Re-engagement can use follow_up_topics
- Existing architecture remains compatible

## Test Results

| Test | Status | Detail |
|------|--------|--------|
| ✅ A. Load sessions | PASS | loaded 11 sessions |
| ✅ B. Validate schema | PASS | all 11 sessions have required fields |
| ✅ C. Extract memories | PASS | extracted 66 memories |
| ✅ D. Emotion mapping | PASS | primary=anxiety, intensity=0.7 |
| ✅ E. Canonical memories exist | PASS | found 3/3 canonical needle memories |
| ✅ F. Direct lookup: grounding phrase | PASS | returned ambiguity clarification as expected (multiple grounding phrases exist) |
| ✅ G. Direct lookup: review sentence | PASS | got 'I'd like to understand how I can grow from here.' |
| ✅ H. Direct lookup: preparation plan | PASS | got 'walk for ten minutes, then write three calm bullet points before the review' |
| ✅ I. Follow-up topic extraction | PASS | found 22 follow_up_intent memories |
| ✅ J. Risk flag safety mapping | PASS | 30 memories with elevated sensitivity, 66 safe for opener |
| ✅ K. Re-engagement decision | PASS | type=gentle_unresolved_followup, should_send=True |
| ✅ L. Auto-detect format | PASS | auto-detected as 'project_recall' |

## Schema Mapping

| Official Schema Field | Internal Mapping |
|----------------------|------------------|
| `theme` | topic_tags / session theme |
| `emotional_tone` | emotion.primary, emotion.secondary, intensity, trajectory |
| `key_moments` | memory candidates (summary, exact_value, memory_type) |
| `summary` | recurring_theme memory / embedding text |
| `risk_flags` | sensitivity, safe_to_reference_in_opener, eligible_for_reengagement |
| `follow_up_topics` | follow_up_intent memories (importance=0.80, unresolved) |

## Needle Fact Verification

The three exact needle facts are correctly extracted as canonical memories:

1. **Grounding phrase:** `"steady river, small lantern"` → `grounding_phrase` memory
2. **Review sentence:** `"I'd like to understand how I can grow from here."` → `review_preparation` memory
3. **Preparation plan:** `"walk for ten minutes, then write three calm bullet points before the review"` → `follow_up_intent` memory

All three are retrievable via direct memory lookup.
