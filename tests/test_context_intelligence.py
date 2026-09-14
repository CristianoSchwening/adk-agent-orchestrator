from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from orchestrator.agents.context_intelligence import (
    context_package_from_draft,
    create_context_package_normalizer,
)
from orchestrator.config import OrchestratorSettings
from orchestrator.context import UserProfile, build_task_context, load_user_profile
from orchestrator.mapping import map_adk_execution
from orchestrator.planning import PlannedTask


def context_draft() -> dict[str, object]:
    return {
        "objective": "Analyze the customer dataset and write findings",
        "workstream": {"name": "Customer analysis", "summary": "Evidence-backed analysis"},
        "entities": [
            {
                "name": "Customer dataset",
                "entity_type": "dataset",
                "description": "Records supplied for analysis",
                "aliases": ["customers"],
                "related_capabilities": ["data_analysis"],
            },
            {
                "name": "Unrelated supplier",
                "entity_type": "organization",
                "description": "A separate procurement counterparty",
                "aliases": [],
                "related_capabilities": ["procurement"],
            },
        ],
        "constraints": ["Use only supplied records"],
        "terminology": {"customer": "A record in the supplied dataset", "factory": "Irrelevant"},
        "tool_categories": ["data"],
    }


def test_context_draft_materializes_workstream_and_entities() -> None:
    package = context_package_from_draft(context_draft())

    assert package.context_id.startswith("CTX-")
    assert package.workstream.workstream_id.startswith("WS-")
    assert [entity.entity_id for entity in package.entities] == ["ENT-001", "ENT-002"]
    assert package.schema_version == "orchestrator.context_package.v2"


def test_repository_profile_is_loaded_and_attached_to_context(tmp_path) -> None:
    profile_path = tmp_path / "config" / "user-profile.json"
    profile_path.parent.mkdir()
    profile_path.write_text(
        json.dumps(
            {
                "user_id": "user-1",
                "display_name": "Alex",
                "locale": "pt-BR",
                "timezone": "America/Sao_Paulo",
                "expertise": ["architecture"],
                "preferences": {"response_style": "concise"},
                "constraints": ["Do not expose personal data"],
            }
        ),
        encoding="utf-8",
    )

    profile = load_user_profile("config/user-profile.json", repository_root=tmp_path)
    package = context_package_from_draft(context_draft(), user_profile=profile)

    assert package.user_profile is not None
    assert package.user_profile.display_name == "Alex"
    assert package.to_dict()["user_profile"]["preferences"]["response_style"] == "concise"


def test_profile_path_cannot_escape_repository(tmp_path) -> None:
    with pytest.raises(ValueError, match="inside the repository"):
        load_user_profile("../user-profile.json", repository_root=tmp_path)


def test_context_normalizer_publishes_package_before_planning() -> None:
    node = create_context_package_normalizer()
    ctx = SimpleNamespace(state={})

    forwarded = json.loads(node._func(ctx=ctx, node_input=context_draft()))

    assert ctx.state["context_package_status"] == "ready"
    assert ctx.state["workstream_id"].startswith("WS-")
    assert ctx.state["context_entity_count"] == 2
    assert forwarded["workstream"]["workstream_id"] == ctx.state["workstream_id"]


def test_task_context_is_minimal_and_tools_are_real_and_contextual() -> None:
    profile = UserProfile(
        user_id="user-1",
        preferences={"response_style": "concise"},
        constraints=["Avoid unexplained jargon"],
    )
    package = context_package_from_draft(context_draft(), user_profile=profile)
    task = PlannedTask(
        task_id="TASK-001",
        title="Analyze customer records",
        description="Inspect the customer dataset",
        task_type="data_analysis",
        required_capabilities=["data_analysis"],
        acceptance_criteria=["Findings cite records"],
    )

    context = build_task_context(
        package,
        task,
        dependency_results={"TASK-000": {"records": 10}},
        allowed_tool_names={"inspect_json_records", "fetch_http_text"},
    )

    assert [entity.name for entity in context.entities] == ["Customer dataset"]
    assert context.contextual_tools == ["inspect_json_records"]
    assert context.terminology == {"customer": "A record in the supplied dataset"}
    assert context.user_profile == profile
    assert context.constraints == ["Use only supplied records", "Avoid unexplained jargon"]
    assert context.schema_version == "orchestrator.task_context.v2"
    assert "context_id" not in context.to_dict()


def test_execution_contract_projects_context_package_and_task_contexts() -> None:
    package = context_package_from_draft(context_draft())
    contract = map_adk_execution(
        session={
            "session_id": "session-context",
            "state": {
                "context_package": package.to_dict(),
                "task_contexts": {"TASK-001": {"task_id": "TASK-001", "contextual_tools": []}},
            },
        },
        events=[],
        objective=package.objective,
        final_response="",
        settings=OrchestratorSettings(),
    )

    assert contract.context_package is not None
    assert contract.context_package["workstream"]["workstream_id"].startswith("WS-")
    assert contract.task_contexts["TASK-001"]["task_id"] == "TASK-001"
