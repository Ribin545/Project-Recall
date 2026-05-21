"""
Project Recall — Build Memory Index

Loads extracted_memories.json (or a specified input), generates embeddings
with sentence-transformers, and stores them in ChromaDB.

Usage:
    python app/build_memory_index.py
    python app/build_memory_index.py --input data/extracted_memories_project_recall.json --persist-dir data/chroma_project_recall_db --collection project_recall_memories

This is a one-time setup script (or re-run when memories change).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentence_transformers import SentenceTransformer

from app.vector_store import build_index

# Import active paths from central config
from app.paths import (
    PROJECT_RECALL_MEMORIES_PATH,
    PROJECT_RECALL_CHROMA_DIR,
    PROJECT_RECALL_COLLECTION,
)

# --- Default paths ---
DEFAULT_MEMORIES_PATH = PROJECT_RECALL_MEMORIES_PATH
DEFAULT_CHROMA_DIR = PROJECT_RECALL_CHROMA_DIR
DEFAULT_COLLECTION = PROJECT_RECALL_COLLECTION

# --- Embedding model ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dim, fast, good quality


def load_memories(memories_path: str):
    """
    Load extracted memories from JSON.
    
    Args:
        memories_path: Path to extracted memories JSON.
    
    Returns:
        List of memory dicts.
    """
    with open(memories_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_embedding_text(memory: dict) -> str:
    """
    Format a memory dict into a source-kind-specific rich text string for embedding.

    Different memory source kinds get different emphasis for better retrieval:
    - summary: emphasizes broad session context
    - key_moment: emphasizes specific moment details
    - follow_up_topic: emphasizes continuation topic
    - exact_user_request: emphasizes exact remembered value
    """
    source_kind = memory.get("memory_source_kind", "key_moment")
    parts = []

    # Common header
    parts.append(f"Memory type: {memory.get('memory_type', '')}.")
    parts.append(f"Source kind: {source_kind}.")

    theme = memory.get("theme", "")
    if theme:
        parts.append(f"Theme: {theme}.")

    # Source-kind-specific content ordering
    if source_kind == "summary":
        # Session summary: broad context first
        summary = memory.get("summary", "")
        if summary:
            parts.append(f"Session summary: {summary}")

        source_text = memory.get("source_text", "")
        if source_text and source_text != summary:
            parts.append(f"Source text: {source_text}")

    elif source_kind == "exact_user_request":
        # Exact canonical: exact value first
        if memory.get("exact_value"):
            parts.append(f"Exact remembered value: {memory['exact_value']}")

        source_text = memory.get("source_text", "")
        if source_text:
            parts.append(f"Source text: {source_text}")

        summary = memory.get("summary", "")
        if summary and summary != source_text:
            parts.append(f"Summary: {summary}")

    elif source_kind == "follow_up_topic":
        # Follow-up: topic first
        source_text = memory.get("source_text", "")
        if source_text:
            parts.append(f"Follow-up topic: {source_text}")

        summary = memory.get("summary", "")
        if summary and summary != source_text:
            parts.append(f"Summary: {summary}")

    else:
        # key_moment and others: source_text first, then summary
        source_text = memory.get("source_text", "")
        if source_text:
            parts.append(f"Source text: {source_text}")

        summary = memory.get("summary", "")
        if summary and summary != source_text:
            parts.append(f"Summary: {summary}")

    # Common metadata
    tags = memory.get("topic_tags", [])
    if tags:
        parts.append(f"Topic tags: {', '.join(tags)}")

    follow_up = memory.get("follow_up_topics", [])
    if follow_up:
        parts.append(f"Follow-up topics: {', '.join(follow_up)}")

    emotion = memory.get("emotion", {})
    if emotion.get("primary"):
        parts.append(f"Primary emotion: {emotion['primary']}")
    if emotion.get("secondary"):
        parts.append(f"Secondary emotions: {', '.join(emotion['secondary'])}")
    if emotion.get("all_emotions"):
        parts.append(f"All emotions: {', '.join(emotion['all_emotions'])}")

    parts.append(f"Resolution: {memory.get('resolved_status', 'unknown')}")

    if memory.get("user_explicitly_asked_to_remember"):
        parts.append("User explicitly asked to remember: yes")

    return ". ".join(parts) + "."


def main():
    """
    Main entry point: load memories, build embeddings, store in ChromaDB.
    """
    parser = argparse.ArgumentParser(description="Build ChromaDB vector index from extracted memories")
    parser.add_argument(
        "--input",
        default=DEFAULT_MEMORIES_PATH,
        help="Path to extracted memories JSON",
    )
    parser.add_argument(
        "--persist-dir",
        default=DEFAULT_CHROMA_DIR,
        help="ChromaDB persistence directory",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="ChromaDB collection name",
    )
    args = parser.parse_args()

    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Loading memories from {args.input}...")
    memories = load_memories(args.input)
    print(f"Loaded {len(memories)} memories.")

    # Pre-compute embedding text
    for m in memories:
        m["embedding_text"] = build_embedding_text(m)

    def embed_fn(texts):
        return model.encode(texts, show_progress_bar=False).tolist()

    # Monkey-patch vector_store paths for this run
    import app.vector_store as vs
    vs.CHROMA_DIR = args.persist_dir
    vs.DEFAULT_COLLECTION = args.collection

    build_index(memories, embed_fn, batch_size=100)

    print("Done.")


if __name__ == "__main__":
    main()
