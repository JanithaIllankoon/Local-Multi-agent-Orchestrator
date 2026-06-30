"""
model_client.py

The single way the app talks to any model. Every agent calls call_model(role=...)
and never worries about URLs, retries, or which model is behind the role.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .model_registry import registry


@dataclass
class ModelResponse:
    role: str
    content: str               # the final answer text
    reasoning: str | None      # chain-of-thought, if the model returns it
                               # separately (DeepSeek-R1 does). For the trace,
                               # never used as the answer itself.
    latency_ms: int
    raw: dict[str, Any]        # full server JSON, kept for logging


async def call_model(
    role: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,   # None = use the role's default
    max_tokens: int | None = None,
) -> ModelResponse:
    """
    Send an OpenAI-style chat request for `role` and return the reply.
    Retries on network/5xx errors per backend_defaults in models.yaml.
    """
    cfg = registry.get_role(role)

    # Phase 2: make sure this role's model server is the one running before we
    # call it (may stop another model and load this one - blocking, so run it
    # off the event loop). No-op when manage_servers is off.
    if registry.manage_servers:
        from .server_manager import manager
        await asyncio.to_thread(manager.ensure_running_for_endpoint, cfg.endpoint)

    payload = {
        "model": role,  # llama.cpp ignores this, but the API expects the field
        "messages": messages,
        "temperature": cfg.temperature if temperature is None else temperature,
        "max_tokens": cfg.max_tokens if max_tokens is None else max_tokens,
    }

    last_error: Exception | None = None
    # Try once, then retry up to max_retries more times if the call fails.
    for attempt in range(registry.max_retries + 1):
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=registry.timeout_seconds) as client:
                resp = await client.post(cfg.endpoint, json=payload)
                resp.raise_for_status()
            latency_ms = int((time.perf_counter() - start) * 1000)

            data = resp.json()
            message = data["choices"][0]["message"]
            return ModelResponse(
                role=role,
                content=message.get("content") or "",
                reasoning=message.get("reasoning_content"),
                latency_ms=latency_ms,
                raw=data,
            )
        except Exception as e:  # network error, timeout, bad status, bad JSON
            last_error = e
            # Don't sleep-spin on the last attempt; just fall through to raise.
            if attempt < registry.max_retries:
                continue

    raise RuntimeError(
        f"call_model(role='{role}') failed after {registry.max_retries + 1} "
        f"attempts against {cfg.endpoint}: {last_error}"
    )
