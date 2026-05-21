# 09 — Direct Memory Lookup

## Why Not Use Vector Search for Exact Recall?

Vector search finds **semantically similar** text. But exact recall questions need **identical matches** to canonical memories.

**Problem:**
- User asks: "What was my grounding phrase?"
- Vector DB might retrieve: "User described panic before bedtime" (semantic: anxiety-related)
- But the user wants the **exact phrase**, not a summary about anxiety

**Solution:** Direct canonical lookup bypasses vector search entirely.

---

## Canonical Memory Lookup Flow

```
User: "What was my grounding phrase?"
    ↓
Query type detection → "grounding_phrase"
    ↓
Canonical lookup by canonical_slot
    ↓
Memory with canonical_slot="grounding_phrase"
    ↓
Return exact_value
```

---

## What Is a Canonical Memory?

A canonical memory is one the user **explicitly asked** to remember:

```json
{
  "memory_id": "mem_sess_011_exact_1",
  "memory_type": "grounding_phrase",
  "canonical_slot": "grounding_phrase",
  "exact_value": "Quiet room, soft blanket, slow breath",
  "is_canonical": true,
  "user_explicitly_asked_to_remember": true,
  "confidence": 1.0
}
```

---

## Query Type Detection

`app/direct_memory_lookup.py` detects query types from keywords:

| Query Type | Trigger Phrases | Memory Type |
|-----------|----------------|-------------|
| `grounding_phrase` | "grounding phrase", "calming phrase", "phrase I used" | `grounding_phrase` |
| `communication_script` | "exact sentence", "sentence did I ask", "what line did I" | `communication_script` |
| `preparation_plan` | "preparation plan", "small plan", "before the review" | `follow_up_intent` |

---

## Example: "What was my grounding phrase?"

**Step 1: Detect query type**
- Input: "What was my grounding phrase?"
- Match: "grounding phrase" → query_type = `grounding_phrase`

**Step 2: Lookup canonical_slot**
- Search memories where `canonical_slot="grounding_phrase"`
- Found: `mem_sess_011_exact_1` (Quiet room, soft blanket, slow breath)
- Found: `mem_sess_008_exact_1` (steady river, small lantern)

**Step 3: Handle ambiguity**
- Multiple matches → return clarification:
  "I found more than one phrase. Do you mean sleep hygiene: 'Quiet room...' or productivity: 'steady river...'?"

**Step 4: If single match**
- Return exact value directly

---

## Example: "What exact sentence did I ask you to remember?"

**Step 1: Detect query type**
- Input: "What exact sentence did I ask you to remember?"
- Match: "exact sentence" + "ask you to remember" → query_type = `communication_script`

**Step 2: Lookup**
- Search memories where `memory_type="communication_script"` and `is_canonical=true`
- Found: `mem_sess_007_exact_0`
- exact_value: "I'd like to understand how I can grow from here."

**Step 3: Return**
- Direct answer with exact value

---

## Why Embeddings Confuse Distractors

**Distractor memory:**
```json
{
  "memory_id": "mem_test_distractor_0",
  "summary": "A random phrase about bedtime routines",
  "is_distractor": true
}
```

If using only vector search:
- "What was my grounding phrase?" → might retrieve distractor (semantic: bedtime)
- Wrong answer injected

With canonical lookup:
- Searches by `canonical_slot`, not semantic similarity
- Distractor has no `canonical_slot` → ignored

---

## Fallback Behavior

| Scenario | Behavior |
|----------|----------|
| No canonical match found | Return: "I don't have a specific phrase remembered. Would you like to tell me one?" |
| Multiple matches | Ask clarifying question with options |
| Match found but low confidence | Return with uncertainty language |
| Match found but high sensitivity | Block and return vague response |

---

## Implementation

`app/direct_memory_lookup.py`:
- `detect_query_type(query)` → Returns query type or None
- `lookup_canonical(user_id, query_type)` → Returns matching memories
- `handle_ambiguity(matches)` → Returns clarification or single answer
- `is_direct_memory_question(query)` → Boolean check for routing

---

## When Direct Lookup Is Used

```python
# In app/main.py chat handler
if is_direct_memory_question(user_message):
    # Route to direct_memory_lookup.py
    result = direct_memory_lookup(user_id, user_message)
    # Bypass vector retrieval + judge
else:
    # Route through full pipeline
    candidates = retriever.retrieve(...)
    approved = judge.evaluate(...)
```

**Benefit:** Faster, more accurate, no vector confusion for exact recall.

---

## Production Improvements

- **User-confirmed memories:** Let users explicitly mark "remember this" in chat
- **Edit/delete canonicals:** UI for managing remembered phrases
- **Multiple slots per type:** Support "work grounding phrase" vs "sleep grounding phrase"