"""ADK-native context extraction before task planning."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from orchestrator.adk_compat import load_agent_class, load_workflow_classes
from orchestrator.config import OrchestratorSettings
from orchestrator.context import ContextEntity, ContextPackage, Workstream
from orchestrator.model import create_gemini_model

CONTEXT_PACKAGE_DRAFT_SCHEMA = {
    "type": "object",
    "required": [
        "objective",
        "workstream",
        "entities",
        "constraints",
        "terminology",
        "tool_categories",
    ],
    "additionalProperties": False,
    "properties": {
        "objective": {"type": "string"},
        "workstream": {
            "type": "object",
            "required": ["name", "summary"],
            "additionalProperties": False,
            "properties": {"name": {"type": "string"}, "summary": {"type": "string"}},
        },
        "entities": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "entity_type",
                    "description",
                    "aliases",
                    "related_capabilities",
                ],
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "entity_type": {"type": "string"},
                    "description": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "related_capabilities": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "constraints": {"type": "array", "items": {"type": "string"}},
        "terminology": {"type": "object", "additionalProperties": {"type": "string"}},
        "tool_categories": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["filesystem", "http", "documents", "data", "model", "mcp", "core"],
            },
        },
    },
}

CONTEXT_INTELLIGENCE_INSTRUCTION = """
Você é o Context Intelligence Agent generalista. Antes do planejamento, transforme o objetivo
do usuário em um pacote de contexto mínimo, factual e independente de domínio.

Regras:
- Preserve o objetivo original e extraia apenas restrições expressas ou diretamente implicadas.
- Defina um workstream coeso que agrupe esta execução sem inventar uma área industrial.
- Identifique somente entidades relevantes: pessoas, organizações, sistemas, documentos,
  datasets, produtos, lugares, conceitos ou outros objetos citados no objetivo.
- Declare capacidades relacionadas às entidades, nunca nomes de agentes.
- Registre terminologia apenas quando um termo precisar de significado específico neste objetivo.
- Sugira categorias de tools, não tools inexistentes nem chamadas concretas.
- Não planeje tarefas, não escolha agentes e não execute o objetivo.
- Retorne somente o objeto exigido pelo output_schema.
""".strip()


def create_context_intelligence_agent(settings: OrchestratorSettings) -> Any:
    LlmAgent = load_agent_class()
    return LlmAgent(
        model=create_gemini_model(settings, role="reasoning"),
        name="context_intelligence_agent",
        description="Builds a domain-neutral ContextPackage before task planning.",
        instruction=CONTEXT_INTELLIGENCE_INSTRUCTION,
        output_schema=CONTEXT_PACKAGE_DRAFT_SCHEMA,
        output_key="context_package_draft",
    )


def context_package_from_draft(value: Any) -> ContextPackage:
    payload = _structured_payload(value)
    workstream = payload.get("workstream") or {}
    workstream_id = f"WS-{uuid4()}"
    return ContextPackage(
        context_id=f"CTX-{uuid4()}",
        objective=str(payload.get("objective") or "").strip(),
        workstream=Workstream(
            workstream_id=workstream_id,
            name=str(workstream.get("name") or "").strip(),
            summary=str(workstream.get("summary") or "").strip(),
        ),
        entities=[
            ContextEntity(
                entity_id=f"ENT-{index:03d}",
                name=str(item.get("name") or "").strip(),
                entity_type=str(item.get("entity_type") or "concept").strip(),
                description=str(item.get("description") or "").strip(),
                aliases=[str(alias) for alias in item.get("aliases") or []],
                related_capabilities=[
                    str(capability) for capability in item.get("related_capabilities") or []
                ],
            )
            for index, item in enumerate(payload.get("entities") or [], start=1)
            if isinstance(item, dict)
        ],
        constraints=[str(item) for item in payload.get("constraints") or []],
        terminology={
            str(key): str(item) for key, item in (payload.get("terminology") or {}).items()
        },
        tool_categories=[str(item) for item in payload.get("tool_categories") or []],
    )


def create_context_package_normalizer() -> Any:
    _, FunctionNode, _, _, _ = load_workflow_classes()

    def normalize(ctx: Any, node_input: Any) -> str:
        package = context_package_from_draft(node_input)
        if not package.objective or not package.workstream.name:
            raise ValueError("context package requires objective and workstream name")
        ctx.state["context_package"] = package.to_dict()
        ctx.state["context_package_status"] = "ready"
        ctx.state["workstream_id"] = package.workstream.workstream_id
        ctx.state["context_entity_count"] = len(package.entities)
        return json.dumps(package.to_dict(), ensure_ascii=False)

    return FunctionNode(func=normalize, name="normalize_context_package")


def _structured_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        payload = value
    elif hasattr(value, "model_dump"):
        payload = value.model_dump()
    else:
        parts = getattr(value, "parts", None) or []
        text = "".join(str(getattr(part, "text", "") or "") for part in parts)
        try:
            payload = json.loads((text or str(value)).strip())
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("context intelligence returned invalid structured output") from exc
    if not isinstance(payload, dict):
        raise ValueError("context intelligence output must be a JSON object")
    return payload
