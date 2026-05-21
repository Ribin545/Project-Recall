# 05 — Vector DB and Retrieval

## What Is a Vector DB?

A vector database stores **embeddings** — numerical representations of text — and finds similar vectors using distance metrics.

**Why not just keyword search?**
- Keyword search misses semantic similarity ("anxious" vs "nervous")
- Vector search captures meaning even with different words
- But: vector search can retrieve **semantically similar but topically wrong** memories

---

## Embedding Model

**Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Size:** 22MB
- **Dimensions:** 384
- **Source:** HuggingFace (auto-downloaded on first run)
- **Device:** CPU (no GPU required)

**Why this model?**
- Small, fast, no API costs
- Good enough for prototype retrieval
- Production would use larger models (e.g., `all-mpnet-base-v2`) or domain-specific models

---

## What Gets Embedded?

Each memory card generates rich embedding text via `to_embedding_text()`:

```python
"Memory type: grounding_phrase. Source kind: exact_user_request. "
"Theme: sleep hygiene. Summary: Grounding phrase: Quiet room... "
"Topic tags: sleep hygiene, anxiety. Primary emotion: anxiety. "
"Resolution: unresolved. Exact value: Quiet room, soft blanket, slow breath."
```

**Why rich text?**
- Embeds memory type, theme, emotion, resolution, exact value
- Not just the summary — which might be too generic
- Enables retrieval by emotion, type, or theme, not just keywords

---

## Good vs Bad Embedding Text

| Bad (just summary) | Good (rich embedding text) |
|-------------------|---------------------------|
| "User felt anxious" | "Memory type: grounding_phrase. Theme: sleep hygiene. Primary emotion: anxiety. Exact value: Quiet room, soft blanket, slow breath." |

The bad version could match any anxiety-related query. The good version matches specific queries about sleep + anxiety + grounding phrases.

---

## ChromaDB Configuration

| Setting | Value |
|---------|-------|
| Library | `chromadb` (Python client) |
| Persist directory | `data/chroma_project_recall_db` |
| Collection name | `project_recall_memories` |
| Distance metric | Cosine similarity |
| Metadata stored | All memory fields (for filtering) |

---

## Dense Vector Retrieval

`app/memory_retriever.py` implements dense retrieval:

1. Embed user query → 384-dimension vector
2. Query ChromaDB collection → get top-k by cosine similarity
3. Filter by `user_id` (user isolation)
4. Return candidate memory cards

```python
# Default retrieval
candidates = retriever.retrieve(query="anxiety before bed", user_id="demo_user", top_k=12)
```

---

## Hybrid Retrieval (Sparse + Dense)

`app/hybrid_memory_retriever.py` implements hybrid retrieval:

| Component | Role |
|-----------|------|
| **Dense** | Semantic similarity via embeddings |
| **Sparse** | Keyword overlap via BM25-style scoring |
| **Fusion** | Weighted combination: `score = α*dense + (1-α)*sparse` |

**Why hybrid?**
- Dense catches semantic similarity ("anxious" ≈ "nervous")
- Sparse ensures keyword matches aren't lost
- Better recall for exact phrases and technical terms

---

## Why Vector DB Is a Candidate Generator

**Critical:** The vector DB does **not** decide which memory to use. It only generates candidates.

```
Vector DB → Top 12-15 candidates
    ↓
Best Memory Selector → Ranked by YAML weights
    ↓
LLM Relevance Judge → Approve / Reject
    ↓
Single approved memory → Injected into prompt
```

**Why this matters:**
- Vector DB might retrieve a memory about "family dinner" when user asks about "dinner anxiety"
- The judge catches this mismatch and rejects it
- Only approved memories reach the final prompt

---

## Rebuilding the Index

```bash
# Auto-clears old collection and rebuilds
python app/build_memory_index.py

# Or manually
rm -rf data/chroma_project_recall_db
python app/build_memory_index.py
```

**Index includes:**
- All memory cards from `data/extracted_memories_project_recall.json`
- Metadata for filtering (user_id, theme, memory_type, etc.)
- Rich embedding text for each memory

---

## Debugging Retrieval

Test retrieval via API:
```bash
curl "http://localhost:8000/debug/retrieve-memory/demo_user?q=anxiety%20before%20bed"
```

Or in code:
```python
from app.memory_retriever import MemoryRetriever
r = MemoryRetriever("data/chroma_project_recall_db", "project_recall_memories")
results = r.retrieve("grounding phrase", user_id="demo_user", top_k=5)
for res in results:
    print(f"{res['memory_id']}: {res['summary'][:60]}...")
```

---

## Production Upgrades

| Current | Production Upgrade |
|---------|-------------------|
| all-MiniLM-L6-v2 (384d) | Domain-specific or larger model (768d+) |
| Pure dense | Hybrid dense + sparse + reranker |
| Cosine similarity | Learned ranking model |
| Single collection | Per-user or per-tenant collections |
| Local ChromaDB | Pinecone/Weaviate/Qdrant with replication |