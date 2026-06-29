from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "jobs.json"


def _load() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {}
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def _save(data: dict[str, Any]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create_job(job_id: str, file_name: str) -> None:
    data = _load()
    data[job_id] = {
        "id": job_id,
        "file_name": file_name,
        "status": "processing",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save(data)


def update_job(job_id: str, patch: dict[str, Any]) -> None:
    data = _load()
    job = data.setdefault(job_id, {"id": job_id})
    job.update(patch)
    job["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save(data)


def get_job(job_id: str) -> dict[str, Any] | None:
    return _load().get(job_id)


def list_jobs() -> list[dict[str, Any]]:
    return sorted(_load().values(), key=lambda item: item.get("created_at", ""), reverse=True)

