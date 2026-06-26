// app.js - talks to /api/chat and paints the chat + trace as events stream in.

const messagesEl = document.getElementById("messages");
const traceEl = document.getElementById("trace");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const modeEl = document.getElementById("mode");
const statusEl = document.getElementById("status");

// Friendly labels for the trace cards.
const ROLE_LABELS = {
  supervisor: "Supervisor",
  coder_fast: "Fast Coder",
  coder_strong: "Strong Coder",
  reasoning_critic: "Reasoning Critic",
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
      body: JSON.stringify({ message, mode: modeEl.value }),
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
