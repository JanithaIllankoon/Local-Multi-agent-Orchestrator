"""
model_registry.py

Loads config/models.yaml and tells the rest of the app, for any given role,
which endpoint to call and with what settings. Nothing else in the codebase
should ever read models.yaml directly - they all go through here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# config/models.yaml lives two levels up from this file (src/models/ -> repo root)
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "models.yaml"


@dataclass
class RoleConfig:
    role: str
    endpoint: str          # the full http URL we POST chat requests to
    temperature: float
    max_tokens: int
    can_call_tools: bool


class ModelRegistry:
    def __init__(self, config_path: Path = _CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self._cfg = yaml.safe_load(f)

        self._defaults = self._cfg.get("backend_defaults", {})

        # MVP switch: when single_endpoint_mode is on, every role is served by
        # ONE running model (single_endpoint). This lets us build the whole
        # pipeline against one model before juggling several servers.
        self._single_mode = self._cfg.get("single_endpoint_mode", False)
        self._single_endpoint = self._cfg.get("single_endpoint", "")

    def get_role(self, role: str) -> RoleConfig:
        roles = self._cfg.get("roles", {})
        if role not in roles:
            raise KeyError(f"Unknown role '{role}'. Check config/models.yaml.")
        r = roles[role]

        # In single-endpoint mode we ignore each role's own endpoint and send
        # everything to the one server that's actually running.
        endpoint = self._single_endpoint if self._single_mode else r["endpoint"]

        return RoleConfig(
            role=role,
            endpoint=endpoint,
            temperature=r.get("temperature", 0.2),
            max_tokens=r.get("max_tokens", 2048),
            can_call_tools=r.get("can_call_tools", False),
        )

    @property
    def timeout_seconds(self) -> int:
        return self._defaults.get("timeout_seconds", 300)

    @property
    def max_retries(self) -> int:
        return self._defaults.get("max_retries", 2)


# One shared instance the whole app imports.
registry = ModelRegistry()
