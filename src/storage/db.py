"""
db.py

The persistence layer. Stores every conversation so it survives a backend
restart: sessions, the user/assistant messages in them, and the full agent
trace (one row per model call) behind each assistant reply.

Plain sqlite3 on purpose - no ORM. The orchestrator and API are the only
callers; nothing else should open the DB file directly.

Schema:
  sessions(id, title, mode, created_at, updated_at)
  messages(id, session_id, role, content, mode, created_at)   role: user|assistant
  traces(id, session_id, message_id, agent_role, event_type,
         content, reasoning, latency_ms, is_final, created_at)
    -> message_id points at the USER message that triggered the run, so
       reopening a session can replay each turn's trace.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# data/ lives at the repo root (src/storage/ -> repo root). The .db file is
# git-ignored (see .gitignore: *.db).
_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "orchestrator.db"

# sqlite3 connections aren't safe to share across threads by default, and
# FastAPI may hop threads. We use one connection guarded by a lock - traffic
# here is tiny (a few writes per chat turn), so a global lock is plenty.
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            mode       TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            mode       TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS traces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            message_id  INTEGER REFERENCES messages(id) ON DELETE CASCADE,
            agent_role  TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            content     TEXT,
            reasoning   TEXT,
            latency_ms  INTEGER,
            is_final    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_traces_session   ON traces(session_id);
        """
    )
    conn.commit()


# --- sessions ---------------------------------------------------------------

def create_session(title: str, mode: str | None = None) -> int:
    """Start a new session and return its id."""
    now = _now()
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO sessions (title, mode, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (title[:120] or "New chat", mode, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def touch_session(session_id: int) -> None:
    """Bump updated_at so the session sorts to the top of the list."""
    with _lock:
        conn = _connect()
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
        )
        conn.commit()


def list_sessions(limit: int = 100) -> list[dict[str, Any]]:
    """Most-recently-active sessions first, for the sidebar."""
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT id, title, mode, created_at, updated_at "
            "FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(session_id: int) -> dict[str, Any] | None:
    """Full session payload for reopening: messages, each with its trace."""
    with _lock:
        conn = _connect()
        s = conn.execute(
            "SELECT id, title, mode, created_at, updated_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if s is None:
            return None
        msgs = conn.execute(
            "SELECT id, role, content, mode, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        traces = conn.execute(
            "SELECT id, message_id, agent_role, event_type, content, reasoning, "
            "latency_ms, is_final, created_at FROM traces "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

    return {
        "session": dict(s),
        "messages": [dict(m) for m in msgs],
        "traces": [dict(t) for t in traces],
    }


def delete_session(session_id: int) -> None:
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()


# --- messages & traces ------------------------------------------------------

def add_message(session_id: int, role: str, content: str, mode: str | None = None) -> int:
    """Store one user or assistant message; returns its id."""
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, mode, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, mode, _now()),
        )
        conn.commit()
        return int(cur.lastrowid)


def add_trace(
    session_id: int,
    message_id: int | None,
    agent_role: str,
    event_type: str,
    content: str,
    reasoning: str | None = None,
    latency_ms: int | None = None,
    is_final: bool = False,
) -> None:
    """Store one trace event (one model call / pipeline step)."""
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO traces (session_id, message_id, agent_role, event_type, "
            "content, reasoning, latency_ms, is_final, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, message_id, agent_role, event_type, content,
             reasoning, latency_ms, 1 if is_final else 0, _now()),
        )
        conn.commit()
