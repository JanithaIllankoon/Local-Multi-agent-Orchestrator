"""
main.py

The web server. Serves the UI and exposes /api/chat, which streams each agent
step to the browser as it happens (Server-Sent Events) so you can watch the
team work instead of waiting for one big reply at the end.

Every turn is also persisted to SQLite (see src/storage/db.py) so sessions
survive a backend restart and can be reopened from the sidebar.

Run it with:   uvicorn src.main:app --reload
Then open:     http://127.0.0.1:8000
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core.orchestrator import handle_message
from .models.model_registry import registry
from .storage import db

app = FastAPI(title="Local Multi-Agent Orchestrator")


@app.on_event("shutdown")
def _stop_managed_server():
    """If we auto-launched a llama-server, stop it on app exit."""
    if registry.manage_servers:
        from .models.server_manager import manager
        manager.shutdown()

_WEB_DIR = Path(__file__).resolve().parents[1] / "web"


class ChatRequest(BaseModel):
    message: str
    mode: str = "auto"          # "auto" | "simple" | "coding" | "deep_review"
    session_id: int | None = None   # None -> start a new session


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Stream the orchestration. Each agent step is sent as one SSE 'data:' line
    containing a JSON trace event. The browser reads them one by one.

    The very first SSE line is a meta event carrying the session_id (new or
    existing) so the UI can track which session this turn belongs to. Every
    trace event and the final assistant reply are written to SQLite as they go.
    """
    # Resolve the session up front: create one on the first turn, titled by
    # the opening message; otherwise reuse the one the UI sent.
    if req.session_id is None:
        session_id = db.create_session(title=req.message, mode=req.mode)
    else:
        session_id = req.session_id
        if db.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Unknown session_id")

    user_msg_id = db.add_message(session_id, "user", req.message, mode=req.mode)

    async def event_stream():
        # Tell the UI which session this is before any trace cards arrive.
        yield f"data: {json.dumps({'meta': 'session', 'session_id': session_id})}\n\n"

        async for event in handle_message(req.message, req.mode):
            db.add_trace(
                session_id, user_msg_id,
                event.agent_role, event.event_type, event.content,
                reasoning=event.reasoning, latency_ms=event.latency_ms,
                is_final=event.is_final,
            )
            if event.is_final:
                db.add_message(session_id, "assistant", event.content, mode=req.mode)
            yield f"data: {json.dumps(asdict(event))}\n\n"

        db.touch_session(session_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/sessions")
async def get_sessions():
    """List past sessions, most recently active first (for the sidebar)."""
    return {"sessions": db.list_sessions()}


@app.get("/api/sessions/{session_id}")
async def get_one_session(session_id: int):
    """Full session payload (messages + trace) so a session can be reopened."""
    data = db.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    return data


@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: int):
    db.delete_session(session_id)
    return {"ok": True}


# Serve the web UI. index.html at "/", other assets (css/js) from /static.
@app.get("/")
async def index():
    return FileResponse(_WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")
