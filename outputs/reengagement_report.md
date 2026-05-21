# Re-Engagement Trigger Logic Report
**Date:** 2026-05-21 03:25:13
**Results:** 10/10 PASS
---
## Summary
The re-engagement system uses rule-based logic to decide whether to send a notification,
what type, and what safe copy to use. It integrates with:
- `config/response_policy.yaml` (reengagement section)
- `data/extracted_memories_project_recall.json` (emotional metadata + memory types)
- `best_memory_selector.py` (notification mode scoring)
---
## Scenario Results
| Scenario | Should Send | Type | Selected Memory | Copy | Blocked By | Status |
|---|---|---|---|---|---|---|
| Unresolved anxiety, 3 days inactive | yes | gentle_unresolved_followup | synthetic_goal_001 | I know last time felt heavy. I'm here when you're ready to t... | None | PASS |
| Coping follow-up plan, 2 days inactive | yes | coping_strategy_checkin | mem_sess_001_fu00 | Want to check in on the small step that felt calming last ti... | None | PASS |
| 7+ days inactive, soft return | yes | soft_return | synthetic_goal_001 | Whenever you're ready, we can pick up gently from where we l... | None | PASS |
| Notification fatigue (2 sent this week) | no | no_notification | None | -... | fatigue | PASS |
| Notifications disabled by user | no | no_notification | None | -... | consent | PASS |
| Quiet hours active | no | no_notification | None | -... | quiet_hours | PASS |
| High-sensitivity memory should not be selected | yes | gentle_unresolved_followup | synthetic_goal_001 | I'm here. No judgment, just a quiet space whenever you're re... | None | PASS |
| Distractor memories should not be selected | yes | gentle_unresolved_followup | synthetic_goal_001 | I know last time felt heavy. I'm here when you're ready to t... | None | PASS |
| Exact-value memory must not leak into copy | yes | gentle_unresolved_followup | synthetic_goal_001 | I know last time felt heavy. I'm here when you're ready to t... | None | PASS |
| Goal progress memory triggers goal checkin | yes | goal_progress_checkin | synthetic_goal_001 | The goal you were excited about — want to celebrate one smal... | None | PASS |

---
## Detailed Per-Scenario Breakdown

### Scenario 1: Unresolved anxiety, 3 days inactive
**Expected:** `gentle_unresolved_followup`
**Actual:** `gentle_unresolved_followup`
**Status:** PASS
**Should send:** True
**Priority:** high
**Selected memory:** synthetic_goal_001
**Memory type:** user_goal
**Selected topic:** personal goal
**Selected emotion:** hopefulness
**Copy:** "I know last time felt heavy. I'm here when you're ready to talk."
**Reason:** gentle_unresolved_followup triggered after 3 days. Memory: user_goal (importance=0.82, resolved=partially_resolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

### Scenario 2: Coping follow-up plan, 2 days inactive
**Expected:** `coping_strategy_checkin`
**Actual:** `coping_strategy_checkin`
**Status:** PASS
**Should send:** True
**Priority:** medium
**Selected memory:** mem_sess_001_fu00
**Memory type:** follow_up_intent
**Selected topic:** plan and follow-up
**Selected emotion:** anxiety
**Copy:** "Want to check in on the small step that felt calming last time?"
**Reason:** coping_strategy_checkin triggered after 2 days. Memory: follow_up_intent (importance=0.8, resolved=unresolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

### Scenario 3: 7+ days inactive, soft return
**Expected:** `soft_return`
**Actual:** `soft_return`
**Status:** PASS
**Should send:** True
**Priority:** low
**Selected memory:** synthetic_goal_001
**Memory type:** user_goal
**Selected topic:** personal goal
**Selected emotion:** hopefulness
**Copy:** "Whenever you're ready, we can pick up gently from where we left off."
**Reason:** soft_return triggered after 7 days. Memory: user_goal (importance=0.82, resolved=partially_resolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

### Scenario 4: Notification fatigue (2 sent this week)
**Expected:** `no_notification`
**Actual:** `no_notification`
**Status:** PASS
**Should send:** False
**Priority:** none
**Selected memory:** None
**Memory type:** None
**Selected topic:** None
**Selected emotion:** None
**Copy:** "None"
**Reason:** Notification blocked: fatigue
**Safety notes:**
- Blocked by fatigue
**Blocked by:** fatigue

### Scenario 5: Notifications disabled by user
**Expected:** `no_notification`
**Actual:** `no_notification`
**Status:** PASS
**Should send:** False
**Priority:** none
**Selected memory:** None
**Memory type:** None
**Selected topic:** None
**Selected emotion:** None
**Copy:** "None"
**Reason:** Notification blocked: consent
**Safety notes:**
- Blocked by consent
**Blocked by:** consent

### Scenario 6: Quiet hours active
**Expected:** `no_notification`
**Actual:** `no_notification`
**Status:** PASS
**Should send:** False
**Priority:** none
**Selected memory:** None
**Memory type:** None
**Selected topic:** None
**Selected emotion:** None
**Copy:** "None"
**Reason:** Notification blocked: quiet_hours
**Safety notes:**
- Blocked by quiet_hours
**Blocked by:** quiet_hours

### Scenario 7: High-sensitivity memory should not be selected
**Expected:** `gentle_unresolved_followup`
**Actual:** `gentle_unresolved_followup`
**Status:** PASS
**Should send:** True
**Priority:** high
**Selected memory:** synthetic_goal_001
**Memory type:** user_goal
**Selected topic:** personal goal
**Selected emotion:** hopefulness
**Copy:** "I'm here. No judgment, just a quiet space whenever you're ready."
**Reason:** gentle_unresolved_followup triggered after 3 days. Memory: user_goal (importance=0.82, resolved=partially_resolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

### Scenario 8: Distractor memories should not be selected
**Expected:** `gentle_unresolved_followup`
**Actual:** `gentle_unresolved_followup`
**Status:** PASS
**Should send:** True
**Priority:** high
**Selected memory:** synthetic_goal_001
**Memory type:** user_goal
**Selected topic:** personal goal
**Selected emotion:** hopefulness
**Copy:** "I know last time felt heavy. I'm here when you're ready to talk."
**Reason:** gentle_unresolved_followup triggered after 3 days. Memory: user_goal (importance=0.82, resolved=partially_resolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

### Scenario 9: Exact-value memory must not leak into copy
**Expected:** `gentle_unresolved_followup`
**Actual:** `gentle_unresolved_followup`
**Status:** PASS
**Should send:** True
**Priority:** high
**Selected memory:** synthetic_goal_001
**Memory type:** user_goal
**Selected topic:** personal goal
**Selected emotion:** hopefulness
**Copy:** "I know last time felt heavy. I'm here when you're ready to talk."
**Reason:** gentle_unresolved_followup triggered after 3 days. Memory: user_goal (importance=0.82, resolved=partially_resolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

### Scenario 10: Goal progress memory triggers goal checkin
**Expected:** `goal_progress_checkin`
**Actual:** `goal_progress_checkin`
**Status:** PASS
**Should send:** True
**Priority:** medium
**Selected memory:** synthetic_goal_001
**Memory type:** user_goal
**Selected topic:** personal goal
**Selected emotion:** hopefulness
**Copy:** "The goal you were excited about — want to celebrate one small step?"
**Reason:** goal_progress_checkin triggered after 5 days. Memory: user_goal (importance=0.82, resolved=partially_resolved).
**Safety notes:**
- Copy passes safety audit.
**Blocked by:** None

---
## Safety Audit Summary
All notification copies were audited for:
- No exact_value leakage
- No forbidden phrases (anxiety, shame, therapy, etc.)
- No names or private details
- Vague, warm, optional tone
- Lock-screen safe

**All scenarios passed safety audit.**
