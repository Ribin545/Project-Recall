# Reliability Guardrail Test Report

**Date:** 2026-05-21 16:41:31

## JUDGE_INVALID_JSON

- **Status:** PASS
- **Checks:**
  - WARN: fallback approved memory with low confidence
- **judge_status:** [deterministic_fallback]
- **use_memory:** True

## JUDGE_TIMEOUT

- **Status:** PASS
- **Checks:**
  - WARN: fallback approved memory without LLM judge
- **use_memory:** True

## CORRECT_MEMORY_NOT_FIRST

- **Status:** PASS
- **Checks:**
- **selected:** ['mem_correct']
- **confidence:** 0.85

## VECTOR_MISSES_SPARSE_FINDS

- **Status:** PASS
- **Checks:**
  - PASS: sparse score 0.293 finds relevant memory
- **sparse_score:** 0.293

## TOPIC_EXTRACTION_EMPTY

- **Status:** PASS
- **Checks:**
- **intent:** specific_episode_recall
- **memory_need:** summary_level

## NO_RELEVANT_MEMORY

- **Status:** PASS
- **Checks:**
- **use_memory:** False
- **confidence:** 0.2

## DIRECT_EXACT_RECALL

- **Status:** PASS
- **Checks:**
  - PASS: ambiguous direct recall handled safely
- **exact_value:** None

## NO_MEMORY_FALLBACK_PROMPT

- **Status:** PASS
- **Checks:**
- **prompt_length:** 1336

---

**Summary:** PASS=8 FAIL=0
