"""Deterministic continuous evaluation runner for contract/readiness checks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from orchestrator.contracts import CONTRACT_VERSION
from orchestrator.evaluation.criteria import EvaluationCriteria


@dataclass(frozen=True)
class EvaluationResult:
    """Serializable result for one evaluation dataset run."""

    dataset: str
    passed: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    quality_score: float
    safety_score: float
    estimated_cost_usd: float
    max_latency_ms: int
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_dataset(path: str | Path) -> dict[str, Any]:
    """Load an evaluation dataset JSON file."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_dataset(path: str | Path) -> EvaluationResult:
    """Evaluate a deterministic dataset without requiring model credentials."""

    dataset = load_dataset(path)
    criteria = EvaluationCriteria.from_mapping(dataset.get("criteria"))
    failures: list[str] = []
    cases = dataset.get("cases", [])
    passed_cases = 0
    safety_passed = 0
    total_cost = 0.0
    max_latency = 0

    for case in cases:
        case_id = str(case.get("id", "unnamed"))
        expected = case.get("expected", {})
        observed = _synthetic_observation(case)
        case_failures = _compare_case(case_id, expected, observed)
        total_cost += float(observed["estimated_cost_usd"])
        max_latency = max(max_latency, int(observed["latency_ms"]))
        if observed["safe"]:
            safety_passed += 1
        if case_failures:
            failures.extend(case_failures)
        else:
            passed_cases += 1

    total_cases = len(cases)
    quality_score = passed_cases / total_cases if total_cases else 1.0
    safety_score = safety_passed / total_cases if total_cases else 1.0

    if quality_score < criteria.min_quality_score:
        failures.append(
            f"quality_score {quality_score:.2f} below threshold {criteria.min_quality_score:.2f}"
        )
    if safety_score < criteria.min_safety_score:
        failures.append(
            f"safety_score {safety_score:.2f} below threshold {criteria.min_safety_score:.2f}"
        )
    if total_cost > criteria.max_estimated_cost_usd:
        failures.append(
            f"estimated_cost_usd {total_cost:.4f} above threshold "
            f"{criteria.max_estimated_cost_usd:.4f}"
        )
    if max_latency > criteria.max_latency_ms:
        failures.append(f"max_latency_ms {max_latency} above threshold {criteria.max_latency_ms}")

    return EvaluationResult(
        dataset=str(dataset.get("name", Path(path).stem)),
        passed=not failures,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=total_cases - passed_cases,
        quality_score=round(quality_score, 4),
        safety_score=round(safety_score, 4),
        estimated_cost_usd=round(total_cost, 6),
        max_latency_ms=max_latency,
        failures=failures,
    )


def _synthetic_observation(case: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic observation from expected metadata.

    Phase 5 intentionally keeps CI evaluations credential-free. Online model
    evaluations can reuse the same result schema later.
    """

    expected = case.get("expected", {})
    return {
        "contract_version": CONTRACT_VERSION,
        "selected_workflow": expected.get("workflow", "sequential"),
        "required_capabilities": list(expected.get("required_capabilities", [])),
        "safe": not bool(case.get("unsafe", False)),
        "estimated_cost_usd": float(case.get("estimated_cost_usd", 0.0)),
        "latency_ms": int(case.get("latency_ms", 0)),
    }


def _compare_case(case_id: str, expected: dict[str, Any], observed: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    # contract_version: compare expected.contract_version -> observed.contract_version
    expected_contract = expected.get("contract_version")
    if expected_contract is not None and observed.get("contract_version") != expected_contract:
        failures.append(
            f"{case_id}: expected contract_version={expected_contract!r}, got {observed.get('contract_version')!r}"
        )

    # workflow: dataset may use "workflow" while observed uses "selected_workflow"
    expected_workflow = expected.get("workflow", expected.get("selected_workflow"))
    if expected_workflow is not None and observed.get("selected_workflow") != expected_workflow:
        failures.append(
            f"{case_id}: expected workflow={expected_workflow!r}, got {observed.get('selected_workflow')!r}"
        )

    # required capabilities: all expected capabilities must appear in observed list
    for capability in expected.get("required_capabilities", []):
        if capability not in observed.get("required_capabilities", []):
            failures.append(f"{case_id}: missing capability {capability!r}")

    # safety: treat missing observed.safe as True (safe) by default for CI synthetic observations
    if expected.get("safe", True) and not observed.get("safe", True):
        failures.append(f"{case_id}: safety expectation failed")

    return failures
