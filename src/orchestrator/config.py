"""Runtime configuration for the ADK orchestrator foundation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Literal

MCPTransport = Literal["stdio", "sse", "streamable_http"]
ProgressiveFinalSummarizerMode = Literal["enabled", "disabled", "auto"]
ProgressiveFinalResponseStrategy = Literal[
    "last_agent_response",
    "summarizer_response",
    "root_selected_response",
    "all_visible_responses",
]
WorkspaceEnforcementMode = Literal["audit", "strict"]
ModelRole = Literal["router", "reasoning", "worker", "finalizer"]


@dataclass(frozen=True)
class MCPServerSettings:
    """Configuration for one external MCP server/toolset."""

    name: str
    transport: MCPTransport = "stdio"
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> MCPServerSettings:
        """Build MCP server settings from a JSON-compatible mapping."""

        name = str(value.get("name", "")).strip()
        if not name:
            raise ValueError("MCP server entry must include a non-empty name.")

        transport = str(value.get("transport", "stdio")).strip() or "stdio"
        if transport not in {"stdio", "sse", "streamable_http"}:
            raise ValueError(f"Unsupported MCP transport: {transport}")

        raw_args = value.get("args", ())
        if isinstance(raw_args, str):
            args = (raw_args,)
        else:
            args = tuple(str(item) for item in raw_args)

        raw_env = value.get("env", {}) or {}
        if not isinstance(raw_env, dict):
            raise ValueError("MCP server env must be an object when provided.")

        return cls(
            name=name,
            transport=transport,  # type: ignore[arg-type]
            command=_optional_str(value.get("command")),
            args=args,
            url=_optional_str(value.get("url")),
            env={str(key): str(env_value) for key, env_value in raw_env.items()},
        )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_positive_float(raw_value: str | None, default: float, env_name: str) -> float:
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a number.") from exc
    if value <= 0:
        raise ValueError(f"{env_name} must be greater than zero.")
    return value


def _parse_positive_int(raw_value: str | None, default: int, env_name: str) -> int:
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{env_name} must be greater than zero.")
    return value


def _parse_bool(raw_value: str | None, default: bool, env_name: str) -> bool:
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{env_name} must be a boolean.")


def _parse_workspace_mode(raw_value: str | None) -> WorkspaceEnforcementMode:
    normalized = (raw_value or "strict").strip().lower()
    if normalized not in {"audit", "strict"}:
        raise ValueError("ADK_WORKSPACE_MODE must be either audit or strict.")
    return normalized  # type: ignore[return-value]


def _parse_mcp_servers(raw_value: str | None) -> tuple[MCPServerSettings, ...]:
    if raw_value is None or not raw_value.strip():
        return ()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("ADK_MCP_SERVERS must be valid JSON.") from exc
    if not isinstance(payload, list):
        raise ValueError("ADK_MCP_SERVERS must be a JSON array.")
    return tuple(MCPServerSettings.from_mapping(item) for item in payload)


def _normalize_progressive_final_summarizer_mode(
    value: bool | str,
) -> ProgressiveFinalSummarizerMode:
    if isinstance(value, bool):
        return "enabled" if value else "disabled"
    normalized = str(value).strip().lower()
    boolean_aliases = {
        "true": "enabled",
        "1": "enabled",
        "yes": "enabled",
        "on": "enabled",
        "false": "disabled",
        "0": "disabled",
        "no": "disabled",
        "off": "disabled",
    }
    normalized = boolean_aliases.get(normalized, normalized)
    if normalized not in {"enabled", "disabled", "auto"}:
        raise ValueError(
            "final_summarizer_enabled must be a boolean or one of: enabled, disabled, auto."
        )
    return normalized  # type: ignore[return-value]


def _normalize_progressive_final_response_strategy(
    value: str,
) -> ProgressiveFinalResponseStrategy:
    normalized = str(value).strip().lower()
    allowed = {
        "last_agent_response",
        "summarizer_response",
        "root_selected_response",
        "all_visible_responses",
    }
    if normalized not in allowed:
        raise ValueError(
            "final_response_strategy must be one of: last_agent_response, "
            "summarizer_response, root_selected_response, all_visible_responses."
        )
    return normalized  # type: ignore[return-value]


@dataclass(frozen=True)
class ProgressiveMultiAgentResponseSettings:
    """Configuration for the progressive multi-agent response workflow."""

    final_summarizer_enabled: bool | ProgressiveFinalSummarizerMode = "disabled"
    final_response_strategy: ProgressiveFinalResponseStrategy = "all_visible_responses"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "final_summarizer_enabled",
            _normalize_progressive_final_summarizer_mode(self.final_summarizer_enabled),
        )
        object.__setattr__(
            self,
            "final_response_strategy",
            _normalize_progressive_final_response_strategy(self.final_response_strategy),
        )

    @classmethod
    def from_env(cls) -> ProgressiveMultiAgentResponseSettings:
        """Build progressive workflow settings from optional environment variables."""

        return cls(
            final_summarizer_enabled=os.getenv(
                "ADK_PROGRESSIVE_FINAL_SUMMARIZER_ENABLED",
                cls.final_summarizer_enabled,
            ),
            final_response_strategy=os.getenv(
                "ADK_PROGRESSIVE_FINAL_RESPONSE_STRATEGY",
                cls.final_response_strategy,
            ),
        )


@dataclass(frozen=True)
class OrchestratorSettings:
    """Settings required to bootstrap an ADK runner and local tool layer."""

    app_name: str = "adk-agent-orchestrator"
    user_id: str = "local-user"
    model: str = "gemini-flash-latest"
    router_model: str | None = None
    reasoning_model: str | None = None
    worker_model: str | None = None
    finalizer_model: str | None = None
    fallback_model: str | None = None
    model_retry_attempts: int = 4
    model_retry_initial_delay_seconds: float = 1.0
    model_retry_max_delay_seconds: float = 8.0
    model_retry_exponential_base: float = 2.0
    model_retry_jitter_seconds: float = 1.0
    tool_timeout_seconds: float = 10.0
    mcp_servers: tuple[MCPServerSettings, ...] = ()
    workspace_enabled: bool = True
    workspace_mode: WorkspaceEnforcementMode = "strict"
    workspace_root: str = "observability/verbalized_workspace/traces"
    workspace_max_bytes: int = 65_536
    task_plan_root: str = "data/task_plans"
    task_plan_max_bytes: int = 262_144
    task_run_root: str = "data/task_runs"
    task_run_max_bytes: int = 524_288
    progressive_multi_agent_response: ProgressiveMultiAgentResponseSettings = field(
        default_factory=ProgressiveMultiAgentResponseSettings
    )

    def model_for(self, role: ModelRole) -> str:
        """Resolve a role-specific model while preserving ``ADK_MODEL`` compatibility."""

        override = {
            "router": self.router_model,
            "reasoning": self.reasoning_model,
            "worker": self.worker_model,
            "finalizer": self.finalizer_model,
        }[role]
        return override or self.model

    def resolved_model_basket(self) -> dict[str, str | None]:
        """Return the effective model assigned to every orchestration role."""

        basket: dict[str, str | None] = {
            role: self.model_for(role)
            for role in ("router", "reasoning", "worker", "finalizer")
        }
        basket["fallback"] = self.fallback_model
        return basket

    @classmethod
    def from_env(cls) -> OrchestratorSettings:
        """Build settings from environment variables with safe local defaults."""

        return cls(
            app_name=os.getenv("ADK_APP_NAME", cls.app_name).strip() or cls.app_name,
            user_id=os.getenv("ADK_USER_ID", cls.user_id).strip() or cls.user_id,
            model=os.getenv("ADK_MODEL", cls.model).strip() or cls.model,
            router_model=_optional_str(os.getenv("ADK_MODEL_ROUTER")),
            reasoning_model=_optional_str(os.getenv("ADK_MODEL_REASONING")),
            worker_model=_optional_str(os.getenv("ADK_MODEL_WORKER")),
            finalizer_model=_optional_str(os.getenv("ADK_MODEL_FINALIZER")),
            fallback_model=_optional_str(os.getenv("ADK_MODEL_FALLBACK")),
            model_retry_attempts=_parse_positive_int(
                os.getenv("ADK_MODEL_RETRY_ATTEMPTS"),
                cls.model_retry_attempts,
                "ADK_MODEL_RETRY_ATTEMPTS",
            ),
            model_retry_initial_delay_seconds=_parse_positive_float(
                os.getenv("ADK_MODEL_RETRY_INITIAL_DELAY_SECONDS"),
                cls.model_retry_initial_delay_seconds,
                "ADK_MODEL_RETRY_INITIAL_DELAY_SECONDS",
            ),
            model_retry_max_delay_seconds=_parse_positive_float(
                os.getenv("ADK_MODEL_RETRY_MAX_DELAY_SECONDS"),
                cls.model_retry_max_delay_seconds,
                "ADK_MODEL_RETRY_MAX_DELAY_SECONDS",
            ),
            model_retry_exponential_base=_parse_positive_float(
                os.getenv("ADK_MODEL_RETRY_EXPONENTIAL_BASE"),
                cls.model_retry_exponential_base,
                "ADK_MODEL_RETRY_EXPONENTIAL_BASE",
            ),
            model_retry_jitter_seconds=_parse_positive_float(
                os.getenv("ADK_MODEL_RETRY_JITTER_SECONDS"),
                cls.model_retry_jitter_seconds,
                "ADK_MODEL_RETRY_JITTER_SECONDS",
            ),
            tool_timeout_seconds=_parse_positive_float(
                os.getenv("ADK_TOOL_TIMEOUT_SECONDS"),
                cls.tool_timeout_seconds,
                "ADK_TOOL_TIMEOUT_SECONDS",
            ),
            mcp_servers=_parse_mcp_servers(os.getenv("ADK_MCP_SERVERS")),
            workspace_enabled=_parse_bool(
                os.getenv("ADK_WORKSPACE_ENABLED"),
                cls.workspace_enabled,
                "ADK_WORKSPACE_ENABLED",
            ),
            workspace_mode=_parse_workspace_mode(os.getenv("ADK_WORKSPACE_MODE")),
            workspace_root=(
                os.getenv("ADK_WORKSPACE_ROOT", cls.workspace_root).strip()
                or cls.workspace_root
            ),
            workspace_max_bytes=_parse_positive_int(
                os.getenv("ADK_WORKSPACE_MAX_BYTES"),
                cls.workspace_max_bytes,
                "ADK_WORKSPACE_MAX_BYTES",
            ),
            task_plan_root=(
                os.getenv("ADK_TASK_PLAN_ROOT", cls.task_plan_root).strip()
                or cls.task_plan_root
            ),
            task_plan_max_bytes=_parse_positive_int(
                os.getenv("ADK_TASK_PLAN_MAX_BYTES"),
                cls.task_plan_max_bytes,
                "ADK_TASK_PLAN_MAX_BYTES",
            ),
            task_run_root=(
                os.getenv("ADK_TASK_RUN_ROOT", cls.task_run_root).strip()
                or cls.task_run_root
            ),
            task_run_max_bytes=_parse_positive_int(
                os.getenv("ADK_TASK_RUN_MAX_BYTES"),
                cls.task_run_max_bytes,
                "ADK_TASK_RUN_MAX_BYTES",
            ),
            progressive_multi_agent_response=ProgressiveMultiAgentResponseSettings.from_env(),
        )
