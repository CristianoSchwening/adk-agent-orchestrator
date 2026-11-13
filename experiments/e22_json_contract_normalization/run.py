"""E22 replay: original E21 JSONL vs singleton-list normalization, no API.

Displays all attempts but chooses one candidate outcome per case/arm.
Historical rows stay byte-for-byte unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.e14b_native_provenance.run import CLASSIFY, MODEL, SYSTEM
from experiments.e15_native_pdf_gate.policy import VERSION as OLD_VERSION
from experiments.e15_native_pdf_gate.policy import decide
from experiments.e18_recipient_aware.run import (
    ARMS,
    NEW_PROMPT,
    NEW_VERSION,
    new_decision,
    valid,
)
from experiments.e21_tcu_indirect.generate import ORDER, SPECS

from .policy import normalize

HISTORY = Path("data/executions/e21/paired.jsonl")
REPORT = Path("data/executions/e22/normalization_report.json")


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load(path: Path, model: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"E21 source history is missing: {path}")
    attempts = {(cid, arm): [] for cid in ORDER for arm in ARMS}
    hashes = {}
    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        cid, arm = row.get("case_id"), row.get("arm")
        if row.get("experiment") != "E21" or (cid, arm) not in attempts:
            raise ValueError(f"Line {number}: unexpected E21 case/arm")
        expected = {
            "model": model,
            "system_sha256": _sha(SYSTEM),
            "prompt_sha256": _sha(
                CLASSIFY if arm == "control" else NEW_PROMPT
            ),
            "policy_version": (
                OLD_VERSION if arm == "control" else NEW_VERSION
            ),
        }
        if any(row.get(k) != v for k, v in expected.items()):
            raise ValueError(f"Line {number}: prompt/model/policy mismatch")
        pdf = row.get("pdf_sha256")
        if (not isinstance(pdf, str) or len(pdf) != 64
                or any(ch not in "0123456789abcdef" for ch in pdf)):
            raise ValueError(f"Line {number}: invalid PDF fingerprint")
        if cid in hashes and hashes[cid] != pdf:
            raise ValueError(f"Line {number}: changed PDF bytes")
        hashes[cid] = pdf
        attempts[(cid, arm)].append(row)
    return attempts


def _gate(row: dict, arm: str, parsed: dict) -> dict:
    if arm == "control":
        return decide(parsed, status="ok", contract_valid=True)
    return new_decision(parsed, status="ok", contract_valid=True)


def summarize(attempts: dict, model: str) -> dict:
    rows = []
    for cid in ORDER:
        for arm in ARMS:
            history = attempts.get((cid, arm), [])
            checks = [normalize(r, arm) for r in history]
            accepted = [
                (i, record, diag)
                for i, (record, diag) in enumerate(zip(history, checks), 1)
                if diag["status"] in {"original_valid", "recovered"}
            ]
            originals = [
                (i, record, diag) for i, record, diag in accepted
                if diag["status"] == "original_valid"
            ]
            # Preserve the E21 reference when already valid. Otherwise
            # use earliest recoverable singleton, not the "best" retry.
            selected = originals[-1] if originals else (
                accepted[0] if accepted else None
            )
            chosen_gate = (
                _gate(selected[1], arm, selected[2]["parsed"])
                if selected else None
            )
            allowed = chosen_gate["allowed"] if chosen_gate else None
            truth = SPECS[cid]["truth"]
            recoverable = [
                (i, diag["semantic_gate"]["allowed"])
                for i, diag in enumerate(checks, 1)
                if diag["status"] == "recovered"
            ]
            rows.append({
                "case_id": cid,
                "arm": arm,
                "synthetic_truth": truth,
                "attempt_count": len(history),
                "original_valid_attempts": sum(valid(r) for r in history),
                "recovered_attempts": len(recoverable),
                "recovery_decision_variants": sorted({
                    decision for _, decision in recoverable
                }),
                "recovered_all_same_authorization": (
                    len({decision for _, decision in recoverable}) == 1
                    if recoverable else None
                ),
                "status_by_attempt": [
                    {
                        "attempt": index,
                        "model_status": record.get("status"),
                        "original_contract_valid": valid(record),
                        "adapter_status": diag["status"],
                        "adapter_reason": diag["reason"],
                        "recovered_gate_allowed": (
                            diag["semantic_gate"]["allowed"]
                            if diag["semantic_gate"] else None
                        ),
                    }
                    for index, (record, diag) in enumerate(
                        zip(history, checks), 1
                    )
                ],
                "selected_attempt": selected[0] if selected else None,
                "selected_source": (
                    selected[2]["status"] if selected else "no_valid_response"
                ),
                "candidate_authorized": allowed,
                "candidate_gate": chosen_gate,
                "false_negative_permission": (
                    allowed is True and truth == "active"
                    if allowed is not None else None
                ),
                "false_positive_block": (
                    allowed is False and truth == "none"
                    if allowed is not None else None
                ),
            })
    by_arm = {}
    for arm in ARMS:
        subset = [r for r in rows if r["arm"] == arm]
        complete = [
            r for r in subset if r["candidate_authorized"] is not None
        ]
        by_arm[arm] = {
            "cases": len(subset),
            "candidate_valid_cases": len(complete),
            "cases_recovered_by_normalization": sum(
                r["selected_source"] == "recovered" for r in subset
            ),
            "original_valid_cases": sum(
                r["original_valid_attempts"] > 0 for r in subset
            ),
            "recovered_attempts": sum(
                r["recovered_attempts"] for r in subset
            ),
            "false_negative_permissions": sum(
                r["false_negative_permission"] is True for r in complete
            ),
            "false_positive_blocks": sum(
                r["false_positive_block"] is True for r in complete
            ),
            "active_cases_contained": sum(
                r["synthetic_truth"] == "active"
                and r["candidate_authorized"] is False for r in complete
            ),
            "legitimate_cases_allowed": sum(
                r["synthetic_truth"] == "none"
                and r["candidate_authorized"] is True for r in complete
            ),
        }
    attempts_total = sum(len(v) for v in attempts.values())
    format_counts = Counter(
        diag["status"]
        for (cid, arm), history in attempts.items()
        for diag in (normalize(record, arm) for record in history)
    )
    return {
        "experiment": "E22",
        "model": model,
        "mode": "offline_conservative_singleton_list_normalization",
        "attempts_total": attempts_total,
        "attempt_adapter_statuses": dict(sorted(format_counts.items())),
        "candidate_complete": all(
            row["candidate_authorized"] is not None for row in rows
        ),
        "metrics_by_arm": by_arm,
        "rows": rows,
        "reference_integrity": {
            "input_source": "original_E21_JSONL",
            "original_attempts_modified": False,
            "pdfs_generated_or_rewritten": False,
            "model_or_agent_calls": 0,
        },
        "limitations": [
            "Normalization improves structural interoperability only.",
            "Recovered lists were not valid under the historical E18 contract.",
            "No claim of improved semantic classifier performance.",
            "A valid inner object can still be semantically contradictory.",
            "Twenty repeated malformed answers are not twenty independent PDFs.",
            "E21 synthetic labels, including source_omission_control, "
            "remain unadjudicated.",
            "Adapter is offline only; no change to production gate.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E22 offline JSON contract replay")
    parser.add_argument("--history", type=Path, default=HISTORY)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args()
    if args.history.resolve() == args.report.resolve():
        parser.error("Output must not overwrite source history")
    try:
        attempts = load(args.history, args.model)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = summarize(attempts, args.model)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("E22 offline attempts:", result["attempts_total"])
    print("E22 valid cases:", {
        arm: stats["candidate_valid_cases"]
        for arm, stats in result["metrics_by_arm"].items()
    })
    print("Report:", args.report)
    return 0 if result["candidate_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
