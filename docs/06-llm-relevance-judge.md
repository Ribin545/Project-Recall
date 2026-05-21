# 06 — LLM Relevance Judge

## Why the Judge Exists

Vector DB retrieves candidates by semantic similarity. But semantic similarity ≠ topical relevance.

**Example failure:**
- User asks: "What did we explore about family boundaries?"
- Vector DB retrieves: "User chose quiet exit strategy from family dinner" (semantic: family + quiet)
- But the user asked about **boundaries with brother**, not dinner exits

The LLM judge catches this mismatch.

---

## What the Judge Does

The judge receives:
1. User's query (with detected emotion)
2. Top candidate memories (12-15 cards)
3. Recent conversation history

And returns a JSON decision:
- `use_memory`: true/false
- `selected_memory_ids`: Which memories to use
- `supporting_memory_ids`: Additional context memories
- `rejected_memories`: Why others were rejected
- `confidence`: 0.0-1.0
- `detail_level_recommendation`: How much detail to include
- `answer_basis`: Why this memory was chosen

---

## Judge Input Format

```
User: "I had anxiety recently do you remember it? that time i had anxiety before bedtim"

Detected emotion: anxiety (intensity: 0.7)

Recent conversation:
[none]

Candidate memories:
1. [mem_sess_011_km_0] Summary: "User described panic before bedtime..."
   Type: unresolved_theme, Theme: sleep hygiene, Emotion: anxiety

2. [mem_sess_008_exact_1] Summary: "2 AM looping thoughts about productivity pressure"
   Type: grounding_phrase, Theme: productivity pressure...

[10 more candidates...]
```

---

## Judge Output Example

```json
{
  "use_memory": true,
  "selected_memory_ids": ["mem_sess_011_km_0"],
  "supporting_memory_ids": [],
  "rejected_memories": [
    {
      "memory_id": "mem_sess_008_exact_1",
      "reason": "This is about productivity pressure, not bedtime anxiety"
    }
  ],
  "confidence": 0.85,
  "detail_level_recommendation": "summary_level",
  "answer_basis": "User specifically mentioned bedtime anxiety, which matches the sleep hygiene session"
}
```

---

## Confidence Gate

| Confidence | Action |
|------------|--------|
| ≥ 0.7 | Approve memory, use in response |
| 0.4-0.7 | Approve with caution, lower detail level |
| < 0.4 | Reject, use no-memory fallback |

**No-memory fallback:**
The prompt tells the LLM: "No approved memories match. Respond warmly without referencing specific past sessions."

---

## The Judge Does NOT Write the Final Response

**Important distinction:**
- The **judge** decides **which memory to use** (or none)
- The **final LLM** writes the **actual response text**

This separation prevents the judge from being distracted by writing style while evaluating relevance.

---

## Implementation

`app/memory_relevance_judge.py`:
- Builds structured prompt with candidates
- Calls LLM via `app/llm_client.py`
- Parses JSON response
- Applies confidence gate
- Returns approved/rejected memories

---

## Failure Modes and Mitigations

| Failure | Mitigation |
|---------|-----------|
| Judge returns invalid JSON | Fallback: approve first memory with low confidence |
| Judge times out | Fallback: approve without judge |
| Judge selects wrong memory | Confidence gate + no-memory fallback |
| Judge is too conservative | Lower confidence threshold in YAML |

---

## Why Not Just Use Vector DB Directly?

| Approach | Problem | Judge Solution |
|----------|---------|---------------|
| Top-1 vector result | Might be semantically close but wrong topic | Judge validates topical match |
| Top-k without filtering | Too many memories, prompt bloat | Judge picks 1-2 relevant ones |
| No validation | Wrong memory injected silently | Judge rejects mismatches |

---

## Production Improvements

- **Caching:** Cache judge decisions for identical queries
- **Evaluation:** Human-rated relevance dataset for tuning
- **Smaller model:** Use smaller LLM for judge (faster, cheaper)
- **Retry logic:** Retry once on JSON parse failure
- **Confidence calibration:** Tune thresholds on eval data