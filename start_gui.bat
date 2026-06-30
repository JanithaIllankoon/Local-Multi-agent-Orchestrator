@echo off
rem Double-click this to open the Orchestrator control panel.
rem Uses pythonw so no extra console window appears - the GUI has its own log.
cd /d "%~dp0"
start "" pythonw scripts\launcher.py
