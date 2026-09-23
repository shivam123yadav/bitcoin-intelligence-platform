from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.paths import PROJECT_ROOT


ARTIFACT_ROOT = PROJECT_ROOT / "backend" / "data" / "artifacts"


def artifact_path(dataset_version: str, name: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in dataset_version).strip("._")
    directory = ARTIFACT_ROOT / f"v{safe}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{name}.json"


def load_artifact(dataset_version: str, name: str) -> dict[str, Any] | None:
    path = artifact_path(dataset_version, name)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_artifact(dataset_version: str, name: str, payload: dict[str, Any]) -> None:
    path = artifact_path(dataset_version, name)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    temp.replace(path)
