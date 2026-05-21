"""
Project Recall — Vector Store

Local ChromaDB wrapper for memory embeddings and retrieval.

Design:
- Persistent ChromaDB client stored in data/chroma_project_recall_db/.
- Cosine similarity for semantic search.
- Metadata filtering by user_id and other fields.
- Batch indexing for memory efficiency.
"""
import os
import json
from typing import List, Dict, Optional

import chromadb

# Import active paths from central config
from app.paths import (
    PROJECT_RECALL_CHROMA_DIR,
    PROJECT_RECALL_MEMORIES_PATH,
    PROJECT_RECALL_COLLECTION,
)

CHROMA_DIR = PROJECT_RECALL_CHROMA_DIR
MEMORIES_PATH = PROJECT_RECALL_MEMORIES_PATH
DEFAULT_COLLECTION = PROJECT_RECALL_COLLECTION


def get_client():
    """
    Get or create a persistent ChromaDB client.
    
    Returns:
        chromadb.PersistentClient instance.
    """
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_collection(client, name: str = "project_recall_memories"):
    """
    Get or create the memories collection.
    
    Uses cosine space (hnsw:space=cosine) for semantic similarity.
    
    Args:
        client: ChromaDB client.
        name: Collection name.
    
    Returns:
        ChromaDB collection object.
    """
    try:
        return client.get_collection(name=name)
    except Exception:
        return client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )


def build_index(memories: List[Dict], embedding_fn, batch_size: int = 100, collection_name: str = None):
    """
    Build vector index from extracted memories.
    
    Clears any existing index, then adds memories in batches.
    Stores rich metadata for retrieval filtering and reranking.
    
    Args:
        memories: List of memory dicts.
        embedding_fn: Function that takes a list of texts and returns embeddings.
        batch_size: Number of memories to index per batch.
        collection_name: Optional collection name override.
    
    Returns:
        The ChromaDB collection.
    """
    client = get_client()
    name = collection_name or DEFAULT_COLLECTION
    collection = get_collection(client, name=name)

    # Clear existing
    try:
        existing = collection.count()
        if existing > 0:
            print(f"Clearing existing {existing} memories from index...")
            client.delete_collection(collection.name)
            collection = get_collection(client, name=name)
    except Exception:
        pass

    total = len(memories)
    print(f"Building index for {total} memories...")

    for i in range(0, total, batch_size):
        batch = memories[i : i + batch_size]

        ids = [m["memory_id"] for m in batch]
        documents = [m.get("summary", "") for m in batch]
        metadatas = []
        for m in batch:
            emo = m.get("emotion", {})
            meta = {
                # Core IDs
                "memory_id": str(m["memory_id"]),
                "user_id": str(m["user_id"]),
                "source_session_id": str(m.get("source_session_id", "")),
                "source_timestamp": str(m.get("source_timestamp", "")),
                # Memory type info
                "memory_type": str(m["memory_type"]),
                "memory_source_kind": str(m.get("memory_source_kind", "key_moment")),
                "theme": str(m.get("theme", "")),
                # Rich text content
                "source_text": str(m.get("source_text", "")),
                "summary": str(m.get("summary", "")),
                "exact_value": str(m.get("exact_value", "") or ""),
                "canonical_slot": str(m.get("canonical_slot", "") or ""),
                # Topic tags
                "topic_tags_json": json.dumps(m.get("topic_tags", []), ensure_ascii=False),
                "follow_up_topics_json": json.dumps(m.get("follow_up_topics", []), ensure_ascii=False),
                "risk_flags_json": json.dumps(m.get("risk_flags", []), ensure_ascii=False),
                # Emotion
                "emotion_primary": str(emo.get("primary", "neutral")),
                "emotion_secondary_json": json.dumps(emo.get("secondary", []), ensure_ascii=False),
                "emotion_all_json": json.dumps(emo.get("all_emotions", []), ensure_ascii=False),
                "emotion_intensity": float(emo.get("intensity", 0.5)),
                "emotion_trajectory": str(emo.get("trajectory", "unknown")),
                # Safety
                "resolved_status": str(m.get("resolved_status", "unknown")),
                "importance": float(m.get("importance", 0.5)),
                "sensitivity": float(m.get("sensitivity", 0.0)),
                "safe_to_reference_in_opener": bool(m.get("safe_to_reference_in_opener", True)),
                "follow_up_recommended": bool(m.get("follow_up_recommended", False)),
                "is_canonical": bool(m.get("is_canonical", False)),
                "user_explicitly_asked_to_remember": bool(m.get("user_explicitly_asked_to_remember", False)),
                "is_distractor": bool(m.get("is_distractor", False)),
                "confidence": float(m.get("confidence", 0.5)),
            }
            metadatas.append(meta)
        embeddings = embedding_fn([m.get("embedding_text", m.get("summary", "")) for m in batch])

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        print(f"  Indexed {min(i + batch_size, total)}/{total}")

    print(f"Index built. Total: {collection.count()}")
    return collection


def query_index(
    query_embedding: List[float],
    user_id: Optional[str] = None,
    top_k: int = 5,
    where_filter: Optional[Dict] = None,
):
    """
    Query the vector index with optional user and metadata filters.
    
    Builds a ChromaDB where clause from user_id and optional filter dict.
    
    Args:
        query_embedding: The query vector.
        user_id: Filter by user_id (recommended for multi-user).
        top_k: Number of results.
        where_filter: Additional metadata filters.
    
    Returns:
        ChromaDB query results dict.
    """
    client = get_client()
    collection = get_collection(client)

    conditions = []
    if user_id:
        conditions.append({"user_id": {"$eq": user_id}})
    if where_filter:
        for key, value in where_filter.items():
            conditions.append({key: {"$eq": value}})

    if len(conditions) == 0:
        filter_dict = None
    elif len(conditions) == 1:
        filter_dict = conditions[0]
    else:
        filter_dict = {"$and": conditions}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=filter_dict,
        include=["metadatas", "distances", "documents"],
    )

    return results
