"""Atomic persistence for dispatcher state after every transition."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock

from orchestrator.dispatching.models import PlanRun

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class FileTaskRunRepository:
    def __init__(self, root: str | Path, *, repository_root: str | Path, max_bytes: int = 524_288):
        self.repository_root = Path(repository_root).resolve()
        candidate = Path(root)
        self.root = (
            candidate if candidate.is_absolute() else self.repository_root / candidate
        ).resolve()
        try:
            self.root.relative_to(self.repository_root)
        except ValueError as exc:
            raise ValueError("task-run root must stay inside the repository") from exc
        self.max_bytes = max_bytes
        self._lock = Lock()

    def save(self, run: PlanRun) -> Path:
        payload = json.dumps(run.to_dict(), ensure_ascii=False, indent=2, sort_keys=True).encode()
        if len(payload) > self.max_bytes:
            raise ValueError(f"task run exceeds configured limit of {self.max_bytes} bytes")
        target = self._path(run.run_id)
        with self._lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".json.tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, target)
        return target

    def get(self, run_id: str) -> PlanRun | None:
        target = self._path(run_id)
        return (
            PlanRun.from_dict(json.loads(target.read_text(encoding="utf-8")))
            if target.exists()
            else None
        )

    def _path(self, run_id: str) -> Path:
        if not _SAFE_COMPONENT.fullmatch(run_id):
            raise ValueError("run_id contains unsafe path characters")
        return self.root / f"{run_id}.json"
