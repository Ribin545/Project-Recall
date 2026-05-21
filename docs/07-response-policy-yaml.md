# 07 — Response Policy YAML

## What Is response_policy.yaml?

`config/response_policy.yaml` is the **single control file** for the entire system's behavior. Product/clinical teams can tune responses by editing this file — no code changes required.

**What it controls:**
- How memories are selected (weights, penalties, modes)
- How the assistant responds per emotion
- How direct memory questions are handled
- Memory type safety rules
- Re-engagement rules

---

## Global Safety

```yaml
global_safety:
  never_reference_high_sensitivity_in_opener: true
  never_ask_directly_about_sensitive_memory_unless_user_mentions: true
  never_expose_exact_value_for_emotional_disclosure: true
  max_memories_in_response: 1
  use_uncertainty_language: false
  avoid_mechanical_phrases:
    - "according to your records"
    - "retrieved memory"
    - "database"
    - "stored memory"
  default_allowed_detail_level: "exact_value"
```

| Setting | Meaning |
|---------|---------|
| `max_memories_in_response` | Only inject 1 memory per response |
| `avoid_mechanical_phrases` | Prevents robotic language |
| `default_allowed_detail_level` | Default detail level when emotion not matched |

---

## Selection Modes

Selection modes define how `best_memory_selector.py` scores candidates:

### emotional_context (default)
```yaml
semantic_similarity_weight: 0.25
emotion_match_weight: 0.25
unresolved_weight: 0.20
recency_weight: 0.10
importance_weight: 0.15
follow_up_weight: 0.05
sensitivity_penalty: 0.25
distractor_penalty: 0.40
overuse_penalty: 0.15
```

**Weights sum to ~1.0.** Higher weight = more important for that mode.

### exact_recall (for direct questions)
```yaml
exact_value_weight: 0.30        # Prioritize exact values
memory_type_match_weight: 0.25  # Match memory type (grounding_phrase, etc.)
distractor_penalty: 0.60        # Strongly penalize distractors
```

### notification (for re-engagement)
```yaml
sensitivity_penalty: 1.0        # Block sensitive memories
high_sensitivity_block: true      # Completely block high-sensitivity cards
```

---

## Emotion Rules

Each emotion has its own response behavior:

```yaml
emotion_rules:
  anxiety:
    selection_mode: "emotional_context"
    mention_related_memory: true      # Can reference memory
    ask_direct_question: false         # Don't ask "is this about X?"
    preferred_strategy: "validate_then_offer_choice"
    allowed_detail_level: "exact_value"
    tone: "warm, calm, grounding, gently curious"
    prompt_guidance: "Validate the anxiety first..."
    avoid:
      - "Do not push the user to revisit an anxiety trigger."
```

| Field | Meaning |
|-------|---------|
| `mention_related_memory` | Whether to include memory in response |
| `ask_direct_question` | Whether to ask "is this about [memory]?" |
| `preferred_strategy` | How to handle the memory reference |
| `allowed_detail_level` | How specific the memory reference can be |
| `tone` | Injected into system prompt |
| `prompt_guidance` | Additional instructions for the LLM |
| `avoid` | List of forbidden response patterns |

### Changing Behavior via YAML

**Example 1: Make anxiety responses more direct**
```yaml
# Before
anxiety:
  ask_direct_question: false

# After
anxiety:
  ask_direct_question: true
```

Result: The assistant will now ask "Is this the anxiety you felt before bedtime?" instead of just offering a grounding phrase.

**Example 2: Make sadness responses not reference memories**
```yaml
# Before
sadness:
  mention_related_memory: true

# After
sadness:
  mention_related_memory: false
```

Result: The assistant validates sadness but does not bring up past memories.

**Example 3: Change overwhelm strategy**
```yaml
# Before
overwhelm:
  preferred_strategy: "ground_first_then_offer_memory"

# After
overwhelm:
  preferred_strategy: "validate_then_offer_choice"
```

Result: The assistant asks what the user wants instead of immediately offering a grounding technique.

---

## Allowed Detail Levels

| Level | Meaning | Example |
|-------|---------|---------|
| `none` | No memory reference | [No memory used] |
| `vague` | Hint at theme only | "We talked about some difficult things recently..." |
| `topic_only` | Name the topic | "We explored sleep-related anxiety..." |
| `summary_level` | Summarize the memory | "You mentioned feeling anxious before bed..." |
| `exact_value` | Quote exact phrase | "Your grounding phrase is 'Quiet room, soft blanket, slow breath'" |

The YAML controls which level is allowed per emotion and memory type.

---

## Direct Memory Questions

```yaml
direct_memory_questions:
  enabled: true
  selection_mode: "exact_recall"
  allowed_detail_level: "exact_value"
```

**Query type hints:**
```yaml
query_type_hints:
  grounding_phrase:
    phrases: ["grounding phrase", "calming phrase", "phrase I used"]
    preferred_memory_type: "grounding_phrase"
```

When the user asks "What was my grounding phrase?", the system:
1. Detects `grounding_phrase` query type
2. Switches to `exact_recall` mode
3. Prioritizes `grounding_phrase` memory type
4. Returns exact value

---

## Memory Type Rules

```yaml
memory_type_rules:
  relationship_context:
    can_reference_directly: false      # Never quote directly
    ask_direct_question: false
    preferred_strategy: "only_if_user_mentions"
    protect_named_entities: true      # Don't say "brother" unless user does
    sensitivity_threshold: 0.60

  grounding_phrase:
    can_reference_directly: true        # OK to quote exact phrase
    ask_direct_question: false
    preferred_strategy: "offer_grounding"
    sensitivity_threshold: 0.30
```

| Field | Meaning |
|-------|---------|
| `can_reference_directly` | Can the LLM quote the exact value? |
| `protect_named_entities` | Don't mention names unless user does |
| `sensitivity_threshold` | Minimum sensitivity to trigger caution |

---

## Re-engagement Rules

```yaml
reengagement:
  enabled: true
  max_notifications_per_7_days: 2
  min_days_between_notifications: 2
  never_include_exact_values: true
  never_include_names: true
  never_include_high_sensitivity: true
  notification_detail_level: "exact_value"  # Actually: vague in practice

  trigger_rules:
    gentle_unresolved_followup:
      min_days_since_last_session: 3
      allowed_emotions: [anxiety, sadness, overwhelm, shame, loneliness, uncertainty]
      allowed_resolved_status: [unresolved, partially_resolved]
```

---

## Why YAML?

| Benefit | Example |
|---------|---------|
| **No code changes** | Clinical team edits YAML, deploys |
| **A/B testing** | Two YAML versions, measure outcomes |
| **Audit trail** | YAML versioned in git |
| **Safety** | Clear rules prevent unsafe responses |
| **Customization** | Per-deployment behavior tuning |

---

## Testing YAML Changes

After editing `config/response_policy.yaml`:

```bash
# Test policy adherence
python app/policy_adherence_test.py --provider ollama --model llama3.1

# Test re-engagement
python app/reengagement_test.py

# Manual test via chat UI
uvicorn app.main:app --reload