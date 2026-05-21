"""
Project Recall — Central Default Paths

Single source of truth for active data file locations.
All active modules should import from here.
"""
import os

# Base directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")

# --- Active Project Recall schema paths ---
PROJECT_RECALL_SESSIONS_PATH = os.path.join(DATA_DIR, "sample_project_recall_sessions.json")
PROJECT_RECALL_MEMORIES_PATH = os.path.join(DATA_DIR, "extracted_memories_project_recall.json")
PROJECT_RECALL_CHROMA_DIR = os.path.join(DATA_DIR, "chroma_project_recall_db")
PROJECT_RECALL_COLLECTION = "project_recall_memories"

# --- Legacy paths (kept for reference, not active) ---
LEGACY_DUMMY_SESSIONS_PATH = os.path.join(DATA_DIR, "dummy_large_session_history.json")
LEGACY_EXTRACTED_MEMORIES_PATH = os.path.join(DATA_DIR, "extracted_memories.json")
LEGACY_CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
LEGACY_COLLECTION = "memories"

# --- Other active data files ---
FORGETTING_QUESTIONS_PATH = os.path.join(DATA_DIR, "forgetting_test_questions.json")
CHAT_HISTORY_PATH = os.path.join(DATA_DIR, "chat_history.json")
RESPONSE_POLICY_PATH = os.path.join(CONFIG_DIR, "response_policy.yaml")