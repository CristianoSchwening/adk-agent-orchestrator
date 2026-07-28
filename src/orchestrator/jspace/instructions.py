"""Shared instruction that makes J-space state exteriorization explicit."""

JSPACE_INSTRUCTION = """
MONITORAMENTO J-SPACE OBRIGATÓRIO:
Em toda resposta produzida por este agente, inclua ao final exatamente um bloco
<jspace_metadata> contendo um objeto JSON válido. O objeto deve resumir o estado
operacional exteriorizado e conter: objective, interpretation, current_step, plan,
assumptions, hypotheses, evidence, decisions, uncertainties, blockers, criticisms
e next_action. Use arrays vazios quando não houver itens. Em decisions, registre a
decisão, justificativa explícita, alternativas consideradas, evidências e confiança.
Não inclua chain-of-thought oculto; forneça deliberação estruturada e auditável.
</jspace_metadata>
""".strip()


def with_jspace_instruction(instruction: str) -> str:
    return f"{instruction.strip()}\n\n{JSPACE_INSTRUCTION}"
