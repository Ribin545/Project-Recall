"""
Project Recall - LLM Client

Unified provider wrapper for text generation.

Currently supported providers:
- Ollama (local)
- Gemini (hosted API)
"""
import httpx
from typing import List, Dict, Tuple

from app.config import (
    LLM_PROVIDER,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_API_BASE,
)


def _split_system_and_messages(messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    """Split a chat history into one concatenated system prompt plus non-system messages."""
    system_parts = []
    non_system = []
    for message in messages:
        if message.get("role") == "system":
            content = (message.get("content") or "").strip()
            if content:
                system_parts.append(content)
        else:
            non_system.append(message)
    return "\n\n".join(system_parts).strip(), non_system


def _chat_ollama(messages: List[Dict[str, str]], model: str = None) -> str:
    """Send a chat request to Ollama and return the assistant response text."""
    model = model or OLLAMA_MODEL
    url = f"{OLLAMA_HOST}/api/chat"

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            assistant_message = data.get("message", {})
            content = assistant_message.get("content", "").strip()

            if not content:
                return "I'm here, but I didn't get a clear response. Could you say that again?"

            return content

    except httpx.ConnectError:
        return (
            "It looks like Ollama isn't running. "
            "Please start Ollama and make sure the model is available."
        )
    except httpx.TimeoutException:
        return (
            "Hmm, the model is taking longer than usual to respond. "
            "You might be running on limited hardware, or the model could be loading. Try again in a moment."
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            return (
                f"Model '{model}' was not found in Ollama. "
                f"Try running: ollama pull {model}"
            )
        return (
            f"Ollama returned an error (status {status}). "
            "Please check that the model is installed and Ollama is running."
        )
    except Exception:
        return (
            "Something went wrong while reaching the AI backend. "
            "Please check your setup and try again."
        )


def _chat_gemini(messages: List[Dict[str, str]], model: str = None) -> str:
    """Send a chat request to the Gemini API and return the generated text."""
    if not GEMINI_API_KEY:
        return (
            "Gemini is selected as the LLM provider, but GEMINI_API_KEY is not set. "
            "Add it to your .env file or switch LLM_PROVIDER back to ollama."
        )

    model = model or GEMINI_MODEL
    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    system_prompt, non_system_messages = _split_system_and_messages(messages)

    # Add conversational instruction for Gemma models
    if "gemma" in model.lower():
        system_prompt = (
            system_prompt + "\n\nCRITICAL: Respond in a warm, natural, conversational tone. "
            "Do NOT use bullet points, markdown, asterisks, or analytical summaries. "
            "Write as if speaking directly to a friend — short sentences, gentle language. "
            "No headers, no bold text, no lists. Just plain warm text."
        )

    contents = []
    for message in non_system_messages:
        role = message.get("role", "user")
        if role == "assistant":
            role = "model"
        elif role not in ("user", "model"):
            role = "user"

        contents.append(
            {
                "role": role,
                "parts": [{"text": message.get("content", "")}],
            }
        )

    if not contents:
        contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

    payload = {"contents": contents}
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, params={"key": GEMINI_API_KEY}, json=payload)
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return "Gemini returned no candidates. Please try again."

            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(part.get("text", "") for part in parts).strip()
            if not content:
                return "Gemini returned an empty response. Please try again."

            # Post-process Gemma responses: remove bullet markers
            if "gemma" in model.lower():
                import re
                # Remove bullet markers like "*   " or "- "
                content = re.sub(r'^\s*[\*\-]\s+', '', content, flags=re.MULTILINE)
                # Remove markdown bold/italic
                content = re.sub(r'\*\*|\*|__|_', '', content)
                # Clean up extra whitespace
                content = re.sub(r'\n\s*\n', '\n\n', content).strip()

            return content

    except httpx.TimeoutException:
        return (
            "Gemini is taking longer than usual to respond. "
            "Please try again in a moment."
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        if status in (401, 403):
            return (
                "Gemini rejected the request. Please verify GEMINI_API_KEY and model access. "
                f"(status {status})"
            )
        if status == 404:
            return (
                f"Gemini model '{model}' was not found. "
                "Please verify GEMINI_MODEL in .env."
            )
        return f"Gemini returned an error (status {status}). Details: {detail}"
    except Exception:
        return (
            "Something went wrong while reaching the Gemini backend. "
            "Please check your setup and try again."
        )


def chat(messages: List[Dict[str, str]], model: str = None) -> str:
    """
    Send a list of messages to the configured LLM provider and return the reply.

    Args:
        messages: A list of dicts with keys "role" and "content".
        model: Optional model override. Defaults to the active provider model.

    Returns:
        The assistant's text response, or a friendly fallback message on error.
    """
    provider = LLM_PROVIDER
    if provider == "gemini":
        return _chat_gemini(messages, model=model)
    if provider == "ollama":
        return _chat_ollama(messages, model=model)
    return (
        f"Unsupported LLM_PROVIDER '{provider}'. "
        "Use 'ollama' or 'gemini' in your .env file."
    )