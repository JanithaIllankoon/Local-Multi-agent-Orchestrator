"""
server_manager.py

Phase 2: automatic local model swapping.

On an 8GB GPU only ONE big model can be alive at a time, so the orchestrator
can't keep five llama-servers running. Instead, before each agent call we make
sure the right server is up - launching it and stopping whatever was running
before. Roles that share a model (supervisor + coder_fast both use the MoE on
port 8001) share a server, so no needless restart happens between them.

Driven by config/server_commands.yaml (launch specs) and the manage_servers /
single_endpoint_mode flags in models.yaml. When manage_servers is off this
module does nothing and you start servers by hand (the Phase 0/1 workflow).

Why structured argv instead of a command string: the project path has spaces.
We hand subprocess a LIST so each argument is quoted correctly on Windows -
the exact bug recorded in the launch-gotchas notes.
"""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC_PATH = _REPO_ROOT / "config" / "server_commands.yaml"


class _Running:
    """Bookkeeping for the one server currently alive."""
    def __init__(self, name: str, port: int, proc: subprocess.Popen):
        self.name = name
        self.port = port
        self.proc = proc


class ModelServerManager:
    def __init__(self, spec_path: Path = _SPEC_PATH):
        with open(spec_path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        self._exe = spec["llama_server_exe"]
        d = spec.get("defaults", {})
        self._host = d.get("host", "127.0.0.1")
        self._startup_timeout = d.get("startup_timeout_seconds", 300)
        self._poll = d.get("health_poll_seconds", 2)
        self._servers = spec.get("servers", {})

        # port -> server name, so we can resolve a role (which carries an
        # endpoint URL) to the server that should answer it.
        self._by_port = {s["port"]: name for name, s in self._servers.items()}

        self._lock = threading.Lock()   # serialize swaps; only one model at a time
        self._current: _Running | None = None

    # -- public API ----------------------------------------------------------

    def ensure_running_for_endpoint(self, endpoint: str) -> None:
        """
        Make sure the server that owns `endpoint`'s port is the one running.
        Blocking: may stop the current server and wait for the new one to load.
        Safe to call every request - it's a no-op when the right server is up.
        """
        port = urlparse(endpoint).port
        name = self._by_port.get(port)
        if name is None:
            # Endpoint isn't one we manage (e.g. an external server). Leave it.
            return

        with self._lock:
            if self._current is not None and self._current.port == port:
                if self._current.proc.poll() is None:
                    return  # already running and healthy enough
                # It died on us; fall through to relaunch.
                self._current = None

            self._stop_current_locked()
            self._start_locked(name)

    def shutdown(self) -> None:
        """Stop the running server, if any (call on app shutdown)."""
        with self._lock:
            self._stop_current_locked()

    @property
    def current_server(self) -> str | None:
        c = self._current
        return c.name if c and c.proc.poll() is None else None

    # -- internals -----------------------------------------------------------

    def _build_argv(self, name: str) -> list[str]:
        s = self._servers[name]
        model = str((_REPO_ROOT / s["model"]).resolve())
        argv = [self._exe, "-m", model,
                "--host", self._host, "--port", str(s["port"])]
        # Resolve any path-like extra args (e.g. --mmproj) against the repo root.
        extra = list(s.get("args", []))
        for i, tok in enumerate(extra):
            if tok.startswith("models/") or tok.startswith("models\\"):
                extra[i] = str((_REPO_ROOT / tok).resolve())
        argv.extend(extra)
        return argv

    def _start_locked(self, name: str) -> None:
        s = self._servers[name]
        port = s["port"]
        model_path = (_REPO_ROOT / s["model"]).resolve()
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model for server '{name}' not found: {model_path}"
            )

        argv = self._build_argv(name)
        # Popen with a LIST -> correct quoting despite the space in the path.
        proc = subprocess.Popen(argv, cwd=str(_REPO_ROOT))
        self._current = _Running(name, port, proc)
        self._wait_until_ready(port, proc, name)

    def _wait_until_ready(self, port: int, proc: subprocess.Popen, name: str) -> None:
        """Poll the server's /health until it answers or we time out."""
        url = f"http://{self._host}:{port}/health"
        deadline = time.time() + self._startup_timeout
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"llama-server '{name}' exited during startup "
                    f"(code {proc.returncode})."
                )
            try:
                r = httpx.get(url, timeout=self._poll)
                if r.status_code == 200:
                    return
            except Exception:
                pass  # not up yet
            time.sleep(self._poll)
        # Timed out: kill the half-started process so we don't leak it.
        self._stop_current_locked()
        raise TimeoutError(
            f"llama-server '{name}' did not become ready within "
            f"{self._startup_timeout}s."
        )

    def _stop_current_locked(self) -> None:
        c = self._current
        self._current = None
        if c is None:
            return
        if c.proc.poll() is None:
            c.proc.terminate()
            try:
                c.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                c.proc.kill()


# One shared manager for the app. Cheap to construct (just parses YAML).
manager = ModelServerManager()
