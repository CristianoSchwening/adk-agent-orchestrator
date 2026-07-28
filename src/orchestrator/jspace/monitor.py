"""Runtime enforcement and event capture for agent J-space metadata."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from orchestrator.jspace.models import (
    AgentIdentity,
    JSpaceSnapshot,
    JSpaceValidationError,
    Lifecycle,
    PromptCapture,
    StructuredDeliberation,
)
from orchestrator.jspace.repository import FileJSpaceRepository

JSPACE_BLOCK_PATTERN = re.compile(
    r"<jspace_metadata>\s*(\{.*?\})\s*</jspace_metadata>", re.DOTALL
)


class JSpaceMonitor:
    """Track participating agents and require structured state on model output."""

    def __init__(
        self,
        *,
        session_id: str,
        objective: str,
        repository: FileJSpaceRepository,
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
                StructuredDeliberation(
                    objective=self.objective,
                    interpretation="Agent invocation started.",
                    current_step="Process the assigned objective.",
                    next_action="Produce structured J-space metadata.",
                ),
                model_output=None,
                invocation_id=invocation_id,
            )
            self.started_agents.add(agent_name)

        if event_type in {"tool_call", "tool_response"}:
            self._save(
                agent_name,
                "tool_result",
                StructuredDeliberation(
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
            deliberation = extract_deliberation(model_output, objective=self.objective)
        except JSpaceValidationError as exc:
            self._violate(agent_name, str(exc), model_output, invocation_id)
            return
        self._save(
            agent_name,
            "progress",
            deliberation,
            model_output=model_output,
            invocation_id=invocation_id,
        )

    def complete(self, *, agent_name: str, invocation_id: str | None = None) -> None:
        if agent_name in self.terminal_agents:
            return
        self._save(
            agent_name,
            "completed",
            StructuredDeliberation(
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
            StructuredDeliberation(
                objective=self.objective,
                interpretation="Agent output violated the J-space contract.",
                blockers=[message],
                next_action="Emit a valid <jspace_metadata> JSON block.",
            ),
            model_output=model_output,
            invocation_id=invocation_id,
            valid=False,
        )
        self._save(
            agent_name,
            "failed",
            StructuredDeliberation(
                objective=self.objective,
                interpretation="The runtime stopped the agent because J-space validation failed.",
                blockers=[message],
                next_action="Correct the structured metadata and retry.",
            ),
            model_output=None,
            invocation_id=invocation_id,
            valid=False,
        )
        self.terminal_agents.add(agent_name)
        if self.mode == "strict":
            raise JSpaceValidationError(violation)

    def _save(
        self,
        agent_name: str,
        phase: str,
        deliberation: StructuredDeliberation,
        *,
        model_output: str | None,
        invocation_id: str | None,
        valid: bool = True,
    ) -> None:
        self.sequences[agent_name] += 1
        snapshot = JSpaceSnapshot(
            session_id=self.session_id,
            invocation_id=invocation_id,
            sequence=self.sequences[agent_name],
            agent=AgentIdentity(name=agent_name),
            lifecycle=Lifecycle(
                phase=phase,  # type: ignore[arg-type]
                status="running" if phase in {"started", "progress", "tool_result"} else phase,
            ),
            jspace=deliberation,
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
                    "type": "structured_deliberation",
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


def extract_deliberation(text: str, *, objective: str) -> StructuredDeliberation:
    match = JSPACE_BLOCK_PATTERN.search(text or "")
    if not match:
        raise JSpaceValidationError("model output is missing <jspace_metadata>")
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise JSpaceValidationError("jspace metadata contains invalid JSON") from exc
    return StructuredDeliberation.from_mapping(value, objective=objective)


def strip_jspace_metadata(text: str) -> str:
    """Remove the monitoring envelope from user-visible model text."""

    return JSPACE_BLOCK_PATTERN.sub("", text or "").strip()
