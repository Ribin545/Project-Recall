# 03 — Data Schema and Memory Cards

## Official Project Recall Session Schema

Sessions are stored as a JSON array in `data/sample_project_recall_sessions.json`:

```json
[
  {
    "user_id": "demo_user",
    "session_id": "sess_001",
    "timestamp": "2026-05-19T09:00:00Z",
    "theme": "work stress and burnout",
    "emotional_tone": ["anxious", "overwhelmed", "hopeful"],
    "key_moments": [
      "User reported panic before meetings",
      "Discussed grounding exercise",
      "User committed to sleep routine"
    ],
    "summary": "User described increasing stress before team meetings...",
    "risk_flags": [],
    "follow_up_topics": [
      "sleep hygiene",
      "manager conflict"
    ]
  }
]
```

## Why `user_id` Is Included

Each session includes `user_id` because:
- The system supports multi-user isolation (each user has their own memory set)
- The demo uses `demo_user`, but production could use real user IDs
- Retrieval filters by `user_id` so users only see their own memories

---

## Field Mapping to Memory Cards

| Session Field | Becomes | Memory Card Fields |
|-------------|---------|------------------|
| `theme` | topic tags | `topic_tags: ["work stress", "burnout"]` |
| `emotional_tone` | emotion metadata | `emotion.primary`, `emotion.secondary` |
| `key_moments[]` | key moment cards | `memory_type`, `summary`, `exact_value` |
| `summary` | session summary card | `memory_type: session_summary` |
| `follow_up_topics[]` | follow-up intent cards | `memory_type: follow_up_intent` |
| `risk_flags[]` | safety metadata | `sensitivity`, `safe_to_reference_in_opener` |

---

## Memory Card Fields

Each memory card is a Pydantic model (`app/memory_schema.py`):

| Field | Type | Description |
|-------|------|-------------|
| `memory_id` | str | Unique ID (e.g., `mem_sess_001_km_0`) |
| `user_id` | str | Owner user |
| `source_session_id` | str | Originating session |
| `source_timestamp` | str | Session timestamp |
| `memory_type` | str | Category (see below) |
| `memory_source_kind` | str | `summary`, `key_moment`, `follow_up_topic`, `exact_user_request` |
| `theme` | str | Session theme |
| `source_text` | str | Original text from session |
| `summary` | str | Human-readable summary |
| `exact_value` | str | Exact phrase to remember (for canonical memories) |
| `canonical_slot` | str | Normalized slot name (e.g., `grounding_phrase`) |
| `topic_tags` | list | Derived topic tags |
| `follow_up_topics` | list | Unresolved topics |
| `risk_flags` | list | Safety flags |
| `emotion` | Emotion | Primary, secondary, intensity, valence, arousal |
| `importance` | float | 0.0-1.0 importance score |
| `sensitivity` | float | 0.0-1.0 privacy level |
| `resolved_status` | str | `resolved`, `unresolved`, `partially_resolved`, `unknown` |
| `follow_up_recommended` | bool | Should follow up next session? |
| `safe_to_reference_in_opener` | bool | Safe for greeting? |
| `is_distractor` | bool | Test distractor flag |
| `is_canonical` | bool | User explicitly asked to remember |
| `user_explicitly_asked_to_remember` | bool | Same as above |
| `confidence` | float | 0.0-1.0 confidence in exact recall |
| `created_at` | str | ISO timestamp |

---

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `session_summary` | Overall session theme | "User discussed work stress and burnout" |
| `recurring_theme` | Pattern across sessions | "Recurring anxiety about performance" |
| `unresolved_theme` | Still open issue | "Manager conflict unresolved" |
| `coping_strategy` | Technique user tried | "Used breathing exercise before meeting" |
| `relationship_context` | Relationship dynamic | "Difficulty setting boundaries with brother" |
| `communication_script` | Exact phrase to use | "I'd like to understand how I can grow from here" |
| `remembered_phrase` | User's exact phrase | "steady river, small lantern" |
| `grounding_phrase` | Calming technique phrase | "Quiet room, soft blanket, slow breath" |
| `follow_up_intent` | Topic to revisit | "sleep hygiene", "manager conflict" |
| `user_goal` | User-stated goal | "Practice grounding phrase nightly" |
| `emotional_pattern` | Emotional trend | "Anxiety peaks before bedtime" |
| `preference` | User preference | "Prefers short, actionable suggestions" |

---

## Memory Source Kinds

| Source | Where From | Examples |
|--------|-----------|----------|
| `summary` | `session.summary` | Session overview |
| `key_moment` | `session.key_moments[]` | Specific moments |
| `follow_up_topic` | `session.follow_up_topics[]` | Unresolved topics |
| `exact_user_request` | Detected in text | "Remember this phrase for me" |

---

## Canonical Memory Example

A canonical memory is one the user explicitly asked to remember:

```json
{
  "memory_id": "mem_sess_011_exact_1",
  "memory_type": "grounding_phrase",
  "memory_source_kind": "exact_user_request",
  "summary": "Grounding phrase: Quiet room, soft blanket, slow breath.",
  "exact_value": "Quiet room, soft blanket, slow breath.",
  "canonical_slot": "grounding_phrase",
  "is_canonical": true,
  "user_explicitly_asked_to_remember": true,
  "confidence": 1.0,
  "sensitivity": 0.2
}
```

---

## Risk Flags and Safety

| Risk Flag | Effect on Memory |
|-----------|------------------|
| `suicidal_ideation` | `sensitivity=1.0`, blocked from all references |
| `self_harm` | `sensitivity=1.0`, blocked |
| `severe_isolation` | `sensitivity=0.8`, opener blocked |
| `substance_use` | `sensitivity=0.7`, vague references only |
| `domestic_conflict` | `sensitivity=0.8`, no direct questions |

---

## Sensitivity Levels

| Level | Meaning | Example |
|-------|---------|---------|
| 0.0-0.3 | Safe to reference freely | Grounding phrases, goals |
| 0.3-0.6 | Reference cautiously | Unresolved work stress |
| 0.6-0.8 | Avoid in opener, vague only | Relationship conflicts |
| 0.8-1.0 | Blocked from all references | Self-harm, severe isolation |

---

## Embedding Text

Each memory card generates rich embedding text via `to_embedding_text()`:

```
Memory type: grounding_phrase. Source kind: exact_user_request.
Theme: sleep hygiene. Source text: User chose a grounding phrase.
Summary: Grounding phrase: Quiet room, soft blanket, slow breath.
Topic tags: sleep hygiene, anxiety, bedtime.
Primary emotion: anxiety. Secondary emotions: overwhelmed.
Resolution: unresolved. Exact value: Quiet room, soft blanket, slow breath.
User explicitly asked to remember: yes.
```

This rich text (not just the summary) ensures the vector DB captures theme, emotion, type, and exact value for better retrieval.