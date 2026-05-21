/**
 * Project Recall - Chat Frontend
 *
 * Simple vanilla JS chat UI that communicates with the FastAPI backend.
 * Features:
 *   - Chat messaging with user/assistant bubbles
 *   - Round-trip timing debug panel
 *   - Memory mode toggle (baseline vs memory-aware)
 *   - Notification Simulator (re-engagement decision demo)
 */
const API_BASE = ""; // Same origin
const USER_ID = "demo_user";

const chatWindow = document.getElementById("chat-window");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const newSessionBtn = document.getElementById("new-session-btn");
const newSessionMemoryBtn = document.getElementById("new-session-memory-btn");
const resetBtn = document.getElementById("reset-btn");
const memoryToggle = document.getElementById("memory-toggle");
const subtitle = document.getElementById("subtitle");

// Timing state
let timingState = {};
let memoryEnabled = false;

// --- UI Helpers ---

function appendMessage(role, content) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.textContent = content;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendTimingInfo(html) {
    const div = document.createElement("div");
    div.classList.add("message", "system");
    div.innerHTML = html;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setLoading(isLoading) {
    sendBtn.disabled = isLoading;
    messageInput.disabled = isLoading;
    if (isLoading) {
        sendBtn.textContent = "…";
    } else {
        sendBtn.textContent = "Send";
        messageInput.focus();
    }
}

function showSystemMessage(text) {
    appendMessage("system", text);
}

function formatMs(ms) {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

function updateSubtitle() {
    const currentLlm = timingState.llm
        ? `${timingState.llm.provider}:${timingState.llm.model}`
        : null;

    if (memoryEnabled) {
        subtitle.textContent = currentLlm
            ? `Memory mode ON — retrieving past sessions — ${currentLlm}`
            : "Memory mode ON — retrieving past sessions";
        subtitle.style.color = "#4fd1c5";
    } else {
        subtitle.textContent = currentLlm
            ? `Memory mode OFF — baseline forgetting behavior — ${currentLlm}`
            : "Memory mode OFF — baseline forgetting behavior";
        subtitle.style.color = "#a0a0c0";
    }
}

// --- API Calls ---

async function startNewSession(useMemory = false) {
    const t0 = performance.now();
    setLoading(true);
    try {
        chatWindow.innerHTML = "";
        const r = await fetch(`${API_BASE}/new-session/${USER_ID}?memory=${useMemory}`);
        const data = await r.json();
        const t1 = performance.now();

        memoryEnabled = data.memory_enabled;
        timingState.llm = data.llm || null;
        updateSubtitle();
        memoryToggle.checked = memoryEnabled;

        appendMessage("assistant", data.opening_message);

        let timingHtml = `⏱ New session ready in <b>${formatMs(t1 - t0)}</b>`;
        if (memoryEnabled) {
            timingHtml += ` &nbsp;|&nbsp; 🧠 <b>Memory enabled</b>`;
        } else {
            timingHtml += ` &nbsp;|&nbsp; 🧠 <b>Memory disabled</b>`;
        }
        if (data.llm) {
            timingHtml += ` &nbsp;|&nbsp; 🤖 <b>${data.llm.provider}:${data.llm.model}</b>`;
        }
        appendTimingInfo(timingHtml);

    } catch (err) {
        showSystemMessage("Failed to start a new session.");
        console.error(err);
    } finally {
        setLoading(false);
    }
}

async function sendMessage(text) {
    if (!text.trim()) return;

    const t0 = performance.now();
    timingState = { t0 };

    appendMessage("user", text);
    messageInput.value = "";
    setLoading(true);

    // Show a pending indicator
    const pendingId = setInterval(() => {
        const elapsed = performance.now() - t0;
        sendBtn.textContent = `…${formatMs(elapsed)}`;
    }, 250);

    try {
        const backendStart = performance.now();
        const r = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: USER_ID, message: text }),
        });
        const backendEnd = performance.now();
        timingState.networkMs = backendEnd - backendStart;

        const data = await r.json();
        const t1 = performance.now();
        timingState.totalMs = t1 - t0;
        timingState.llm = data.llm || timingState.llm || null;

        updateSubtitle();

        appendMessage("assistant", data.reply);

        // Show timing breakdown
        let timingHtml = `
            ⏱ <b>Total:</b> ${formatMs(timingState.totalMs)}
            &nbsp;|&nbsp; <b>Frontend render:</b> ${formatMs(timingState.totalMs - timingState.networkMs)}
            &nbsp;|&nbsp; <b>Backend request:</b> ${formatMs(timingState.networkMs)}
        `;
        appendTimingInfo(timingHtml);

        // If backend sent timing data, show breakdown
        if (data.backend_ms) {
            const networkOverhead = timingState.networkMs - data.backend_ms;
            let detailHtml = `
                🖥 <b>Backend logic:</b> ${formatMs(data.backend_ms)}
                &nbsp;|&nbsp; <b>Network overhead:</b> ${formatMs(Math.max(0, networkOverhead))}
            `;
            if (data.memory_used) {
                detailHtml += ` &nbsp;|&nbsp; 🧠 <b>Memory injected</b>`;
            }
            if (data.llm) {
                detailHtml += ` &nbsp;|&nbsp; 🤖 <b>${data.llm.provider}:${data.llm.model}</b>`;
            }
            appendTimingInfo(detailHtml);

            if (data.timing_breakdown_ms) {
                const tb = data.timing_breakdown_ms;
                let breakdownHtml = `
                    🧩 <b>Emotion:</b> ${formatMs(tb.emotion_detection_ms || 0)}
                    &nbsp;|&nbsp; <b>Direct lookup:</b> ${formatMs(tb.direct_lookup_ms || 0)}
                    &nbsp;|&nbsp; <b>Query build:</b> ${formatMs(tb.query_build_ms || 0)}
                    &nbsp;|&nbsp; <b>Retrieval:</b> ${formatMs(tb.memory_retrieval_ms || 0)}
                `;
                appendTimingInfo(breakdownHtml);

                breakdownHtml = `
                    🧠 <b>Selection:</b> ${formatMs(tb.memory_selection_ms || 0)}
                    &nbsp;|&nbsp; <b>Policy:</b> ${formatMs(tb.policy_ms || 0)}
                    &nbsp;|&nbsp; <b>Prompt:</b> ${formatMs(tb.prompt_build_ms || 0)}
                    &nbsp;|&nbsp; <b>LLM:</b> ${formatMs(tb.llm_ms || 0)}
                    &nbsp;|&nbsp; <b>Persist:</b> ${formatMs(tb.persist_ms || 0)}
                `;
                appendTimingInfo(breakdownHtml);
            }
        }

    } catch (err) {
        showSystemMessage("Failed to get a reply. Is the backend running?");
        console.error(err);
    } finally {
        clearInterval(pendingId);
        setLoading(false);
    }
}

async function resetHistory() {
    const t0 = performance.now();
    setLoading(true);
    try {
        await fetch(`${API_BASE}/reset/${USER_ID}`, { method: "POST" });
        chatWindow.innerHTML = "";
        const t1 = performance.now();
        showSystemMessage("Chat history has been cleared.");
        appendTimingInfo(`⏱ Reset done in <b>${formatMs(t1 - t0)}</b>`);
    } catch (err) {
        showSystemMessage("Failed to reset history.");
        console.error(err);
    } finally {
        setLoading(false);
    }
}

async function toggleMemoryMode() {
    memoryEnabled = memoryToggle.checked;
    try {
        await fetch(`${API_BASE}/memory-setting/${USER_ID}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: memoryEnabled }),
        });
        updateSubtitle();
    } catch (err) {
        console.error("Failed to toggle memory mode:", err);
    }
}

// --- Event Listeners ---

sendBtn.addEventListener("click", () => {
    sendMessage(messageInput.value);
});

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendMessage(messageInput.value);
    }
});

newSessionBtn.addEventListener("click", () => {
    startNewSession(false);
});

newSessionMemoryBtn.addEventListener("click", () => {
    startNewSession(true);
});

resetBtn.addEventListener("click", () => {
    resetHistory();
});

memoryToggle.addEventListener("change", () => {
    toggleMemoryMode();
});

// -----------------------------------------------------------------------------
// Notification Simulator
// -----------------------------------------------------------------------------
// This section implements the re-engagement decision demo in the UI.
// It reads user-controlled inputs (days, emotion, fatigue, consent, LLM toggle),
// calls the backend /debug/reengagement endpoint, and renders:
//   - A status banner (green for "would send", red for "blocked")
//   - A fake phone notification card showing the copy
//   - A JSON dump of the full decision object for inspection
// -----------------------------------------------------------------------------

// DOM references for the simulator section
const simRunBtn = document.getElementById("sim-run-btn");      // Simulate button
const simResult = document.getElementById("sim-result");      // Result container
const simStatus = document.getElementById("sim-status");      // Status text banner
const simCard = document.getElementById("sim-card");          // Phone notification card
const simBody = document.getElementById("sim-body");          // Notification body text
const simJson = document.getElementById("sim-json");          // Raw JSON dump area

/**
 * Run the notification simulator.
 *
 * Reads form values from the simulator section, calls the backend
 * /debug/reengagement endpoint, and updates the UI with:
 *   - Status (send / blocked)
 *   - Notification card (if send)
 *   - Full decision JSON
 */
async function runNotificationSimulator() {
    // -------------------------------------------------------------------------
    // 1. Read input values from the simulator form
    // -------------------------------------------------------------------------
    const days = document.getElementById("sim-days").value;
    const emotion = document.getElementById("sim-emotion").value;
    const fatigue = document.getElementById("sim-fatigue").value;
    const consent = document.getElementById("sim-consent").checked;
    const useLlm = document.getElementById("sim-llm").checked;

    // -------------------------------------------------------------------------
    // 2. Reset the result area and show "Simulating..."
    // -------------------------------------------------------------------------
    simResult.classList.remove("hidden");
    simStatus.textContent = "Simulating...";
    simBody.textContent = "";
    simJson.textContent = "";

    // -------------------------------------------------------------------------
    // 3. Call the backend debug endpoint
    // -------------------------------------------------------------------------
    try {
        // Build the query string with all simulator parameters
        const url = (
            `${API_BASE}/debug/reengagement/${USER_ID}` +
            `?days_since_last_session=${days}` +
            `&notifications_sent_last_7_days=${fatigue}` +
            `&personalized_notifications_enabled=${consent}` +
            `&quiet_hours_active=false` +
            `&last_session_close_emotion=${emotion}` +
            `&use_llm=${useLlm}`
        );

        const res = await fetch(url);
        const data = await res.json();

        // ---------------------------------------------------------------------
        // 4. Handle backend errors
        // ---------------------------------------------------------------------
        if (data.error) {
            simStatus.textContent = "Error: " + data.error;
            simCard.classList.add("hidden");  // Hide the notification card
            return;
        }

        // ---------------------------------------------------------------------
        // 5. Render the result
        // ---------------------------------------------------------------------
        if (data.should_send) {
            // Green status: notification WOULD be sent
            const llmLabel = data.llm ? ` via ${data.llm.provider}:${data.llm.model}` : "";
            simStatus.textContent = `Would send: ${data.notification_type} (priority: ${data.priority})${llmLabel}`;
            simStatus.className = "sim-status send";
            simBody.textContent = data.copy;
            simCard.classList.remove("hidden");  // Show the phone card
        } else {
            // Red status: notification BLOCKED (fatigue, consent, etc.)
            const llmLabel = data.llm ? ` via ${data.llm.provider}:${data.llm.model}` : "";
            simStatus.textContent = `Blocked: ${data.blocked_by}${llmLabel}`;
            simStatus.className = "sim-status blocked";
            simCard.classList.add("hidden");  // Hide the phone card
        }

        // Always show the raw JSON decision object for debugging
        simJson.textContent = JSON.stringify(data, null, 2);

    } catch (err) {
        // Network or fetch error
        simStatus.textContent = "Error: " + err.message;
        simCard.classList.add("hidden");
    }
}

// Wire the Simulate button
if (simRunBtn) {
    simRunBtn.addEventListener("click", runNotificationSimulator);
}

// --- Initialization ---

document.addEventListener("DOMContentLoaded", () => {
    // Start with a baseline session (no memory)
    startNewSession(false);
});
