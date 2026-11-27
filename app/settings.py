"""Small JSON settings store (EULA acceptance etc.)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import EULA_VERSION, data_dir

_PATH = data_dir() / "settings.json"


def load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    _PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def eula_accepted() -> bool:
    return load().get("eula_accepted_version") == EULA_VERSION


def accept_eula() -> None:
    data = load()
    data["eula_accepted_version"] = EULA_VERSION
    data["eula_accepted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save(data)
