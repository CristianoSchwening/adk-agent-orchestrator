"""Load the repository-editable user profile."""

from __future__ import annotations

import json
from pathlib import Path

from orchestrator.context.models import UserProfile


def load_user_profile(
    path: str | Path,
    *,
    repository_root: str | Path,
) -> UserProfile | None:
    """Load a profile inside the repository, returning None when it is absent."""

    root = Path(repository_root).resolve()
    candidate = (root / path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("user profile path must stay inside the repository")
    if not candidate.exists():
        return None
    value = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("user profile must be a JSON object")
    profile = UserProfile.from_dict(value)
    if not profile.user_id:
        raise ValueError("user profile requires a non-empty user_id")
    return profile
