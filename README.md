# Project Recall — Contextual Memory for AI Support Companions

Project Recall is a contextual memory and re-engagement prototype for an AI emotional support companion. It ingests structured session summaries, extracts memory cards, retrieves relevant memories, judges their relevance, applies safety policies, and generates warm, memory-aware LLM responses.

> ⚠️ **Prototype status**: This is a technical assessment project, not a production clinical system.

---

## 1. What This Is

The problem: returning users feel the AI does not remember prior sessions. Generic reminders are weak. The goal is to **remember naturally, safely, and selectively** — without stuffing all history into the prompt.

Project Recall solves this by:

- Ingesting **structured session JSON** (not raw transcripts)
- Extracting **rich memory cards** with emotion metadata
- Using **vector DB retrieval** to find candidate memories
- Applying an **LLM relevance judge** to confirm topical match
- Applying **response policy rules** per emotion and memory type
- Injecting only **approved memories** into a **turn-local prompt**
- Supporting **direct canonical lookup** for exact recall questions
- Generating **re-engagement notifications** based on unresolved topics

---

## 2. The Problem

| Problem | Why It Happens | Our Solution |
|---|---|---|
| AI forgets past sessions | No persistent memory | Structured memory cards + vector DB |
| Generic "check-ins" | No emotional context | Emotion-aware retrieval + policy |
| Wrong memory injected | Semantic-only retrieval | LLM judge + topic-aware selection |
| Unsafe memory leaks | No safety controls | Sensitivity scoring + YAML policy |
| Prompt bloat | Full history stuffed | Turn-local injection of top-1 memory |

---

## 3. High-Level Architecture

```
Session JSON
    ↓
Memory Extraction  →  Memory Cards (with emotion + safety metadata)
    ↓
Vector DB / Hybrid Retrieval  →  Top candidates
    ↓
LLM Memory Relevance Judge  →  Approved / Rejected
    ↓
Response Policy YAML  →  Detail level, tone, safety
    ↓
Turn-Local Prompt Injection
    ↓
LLM Response
```

**Direct recall path:**
```
"What was my grounding phrase?"
    ↓
Canonical lookup (exact match)
    ↓
Answer with exact value
```

**Re-engagement path:**
```
Unresolved memories + user state
    ↓
Rule engine
    ↓
Safe notification preview (vague, no exact values)
```

---

## 4. Active Data Schema

The system expects session history in this compact JSON format:

```json
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
  "summary": "User described increasing stress...",
  "risk_flags": [],
  "follow_up_topics": [
    "sleep hygiene",
    "manager conflict"
  ]
}
```

**Field mapping:**
| Field | Becomes |
|-------|---------|
| `theme` | topic tags for retrieval |
| `emotional_tone` | emotion metadata (primary, secondary, intensity) |
| `key_moments` | memory cards (exact_value, summary, type) |
| `summary` | session_summary memory card |
| `follow_up_topics` | follow_up_intent memory cards |
| `risk_flags` | sensitivity + safety controls |

---

## 5. Key Concepts

| Term | Definition |
|------|------------|
| **Memory card** | A structured object with summary, emotion, metadata, and optional exact value |
| **Session summary card** | A memory card capturing the overall session theme |
| **Key moment card** | A memory card from a specific moment in the session |
| **Follow-up card** | A memory card tracking unresolved topics for re-engagement |
| **Exact canonical memory** | A memory the user explicitly asked to remember, with `is_canonical=true` |
| **Vector DB** | ChromaDB storing memory embeddings for semantic search |
| **LLM relevance judge** | An LLM that validates whether retrieved memories match the user's query |
| **Response policy YAML** | `config/response_policy.yaml` — controls behavior per emotion |
| **Turn-local prompt injection** | Approved memories injected near the current user message, not buried in system prompt |
| **Re-engagement** | Rule-based notification generation for inactive users |

---

## 6. Setup

```bash
# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Configure `.env`:**
```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `gemini` | `ollama` or `gemini` |
| `OLLAMA_HOST` | `http://localhost:11434` | Local Ollama server |
| `OLLAMA_MODEL` | `llama3.1` | Ollama model name |
| `GEMINI_API_KEY` | — | Gemini API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | Gemini model name |

---

## 7. Run the Pipeline

```bash
# 1. Generate sample sessions
python generate_project_recall_sessions.py

# 2. Validate schema
python app/validate_project_recall_sessions.py

# 3. Extract memories
python app/memory_extractor.py

# 4. Build vector index
python app/build_memory_index.py

# 5. Verify end-to-end
python app/validate_active_project_recall_pipeline.py
```

---

## 8. Run the App

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` for the chat UI.

**Main endpoints:**

| Endpoint | Description |
|----------|-------------|
| `POST /chat` | Main chat endpoint (with memory support) |
| `GET /new-session/{user_id}?memory=true` | Start new session |
| `GET /debug/memories/{user_id}` | List extracted memories |
| `GET /debug/retrieve-memory/{user_id}?q=...` | Test vector retrieval |
| `GET /debug/reengagement/{user_id}` | Preview re-engagement decision |

---

## 9. Run Tests

```bash
# Schema + ingestion
python app/project_recall_ingestion_test.py

# Pipeline validation
python app/validate_active_project_recall_pipeline.py

# Policy adherence (requires LLM)
python app/policy_adherence_test.py --provider ollama --model llama3.1

# Re-engagement
python app/reengagement_test.py

# Reliability guardrails
python app/reliability_guardrail_test.py
```

---

## 10. Demo Flow

1. **Generate sessions** → Creates 11 varied sessions
2. **Extract memories** → 66 structured memory cards
3. **Build vector DB** → Embedded + indexed
4. **Exact recall**: "What was my grounding phrase?" → "Quiet room, soft blanket, slow breath."
5. **Episode recall**: "Do you remember that family dinner?" → Contextual summary
6. **Emotional query**: "I've been feeling anxious" → Validates + offers related memory
7. **Edit YAML**: Change `anxiety` → `ask_direct_question: true` → Responses become more direct
8. **Re-engagement preview**: `/debug/reengagement/demo_user` → Safe notification copy

---

## 11. Known Limitations

- **Prototype**, not production — no auth, no clinical escalation
- **LLM judge can fail** — handled by confidence gate + no-memory fallback
- **Extraction depends on summary quality** — better `key_moments` = better memories
- **No full cross-session graph reasoning** — memories are isolated cards
- **No temporal trend analysis** — basic timestamp tracking only
- **No user-facing memory edit/delete UI** — memories are read-only
- **No production database** — local JSON + ChromaDB files

---

## 12. What I Would Do With 2 More Weeks

- LLM extraction with stronger evaluation metrics
- Hybrid dense + sparse retrieval (BM25 + vector + reranker)
- Memory edit/delete UI for users
- Temporal/session graph for cross-session reasoning
- Better policy adherence monitoring + A/B testing
- Clinical review workflow
- Analytics dashboard for memory quality

---

## Documentation

Detailed documentation is in `./docs/`:

| Doc | Topic |
|-----|-------|
| `docs/01-system-overview.md` | Architecture and modules |
| `docs/02-setup-and-running.md` | Full setup guide |
| `docs/03-data-schema-and-memory-cards.md` | Schema and card types |
| `docs/04-memory-extraction.md` | Extraction pipeline |
| `docs/05-vector-db-and-retrieval.md` | Retrieval system |
| `docs/06-llm-relevance-judge.md` | Relevance judge |
| `docs/07-response-policy-yaml.md` | YAML policy reference |
| `docs/08-prompt-injection.md` | Turn-local injection |
| `docs/09-direct-memory-lookup.md` | Exact recall |
| `docs/10-reengagement-logic.md` | Notifications |
| `docs/11-testing-and-reports.md` | Test suite |

---

## License

This is a technical assessment project. Not for production use.

---

## Development Acknowledgment

This project was developed with assistance from **Kimi-k2.6** (Moonshot AI), an AI coding assistant that helped with architecture design, implementation, testing, and documentation.
