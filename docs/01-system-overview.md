# 01 — System Overview

## What Project Recall Does

Project Recall is a contextual memory system for AI emotional support companions. It ingests structured session summaries, extracts memory cards with emotional metadata, retrieves relevant memories for user queries, and generates warm, safe responses that reference past sessions naturally.

> ⚠️ **Prototype**: This is a technical assessment, not a production clinical system.

---

## Why Not Just Basic RAG?

Basic RAG (Retrieval-Augmented Generation) retrieves documents and stuffs them into the prompt. Project Recall adds layers:

| Layer | Purpose | What It Prevents |
|-------|---------|------------------|
| **Structured memory cards** | Rich metadata (emotion, safety, type) | Plain text without context |
| **LLM relevance judge** | Validates if retrieved memories match the query | Wrong memory injection |
| **Response policy YAML** | Per-emotion rules (tone, detail level, safety) | Unsafe tone or leaks |
| **Turn-local injection** | Memories near current message, not system prompt | Prompt dilution, recency bias |
| **Direct canonical lookup** | Exact recall without vector search | Embedding confusion with distractors |
| **Re-engagement engine** | Rule-based notifications for inactive users | Generic, unsafe check-ins |

---

## Active Data Paths

```
data/sample_project_recall_sessions.json
    ↓ (extract)
data/extracted_memories_project_recall.json
    ↓ (embed + index)
data/chroma_project_recall_db/
```

All default paths are defined in `app/paths.py`:
- `PROJECT_RECALL_SESSIONS_PATH` = `data/sample_project_recall_sessions.json`
- `PROJECT_RECALL_MEMORIES_PATH` = `data/extracted_memories_project_recall.json`
- `PROJECT_RECALL_CHROMA_DIR` = `data/chroma_project_recall_db`
- `PROJECT_RECALL_COLLECTION` = `project_recall_memories`

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Message                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Query Understanding                       │
│  • Intent detection (direct_memory / episode / emotional)   │
│  • Emotion detection (rule-based from keywords)            │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    ┌──────────────────┐            ┌──────────────────┐
    │ Direct Memory    │            │ Vector Retrieval │
    │ Lookup           │            │                  │
    │ (exact match)    │            │ (semantic search)│
    └────────┬─────────┘            └────────┬─────────┘
             │                              │
             ▼                              ▼
    ┌──────────────────┐            ┌──────────────────┐
    │ Canonical Memory │            │ Top Candidates   │
    │ (exact_value)    │            │ (12-15 cards)    │
    └────────┬─────────┘            └────────┬─────────┘
             │                              │
             │                              ▼
             │                    ┌──────────────────┐
             │                    │ LLM Relevance    │
             │                    │ Judge            │
             │                    │ (approve/reject) │
             │                    └────────┬─────────┘
             │                              │
             └──────────────┬───────────────┘
                            ▼
              ┌─────────────────────────────┐
              │    Response Policy YAML     │
              │  • Detail level control      │
              │  • Tone per emotion          │
              │  • Safety guardrails         │
              └─────────────┬───────────────┘
                            ▼
              ┌─────────────────────────────┐
              │   Turn-Local Prompt Builder  │
              │  • System prompt             │
              │  • Recent history (5 turns)  │
              │  • Approved memory block     │
              │  • Current user message      │
              └─────────────┬───────────────┘
                            ▼
              ┌─────────────────────────────┐
              │       LLM Response           │
              │    (Ollama or Gemini)        │
              └─────────────────────────────┘
```

---

## Main Modules

| Module | File | Role |
|--------|------|------|
| **Config** | `app/config.py` | Environment variables, settings |
| **Paths** | `app/paths.py` | Central default file paths |
| **Schema** | `app/memory_schema.py` | Pydantic models for Memory, Emotion |
| **Extractor** | `app/memory_extractor.py` | Extracts memory cards from session JSON |
| **Adapter** | `app/project_recall_schema_adapter.py` | Adapts official schema to internal format |
| **Vector Store** | `app/vector_store.py` | ChromaDB wrapper |
| **Retriever** | `app/memory_retriever.py` | Dense vector retrieval + emotion reranking |
| **Hybrid Retriever** | `app/hybrid_memory_retriever.py` | Sparse + dense hybrid retrieval |
| **Best Selector** | `app/best_memory_selector.py` | Score-based memory selection with YAML weights |
| **Emotion Planner** | `app/emotional_memory_planner.py` | Decides which memory, how, what tone |
| **Relevance Judge** | `app/memory_relevance_judge.py` | LLM validates memory relevance |
| **Direct Lookup** | `app/direct_memory_lookup.py` | Canonical exact memory lookup |
| **Emotion Detector** | `app/current_emotion_detector.py` | Rule-based emotion detection |
| **Topic Extractor** | `app/current_topic_extractor.py` | Rule-based topic extraction |
| **Query Builder** | `app/emotion_aware_query_builder.py` | Emotion-tailored retrieval queries |
| **Response Policy** | `app/response_policy.py` | YAML policy loader + interpreter |
| **Prompts** | `app/prompts.py` | System prompt + memory-aware prompt builder |
| **LLM Client** | `app/llm_client.py` | Unified Ollama/Gemini wrapper |
| **Main App** | `app/main.py` | FastAPI routes |
| **Chat Store** | `app/chat_store.py` | Local JSON history + memory settings |
| **Reengagement** | `app/reengagement_rules.py` | Rule-based notification engine |
| **Reengagement State** | `app/reengagement_state.py` | User state helpers |

---

## Response Flow

1. **User sends message** → POST `/chat`
2. **Detect intent** → `query_understanding.py` classifies intent
3. **Detect emotion** → `current_emotion_detector.py` maps keywords to emotions
4. **Route decision**:
   - Direct question → `direct_memory_lookup.py` → exact answer
   - Emotional query → retrieval + judge + policy
   - Generic chat → no memory
5. **Retrieve candidates** → `memory_retriever.py` (dense) or `hybrid_memory_retriever.py` (hybrid)
6. **Select best** → `best_memory_selector.py` scores candidates
7. **Judge relevance** → `memory_relevance_judge.py` approves/rejects
8. **Apply policy** → `response_policy.py` loads YAML rules
9. **Build prompt** → `prompts.py` injects approved memory turn-locally
10. **Generate response** → `llm_client.py` sends to Ollama/Gemini
11. **Store history** → `chat_store.py` saves for next turn