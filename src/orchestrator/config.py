"""Runtime configuration for the ADK orchestrator foundation."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorSettings:
    """Settings required to bootstrap an ADK runner.

    Phase 1 intentionally keeps these values minimal: a logical ADK app name,
    a default user id for local runs, and a model id for the root LLM agent.
    """

    app_name: str = "adk-agent-orchestrator"
    user_id: str = "local-user"
    model: str = "gemini-flash-latest"

    @classmethod
    def from_env(cls) -> OrchestratorSettings:
        """Build settings from environment variables with safe local defaults."""

        return cls(
            app_name=os.getenv("ADK_APP_NAME", cls.app_name).strip() or cls.app_name,
            user_id=os.getenv("ADK_USER_ID", cls.user_id).strip() or cls.user_id,
            model=os.getenv("ADK_MODEL", cls.model).strip() or cls.model,
        )
