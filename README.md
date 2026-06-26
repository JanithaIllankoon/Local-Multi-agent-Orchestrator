# Local Multi-Agent Orchestrator

A local, privacy-preserving multi-agent system where you talk to **one**
interface — the **Orchestrator** — and it internally coordinates several local
LLMs (a supervisor, coders, critics, and later a vision model), aggregates their
output, and returns a single polished answer.

Models run locally via [llama.cpp](https://github.com/ggml-org/llama.cpp)
(`llama-server`) behind OpenAI-style `/v1/chat/completions` endpoints. Upgrading
a model is a config edit, never a code change.

> Full design lives in [`Plan.txt`](Plan.txt). This README is the practical
> getting-started guide.

## Core principle

Separate **thinking**, **suggesting**, and **acting**:

```
User talks to Orchestrator.
Orchestrator talks to agents.
Agents suggest.
Supervisor decides.
Executor acts (later phases).
UI displays result + trace.
```

No specialist model ever touches the filesystem, shell, or GUI directly — only a
safety-gated Executor does, and that comes in later phases.

## Hardware target & the memory reality

Built around a **single 8–12GB NVIDIA GPU**. You **cannot** keep all roles
resident at once. Two coping strategies, both supported by design:

- **Phase 0 (now):** one `llama-server`, one model, every role behind a
  different system prompt. `single_endpoint_mode: true` in
  [`config/models.yaml`](config/models.yaml) makes every role resolve to one
  endpoint. Build the whole orchestration loop on this first.
- **Phase 2+:** a `ModelServerManager` lazily starts/stops per-role servers.
  Several roles **share a GGUF** (the two critics reuse the supervisor model) so
  swaps are cheap — only ~3 real model downloads back all 7 roles.

### Suggested models (all Qwen2.5, Q4_K_M GGUF)

| Role | Model | Notes |
|------|-------|-------|
| supervisor | Qwen2.5-7B-Instruct | planning + JSON |
| coder_fast | Qwen2.5-Coder-3B | quick patches |
| coder_strong | Qwen2.5-Coder-7B | harder coding/review |
| reasoning_critic | *(reuses supervisor GGUF)* | no extra download |
| contrarian_critic | *(reuses supervisor GGUF, hotter temp)* | — |
| summarizer | Qwen2.5-3B-Instruct | cheap/fast |
| vision | Qwen2.5-VL-7B + mmproj | **deferred to Phase 6** |

Staying within one model family keeps the chat template and JSON behavior
consistent.

## Getting started

### 1. Install llama.cpp

Download a prebuilt **CUDA** `llama-server` release from
[llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases) (no need to
compile). Put it on your `PATH`.

### 2. Get one model

Download `Qwen2.5-7B-Instruct-Q4_K_M.gguf` into `models/` (the `models/` and
`workspace/` dirs are git-ignored). Start with **one** model — do not download
all of them yet.

### 3. Start the server

```powershell
llama-server -m "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf" `
  --host 127.0.0.1 --port 8001 --jinja -c 8192 -ngl 99
```

If you hit out-of-memory, lower `-ngl` (e.g. `-ngl 20`) or `-c` (e.g. `-c 4096`).

### 4. Smoke test (do this before writing app code)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_test.ps1
```

Expect `OK - model replied: hello orchestrator`. If this fails, fix it before
anything else — the entire project is Python over this HTTP endpoint.

### 5. Backend (Phase 0, once it exists)

```powershell
pip install fastapi uvicorn pydantic httpx pyyaml aiosqlite rich
uvicorn src.main:app --reload
```

## Project layout

```
config/
  models.yaml            # role -> model/endpoint registry (the swap point)
  server_commands.yaml   # llama-server launch commands per role (Phase 2+)
scripts/
  smoke_test.ps1         # verify llama-server before building
src/
  models/model_client.py # call_model(role=...) - the one model seam (sketch)
  core/orchestrator.py   # the task controller / mode pipelines (sketch)
Plan.txt                 # full architecture & phased plan
```

> `src/*.py` are currently **interface sketches** (signatures + docstrings, not
> implementations). They define the contracts to build against next.

## Build order

1. **Phase 0** — FastAPI skeleton, model client, supervisor-only chat, basic UI + trace.
2. **Phase 1** — fast/strong coders + reasoning critic, coding-mode pipeline, streaming trace.
3. **Phase 2** — SQLite persistence; `ModelServerManager` + real per-role models.
4. **Phase 3+** — filesystem tools, shell tools, repair loop, then (much later) vision & GUI.

Do **not** build GUI control first. Get the text orchestrator genuinely reliable
before adding any tools.

### First milestone

Type *"write a Python calculator"*, watch supervisor → fast coder → strong coder
→ critic → final stream into the trace panel, get a clean answer — all on one
local Qwen2.5-7B via llama.cpp.
