"""E07 — duas decisões independentes para texto jurídico não confiável.

Esta política só produz metadados auditáveis. Não executa bloqueio no ADK
nem remove ou altera evidências. O consumidor deve impor a fronteira de confiança.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from experiments.instructional_nature.b03 import consistency_flags, validate_output

Disposition = Literal["data_only", "contain_operational_directive", "undetermined"]
ContextStatus = Literal[
    "not_provided", "verified_sufficient", "verified_insufficient", "not_assessed"
]
POLICY_VERSION = "E07-dual-axis-v1"
POLICY_SHA256 = hashlib.sha256(POLICY_VERSION.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DualDecision:
    document_id: str
    excerpt: str
    excerpt_sha256: str
    instruction_disposition: Disposition
    human_review_required: bool
    review_reasons: tuple[str, ...]
    instruction_reasons: tuple[str, ...]
    context_status: ContextStatus
    ingestion_anomaly: bool
    classifier_valid: bool
    consistency_flags: tuple[str, ...]
    operational_authority_granted: bool = False

    def as_dict(self) -> dict:
        result = asdict(self)
        result["review_reasons"] = list(self.review_reasons)
        result["instruction_reasons"] = list(self.instruction_reasons)
        result["consistency_flags"] = list(self.consistency_flags)
        result["policy_version"] = POLICY_VERSION
        result["policy_sha256"] = POLICY_SHA256
        result["may_continue_automatic_analysis"] = (
            not self.human_review_required
            and self.instruction_disposition == "data_only"
        )
        return result


def decide_dual(
    *, document_id: str, excerpt: str, classification: dict | None,
    context_status: ContextStatus = "not_provided",
    ingestion_anomaly: bool = False,
) -> DualDecision:
    """A classe do trecho não é sobrescrita pela necessidade de revisão.

    not_provided = metadado ausente no braço de controle (não inferir falha).
    not_assessed = metadado explicitamente não verificado (solicitar revisão).
    """
    allowed = {
        "not_provided", "verified_sufficient", "verified_insufficient", "not_assessed"
    }
    if context_status not in allowed:
        raise ValueError("Estado de contexto não reconhecido")
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("document_id é obrigatório")
    if not isinstance(excerpt, str) or not excerpt.strip():
        raise ValueError("excerpt é obrigatório")
    if type(ingestion_anomaly) is not bool:
        raise ValueError("ingestion_anomaly deve ser booleano")
    valid = False
    if isinstance(classification, dict):
        check = validate_output(
            json.dumps(classification, ensure_ascii=False), excerpt
        )
        valid = check["contract_valid"] is True
    flags = tuple(consistency_flags(classification)) if valid else ()
    instruction_reasons: list[str] = []
    review_reasons: list[str] = []
    if not valid:
        disposition: Disposition = "undetermined"
        instruction_reasons.append("classifier_missing_or_invalid")
        review_reasons.append("classifier_missing_or_invalid")
    elif flags:
        disposition = "undetermined"
        instruction_reasons.append("classifier_inconsistent")
        review_reasons.append("classifier_inconsistent")
    elif classification["enquadramento"] == "ambiguous":
        disposition = "undetermined"
        instruction_reasons.append("classifier_ambiguous")
        review_reasons.append("classifier_ambiguous")
    elif (
        classification["enquadramento"] == "active"
        and classification["contem_instrucao_ia"]
        and classification["tentativa_redirecionamento"]
    ):
        disposition = "contain_operational_directive"
        instruction_reasons.append("active_operational_redirect")
    else:
        disposition = "data_only"
        instruction_reasons.append("no_active_redirect_detected")
    if valid and classification["requer_revisao"]:
        review_reasons.append("classifier_requests_review")
    if context_status == "verified_insufficient":
        review_reasons.append("verified_insufficient_context")
    elif context_status == "not_assessed":
        review_reasons.append("context_not_assessed")
    if ingestion_anomaly:
        review_reasons.append("ingestion_representation_anomaly")
    return DualDecision(
        document_id=document_id,
        excerpt=excerpt,
        excerpt_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        instruction_disposition=disposition,
        human_review_required=bool(review_reasons),
        review_reasons=tuple(review_reasons),
        instruction_reasons=tuple(instruction_reasons),
        context_status=context_status,
        ingestion_anomaly=ingestion_anomaly,
        classifier_valid=valid,
        consistency_flags=flags,
    )


def e06_context_status(context_complete: bool | None) -> ContextStatus:
    """Converte a semântica já registrada no E06, sem inventar sensor."""
    if context_complete is True:
        return "verified_sufficient"
    if context_complete is False:
        return "verified_insufficient"
    if context_complete is None:
        return "not_assessed"
    raise ValueError("context_complete E06 deve ser True/False/None")
