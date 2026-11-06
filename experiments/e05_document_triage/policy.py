"""E05 — política de triagem *offline*; sem bloqueio, sem chamada ao Gemini.

A decisão é um contrato auditável sobre uma classificação já disponível.
O texto original e a evidência permanecem intactos. 'contain' significa
negação de autoridade operacional, NÃO remoção do trecho da evidência.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from experiments.instructional_nature.b03 import consistency_flags, validate_output

Action = Literal["release", "review", "contain"]
POLICY_VERSION = "E05-policy-v1"
POLICY_SHA256 = hashlib.sha256(POLICY_VERSION.encode()).hexdigest()


@dataclass(frozen=True)
class Decision:
    action: Action
    reasons: tuple[str, ...]
    document_id: str
    excerpt_sha256: str
    evidence_excerpt: str
    classifier_valid: bool
    classification: dict | None
    consistency_flags: tuple[str, ...]
    review_required: bool
    operational_authority_granted: bool = False

    def as_dict(self) -> dict:
        return {
            "policy_version": POLICY_VERSION,
            "policy_sha256": POLICY_SHA256,
            "action": self.action,
            "reasons": list(self.reasons),
            "document_id": self.document_id,
            "excerpt_sha256": self.excerpt_sha256,
            "evidence_excerpt": self.evidence_excerpt,
            "classifier_valid": self.classifier_valid,
            "classification": self.classification,
            "consistency_flags": list(self.consistency_flags),
            "review_required": self.review_required,
            "operational_authority_granted": self.operational_authority_granted,
        }


def decide(
    *,
    document_id: str,
    excerpt: str,
    classification: dict | None,
    context_complete: bool | None = None,
    ingestion_anomaly: bool = False,
) -> Decision:
    """Fail-closed para revisão, não para exclusão da evidência.

    context_complete é um dado EXTERNO do processo de ingestão ou revisão,
    não algo inferido magicamente do texto nem rótulo de pesquisa do corpus.
    None = não aferido; False = contexto sabidamente insuficiente.
    """
    if not document_id.strip() or not excerpt.strip():
        raise ValueError("ID documental e trecho original são obrigatórios")
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    flags: list[str] = []
    reasons: list[str] = []
    valid = False
    if isinstance(classification, dict):
        result = validate_output(
            json.dumps(classification, ensure_ascii=False), excerpt
        )
        valid = result["contract_valid"] is True
    if not valid:
        reasons.append("missing_or_invalid_classifier_output")
        action: Action = "review"
    else:
        flags = consistency_flags(classification)
        if context_complete is False:
            reasons.append("insufficient_document_context")
        if ingestion_anomaly:
            reasons.append("ingestion_representation_anomaly")
        if flags:
            reasons.append("classifier_inconsistency")
        if (
            classification["enquadramento"] == "ambiguous"
            or classification["requer_revisao"]
        ):
            reasons.append("model_uncertainty_or_review")
        if reasons:
            action = "review"
        elif (
            classification["enquadramento"] == "active"
            and classification["contem_instrucao_ia"]
            and classification["tentativa_redirecionamento"]
        ):
            reasons.append("active_operational_redirect")
            action = "contain"
        else:
            # Nenhum trecho documental ganha autoridade: apenas dados
            # classificados de forma não contraditória seguem para análise.
            reasons.append("no_active_redirect_detected")
            action = "release"
    # Verificação de contexto/anomalia também se aplica a contrato inválido.
    if context_complete is False and "insufficient_document_context" not in reasons:
        reasons.append("insufficient_document_context")
    if ingestion_anomaly and "ingestion_representation_anomaly" not in reasons:
        reasons.append("ingestion_representation_anomaly")
    return Decision(
        action=action,
        reasons=tuple(reasons),
        document_id=document_id,
        excerpt_sha256=digest,
        evidence_excerpt=excerpt,
        classifier_valid=valid,
        classification=classification if valid else None,
        consistency_flags=tuple(flags),
        review_required=action == "review",
    )


def result_for_downstream(decision: Decision) -> dict:
    """Envelope de integração *proposto*; não executa agente nem altera PDF.

    A aplicação consumidora precisa aplicar a fronteira de confiança.
    Até lá, esta função apenas especifica metadados e não assegura bloqueio.
    """
    return {
        "document_id": decision.document_id,
        "evidence_text": decision.evidence_excerpt,
        "evidence_sha256": decision.excerpt_sha256,
        "operational_authority": "denied",
        "triage_action": decision.action,
        "may_continue_automatic_analysis": decision.action == "release",
        "review_required": decision.review_required,
        "audit": decision.as_dict(),
    }
