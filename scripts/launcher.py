"""
launcher.py

A tiny text-only control panel for the Local Multi-Agent Orchestrator.
No web knowledge needed: press Start and your browser opens to the chat UI.

Buttons:
  Start    - launch the backend (uvicorn), then open the chat UI in your browser
  Stop     - stop the backend and any llama-server it started
  Restart  - stop then start again (use after editing config)
  Open UI  - reopen the chat page in your browser

Run it:  python scripts/launcher.py     (or double-click start_gui.bat)

Tkinter ships with Python, so there's nothing to install. The backend runs as
a child process; closing this window stops it.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import scrolledtext

REPO_ROOT = Path(__file__).resolve().parents[1]
PORT = 8000
URL = f"http://127.0.0.1:{PORT}"


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.proc: subprocess.Popen | None = None
        self._log_q: queue.Queue[str] = queue.Queue()

        root.title("Orchestrator Control")
        root.geometry("640x420")
        root.minsize(480, 320)

        # --- top: status + buttons ---
        top = tk.Frame(root)
        top.pack(fill="x", padx=8, pady=8)

        self.status_var = tk.StringVar(value="Stopped")
        tk.Label(top, text="Server:").pack(side="left")
        self.status_lbl = tk.Label(top, textvariable=self.status_var,
                                   font=("Segoe UI", 10, "bold"))
        self.status_lbl.pack(side="left", padx=(4, 16))

        self.start_btn = tk.Button(top, text="Start", width=9, command=self.start)
        self.stop_btn = tk.Button(top, text="Stop", width=9, command=self.stop,
                                  state="disabled")
        self.restart_btn = tk.Button(top, text="Restart", width=9,
                                     command=self.restart, state="disabled")
        self.open_btn = tk.Button(top, text="Open UI", width=9,
                                  command=lambda: webbrowser.open(URL),
                                  state="disabled")
        for b in (self.start_btn, self.stop_btn, self.restart_btn, self.open_btn):
            b.pack(side="left", padx=3)

        # --- log area ---
        self.log = scrolledtext.ScrolledText(root, height=18, wrap="word",
                                             state="disabled",
                                             font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._set_status("Stopped", "gray25")
        self._log(f"Ready. Backend will serve {URL}\n")

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self._drain_log)

    # --- status / logging helpers ---

    def _set_status(self, text: str, color: str) -> None:
        self.status_var.set(text)
        self.status_lbl.config(fg=color)

    def _log(self, text: str) -> None:
        """Thread-safe: reader threads push here, the UI drains on a timer."""
        self._log_q.put(text)

    def _drain_log(self) -> None:
        while not self._log_q.empty():
            line = self._log_q.get_nowait()
            self.log.config(state="normal")
            self.log.insert("end", line)
            self.log.see("end")
            self.log.config(state="disabled")
        self.root.after(100, self._drain_log)

    def _running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # --- actions ---

    def start(self) -> None:
        if self._running():
            self._log("Already running.\n")
            return

        self._set_status("Starting...", "orange")
        self.start_btn.config(state="disabled")
        self._log(f"\n--- Starting backend on {URL} ---\n")

        # Launch uvicorn as a child process from the repo root. New process
        # group so we can kill the whole tree cleanly on Windows.
        cmd = [sys.executable, "-m", "uvicorn", "src.main:app",
               "--port", str(PORT)]
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        self.proc = subprocess.Popen(
            cmd, cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=creationflags,
        )

        threading.Thread(target=self._pump_output, daemon=True).start()
        threading.Thread(target=self._wait_ready, daemon=True).start()

    def _pump_output(self) -> None:
        """Stream the backend's console output into the log box."""
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            self._log(line)
        # Process ended.
        self._log("--- Backend process exited ---\n")
        self.root.after(0, self._on_stopped)

    def _wait_ready(self) -> None:
        """Poll the server until it answers, then open the browser."""
        deadline = time.time() + 60
        while time.time() < deadline:
            if not self._running():
                return  # died during startup; _pump_output handles UI reset
            try:
                with urllib.request.urlopen(URL, timeout=2) as r:
                    if r.status == 200:
                        self.root.after(0, self._on_ready)
                        return
            except Exception:
                pass
            time.sleep(1)
        self._log("Server did not become ready within 60s "
                  "(it may still be loading a model).\n")

    def _on_ready(self) -> None:
        self._set_status("Running", "forest green")
        self.stop_btn.config(state="normal")
        self.restart_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self._log(f"Server is up. Opening {URL}\n")
        webbrowser.open(URL)

    def _on_stopped(self) -> None:
        self._set_status("Stopped", "gray25")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.restart_btn.config(state="disabled")
        self.open_btn.config(state="disabled")

    def stop(self) -> None:
        self._set_status("Stopping...", "orange")
        self._kill_backend()
        self._kill_llama_servers()
        self.proc = None
        self._on_stopped()
        self._log("--- Stopped ---\n")

    def _kill_backend(self) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        pid = self.proc.pid
        if sys.platform == "win32":
            # /T kills the whole tree (uvicorn + its worker), /F forces it.
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True)
        else:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            pass

    def _kill_llama_servers(self) -> None:
        """Safety net: if model-swapping launched a llama-server, stop it too.
        (A forced backend kill can skip the graceful shutdown hook.)"""
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                           capture_output=True)

    def restart(self) -> None:
        self._log("\n--- Restarting ---\n")
        self.stop()
        self.root.after(800, self.start)

    def on_close(self) -> None:
        if self._running():
            self._kill_backend()
            self._kill_llama_servers()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
