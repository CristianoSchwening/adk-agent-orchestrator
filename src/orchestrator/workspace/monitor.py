"""Runtime enforcement for complete structured verbalized-workspace responses."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from orchestrator.workspace.models import (
    AgentIdentity,
    Lifecycle,
    PromptCapture,
    VerbalizedWorkspace,
    WorkspaceSnapshot,
    WorkspaceValidationError,
)
from orchestrator.workspace.repository import FileWorkspaceRepository


class WorkspaceMonitor:
    """Track agents and require complete structured workspace responses."""

    def __init__(
        self,
        *,
        session_id: str,
        objective: str,
        repository: FileWorkspaceRepository,
        mode: str = "strict",
        agent_instructions: dict[str, str] | None = None,
        agent_tools: dict[str, list[dict[str, Any]]] | None = None,
        session_context: dict[str, Any] | None = None,
    ) -> None:
        self.session_id = session_id
        self.objective = objective
        self.repository = repository
        self.mode = mode
        self.agent_instructions = agent_instructions or {}
        self.agent_tools = agent_tools or {}
        self.session_context = session_context or {}
        self.sequences: dict[str, int] = defaultdict(int)
        self.started_agents: set[str] = set()
        self.terminal_agents: set[str] = set()
        self.paths: list[Path] = []
        self.snapshot_records: list[dict[str, Any]] = []
        self.violations: list[str] = []

    def observe(
        self,
        *,
        agent_name: str,
        model_output: str,
        invocation_id: str | None = None,
        event_type: str = "model",
    ) -> None:
        if agent_name not in self.started_agents:
            self._save(
                agent_name,
                "started",
                VerbalizedWorkspace(
                    objective=self.objective,
                    interpretation="Agent invocation started.",
                    current_step="Process the assigned objective.",
                    next_action="Produce a structured verbalized workspace.",
                ),
                model_output=None,
                invocation_id=invocation_id,
            )
            self.started_agents.add(agent_name)

        if event_type in {"tool_call", "tool_response"}:
            self._save(
                agent_name,
                "tool_result",
                VerbalizedWorkspace(
                    objective=self.objective,
                    interpretation="Tool activity observed for the agent.",
                    current_step=event_type,
                    evidence=[{"type": event_type, "content": model_output}],
                    next_action="Continue the current agent step.",
                ),
                model_output=model_output,
                invocation_id=invocation_id,
            )
            return
        try:
            workspace = extract_workspace(model_output, objective=self.objective)
        except WorkspaceValidationError as exc:
            self._violate(agent_name, str(exc), model_output, invocation_id)
            return
        self._save(
            agent_name,
            "progress",
            workspace,
            model_output=model_output,
            invocation_id=invocation_id,
        )

    def complete(self, *, agent_name: str, invocation_id: str | None = None) -> None:
        if agent_name in self.terminal_agents:
            return
        self._save(
            agent_name,
            "completed",
            VerbalizedWorkspace(
                objective=self.objective,
                interpretation="Agent output accepted by the runtime monitor.",
                current_step="Completed",
                next_action="Return control to the orchestrator.",
            ),
            model_output=None,
            invocation_id=invocation_id,
        )
        self.terminal_agents.add(agent_name)

    def _violate(
        self,
        agent_name: str,
        message: str,
        model_output: str,
        invocation_id: str | None,
    ) -> None:
        violation = f"{agent_name}: {message}"
        self.violations.append(violation)
        self._save(
            agent_name,
            "violation",
            VerbalizedWorkspace(
                objective=self.objective,
                interpretation="Agent output violated the verbalized workspace contract.",
                blockers=[message],
                next_action="Emit one complete JSON object matching the output schema.",
            ),
            model_output=model_output,
            invocation_id=invocation_id,
            valid=False,
        )
        self._save(
            agent_name,
            "failed",
            VerbalizedWorkspace(
                objective=self.objective,
                interpretation="The runtime stopped the agent after workspace validation failed.",
                blockers=[message],
                next_action="Correct the structured metadata and retry.",
            ),
            model_output=None,
            invocation_id=invocation_id,
            valid=False,
        )
        self.terminal_agents.add(agent_name)
        if self.mode == "strict":
            raise WorkspaceValidationError(violation)

    def _save(
        self,
        agent_name: str,
        phase: str,
        workspace: VerbalizedWorkspace,
        *,
        model_output: str | None,
        invocation_id: str | None,
        valid: bool = True,
    ) -> None:
        self.sequences[agent_name] += 1
        snapshot = WorkspaceSnapshot(
            session_id=self.session_id,
            invocation_id=invocation_id,
            sequence=self.sequences[agent_name],
            agent=AgentIdentity(name=agent_name),
            lifecycle=Lifecycle(
                phase=phase,  # type: ignore[arg-type]
                status="running" if phase in {"started", "progress", "tool_result"} else phase,
            ),
            workspace=workspace,
            prompt_capture=PromptCapture(
                agent_instruction=self.agent_instructions.get(agent_name),
                session_context=self.session_context,
                input_messages=[{"role": "user", "content": self.objective}],
                tool_definitions=self.agent_tools.get(agent_name, []),
                model_output=model_output,
            ),
            integrity={
                "redacted": False,
                "validation_status": "valid" if valid else "invalid",
                "reasoning_capture": {
                    "type": "verbalized_operational_workspace",
                    "is_hidden_chain_of_thought": False,
                },
            },
        )
        path = self.repository.save(snapshot)
        self.paths.append(path)
        self.snapshot_records.append(
            {
                "trace_id": snapshot.trace_id,
                "agent_name": agent_name,
                "phase": phase,
                "sequence": snapshot.sequence,
                "path": path,
                "timestamp": snapshot.timestamp,
                "invocation_id": invocation_id,
                "validation_status": snapshot.integrity["validation_status"],
            }
        )


def parse_agent_step(text: str, *, objective: str) -> tuple[VerbalizedWorkspace, str]:
    try:
        value = json.loads(text or "")
    except json.JSONDecodeError as exc:
        raise WorkspaceValidationError("agent response is not complete valid JSON") from exc
    if not isinstance(value, dict) or set(value) != {"workspace", "result"}:
        raise WorkspaceValidationError(
            "agent response must contain exactly workspace and result"
        )
    result = value.get("result")
    if not isinstance(result, str):
        raise WorkspaceValidationError("agent response result must be a string")
    workspace = VerbalizedWorkspace.from_mapping(value.get("workspace"), objective=objective)
    return workspace, result


def extract_workspace(text: str, *, objective: str) -> VerbalizedWorkspace:
    return parse_agent_step(text, objective=objective)[0]


def extract_operational_result(text: str, *, objective: str = "agent objective") -> str:
    """Return the operational result only after the complete response validates."""

    return parse_agent_step(text, objective=objective)[1]
