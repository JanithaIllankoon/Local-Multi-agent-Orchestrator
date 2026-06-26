"""
orchestrator.py  -  INTERFACE SKETCH (not implemented yet)

The task controller. NOT a chatbot wrapper. It owns the per-mode pipelines.
Notice it only ever names ROLES, never models or endpoints, and it emits trace
events as it goes (so the UI can stream them over SSE instead of waiting for a
final blob).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class TraceEvent:
    agent_role: str       # "supervisor", "coder_fast", ...
    event_type: str       # "plan" | "agent_response" | "critic_response" | "final_answer" | "error"
    content: str
    latency_ms: int | None = None


async def handle_message(session_id: str, message: str, mode: str = "auto") -> AsyncIterator[TraceEvent]:
    """
    Top-level entry called by POST /api/chat. Yields TraceEvents as each agent
    finishes so the UI updates live; the last event is event_type="final_answer".

    'auto' asks the supervisor to classify, then dispatches to one of the mode
    pipelines below. MVP only needs run_coding_mode well enough to pass the
    Plan.txt §31 acceptance test.
    """
    raise NotImplementedError


async def run_coding_mode(session_id: str, message: str) -> AsyncIterator[TraceEvent]:
    """
    The MVP pipeline (Plan.txt §21.2):

        supervisor.create_plan(message)            -> TraceEvent(plan)
        coder_fast.run(message, plan)              -> TraceEvent(agent_response)
        coder_strong.run(message, plan, fast)      -> TraceEvent(agent_response)
        reasoning_critic.run(..., strong)          -> TraceEvent(critic_response)
        supervisor.finalize([fast, strong, critic])-> TraceEvent(final_answer)

    No tools. Each step is one call_model() behind an agent's system prompt.
    """
    raise NotImplementedError


async def run_simple_mode(session_id: str, message: str) -> AsyncIterator[TraceEvent]:
    """User -> supervisor -> final answer. For chit-chat / trivial questions."""
    raise NotImplementedError
