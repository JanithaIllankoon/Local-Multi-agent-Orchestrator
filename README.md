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

## The AI team (default models)

Each role is filled by a local model chosen to fit a single 8GB GPU. Swap any of
them by editing [`config/models.yaml`](config/models.yaml) — no code changes.
Models are **not** included in this repo (they're multi-GB); download them from
Hugging Face into a local `models/` folder.

| Role | Model | What it does |
|------|-------|--------------|
| 🧭 Supervisor / tools | [Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) | Plans, delegates, calls tools, writes the final answer |
| ⚡ Fast coder | (shares the supervisor model) | Quick first-draft implementations |
| 🛠️ Strong coder | [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) | Reviews and hardens code, harder problems |
| 🔍 Reasoning critic | [DeepSeek-R1-0528-Qwen3-8B](https://huggingface.co/unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF) | Finds flaws, edge cases, weak assumptions |
| 😈 Contrarian critic | [Qwen3-8B-abliterated](https://huggingface.co/huihui-ai/Qwen3-8B-abliterated) | Low-refusal harsh second opinions *(planned)* |
| 👁️ Vision observer | [Qwen3-VL-8B-Thinking](https://huggingface.co/Qwen/Qwen3-VL-8B-Thinking) | Describes screenshots / GUI state *(Phase 6)* |

> On an 8GB GPU these run **one at a time** (the orchestrator swaps between them),
> so each model gets the full GPU while it's active.

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
- [x] **Phase 1** — Multi-agent pipeline: supervisor → 2 coders → reasoning critic
  → contrarian critic, with Coding and Deep Review modes ✅
- [x] **Phase 2** — Session persistence (SQLite: sessions, messages, full trace)
  + automatic local model swapping (one server per role, swapped on demand) ✅
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
(Simple / Coding / Deep Review). The agent trace fills in live on the right,
and every conversation is saved — past **sessions** appear in the left sidebar
and reopen with their full trace, surviving a backend restart.

### Automatic model swapping (optional)

By default everything talks to one hand-started server (`single_endpoint_mode:
true`). To let the orchestrator run a different model per role — swapping them
one at a time so an 8GB GPU is never overcommitted — edit
[`config/models.yaml`](config/models.yaml):

```yaml
single_endpoint_mode: false
manage_servers: true
```

Now you don't run `start_model.ps1` yourself: the backend launches the right
`llama-server` for each agent and stops the previous one, using the launch
specs in [`config/server_commands.yaml`](config/server_commands.yaml). The
first call to a cold model is slow while it loads.

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
<sub>Built for people who want their own private AI team, running entirely on their own hardware.</sub>
</div>
