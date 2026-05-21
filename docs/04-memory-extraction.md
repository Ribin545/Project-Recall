# 04 — Memory Extraction

## How Extraction Works

The extraction pipeline converts session JSON into structured memory cards. It is **rule-based** (not LLM-based) for reliability and reproducibility.

**Pipeline:**
```
sample_project_recall_sessions.json
    ↓
project_recall_schema_adapter.py  (normalize schema)
    ↓
memory_extractor.py  (rule-based extraction)
    ↓
extracted_memories_project_recall.json
```

---

## Rule-Based Extraction

`app/memory_extractor.py` applies deterministic rules:

### 1. Session Summary Card
- Source: `session.summary`
- `memory_type`: `session_summary`
- `memory_source_kind`: `summary`
- Emotion: first emotional_tone = primary, rest = secondary
- Intensity: mapped from emotion keywords (anxious=0.7, overwhelmed=0.8, etc.)

### 2. Key Moment Cards
- Source: `session.key_moments[]` (one card per moment)
- `memory_type`: inferred from content
- `memory_source_kind`: `key_moment`

**Type inference rules:**
| Content Pattern | memory_type |
|----------------|-------------|
| Contains "grounding" or "phrase" | `grounding_phrase` |
| Contains "remember this" or "ask you to remember" | `communication_script` |
| Contains "plan" or "before the" | `follow_up_intent` |
| Contains goal/commitment language | `user_goal` |
| Default | `unresolved_theme` |

### 3. Follow-Up Intent Cards
- Source: `session.follow_up_topics[]`
- `memory_type`: `follow_up_intent`
- `memory_source_kind`: `follow_up_topic`
- Marked as `unresolved` and `follow_up_recommended: true`

### 4. Exact Phrase Detection
When a key moment contains explicit memory language:
- "I'd like you to remember..." → `exact_value` extracted
- `is_canonical`: true
- `user_explicitly_asked_to_remember`: true
- `confidence`: 1.0

**Example:**
```json
{
  "key_moments": [
    "User said: 'I'd like you to remember this phrase for when I feel anxious: Quiet room, soft blanket, slow breath'"
  ]
}
```
Extracts:
- `exact_value`: "Quiet room, soft blanket, slow breath"
- `memory_type`: `grounding_phrase`
- `is_canonical`: true

### 5. Emotion Normalization

| Input Keyword | Mapped Emotion | Intensity |
|-------------|--------------|-----------|
| anxious, panic | anxiety | 0.7 |
| overwhelmed | overwhelm | 0.8 |
| sad, low | sadness | 0.6 |
| angry, frustrated | anger | 0.7 |
| ashamed, embarrassed | shame | 0.6 |
| lonely, alone | loneliness | 0.6 |
| uncertain, stuck | uncertainty | 0.5 |
| hopeful, optimistic | hopefulness | 0.5 |
| relieved, calm | relief | 0.4 |
| neutral, okay | neutral | 0.3 |

Unknown emotions: warning logged, defaults to `uncertainty` + `neutral`.

### 6. Risk Flag Mapping

| Risk Flag | sensitivity | safe_to_reference_in_opener |
|-----------|-------------|----------------------------|
| `suicidal_ideation` | 1.0 | false |
| `self_harm` | 1.0 | false |
| `severe_isolation` | 0.8 | false |
| `substance_use` | 0.7 | false |
| `domestic_conflict` | 0.8 | false |
| (none) | 0.2 | true |

### 7. Importance Scoring

| Factor | Score |
|--------|-------|
| `is_canonical` | +0.3 |
| `user_explicitly_asked_to_remember` | +0.2 |
| `follow_up_recommended` | +0.1 |
| `unresolved` status | +0.1 |
| Base | 0.5 |

---

## Command Line

```bash
# Default (uses paths.py)
python app/memory_extractor.py

# Explicit
python app/memory_extractor.py \
  --input data/sample_project_recall_sessions.json \
  --format project_recall \
  --output data/extracted_memories_project_recall.json

# Supported formats:
#   project_recall  (official schema)
#   auto            (auto-detect)
```

---

## Output

Produces `data/extracted_memories_project_recall.json` — an array of Memory objects.

**From 11 sample sessions:** 66 memory cards extracted
- 11 session summaries
- ~33 key moment cards
- 22 follow-up intent cards
- 3 canonical exact memories

---

## Future Improvement: LLM Extraction

Current extraction is rule-based for stability. Production would benefit from:

1. **LLM extraction** with structured output (JSON schema)
2. **Validator layer** enforcing schema + safety constraints
3. **Rule fallback** for exact phrases and follow-ups
4. **Evaluation metrics** (precision/recall on canonical memories)

Trade-off: LLM extraction is more nuanced but slower and non-deterministic. The current rule-based approach is fast, reproducible, and sufficient for the prototype.