"""Durable snapshots and process-safe, crash-released response locks."""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


class RunBusyError(Exception):
    pass


class HumanRunStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        return self.root / f"{hashlib.sha256(run_id.encode()).hexdigest()}.json"

    def load(self, run_id: str) -> dict:
        try:
            return json.loads(self.path(run_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(run_id) from exc

    def save(self, run_id: str, value: dict) -> None:
        target = self.path(run_id)
        temporary = target.with_suffix(f".{uuid4()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(6):
                try:
                    os.replace(temporary, target)
                    break
                except PermissionError as exc:
                    if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 5:
                        raise
                    time.sleep(0.05 * 2**attempt)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    @contextmanager
    def lock(self, run_id: str):
        with self.path(run_id).with_suffix(".lock").open("a+b") as stream:
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RunBusyError("Esta execução já está processando uma resposta.") from exc
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def run_store_root(settings, repository_root: Path) -> Path:
    candidate = (repository_root / settings.task_run_root).resolve().parent / "executions"
    candidate.relative_to(repository_root.resolve())
    return candidate
