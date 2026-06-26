<div align="center">

# 🧠 Local Multi-Agent Orchestrator

**One chat box. A whole team of local AI models working behind it.**

Talk to a single interface. Under the hood, a supervisor coordinates specialist
models — coders, critics, and a vision agent — that plan, build, review, and
refine before you get one polished answer. Everything runs **100% locally** via
[llama.cpp](https://github.com/ggml-org/llama.cpp). No cloud. No API keys. Your
data never leaves your machine.

![status](https://img.shields.io/badge/status-early%20development-orange)
![runs](https://img.shields.io/badge/runs-100%25%20local-brightgreen)
![backend](https://img.shields.io/badge/backend-llama.cpp-blue)
![license](https://img.shields.io/badge/license-MIT-lightgrey)

</div>

---

## What is this?

Most local-LLM setups are a single model in a chat window. This project asks a
different question: **what if a small team of local models collaborated like a
real engineering team?**

You type one request. Internally:

- A **Supervisor** understands it, makes a plan, and delegates.
- A **Fast Coder** drafts an implementation quickly.
- A **Strong Coder** reviews and hardens it.
- A **Reasoning Critic** hunts for flaws and edge cases.
- A **Contrarian Critic** challenges the whole approach.
- A **Vision Observer** (later) can look at your screen.
- The Supervisor **synthesizes** everything into one clean reply.

You never talk to the specialists directly. You just get a better answer — and a
visible **trace** of how the team got there.

## Why it's different

| | |
|---|---|
| 🔒 **Fully local & private** | Runs on your own GPU via llama.cpp. Nothing is sent anywhere. |
| 🧩 **Multi-agent, not single-model** | Plan → draft → review → critique → synthesize, like a real team. |
| 🔭 **Glass-box, not black-box** | A trace panel shows every agent's step. Debuggable by design. |
| 🛡️ **Safety outside the models** | Models can only *suggest*. A separate gated Executor is the only thing that ever touches files, shell, or GUI. |
| ⚙️ **Swap models via config** | Upgrade any model by editing one YAML file — no code changes. |
| 💻 **Built for modest hardware** | Designed to run on a single 8–12GB GPU, sharing weights across roles. |

## Core principle

> Separate **thinking**, **suggesting**, and **acting**.

```
User talks to the Orchestrator.
The Orchestrator talks to the agents.
Agents suggest.
The Supervisor decides.
The Executor acts.
The UI shows the result — and the full trace.
```

No specialist model ever writes a file, runs a command, or clicks the screen on
its own. Only a deterministic, safety-gated Executor can — and only in later phases.

## How it works

```
            You
             │
        ┌────▼─────┐
        │  Web UI  │  chat + live agent trace
        └────┬─────┘
             │
      ┌──────▼───────┐
      │ Orchestrator │  the task controller
      └──────┬───────┘
             │
      ┌──────▼───────┐
      │  Supervisor  │  plans & delegates
      └──────┬───────┘
   ┌─────────┼──────────┬───────────┬────────────┐
   ▼         ▼          ▼           ▼            ▼
 Fast      Strong   Reasoning   Contrarian    Vision
 Coder     Coder     Critic       Critic     Observer
   └─────────┴──────────┴───────────┴────────────┘
             │
      ┌──────▼───────┐
      │  Supervisor  │  synthesizes the final answer
      └──────┬───────┘
             │
   ┌─────────▼──────────┐
   │ Safety-Gated       │  (later phases) files · shell · screen
   │ Executor → Tools   │
   └────────────────────┘
```

## Tech stack

- **Models:** local GGUF models served by `llama-server` (llama.cpp), OpenAI-compatible API
- **Backend:** Python · FastAPI · Pydantic · httpx
- **Storage:** SQLite
- **Frontend:** lightweight web UI with a live trace panel
- **Default models:** Qwen3 family + DeepSeek-R1 distill (supervisor, two coders,
  reasoner, uncensored critic, vision) — fully configurable per role

## Project status & roadmap

🚧 **Early development, but it runs.** You can already chat with the orchestrator
and watch the agents work in a live trace. Today everything runs on a single
local model; per-role models land in Phase 2.

- [x] **Phase 0** — Backend + chat UI + live agent trace ✅
- [~] **Phase 1** — Multi-agent coding pipeline (supervisor → 2 coders → critic).
  *Done. Contrarian critic + Deep Review mode still to add.*
- [ ] **Phase 2** — Session persistence + automatic local model swapping (each role its own model)
- [ ] **Phase 3** — Filesystem tools (sandboxed workspace)
- [ ] **Phase 4** — Shell execution + self-repair loop
- [ ] **Phase 5** — Multi-file project mode
- [ ] **Phase 6** — Vision: understand screenshots
- [ ] **Phase 7** — GUI control (one safe action at a time)
- [ ] **Phase 8** — Evaluation & benchmarks

> Design philosophy: get the **reasoning layer** rock-solid before adding any
> ability to touch the system. No flashy desktop agent before the brain is reliable.

## Run it locally

You need [llama.cpp](https://github.com/ggml-org/llama.cpp) and at least one GGUF
model. Then, from the project folder:

```powershell
# 1. Install Python deps
pip install -r requirements.txt

# 2. Start a local model on port 8001 (Windows helper script)
powershell -ExecutionPolicy Bypass -File scripts/start_model.ps1 reasoner

# 3. Start the web app
python -m uvicorn src.main:app --port 8000
```

Then open **http://127.0.0.1:8000**, type a prompt, and pick a mode
(Simple / Coding). The agent trace fills in live on the right.

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
<sub>Built for people who want their own private AI team, running entirely on their own hardware.</sub>
</div>
