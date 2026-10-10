"""Deterministic human boundaries; model output cannot authorize a continuation."""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orchestrator.planning.models import utc_now_iso


class HumanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected", "needs_changes", "clarification"]
    comment: str = Field(default="", max_length=20_000)
    idempotency_key: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def validate_comment(self):
        self.comment = self.comment.strip()
        if self.decision != "approved" and not self.comment:
            raise ValueError("A resposta ou justificativa é obrigatória.")
        return self


def input_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if hasattr(value, "parts"):
        return "".join(getattr(part, "text", "") or "" for part in value.parts)
    return json.dumps(value, ensure_ascii=False)


def candidate_text(value: Any) -> str:
    text = input_text(value)
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        return text
    if isinstance(payload, dict) and set(payload) == {"workspace", "result"}:
        from orchestrator.workspace import extract_operational_result
        return extract_operational_result(text)
    return text


def create_human_gate():
    from google.adk.events import Event, EventActions
    from google.adk.events.request_input import RequestInput
    from google.adk.workflow import FunctionNode

    def gate(ctx, node_input):
        records = [dict(item) for item in ctx.state.get("human_requests", [])]
        pending = next((item for item in records if item["status"] == "pending"
                        and item["node_path"] == ctx.node_path), None)
        if pending and pending["request_id"] in ctx.resume_inputs:
            response = HumanResponse.model_validate(ctx.resume_inputs[pending["request_id"]])
            if (pending["kind"] == "clarification") != (response.decision == "clarification"):
                raise ValueError("Response does not match request kind")
            pending.update(status="answered", answered_at=utc_now_iso(), response={
                **response.model_dump(), "source": "human", "user_id": ctx.user_id,
            })
            ctx.state["human_requests"] = records
            ctx.state["human_approval_decision"] = pending["response"]
            needs_approval = ctx.state.get("active_task", {}).get("requires_approval", False)
            ctx.route = ("revise" if response.decision == "needs_changes"
                         or (response.decision == "clarification" and needs_approval)
                         else "clarified" if response.decision == "clarification"
                         else "approved" if response.decision == "approved" else "rejected")
            yield Event(output={
                "task_input": ctx.state.get("human_original_input"),
                "candidate": pending["candidate"], "human_response": pending["response"],
                "instruction": "Respeite a decisão humana e a tarefa original.",
            }, actions=EventActions(route=ctx.route, state_delta=dict(ctx.actions.state_delta)))
            return
        if pending is None:
            active = ctx.state.get("active_task", {})
            metadata = active.get("metadata", {})
            kind = metadata.get("human_input_kind", "approval")
            if active.get("requires_approval") and any(
                item["kind"] == "clarification" and item["status"] == "answered"
                and item.get("run_id") == ctx.state.get("task_run_id")
                and item.get("task_id") == active.get("task_id") for item in records
            ):
                kind = "approval"
            if kind not in {"approval", "clarification"}:
                raise ValueError("Unsupported human input kind")
            question_key = ("approval_question" if kind == "approval"
                            and metadata.get("human_input_kind") == "clarification"
                            else "human_question")
            question = metadata.get(question_key)
            if not isinstance(question, str) or not question.strip():
                question = ("Você aprova esta proposta?" if kind == "approval"
                            else "Forneça a informação necessária para continuar.")
            candidate = candidate_text(node_input)
            if kind == "approval" and (not candidate.strip() or candidate == "null"):
                raise ValueError("approval_candidate_missing: no proposal to approve")
            pending = {
                "request_id": str(uuid4()), "status": "pending", "kind": kind,
                "node_path": ctx.node_path, "invocation_id": ctx.invocation_id,
                "session_id": ctx.session.id, "user_id": ctx.user_id,
                "run_id": ctx.state.get("task_run_id"),
                "plan_id": ctx.state.get("task_plan", {}).get("plan_id"),
                "revision": ctx.state.get("task_plan", {}).get("revision"),
                "task_id": active.get("task_id"), "attempt": ctx.state.get("active_attempt"),
                "message": question.strip(),
                "candidate": candidate,
                "options": (["approved", "needs_changes", "rejected"] if kind == "approval"
                            else ["clarification"]),
                "fields": [{"name": "comment", "label": "Sua resposta", "type": "text"}],
                "criteria": active.get("acceptance_criteria", []),
                "created_at": utc_now_iso(), "response": None,
            }
            records.append(pending)
            ctx.state["human_requests"] = records
        # RequestInput itself carries no state delta. Emit the state first so a
        # fresh process can reconstruct the exact pending boundary.
        yield Event(state=dict(ctx.actions.state_delta))
        yield RequestInput(interrupt_id=pending["request_id"], payload=pending,
                           message=pending["message"])

    return FunctionNode(func=gate, name="human_approval_agent", rerun_on_resume=True)
