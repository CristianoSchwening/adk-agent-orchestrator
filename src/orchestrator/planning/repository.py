"""Atomic JSON persistence for validated task plans."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock

from orchestrator.planning.models import TaskPlan
from orchestrator.planning.validation import TaskPlanValidationError, validate_task_plan

_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]+")


class FileTaskPlanRepository:
    """Store one immutable-intent plan per JSON file inside a controlled root."""

    def __init__(self, root: str | Path, *, repository_root: str | Path, max_bytes: int = 262_144) -> None:
        self.repository_root = Path(repository_root).resolve()
        candidate = Path(root)
        if not candidate.is_absolute():
            candidate = self.repository_root / candidate
        self.root = candidate.resolve()
        try:
            self.root.relative_to(self.repository_root)
        except ValueError as exc:
            raise TaskPlanValidationError(["task-plan root must stay inside the repository"]) from exc
        self.max_bytes = max_bytes
        self._lock = Lock()

    def save(self, plan: TaskPlan) -> Path:
        validate_task_plan(plan)
        payload = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        if len(payload) > self.max_bytes:
            raise TaskPlanValidationError([f"task plan exceeds configured limit of {self.max_bytes} bytes"])
        target = self._path(plan.plan_id)
        with self._lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".json.tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, target)
        return target

    def get(self, plan_id: str) -> TaskPlan | None:
        target = self._path(plan_id)
        if not target.exists():
            return None
        try:
            value = json.loads(target.read_text(encoding="utf-8"))
            plan = TaskPlan.from_dict(value)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise TaskPlanValidationError([f"stored task plan {plan_id} is invalid"]) from exc
        return validate_task_plan(plan)

    def _path(self, plan_id: str) -> Path:
        safe_id = _SAFE_COMPONENT.sub("_", plan_id).strip("._")
        if not safe_id or safe_id != plan_id:
            raise TaskPlanValidationError(["plan_id contains unsafe path characters"])
        return self.root / f"{safe_id}.json"
