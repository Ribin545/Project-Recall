# 10 — Re-engagement Logic

## What Is Re-engagement?

Re-engagement simulates **push notification decisions** for inactive users. It is **not chat** — it decides whether to send a notification and what vague, safe copy to include.

**Goal:** Bring users back when they have unresolved topics, without being annoying or unsafe.

---

## Inputs to the Re-engagement Engine

`app/reengagement_rules.py` evaluates:

| Input | Source |
|-------|--------|
| `days_since_last_session` | Calculated from last session timestamp |
| `last_emotion` | From most recent session |
| `unresolved_themes` | Memories with `resolved_status: unresolved` |
| `follow_up_topics` | `follow_up_intent` memories |
| `notification_count_7d` | How many notifications sent recently |
| `quiet_hours` | Configured quiet hours |
| `consent` | User preference for notifications |

---

## Notification Types

| Type | When | Example Copy |
|------|------|--------------|
| `gentle_unresolved_followup` | Unresolved emotional topics after 3+ days | "We were exploring some important things last time. Want to continue?" |
| `coping_strategy_checkin` | Coping strategies after 2+ days | "How has the calming technique been working?" |
| `goal_progress_checkin` | User goals after 3+ days | "Checking in on your goal from last week." |
| `soft_return` | Inactive 7+ days | "Thinking of you. Here if you want to talk." |
| `no_notification` | No triggers met or safety blocked | [Nothing sent] |

---

## Safety Rules

**Hard blocks:**
- `sensitivity ≥ 0.8` → Blocked from all notifications
- `high_sensitivity_block: true` → Blocked in notification mode
- `never_include_exact_values: true` → No exact phrases in copy
- `never_include_names: true` → No names in copy

**Vagueness requirements:**
```yaml
reengagement:
  notification_detail_level: "vague"  # In practice
```

| Unsafe | Safe |
|--------|------|
| "Remember your grounding phrase 'Quiet room...'" | "We explored some calming techniques." |
| "How is your manager conflict going?" | "There were some work themes we were exploring." |
| "You felt anxious about your brother." | "We were looking at some relationship patterns." |

---

## Example Scenarios

### Scenario 1: Gentle Follow-Up (Approved)
- Last session: 4 days ago
- Emotion: anxiety
- Unresolved: sleep hygiene
- Notifications this week: 1
- **Decision:** Send `gentle_unresolved_followup`
- **Copy:** "We were exploring some important things around rest and calm. Want to pick up where we left off?"

### Scenario 2: Blocked by Sensitivity
- Last session: 5 days ago
- Emotion: sadness
- Unresolved: domestic conflict (sensitivity: 0.9)
- **Decision:** `no_notification`
- **Reason:** High sensitivity blocks all re-engagement

### Scenario 3: Fatigue Limit
- Last session: 2 days ago
- Emotion: overwhelm
- Unresolved: work stress
- Notifications this week: 3 (limit: 2)
- **Decision:** `no_notification`
- **Reason:** Max notifications per week exceeded

---

## Rule Evaluation Flow

```
Input: user state
    ↓
Check consent → No consent? → no_notification
    ↓
Check quiet hours → In quiet hours? → no_notification
    ↓
Check fatigue → Too many notifications? → no_notification
    ↓
Check sensitivity → High sensitivity? → no_notification
    ↓
Evaluate trigger rules
    ↓
Select notification type
    ↓
Generate vague copy
    ↓
Return: {should_send, type, preview_copy}
```

---

## API Endpoint

```
GET /debug/reengagement/{user_id}

Response:
{
  "should_send": true,
  "type": "gentle_unresolved_followup",
  "preview_copy": "We were exploring some important things around rest and calm..."
}
```

---

## Configuration

In `config/response_policy.yaml`:
```yaml
reengagement:
  enabled: true
  max_notifications_per_7_days: 2
  min_days_between_notifications: 2
  never_include_exact_values: true
  never_include_names: true
  never_include_high_sensitivity: true

  trigger_rules:
    gentle_unresolved_followup:
      min_days_since_last_session: 3
      allowed_emotions: [anxiety, sadness, overwhelm, shame, loneliness, uncertainty]
      allowed_resolved_status: [unresolved, partially_resolved]
```

---

## Why Vague Copy Matters

| Risk | Mitigation |
|------|-----------|
| Notification seen by others | No exact values or names |
| User not ready to discuss | "Want to continue?" is optional |
| Wrong memory triggered | Vague language applies to multiple topics |

---

## Production Improvements

- **User preference UI:** Let users configure notification frequency
- **Opt-in/opt-out:** Per-topic notification preferences
- **A/B testing:** Test copy variants for re-engagement rates
- **Time-of-day optimization:** Send when user historically opens app
- **Multi-channel:** SMS, email, push — with different copy constraints