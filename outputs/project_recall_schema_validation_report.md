# Project Recall Schema Validation Report

**Result: 11/11 checks passed**

## Checks
  ✅ File exists
  ✅ Session count 8-15
  ✅ All required fields present
  ✅ emotional_tone is list
  ✅ key_moments is list of strings
  ✅ risk_flags is list
  ✅ follow_up_topics is list
  ✅ Needle values present
  ✅ At least 3 sessions with follow_up_topics
  ✅ At least 1 session with risk_flags
  ✅ No crisis flags in demo data

## Needle Values
The following exact values must appear in key_moments or summary:
- "I'd like to understand how I can grow from here."
- "steady river, small lantern"
- "walk for ten minutes, then write three calm bullet points before the review"
- "I need some space, but I still care about you."
- "I felt hurt, but I want to understand what happened."

## Summary
- Sessions validated: 11
- Passed: 11
- Failed: 0

This report confirms the generated dataset matches the official
Project Recall session-history JSON schema and is safe for demo use.