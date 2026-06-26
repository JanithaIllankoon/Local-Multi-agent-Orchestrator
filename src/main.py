"""
main.py

The web server. Serves the UI and exposes /api/chat, which streams each agent
step to the browser as it happens (Server-Sent Events) so you can watch the
team work instead of waiting for one big reply at the end.

Run it with:   uvicorn src.main:app --reload
Then open:     http://127.0.0.1:8000
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core.orchestrator import handle_message

app = FastAPI(title="Local Multi-Agent Orchestrator")

_WEB_DIR = Path(__file__).resolve().parents[1] / "web"


class ChatRequest(BaseModel):
    message: str
    mode: str = "auto"   # "auto" | "simple" | "coding"


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Stream the orchestration. Each agent step is sent as one SSE 'data:' line
    containing a JSON trace event. The browser reads them one by one.
    """
    async def event_stream():
        async for event in handle_message(req.message, req.mode):
            yield f"data: {json.dumps(asdict(event))}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# Serve the web UI. index.html at "/", other assets (css/js) from /static.
@app.get("/")
async def index():
    return FileResponse(_WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_WEB_DIR), name="static")
