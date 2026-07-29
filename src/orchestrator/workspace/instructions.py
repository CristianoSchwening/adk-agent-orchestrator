"""Shared schema and instruction for a verbalized operational workspace."""

WORKSPACE_OBJECT_SCHEMA = {
    "type": "object",
    "required": [
        "objective",
        "interpretation",
        "current_step",
        "plan",
        "assumptions",
        "hypotheses",
        "evidence",
        "decisions",
        "uncertainties",
        "blockers",
        "criticisms",
        "next_action",
    ],
    "properties": {
        "objective": {"type": "string"},
        "interpretation": {"type": ["string", "null"]},
        "current_step": {"type": ["string", "null"]},
        "plan": {"type": "array", "items": {"type": "object"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "hypotheses": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "object"}},
        "decisions": {"type": "array", "items": {"type": "object"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "criticisms": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": ["string", "null"]},
    },
}

AGENT_STEP_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["workspace", "result"],
    "additionalProperties": False,
    "properties": {
        "workspace": WORKSPACE_OBJECT_SCHEMA,
        "result": {
            "type": "string",
            "description": "The agent's complete operational result for downstream consumers.",
        },
    },
}

WORKSPACE_INSTRUCTION = """
WORKSPACE OPERACIONAL VERBALIZADO OBRIGATÓRIO:
Retorne somente um objeto JSON aderente ao output_schema, com exatamente dois campos:
workspace e result. Em workspace, exteriorize o estado operacional auditável usando
objective, interpretation, current_step, plan, assumptions, hypotheses, evidence,
decisions, uncertainties, blockers, criticisms e next_action. Use arrays vazios quando
não houver itens. O campo result contém a resposta operacional completa do agente.
Confiança declarada pelo modelo é apenas autorrelato e nunca deve ser apresentada como
probabilidade calibrada. Não alegue expor ativações internas, Jacobianos, J-lens,
J-space mecanístico ou chain-of-thought oculto.
""".strip()


def with_workspace_instruction(instruction: str) -> str:
    return f"{instruction.strip()}\n\n{WORKSPACE_INSTRUCTION}"
