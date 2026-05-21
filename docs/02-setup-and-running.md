# 02 — Setup and Running

## Python Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Requirements

| Package | Purpose |
|---------|---------|
| `pydantic` | Schema validation (Memory, Emotion models) |
| `tqdm` | Progress bars for batch operations |
| `numpy` | Numerical operations for scoring |
| `pyyaml` | Response policy YAML parsing |
| `fastapi` | Web framework for API |
| `uvicorn[standard]` | ASGI server |
| `python-dotenv` | Environment variable loading |
| `chromadb` | Vector database |
| `sentence-transformers` | Embedding model (all-MiniLM-L6-v2) |
| `httpx` | HTTP client for LLM APIs |

No external Google/Gemini SDK required — calls use raw REST API via `httpx`.

---

## Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Required For | Description |
|----------|---------|--------------|-------------|
| `LLM_PROVIDER` | `gemini` | All | `ollama` or `gemini` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama | Local Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1` | Ollama | Model name to use |
| `GEMINI_API_KEY` | — | Gemini | API key from Google AI Studio |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | Gemini | Model identifier |

**Ollama setup:**
```bash
# Install Ollama from https://ollama.com
ollama pull llama3.1
# or
ollama pull qwen3.5:4b
```

**Gemini setup:**
1. Get API key from [Google AI Studio](https://aistudio.google.com)
2. Set `GEMINI_API_KEY` in `.env`

---

## Data Pipeline

Run these commands in order:

```bash
# 1. Generate 11 sample sessions with canonical memories
python generate_project_recall_sessions.py

# 2. Validate the generated JSON matches schema
python app/validate_project_recall_sessions.py

# 3. Extract structured memory cards
python app/memory_extractor.py
# Or explicitly:
# python app/memory_extractor.py --input data/sample_project_recall_sessions.json --format project_recall --output data/extracted_memories_project_recall.json

# 4. Build vector DB index (auto-clears old collection)
python app/build_memory_index.py
# Or explicitly:
# python app/build_memory_index.py --input data/extracted_memories_project_recall.json --persist-dir data/chroma_project_recall_db --collection project_recall_memories

# 5. Verify everything works end-to-end
python app/validate_active_project_recall_pipeline.py
```

Expected output after step 5:
```
Results: 12/12 PASS
```

---

## Run the Web App

```bash
uvicorn app.main:app --reload
```

Open `http://localhost:8000` for the chat UI.

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Ollama isn't running` | Ollama not started | Start Ollama: `ollama serve` |
| `Model not found` | Model not pulled | `ollama pull <model_name>` |
| `GEMINI_API_KEY not set` | Missing API key | Add to `.env` |
| `ChromaDB collection not found` | Index not built | Run `app/build_memory_index.py` |
| `sentence-transformers` download slow | First run downloads model | Wait for completion |
| `ImportError: No module named app` | Running from wrong directory | `cd project-recall` first |

---

## Rebuilding the Index

If you change memories or want to clear old data:

```bash
# The build script auto-clears the old collection
python app/build_memory_index.py
```

Or manually:
```bash
# Remove old ChromaDB directory
rm -rf data/chroma_project_recall_db
# Rebuild
python app/build_memory_index.py
```

---

## Switching LLM Providers

Edit `.env`:
```bash
# Use local Ollama
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1

# Or use cloud Gemini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.1-flash-lite-preview
```

No code changes needed — `app/llm_client.py` routes automatically.