"""
orchestrator.py

The task controller. It runs the agents in order and yields a TraceEvent after
each step so the UI can show progress live. The last event is always the final
answer.

Phase 0 has two flows:
  - simple mode:  supervisor answers directly (chat / simple questions)
  - coding mode:  supervisor -> fast coder -> strong coder -> critic -> finalize
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..models import prompt_templates as P
from ..models.model_client import call_model


@dataclass
class TraceEvent:
    agent_role: str       # which agent produced this, e.g. "supervisor"
    event_type: str       # "plan" | "agent_response" | "final_answer" | "error"
    content: str          # the text shown in the trace card
    reasoning: str | None = None   # optional chain-of-thought for the trace
    latency_ms: int | None = None
    is_final: bool = False         # true only on the user-facing answer


def _msg(role: str, content: str) -> dict[str, str]:
    """Tiny helper to build one chat message."""
    return {"role": role, "content": content}


async def handle_message(
    message: str, mode: str = "auto", images: list[str] | None = None,
) -> AsyncIterator[TraceEvent]:
    """
    Entry point used by the API. Picks a flow and streams its trace events.
    'auto' uses a keyword guess for now; later the supervisor will classify.

    If images are attached, the Vision Observer runs first and its description
    is folded into the request the rest of the pipeline sees - so any mode can
    reason about a picture without the coders/critics being multimodal.
    `images` are data URLs (e.g. "data:image/png;base64,...").
    """
    try:
        request = message
        if images:
            vision = await _run_vision(message, images)
            yield TraceEvent("vision", "agent_response", vision.content,
                             reasoning=vision.reasoning, latency_ms=vision.latency_ms)
            request = (f"{message}\n\n"
                       f"[What the vision agent sees in the attached image(s)]:\n"
                       f"{vision.content}")

        if mode in ("simple", "coding", "deep_review"):
            chosen = mode
        else:
            # Cheap guess: treat code-ish requests as coding, else simple.
            chosen = "coding" if _looks_like_coding(message) else "simple"

        if chosen == "deep_review":
            async for ev in run_deep_review_mode(request):
                yield ev
        elif chosen == "coding":
            async for ev in run_coding_mode(request):
                yield ev
        else:
            async for ev in run_simple_mode(request):
                yield ev
    except Exception as e:
        # Surface any failure to the UI instead of hanging silently.
        yield TraceEvent("system", "error", f"Something went wrong: {e}", is_final=True)


async def _run_vision(message: str, images: list[str]):
    """Ask the Vision Observer to describe the attached image(s)."""
    content: list[dict] = [
        {"type": "text",
         "text": f"Describe these image(s) for this request:\n{message}"}
    ]
    for url in images:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return await call_model(
        "vision",
        [_msg("system", P.VISION), {"role": "user", "content": content}],
    )


def _looks_like_coding(message: str) -> bool:
    keywords = ("code", "script", "function", "bug", "python", "javascript",
                "write a", "program", "class ", "def ", "review this")
    text = message.lower()
    return any(k in text for k in keywords)


async def run_simple_mode(message: str) -> AsyncIterator[TraceEvent]:
    """User -> supervisor -> answer. For ordinary questions."""
    reply = await call_model(
        "supervisor",
        [_msg("system", P.SUPERVISOR), _msg("user", message)],
    )
    yield TraceEvent("supervisor", "final_answer", reply.content,
                     reasoning=reply.reasoning, latency_ms=reply.latency_ms,
                     is_final=True)


async def run_coding_mode(message: str) -> AsyncIterator[TraceEvent]:
    """The core multi-agent pipeline (Phase 0/1)."""

    # 1. Supervisor makes a short plan.
    plan = await call_model(
        "supervisor",
        [_msg("system", P.SUPERVISOR),
         _msg("user", f"Make a short plan to handle this request:\n\n{message}")],
    )
    yield TraceEvent("supervisor", "plan", plan.content,
                     reasoning=plan.reasoning, latency_ms=plan.latency_ms)

    # 2. Fast coder writes a first version.
    fast = await call_model(
        "coder_fast",
        [_msg("system", P.CODER_FAST),
         _msg("user", f"Request:\n{message}\n\nPlan:\n{plan.content}")],
    )
    yield TraceEvent("coder_fast", "agent_response", fast.content,
                     latency_ms=fast.latency_ms)

    # 3. Strong coder reviews and improves it.
    strong = await call_model(
        "coder_strong",
        [_msg("system", P.CODER_STRONG),
         _msg("user", f"Request:\n{message}\n\nFirst version:\n{fast.content}")],
    )
    yield TraceEvent("coder_strong", "agent_response", strong.content,
                     latency_ms=strong.latency_ms)

    # 4. Critic looks for flaws and edge cases.
    critic = await call_model(
        "reasoning_critic",
        [_msg("system", P.REASONING_CRITIC),
         _msg("user", f"Request:\n{message}\n\nCode to review:\n{strong.content}")],
    )
    yield TraceEvent("reasoning_critic", "agent_response", critic.content,
                     reasoning=critic.reasoning, latency_ms=critic.latency_ms)

    # 5. Supervisor merges everything into the final answer for the user.
    final = await call_model(
        "supervisor",
        [_msg("system", P.SUPERVISOR),
         _msg("user",
              f"{P.FINALIZE}\n\nUser request:\n{message}\n\n"
              f"Improved code:\n{strong.content}\n\n"
              f"Critic notes:\n{critic.content}")],
    )
    yield TraceEvent("supervisor", "final_answer", final.content,
                     reasoning=final.reasoning, latency_ms=final.latency_ms,
                     is_final=True)


async def run_deep_review_mode(message: str) -> AsyncIterator[TraceEvent]:
    """
    Like coding mode, but adds the contrarian critic for a second, harsher
    opinion before the supervisor finalizes. Use for high-stakes tasks.
    """

    # Steps 1-4 are the same as coding mode: plan, two coders, reasoning critic.
    plan = await call_model(
        "supervisor",
        [_msg("system", P.SUPERVISOR),
         _msg("user", f"Make a short plan to handle this request:\n\n{message}")],
    )
    yield TraceEvent("supervisor", "plan", plan.content,
                     reasoning=plan.reasoning, latency_ms=plan.latency_ms)

    fast = await call_model(
        "coder_fast",
        [_msg("system", P.CODER_FAST),
         _msg("user", f"Request:\n{message}\n\nPlan:\n{plan.content}")],
    )
    yield TraceEvent("coder_fast", "agent_response", fast.content,
                     latency_ms=fast.latency_ms)

    strong = await call_model(
        "coder_strong",
        [_msg("system", P.CODER_STRONG),
         _msg("user", f"Request:\n{message}\n\nFirst version:\n{fast.content}")],
    )
    yield TraceEvent("coder_strong", "agent_response", strong.content,
                     latency_ms=strong.latency_ms)

    critic = await call_model(
        "reasoning_critic",
        [_msg("system", P.REASONING_CRITIC),
         _msg("user", f"Request:\n{message}\n\nCode to review:\n{strong.content}")],
    )
    yield TraceEvent("reasoning_critic", "agent_response", critic.content,
                     reasoning=critic.reasoning, latency_ms=critic.latency_ms)

    # 5. Extra step: contrarian critic challenges the whole approach.
    contrarian = await call_model(
        "contrarian_critic",
        [_msg("system", P.CONTRARIAN_CRITIC),
         _msg("user", f"Request:\n{message}\n\nProposed solution:\n{strong.content}\n\n"
                      f"Reasoning critic already said:\n{critic.content}")],
    )
    yield TraceEvent("contrarian_critic", "agent_response", contrarian.content,
                     reasoning=contrarian.reasoning, latency_ms=contrarian.latency_ms)

    # 6. Supervisor weighs both critics and writes the final answer.
    final = await call_model(
        "supervisor",
        [_msg("system", P.SUPERVISOR),
         _msg("user",
              f"{P.FINALIZE}\n\nUser request:\n{message}\n\n"
              f"Improved code:\n{strong.content}\n\n"
              f"Reasoning critic notes:\n{critic.content}\n\n"
              f"Contrarian critic notes:\n{contrarian.content}")],
    )
    yield TraceEvent("supervisor", "final_answer", final.content,
                     reasoning=final.reasoning, latency_ms=final.latency_ms,
                     is_final=True)
