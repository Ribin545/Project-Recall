"""
Project Recall - FastAPI Backend

Minimal local chat app with optional memory retrieval.
"""
import json
import os
import re
import time
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app import chat_store, llm_client, prompts
from app.config import get_active_llm_info
from app.paths import (
    PROJECT_RECALL_SESSIONS_PATH,
    PROJECT_RECALL_MEMORIES_PATH,
)

# Memory system imports (optional - gracefully degrade if not built yet)
try:
    from app.memory_opener import generate_opener
    from app.memory_retriever import retrieve_memories
    from app.emotional_memory_planner import plan_memory_response
    from app.current_emotion_detector import detect_current_emotion
    from app.emotion_aware_query_builder import build_emotion_aware_query
    from app.best_memory_selector import select_best_memory
    from app.direct_memory_lookup import resolve_direct_memory, get_canonical_candidates
    from app.current_topic_extractor import extract_current_topic_hints
    from app.memory_relevance_judge import judge_memory_relevance
    from app.reengagement_rules import decide_reengagement
    from app.reengagement_state import make_user_state
    from app.response_policy import (
        load_response_policy,
        decide_response_policy,
        generate_policy_based_response,
    )
    # NEW: Reliability upgrades
    from app.hybrid_memory_retriever import hybrid_retrieve_memory_candidates, retrieve_with_fallback
    from app.query_understanding import understand_memory_query
    from app.judge_cache import get_cached_judge_result, save_cached_judge_result
    from app.temporal_utils import parse_time_reference
    _memory_system_available = True
except Exception:
    _memory_system_available = False
    generate_opener = None
    retrieve_memories = None
    plan_memory_response = None
    detect_current_emotion = None
    build_emotion_aware_query = None
    select_best_memory = None
    resolve_direct_memory = None
    get_canonical_candidates = None
    extract_current_topic_hints = None
    judge_memory_relevance = None
    decide_reengagement = None
    make_user_state = None
    load_response_policy = None
    decide_response_policy = None
    generate_policy_based_response = None
    # NEW: Reliability upgrades
    hybrid_retrieve_memory_candidates = None
    retrieve_with_fallback = None
    understand_memory_query = None
    get_cached_judge_result = None
    save_cached_judge_result = None
    parse_time_reference = None

app = FastAPI(title="Project Recall", version="0.1.0")

# Allow CORS so the frontend can talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# --- Request Models ---

class ChatRequest(BaseModel):
    user_id: str
    message: str


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
def serve_index():
    """
    Serve the frontend index.html.
    
    Fallbacks to a simple HTML message if the file is not found.
    """
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Emotion-aware chat with policy-guided memory injection into LLM prompt.
    
    This is the main chat endpoint. It orchestrates the full memory-aware
    pipeline: emotion detection, memory retrieval, policy decision, prompt
    building, LLM generation, and persistence.
    
    Pipeline:
    1. Detect emotion and intent from user message
    2. Build emotion-aware retrieval query
    3. Retrieve relevant memories (direct lookup first, then vector search)
    4. Apply response policy (configurable via YAML)
    5. Build policy-injected system prompt for the LLM
    6. Send to Ollama → LLM generates warm, contextual response
    7. Persist and return
    
    Args:
        req: ChatRequest with user_id and message.
    
    Returns:
        JSON with reply, timing, memory usage flags, and policy details.
    """
    memory_enabled = chat_store.get_user_memory_setting(req.user_id)
    t_start = time.perf_counter()
    timing = {
        "emotion_detection_ms": 0.0,
        "direct_lookup_ms": 0.0,
        "query_build_ms": 0.0,
        "memory_retrieval_ms": 0.0,
        "memory_selection_ms": 0.0,
        "policy_ms": 0.0,
        "prompt_build_ms": 0.0,
        "llm_ms": 0.0,
        "persist_ms": 0.0,
    }

    # Step 1: Detect emotion and intent
    detected_emotion = None
    if detect_current_emotion:
        try:
            t_phase = time.perf_counter()
            detected_emotion = detect_current_emotion(req.message)
            timing["emotion_detection_ms"] = (time.perf_counter() - t_phase) * 1000
        except Exception:
            detected_emotion = None

    if not detected_emotion:
        detected_emotion = {
            "primary": "neutral",
            "intensity": 0.0,
            "intent": "general_chat",
            "needs_memory_lookup": False,
        }

    # Step 2: Memory retrieval pipeline (if needed)
    needs_lookup = detected_emotion.get("needs_memory_lookup", False)
    
    policy_decision = None
    memory_was_used = False
    retrieved_memories = []
    retrieval_query = req.message
    selected_memory = None
    
    # Load active memory for conversation continuity (LLM will decide if to use it)
    active_memory = None
    if memory_enabled:
        try:
            active_memory = chat_store.get_active_memory(req.user_id)
        except Exception:
            active_memory = None

    if memory_enabled and _memory_system_available and needs_lookup:
        # --- NEW: Reliability-aware pipeline ---
        # Step 1b: Query understanding (LLM + rule fallback)
        query_understanding = None
        if understand_memory_query:
            try:
                query_understanding = understand_memory_query(
                    req.message,
                    detected_emotion=detected_emotion,
                    use_llm=True,
                )
            except Exception:
                query_understanding = None

        # Step 1c: Extract topic hints
        topic_hints = None
        if extract_current_topic_hints:
            try:
                topic_hints = extract_current_topic_hints(req.message)
            except Exception:
                topic_hints = None

        # Merge query understanding topic phrases into topic hints
        if query_understanding and query_understanding.get("topic_phrases"):
            if not topic_hints:
                topic_hints = {"topic_hints": [], "strong_topic_terms": [], "topic_family": "general", "confidence": 0.0}
            topic_hints["topic_hints"] = list(set(
                topic_hints.get("topic_hints", []) + query_understanding.get("topic_phrases", [])
            ))
            # Also add related terms for sparse search
            topic_hints["related_terms"] = query_understanding.get("related_terms", [])

        # Step 1d: Parse time reference
        time_ref = None
        if parse_time_reference:
            try:
                time_ref = parse_time_reference(req.message)
            except Exception:
                time_ref = None

        # Determine intent
        is_direct_question = detected_emotion.get("intent") == "direct_memory_question"
        is_episode_recall = detected_emotion.get("intent") == "specific_episode_recall"
        requires_exact = query_understanding.get("requires_exact_value", False) if query_understanding else is_direct_question
        
        # Get session context from previous turns for disambiguation
        session_context = {}
        try:
            session_context = chat_store.get_recent_session_context(req.user_id)
        except Exception:
            session_context = {}

        # --- ALWAYS DO BOTH: Direct canonical lookup AND broad retrieval ---
        # Step 2a: Direct canonical lookup
        canonical_memory = None
        if resolve_direct_memory:
            try:
                t_phase = time.perf_counter()
                canonical_memory = resolve_direct_memory(req.user_id, req.message, session_context=session_context)
                timing["direct_lookup_ms"] = (time.perf_counter() - t_phase) * 1000
            except Exception:
                canonical_memory = None

        # If ambiguous direct memory, ask for clarification immediately
        if canonical_memory and canonical_memory.get("memory_id") == "AMBIGUOUS_DIRECT_MEMORY":
            reply = canonical_memory.get("summary", "I found more than one matching memory. Can you clarify?")
            memory_was_used = False
            selected_memory = None
            judge_result = None
            retrieved_memories = []
            timing["llm_ms"] = 0.0

            # Persist clarification turn
            t_phase = time.perf_counter()
            chat_store.append_message(req.user_id, "user", req.message)
            chat_store.append_message(req.user_id, "assistant", reply)
            timing["persist_ms"] = (time.perf_counter() - t_phase) * 1000

            t_end = time.perf_counter()
            backend_ms = (t_end - t_start) * 1000

            response = {
                "reply": reply,
                "backend_ms": round(backend_ms, 2),
                "memory_enabled": memory_enabled and _memory_system_available,
                "memory_used": False,
                "detected_emotion": detected_emotion.get("primary"),
                "detected_intent": detected_emotion.get("intent"),
                "needs_lookup": needs_lookup,
                "llm": get_active_llm_info(),
                "timing_breakdown_ms": {k: round(v, 2) for k, v in timing.items()},
                "response_mode": "clarify_ambiguous_memory",
                "detail_level": "exact_value",
            }
            return response

        # Step 2b: ALWAYS do broad retrieval (dense + sparse + metadata)
        # Build emotion-aware query
        if build_emotion_aware_query:
            try:
                t_phase = time.perf_counter()
                retrieval_query = build_emotion_aware_query(req.message, detected_emotion)
                timing["query_build_ms"] = (time.perf_counter() - t_phase) * 1000
            except Exception:
                retrieval_query = req.message

        # Normalize query variants for better matching
        # e.g., "2am" → "2 am" so it matches stored text "2 AM"
        normalized_query = retrieval_query
        for variant, canonical in [
            ("2am", "2 am"), ("2AM", "2 AM"), ("2Am", "2 am"),
            ("3am", "3 am"), ("3AM", "3 AM"),
            ("10am", "10 am"), ("10AM", "10 AM"),
            ("11am", "11 am"), ("11AM", "11 AM"),
            ("12am", "12 am"), ("12AM", "12 AM"),
            ("1pm", "1 pm"), ("1PM", "1 PM"),
            ("2pm", "2 pm"), ("2PM", "2 PM"),
        ]:
            normalized_query = normalized_query.replace(variant, canonical)

        # Hybrid retrieve
        retrieved_memories = []
        if hybrid_retrieve_memory_candidates:
            try:
                t_phase = time.perf_counter()
                retrieved_memories = hybrid_retrieve_memory_candidates(
                    user_id=req.user_id,
                    query=normalized_query,
                    detected_emotion=detected_emotion,
                    topic_hints=topic_hints or {},
                    top_k_dense=12,
                    top_k_sparse=12,
                    final_k=15,
                    direct_question=is_direct_question,
                )
                timing["memory_retrieval_ms"] = (time.perf_counter() - t_phase) * 1000
            except Exception:
                # Fallback to pure dense
                if retrieve_memories:
                    try:
                        retrieved_memories = retrieve_memories(
                            user_id=req.user_id,
                            query=retrieval_query,
                            top_k=12,
                            direct_question=is_direct_question,
                        )
                    except Exception:
                        retrieved_memories = []
        elif retrieve_memories:
            try:
                retrieved_memories = retrieve_memories(
                    user_id=req.user_id,
                    query=retrieval_query,
                    top_k=12,
                    direct_question=is_direct_question,
                )
            except Exception:
                retrieved_memories = []

        # Step 2c: MERGE canonical memory into broad retrieval candidates
        # This ensures the judge sees ALL relevant memories, not just broad ones
        if canonical_memory and canonical_memory.get("memory_id") != "AMBIGUOUS_DIRECT_MEMORY":
            seen_ids = {m.get("memory_id") for m in retrieved_memories}
            if canonical_memory.get("memory_id") not in seen_ids:
                # Mark it as a direct lookup result so judge can prefer it for exact questions
                canonical_memory["reason_selected"] = "Direct memory lookup (canonical exact match)"
                canonical_memory["final_score"] = max(canonical_memory.get("final_score", 0.0), 0.95)
                canonical_memory["semantic_similarity"] = max(canonical_memory.get("semantic_similarity", 0.0), 0.95)
                # Insert at beginning so judge sees it first
                retrieved_memories.insert(0, canonical_memory)

        # Step 2d: Also augment with additional canonical candidates
        if get_canonical_candidates:
            try:
                canonical_candidates = get_canonical_candidates(req.user_id, req.message, top_k=3, session_context=session_context)
                seen_ids = {m.get("memory_id") for m in retrieved_memories}
                for mem in canonical_candidates:
                    mid = mem.get("memory_id")
                    if mid and mid not in seen_ids:
                        mem_copy = dict(mem)
                        mem_copy["reason_selected"] = "Canonical candidate augmentation"
                        mem_copy["final_score"] = max(mem_copy.get("final_score", 0.0), 0.85)
                        mem_copy["semantic_similarity"] = max(mem_copy.get("semantic_similarity", 0.0), 0.85)
                        retrieved_memories.append(mem_copy)
                        seen_ids.add(mid)
            except Exception:
                pass

        # NOTE: Removed aggressive candidate filtering for follow-up questions.
        # The active memory is shown in the prompt (Section B), letting the LLM/Judge
        # decide whether to continue or switch topics naturally.
        # Filtering to only recent sessions prevented topic switching.

        # Step 3: LLM Judge with cache + confidence gate
        judge_result = None
        selected_memory = None
        judge_confidence = 0.0
        memory_was_used = False

        if judge_memory_relevance and retrieved_memories:
            # Check cache first
            candidate_ids = [m.get("memory_id", "") for m in retrieved_memories[:8]]
            cached = None
            if get_cached_judge_result:
                try:
                    cached = get_cached_judge_result(req.message, candidate_ids)
                except Exception:
                    cached = None

            if cached:
                judge_result = cached
            else:
                try:
                    t_phase = time.perf_counter()
                    # Pass conversation context so judge understands follow-up references like "that"
                    # But include explicit instruction to consider topic switches
                    judge_context = dict(session_context) if session_context else {}
                    judge_context["_instruction"] = (
                        "The user may be asking a follow-up about the most recent topic, "
                        "OR they may have switched to a different topic. "
                        "Evaluate BOTH possibilities. If the query contains keywords that clearly "
                        "match a different session (e.g., '2am' when previous topic was bedtime), "
                        "prefer the matching session even if it's not the most recent."
                    )
                    judge_result = judge_memory_relevance(
                        user_message=req.message,
                        detected_emotion=detected_emotion,
                        topic_hints=topic_hints or {},
                        candidate_memories=retrieved_memories,
                        policy_config=load_response_policy() if load_response_policy else {},
                        max_candidates=8,
                        conversation_context=judge_context,
                    )
                    timing["memory_selection_ms"] = (time.perf_counter() - t_phase) * 1000

                    # Save to cache
                    if save_cached_judge_result and judge_result:
                        try:
                            save_cached_judge_result(req.message, candidate_ids, judge_result)
                        except Exception:
                            pass
                except Exception:
                    judge_result = None

            # Confidence gate: only use memory if confidence >= 0.65
            # EXCEPTION: For follow-up questions with recent session context,
            # if there's a plausible match from the recent session, still include it
            # but with lower detail level. This lets the assistant say "I remember..."
            # instead of "I don't have a clear record."
            if judge_result:
                judge_confidence = judge_result.get("confidence", 0.0)
                judge_approved = judge_result.get("use_memory") and judge_confidence >= 0.65
                
                if judge_approved:
                    selected_ids = judge_result.get("selected_memory_ids", [])
                    for mem in retrieved_memories:
                        if mem.get("memory_id") in selected_ids:
                            selected_memory = mem
                            break
                    if not selected_memory and selected_ids:
                        selected_memory = {
                            "memory_id": selected_ids[0],
                            "summary": judge_result.get("answer_basis", ""),
                            "semantic_similarity": 1.0,
                            "final_score": 1.0,
                        }
                    memory_was_used = bool(selected_memory)
                else:
                    # Judge rejected — let LLM decide from all candidates in the prompt
                    # Do NOT force a fallback memory, as the LLM sees all candidates in Section C
                    selected_memory = None
                    memory_was_used = False
                
                # Store session context for follow-up disambiguation
                if selected_memory:
                    try:
                        session_id = selected_memory.get("session_id")
                        if not session_id:
                            mid = selected_memory.get("memory_id", "")
                            parts = mid.split("_")
                            if len(parts) >= 2 and parts[0] == "mem":
                                session_id = f"{parts[1]}_{parts[2]}" if len(parts) > 2 else parts[1]
                        theme = selected_memory.get("theme")
                        chat_store.set_session_context(
                            req.user_id, 
                            session_id=session_id, 
                            theme=theme, 
                            memory_id=selected_memory.get("memory_id")
                        )
                    except Exception:
                        pass

        # Step 4: Apply response policy
        if decide_response_policy:
            try:
                t_phase = time.perf_counter()
                policy_config = load_response_policy() if load_response_policy else {}
                policy_decision = decide_response_policy(
                    current_message=req.message,
                    detected_emotion=detected_emotion,
                    retrieved_memories=retrieved_memories,
                    policy_config=policy_config,
                )
                timing["policy_ms"] = (time.perf_counter() - t_phase) * 1000
            except Exception:
                policy_decision = None

        # Override policy when judge approved a memory with high confidence
        if policy_decision and selected_memory and judge_result and judge_result.get("use_memory"):
            policy_decision["mention_memory"] = True
            intent = detected_emotion.get("intent", "general_chat") if detected_emotion else "general_chat"
            if intent == "specific_episode_recall":
                policy_decision["allowed_memory_detail_level"] = "summary_level"
                policy_decision["response_mode"] = "gentle_follow_up"
            elif intent == "direct_memory_question":
                policy_decision["allowed_memory_detail_level"] = "exact_value"
                policy_decision["response_mode"] = "soft_optional_reference"
            elif intent == "emotional_disclosure":
                policy_decision["allowed_memory_detail_level"] = "topic_only"
                policy_decision["response_mode"] = "validate_then_gentle_optional_reference"
            memory_was_used = True
        elif policy_decision and selected_memory:
            memory_was_used = policy_decision.get("mention_memory", False)

    # Step 5: Build turn-local messages (anti-dilution)
    # Memory context is injected close to the current user message, not buried in early system prompt
    t_phase = time.perf_counter()

    # Determine approved memories list (0 or 1 item for now)
    approved_memories = []
    if memory_was_used and selected_memory:
        approved_memories = [selected_memory]

    # Get recent chat history (rolling window)
    recent_history = []
    try:
        full_history = chat_store.get_user_history(req.user_id)
        # Limit to last N messages (configurable via env, default 6)
        max_history = int(os.environ.get("MAX_LLM_HISTORY_MESSAGES", "6"))
        recent_history = full_history[-max_history:] if full_history else []
    except Exception:
        recent_history = []

    # Build turn-local message list
    try:
        messages = prompts.build_turn_local_messages(
            base_system_prompt=prompts.MENTRA_BASE_SYSTEM_PROMPT,
            recent_history=recent_history,
            current_user_message=req.message,
            detected_emotion=detected_emotion,
            query_understanding=query_understanding if 'query_understanding' in locals() else {},
            relevance_judge_result=judge_result,
            approved_memories=approved_memories,
            policy_decision=policy_decision,
            max_history_messages=int(os.environ.get("MAX_LLM_HISTORY_MESSAGES", "6")),
            all_retrieved_memories=retrieved_memories if 'retrieved_memories' in locals() else [],
            active_memory=active_memory,
        )
    except Exception:
        # Fallback to old-style single system prompt if turn-local builder fails
        messages = [{"role": "system", "content": prompts.MENTRA_BASE_SYSTEM_PROMPT}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": req.message})

    timing["prompt_build_ms"] = (time.perf_counter() - t_phase) * 1000

    t_phase = time.perf_counter()
    raw_reply = llm_client.chat(messages)
    timing["llm_ms"] = (time.perf_counter() - t_phase) * 1000

    # Parse memory tracking JSON from LLM response
    llm_selected_memory = None
    reply = raw_reply
    try:
        import re
        # Look for JSON block in the response
        json_match = re.search(r'\{[^}]*"memory_id"[^}]*\}', raw_reply)
        if json_match:
            json_str = json_match.group(0)
            tracking = json.loads(json_str)
            memory_id = tracking.get("memory_id")
            if memory_id:
                # Find the memory in retrieved_memories
                for mem in retrieved_memories:
                    if mem.get("memory_id") == memory_id:
                        llm_selected_memory = mem
                        break
            # Strip JSON from user-facing reply
            reply = raw_reply.replace(json_str, "").strip()
            # Clean up any leftover markers
            reply = re.sub(r'```json\s*', '', reply)
            reply = re.sub(r'```\s*', '', reply).strip()
    except Exception:
        reply = raw_reply

    # Persist
    t_phase = time.perf_counter()
    chat_store.append_message(req.user_id, "user", req.message)
    chat_store.append_message(req.user_id, "assistant", reply)
    timing["persist_ms"] = (time.perf_counter() - t_phase) * 1000

    # Save active memory for conversation continuity
    # Use the memory the LLM explicitly selected via JSON, or fallback to judge selection
    try:
        memory_to_save = llm_selected_memory or selected_memory
        if not memory_to_save and retrieved_memories:
            # Fallback: save top-scoring retrieved memory
            memory_to_save = max(retrieved_memories, key=lambda m: m.get("final_score", 0))
        
        if memory_to_save:
            chat_store.set_active_memory(
                req.user_id,
                memory_to_save.get("memory_id", ""),
                memory_to_save
            )
    except Exception:
        pass

    # DEBUG: Save prompt log for this turn
    try:
        import json as _json
        os.makedirs("outputs/prompt_logs", exist_ok=True)
        prompt_log = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "user_message": req.message,
            "detected_emotion": detected_emotion,
            "needs_lookup": needs_lookup,
            "memory_was_used": memory_was_used,
            "judge_result": judge_result if 'judge_result' in locals() else None,
            "approved_memories": [m.get("memory_id") for m in approved_memories] if 'approved_memories' in locals() else [],
            "messages": [
                {
                    "role": m["role"],
                    "content": m["content"][:2000] if len(m["content"]) > 2000 else m["content"],
                }
                for m in messages
            ],
        }
        safe_msg = "".join(c if c.isalnum() else "_" for c in req.message[:30])
        log_path = f"outputs/prompt_logs/{safe_msg}_{int(time.time())}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            _json.dump(prompt_log, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    t_end = time.perf_counter()
    backend_ms = (t_end - t_start) * 1000

    response = {
        "reply": reply,
        "backend_ms": round(backend_ms, 2),
        "memory_enabled": memory_enabled and _memory_system_available,
        "memory_used": memory_was_used,
        "detected_emotion": detected_emotion.get("primary"),
        "detected_intent": detected_emotion.get("intent"),
        "needs_lookup": needs_lookup,
        "llm": get_active_llm_info(),
        "timing_breakdown_ms": {k: round(v, 2) for k, v in timing.items()},
    }

    if policy_decision:
        response["response_mode"] = policy_decision.get("response_mode")
        response["mention_memory"] = policy_decision.get("mention_memory")
        response["ask_direct_question"] = policy_decision.get("ask_direct_question")
        response["selected_topic"] = policy_decision.get("selected_topic")
        response["detail_level"] = policy_decision.get("allowed_memory_detail_level")

    return response


@app.get("/new-session/{user_id}")
def new_session(user_id: str, memory: bool = False):
    """
    Start a new session and return an opening message.
    
    Clears the user's chat history and generates a memory-aware opener
    if memory mode is enabled and the memory system is available.
    
    Args:
        user_id: Unique user identifier.
        memory: Whether to enable memory-aware session openers.
    
    Returns:
        JSON with opening_message and memory_enabled flag.
    """
    chat_store.set_user_memory_setting(user_id, memory)
    chat_store.clear_user_history(user_id)

    if memory and _memory_system_available and generate_opener:
        opening_message = generate_opener(user_id)
    else:
        opening_message = "Hi, I'm glad you're here. What would you like to talk about today?"

    chat_store.append_message(user_id, "assistant", opening_message)

    return {
        "opening_message": opening_message,
        "memory_enabled": memory and _memory_system_available,
        "llm": get_active_llm_info(),
    }


@app.get("/history/{user_id}")
def get_history(user_id: str):
    """
    Return current local chat history for the user.
    
    Args:
        user_id: Unique user identifier.
    
    Returns:
        JSON with user_id and messages list.
    """
    return {
        "user_id": user_id,
        "messages": chat_store.get_user_history(user_id)
    }


@app.post("/reset/{user_id}")
def reset_history(user_id: str):
    """
    Clear current local chat history for the user.
    
    Args:
        user_id: Unique user identifier.
    
    Returns:
        JSON with status and user_id.
    """
    chat_store.clear_user_history(user_id)
    return {"status": "cleared", "user_id": user_id}


@app.get("/debug/previous-sessions/{user_id}")
def debug_previous_sessions(user_id: str, full: bool = False):
    """
    Debug endpoint showing that previous session data exists locally.
    
    Args:
        user_id: Unique user identifier.
        full: If True, include full session data in the response.
    
    Returns:
        JSON with session count, note about baseline behavior, and optional full data.
    """
    sessions_path = PROJECT_RECALL_SESSIONS_PATH

    sessions = []
    if os.path.exists(sessions_path):
        with open(sessions_path, "r", encoding="utf-8") as f:
            sessions = json.load(f)

    user_sessions = [s for s in sessions if s.get("user_id") == user_id]

    response = {
        "user_id": user_id,
        "previous_sessions_found": len(user_sessions),
        "baseline_uses_this_data": False,
        "note": "Previous sessions exist locally, but baseline chat intentionally does not use them yet.",
        "first_session_id": user_sessions[0]["session_id"] if user_sessions else None,
        "needle_session_id": "session_003",
    }

    if full and user_sessions:
        response["sessions"] = user_sessions

    return response


@app.get("/debug/memories/{user_id}")
def debug_memories(user_id: str):
    """
    Return extracted memories for a user (for inspection).
    
    Args:
        user_id: Unique user identifier.
    
    Returns:
        JSON with memory count, types, and up to 20 memory objects.
    """
    memories_path = PROJECT_RECALL_MEMORIES_PATH

    memories = []
    if os.path.exists(memories_path):
        with open(memories_path, "r", encoding="utf-8") as f:
            all_memories = json.load(f)
            memories = [m for m in all_memories if m.get("user_id") == user_id]

    return {
        "user_id": user_id,
        "total_memories": len(memories),
        "memory_types": list(set(m.get("memory_type", "unknown") for m in memories)),
        "memories": memories[:20],
    }


@app.get("/debug/retrieve-memory/{user_id}")
def debug_retrieve_memory(user_id: str, q: str = ""):
    """
    Test memory retrieval for a query.
    
    Args:
        user_id: Unique user identifier.
        q: Query string for memory retrieval.
    
    Returns:
        JSON with retrieved memories, emotional plan, and error info if any.
    """
    if not _memory_system_available or not retrieve_memories:
        return {
            "error": "Memory system not available. Run: python app/build_memory_index.py",
            "user_id": user_id,
            "query": q,
        }

    try:
        memories = retrieve_memories(user_id=user_id, query=q, top_k=5)

        plan = None
        if plan_memory_response and memories:
            try:
                plan = plan_memory_response(memories, current_user_message=q)
            except Exception as e:
                plan = {"error": str(e)}

        return {
            "user_id": user_id,
            "query": q,
            "results_found": len(memories),
            "memories": memories,
            "emotional_plan": plan,
        }
    except Exception as e:
        return {
            "error": str(e),
            "user_id": user_id,
            "query": q,
        }


@app.get("/memory-setting/{user_id}")
def get_memory_setting(user_id: str):
    """
    Get the user's current memory mode setting.
    
    Args:
        user_id: Unique user identifier.
    
    Returns:
        JSON with user_id and memory_enabled flag.
    """
    enabled = chat_store.get_user_memory_setting(user_id)
    return {"user_id": user_id, "memory_enabled": enabled}


@app.post("/memory-setting/{user_id}")
def set_memory_setting(user_id: str, enabled: bool = True):
    """
    Set the user's memory mode.
    
    Args:
        user_id: Unique user identifier.
        enabled: True to enable memory, False to disable.
    
    Returns:
        JSON with user_id and memory_enabled flag.
    """
    chat_store.set_user_memory_setting(user_id, enabled)
    return {"user_id": user_id, "memory_enabled": enabled}


@app.get("/debug/reengagement/{user_id}")
def debug_reengagement(
    user_id: str,
    days_since_last_session: int = 3,
    notifications_sent_last_7_days: int = 0,
    personalized_notifications_enabled: bool = True,
    quiet_hours_active: bool = False,
    last_session_close_emotion: str = "neutral",
    use_llm: bool = False,
):
    """
    Debug/demo endpoint for the re-engagement decision system.
    Returns the notification decision object without sending real notifications.
    """
    if not _memory_system_available or not decide_reengagement or not make_user_state:
        return {
            "error": "Re-engagement system not available",
            "user_id": user_id,
        }

    user_state = make_user_state(
        user_id=user_id,
        days_since_last_session=days_since_last_session,
        notifications_sent_last_7_days=notifications_sent_last_7_days,
        personalized_notifications_enabled=personalized_notifications_enabled,
        quiet_hours_active=quiet_hours_active,
        last_session_close_emotion=last_session_close_emotion,
    )

    try:
        decision = decide_reengagement(user_state)
        if use_llm and decision.get("should_send") and decision.get("copy"):
            try:
                from app.llm_client import chat as llm_chat
                from app.prompts import NOTIFICATION_LLM_REWRITE_PROMPT_TEMPLATE
                prompt = NOTIFICATION_LLM_REWRITE_PROMPT_TEMPLATE.format(
                    emotion=last_session_close_emotion,
                    copy=decision["copy"],
                )
                personalized = llm_chat([
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Rewrite the notification copy."}
                ])
                decision["copy"] = personalized.strip().strip('"').strip("'")
                decision["copy_source"] = "llm"
            except Exception:
                decision["copy_source"] = "template"
        else:
            decision["copy_source"] = "template"
        decision["llm"] = get_active_llm_info()
        return decision
    except Exception as e:
        return {
            "error": str(e),
            "user_id": user_id,
        }
