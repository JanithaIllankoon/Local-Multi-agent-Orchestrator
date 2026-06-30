// app.js - talks to /api/chat and paints the chat + trace as events stream in.

const messagesEl = document.getElementById("messages");
const traceEl = document.getElementById("trace");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const modeEl = document.getElementById("mode");
const statusEl = document.getElementById("status");
const sessionsEl = document.getElementById("sessions");
const newChatBtn = document.getElementById("new-chat");

// Which session the current chat belongs to. null = a fresh, unsaved chat;
// the backend assigns an id on the first turn and sends it back as a meta event.
let currentSessionId = null;

// Friendly labels for the trace cards.
const ROLE_LABELS = {
  supervisor: "Supervisor",
  coder_fast: "Fast Coder",
  coder_strong: "Strong Coder",
  reasoning_critic: "Reasoning Critic",
  contrarian_critic: "Contrarian Critic",
  system: "System",
};

function addBubble(who, text, cls) {
  const div = document.createElement("div");
  div.className = `bubble ${cls}`;
  div.innerHTML = `<div class="who"></div><div class="body"></div>`;
  div.querySelector(".who").textContent = who;
  div.querySelector(".body").textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function addTraceCard(event) {
  const card = document.createElement("div");
  // Final answers stay open; intermediate steps start collapsed to reduce noise.
  card.className = "trace-card" + (event.is_final ? "" : " collapsed");
  if (event.event_type === "error") card.classList.add("error");

  const label = ROLE_LABELS[event.agent_role] || event.agent_role;
  const ms = event.latency_ms ? `${(event.latency_ms / 1000).toFixed(1)}s` : "";

  card.innerHTML = `
    <div class="head">
      <span class="role"></span>
      <span class="meta"></span>
    </div>
    <div class="content"></div>`;
  card.querySelector(".role").textContent = `${label} · ${event.event_type}`;
  card.querySelector(".meta").textContent = ms;
  card.querySelector(".content").textContent = event.content;

  // Show the model's hidden reasoning underneath, if it sent any.
  if (event.reasoning) {
    const r = document.createElement("div");
    r.className = "reasoning";
    r.textContent = "thinking: " + event.reasoning;
    card.appendChild(r);
  }

  // Click the header to expand/collapse the card.
  card.querySelector(".head").onclick = () => card.classList.toggle("collapsed");

  traceEl.appendChild(card);
  traceEl.scrollTop = traceEl.scrollHeight;
}

async function run() {
  const message = inputEl.value.trim();
  if (!message) return;

  // Reset UI for a new run.
  sendBtn.disabled = true;
  inputEl.value = "";
  traceEl.innerHTML = "";
  addBubble("You", message, "user");
  statusEl.textContent = "Running...";

  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, mode: modeEl.value, session_id: currentSessionId }),
    });

    // Read the SSE stream line by line as the server sends each agent step.
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by a blank line.
      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep the last, possibly-incomplete chunk

      for (const part of parts) {
        const line = part.replace(/^data: /, "").trim();
        if (!line) continue;
        const event = JSON.parse(line);

        // The first line is a meta event telling us the session id (the backend
        // creates a session on the first turn). Track it and refresh the list.
        if (event.meta === "session") {
          const isNew = currentSessionId !== event.session_id;
          currentSessionId = event.session_id;
          if (isNew) loadSessions();
          continue;
        }

        addTraceCard(event);
        statusEl.textContent = `${ROLE_LABELS[event.agent_role] || event.agent_role}...`;
        if (event.is_final) addBubble("Orchestrator", event.content, "assistant");
      }
    }
    statusEl.textContent = "Done";
  } catch (e) {
    addBubble("Orchestrator", "Error: " + e.message, "assistant");
    statusEl.textContent = "Error";
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.onclick = run;
// Ctrl+Enter (or Cmd+Enter) sends, like most chat apps.
inputEl.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run();
});

// --- session sidebar -------------------------------------------------------

// Start a brand-new, unsaved chat: clear both panels and drop the session id.
function startNewChat() {
  currentSessionId = null;
  messagesEl.innerHTML = "";
  traceEl.innerHTML = "";
  statusEl.textContent = "Idle";
  highlightActive();
  inputEl.focus();
}

newChatBtn.onclick = startNewChat;

// Fetch the session list and paint the sidebar.
async function loadSessions() {
  try {
    const resp = await fetch("/api/sessions");
    const { sessions } = await resp.json();
    sessionsEl.innerHTML = "";
    for (const s of sessions) {
      const item = document.createElement("div");
      item.className = "session-item";
      item.dataset.id = s.id;
      item.innerHTML = `<span class="title"></span><button class="del" title="Delete">×</button>`;
      item.querySelector(".title").textContent = s.title;
      item.querySelector(".title").onclick = () => openSession(s.id);
      item.onclick = (e) => { if (!e.target.classList.contains("del")) openSession(s.id); };
      item.querySelector(".del").onclick = (e) => { e.stopPropagation(); deleteSession(s.id); };
      sessionsEl.appendChild(item);
    }
    highlightActive();
  } catch (e) {
    // Sidebar is non-critical; don't break the app if listing fails.
  }
}

function highlightActive() {
  for (const el of sessionsEl.querySelectorAll(".session-item")) {
    el.classList.toggle("active", Number(el.dataset.id) === currentSessionId);
  }
}

// Reopen a saved session: replay its messages and trace into the panels.
async function openSession(id) {
  const resp = await fetch(`/api/sessions/${id}`);
  if (!resp.ok) return;
  const data = await resp.json();

  currentSessionId = id;
  messagesEl.innerHTML = "";
  traceEl.innerHTML = "";

  for (const m of data.messages) {
    if (m.role === "user") addBubble("You", m.content, "user");
    else addBubble("Orchestrator", m.content, "assistant");
  }
  for (const t of data.traces) {
    // Stored traces use 0/1 for is_final; addTraceCard expects a boolean.
    addTraceCard({ ...t, is_final: !!t.is_final });
  }
  statusEl.textContent = "Loaded session";
  highlightActive();
}

async function deleteSession(id) {
  await fetch(`/api/sessions/${id}`, { method: "DELETE" });
  if (id === currentSessionId) startNewChat();
  loadSessions();
}

// Paint the sidebar on first load.
loadSessions();
