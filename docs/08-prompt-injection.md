# 08 — Prompt Injection and Response Validation

## Why Turn-Local Injection?

**Problem:** If memories are in the system prompt, the LLM treats them as permanent context. This causes:

- **Prompt dilution:** Memories compete with other instructions
- **Recency bias:** LLM pays more attention to end-of-prompt content
- **Wrong associations:** Memories bleed into unrelated turns

**Solution:** Inject approved memories **only for the current turn**, near the current user message.

---

## Prompt Structure

```
┌─────────────────────────────────────────────────────────────┐
│  SYSTEM PROMPT (always present)                             │
│  - Persona definition                                       │
│  - Global rules from YAML                                   │
│  - Tone guidance                                            │
│  - NEVER includes specific memories                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  RECENT HISTORY (last 5 turns, sliding window)              │
│  - Previous user messages                                   │
│  - Assistant responses                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  TURN CONTROL BLOCK (injected per turn)                     │
│  - Detected emotion                                          │
│  - Detected intent                                           │
│  - Approved memory (if any)                                  │
│  - Rejected memories (forbidden topics)                      │
│  - Detail level allowed                                      │
│  - Strategy instructions                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  CURRENT USER MESSAGE                                        │
│  - The actual user input                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Example Turn Control Block

```
--- TURN CONTEXT ---
Emotion: anxiety (intensity: 0.7)
Intent: emotional_disclosure
Strategy: validate_then_offer_choice
Allowed detail: exact_value
Approved memory: [mem_sess_011_km_0] User described panic before bedtime...
DO NOT mention: [mem_sess_003_exact_0] Family boundaries (unrelated topic)
--- END TURN CONTEXT ---

User: I've been feeling anxious today...
```

**Key:** The memory is **only** present for this turn. Next turn, a different memory (or none) is injected.

---

## Why Not Stuff All History?

| Approach | Tokens | Problem |
|----------|--------|---------|
| All memories in system prompt | 5000+ | Dilutes instructions, wrong associations |
| Recent conversation only | 500 | No memory awareness |
| **Turn-local injection** | 800 | Memory present only when relevant |

---

## Response Validation (Partial)

The current system validates responses indirectly:
- **No memory fallback:** If judge rejects all memories, the prompt says "respond without referencing specific past sessions"
- **Mechanical phrase filter:** YAML lists forbidden phrases ("according to your records")
- **Detail level enforcement:** YAML controls how specific responses can be

**Not yet implemented:**
- Post-generation exact value leak detection
- Automatic retry on unsafe responses
- Content safety classifier

---

## Rejected Memories as Forbidden Topics

If the judge rejects memories, they can be listed as "DO NOT mention" in the turn block:

```
DO NOT mention: [mem_sess_003_exact_0] Family boundaries (unrelated topic)
```

This prevents the LLM from accidentally referencing a wrong memory that happens to be semantically similar.

---

## Prompt Dilution Prevention

**What dilutes a prompt:**
- Too many instructions
- Too many memories
- Memories at the beginning (far from user message)

**Our approach:**
- System prompt: ~15 lines (persona + rules)
- History: last 5 turns only (~10 lines)
- Turn block: 3-5 lines
- Total: ~30 lines, well within context window

---

## Production Improvements

| Current | Production |
|---------|-----------|
| Manual turn block | Auto-generated with template engine |
| No post-validation | Regex + classifier for exact value leaks |
| No retry | Retry once on unsafe response |
| No content classifier | Integration with safety API |