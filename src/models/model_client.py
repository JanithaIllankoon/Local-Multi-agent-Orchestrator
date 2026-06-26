"""
model_client.py  -  INTERFACE SKETCH (not implemented yet)

The single async entry point for talking to any llama.cpp server. Every agent
goes through call_model(role=...); nothing in the codebase should ever hardcode
a URL or model name. This is the seam that makes "swap models via config only"
true.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelResponse:
    role: str
    content: str               # final answer text (message.content)
    reasoning: str | None      # message.reasoning_content - R1/thinking models
                               # emit chain-of-thought here, NOT in content.
                               # Store it in the trace; never use it as the answer.
    latency_ms: int
    raw: dict[str, Any]        # full provider JSON, for logging / token counts

    # NOTE: reasoning models (DeepSeek-R1 distill) can return content="" if
    # max_tokens is too small - they spend the budget thinking. Give reasoning
    # roles a generous max_tokens (see reasoning_critic in models.yaml).


async def call_model(
    role: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,   # None -> use the role's config value
    max_tokens: int | None = None,
    response_format: dict | None = None,  # e.g. {"type": "json_object"}
    grammar: str | None = None,           # optional GBNF to force valid JSON
) -> ModelResponse:
    """
    Resolve `role` -> endpoint + defaults via the registry, POST an
    OpenAI-style /v1/chat/completions request with httpx, retry on
    timeout/5xx per backend_defaults, and return a ModelResponse.

    Phase 0: registry resolves every role to single_endpoint, so this works
    against one running llama-server. Phase 2: ensure_role_ready(role) is
    called first so the right server is up before the request.
    """
    raise NotImplementedError


def parse_json_lenient(text: str) -> dict | None:
    """
    Local 7B models emit broken JSON constantly (code fences, trailing prose,
    smart quotes). Try strict json.loads, then strip ```json fences, then
    regex the outermost {...}. Returns None if all fail so the caller can run
    the §24 repair loop (ask the same model to fix its JSON) before giving up.
    """
    raise NotImplementedError
