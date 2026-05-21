"""
Project Recall - Configuration Module

Loads environment variables and exposes app settings.
"""
import os
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
GEMINI_API_BASE = os.getenv(
    "GEMINI_API_BASE",
    "https://generativelanguage.googleapis.com/v1beta",
).rstrip("/")


def get_active_llm_info() -> dict:
    """Return the currently configured LLM provider and model for debug/UI display."""
    if LLM_PROVIDER == "gemini":
        return {
            "provider": "gemini",
            "model": GEMINI_MODEL,
        }
    return {
        "provider": "ollama",
        "model": OLLAMA_MODEL,
    }

# Path to the local JSON chat history file
CHAT_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chat_history.json")