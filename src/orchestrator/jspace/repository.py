"""Filesystem persistence for immutable J-space snapshots."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from threading import Lock
from typing import Any

from orchestrator.jspace.models import JSpaceSnapshot, JSpaceValidationError

_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_component(value: str) -> str:
    normalized = _SAFE_COMPONENT.sub("_", value).strip("._")
    if not normalized:
        raise JSpaceValidationError("trace path component is empty after sanitization")
    return normalized[:160]


class FileJSpaceRepository:
    """Persist snapshots atomically below a repository-controlled root."""

    def __init__(
        self, root: str | Path, *, repository_root: str | Path, max_bytes: int = 65_536
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        candidate = Path(root)
        if not candidate.is_absolute():
            candidate = self.repository_root / candidate
        self.root = candidate.resolve()
        try:
            self.root.relative_to(self.repository_root)
        except ValueError as exc:
            raise JSpaceValidationError("J-space root must stay inside the repository") from exc
        self.max_bytes = max_bytes
        self._lock = Lock()

    def save(self, snapshot: JSpaceSnapshot) -> Path:
        payload = json.dumps(
            snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ).encode("utf-8")
        if len(payload) > self.max_bytes:
            raise JSpaceValidationError(
                f"J-space snapshot exceeds configured limit of {self.max_bytes} bytes"
            )

        session = safe_component(snapshot.session_id)
        agent = safe_component(snapshot.agent.name)
        phase = safe_component(snapshot.lifecycle.phase)
        target_dir = self.root / session / agent
        target = target_dir / f"{snapshot.sequence:06d}-{phase}.json"
        with self._lock:
            target_dir.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".json.tmp")
            temporary.write_bytes(payload)
            os.replace(temporary, target)
            self._write_manifest(snapshot)
        return target

    def _write_manifest(self, snapshot: JSpaceSnapshot) -> None:
        session_dir = self.root / safe_component(snapshot.session_id)
        manifest_path = session_dir / "manifest.json"
        manifest: dict[str, Any] = {
            "schema_version": snapshot.schema_version,
            "session_id": snapshot.session_id,
            "agents": {},
            "snapshot_count": 0,
        }
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        agents = manifest.setdefault("agents", {})
        agent_entry = agents.setdefault(snapshot.agent.name, {"snapshot_count": 0})
        agent_entry["snapshot_count"] += 1
        agent_entry["last_phase"] = snapshot.lifecycle.phase
        agent_entry["last_trace_id"] = snapshot.trace_id
        manifest["snapshot_count"] = int(manifest.get("snapshot_count", 0)) + 1
        manifest["updated_at"] = snapshot.timestamp
        temporary = manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, manifest_path)
