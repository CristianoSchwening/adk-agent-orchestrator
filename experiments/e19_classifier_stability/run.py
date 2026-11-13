"""E19: replicate E18 classifiers unchanged to measure decision stability.

Each repetition is a NEW independent Gemini request. No reuse of E18
responses or changes to prompts, contracts, policies, or corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from experiments.e14b_native_provenance.run import MODEL
from experiments.e15_native_pdf_gate.policy import decide
from experiments.e15_native_pdf_gate.run import classify_native
from experiments.e18_recipient_aware.generate import ORDER, generate
from experiments.e18_recipient_aware.run import (
    ARMS, NEW_PROMPT, NEW_VERSION,
    classify_new, new_decision, valid,
)
from experiments.e14b_native_provenance.run import CLASSIFY, SYSTEM
from experiments.e15_native_pdf_gate.policy import VERSION as OLD_VERSION

ROOT = Path("data/experiments/e19")
HISTORY = Path("data/executions/e19/replications.jsonl")
REPORT = Path("data/executions/e19/stability_report.json")
DEFAULT = (
    "registry_instruction", "accountant_workflow",
    "quoted_warning", "raster_citation", "agent_role_switch",
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fingerprint(case: dict, cid: str, arm: str,
                repetition: int, model: str) -> dict:
    if arm not in ARMS or repetition < 1:
        raise ValueError("Braço/repetição inválidos")
    prompt = CLASSIFY if arm == "control" else NEW_PROMPT
    return {
        "experiment": "E19", "case_id": cid, "arm": arm,
        "repetition": repetition, "model": model,
        "pdf_sha256": sha(Path(case["path"]).read_bytes()),
        "system_sha256": sha(SYSTEM.encode("utf-8")),
        "prompt_sha256": sha(prompt.encode("utf-8")),
        "policy_version": OLD_VERSION if arm == "control" else NEW_VERSION,
    }


def load(path: Path, cases: dict, model: str) -> dict:
    latest = {}
    if not path.is_file():
        return latest
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        cid, arm, rep = row.get("case_id"), row.get("arm"), row.get("repetition")
        if (cid not in cases or arm not in ARMS
                or type(rep) is not int or rep < 1):
            raise ValueError(f"Histórico linha {number}: identidade inválida")
        expected = fingerprint(cases[cid], cid, arm, rep, model)
        if any(row.get(k) != v for k, v in expected.items()):
            raise ValueError(f"Histórico linha {number}: fingerprint incompatível")
        key = cid, arm, rep
        previous = latest.get(key)
        if valid(row) or previous is None or not valid(previous):
            latest[key] = row
    return latest


def tokens(row: dict | None) -> int | None:
    if not row or not isinstance(row.get("usage"), dict):
        return None
    value = row["usage"].get("total_token_count")
    return value if type(value) is int else None


def decision_for(row: dict | None, arm: str) -> dict:
    status = row.get("status", "missing") if row else "missing"
    contract = row.get("contract_valid", False) if row else False
    data = row.get("parsed") if row else None
    return (decide(data, status=status, contract_valid=contract)
            if arm == "control"
            else new_decision(data, status=status, contract_valid=contract))


def report(cases: dict, latest: dict, scope: list[str],
           repetitions: int, model: str) -> dict:
    rows = []
    for cid in scope:
        case = cases[cid]
        for arm in ARMS:
            for rep in range(1, repetitions + 1):
                record = latest.get((cid, arm, rep))
                good = valid(record)
                decision = decision_for(record, arm)
                allowed = decision["allowed"] if good else None
                rows.append({
                    "case_id": cid, "arm": arm, "repetition": rep,
                    "expected_framing": case["truth"],
                    "expected_allowed": case["truth"] != "active",
                    "valid": good,
                    "predicted_framing": (
                        record["parsed"]["framing"] if good else None
                    ),
                    "allowed": allowed,
                    "unnecessary_block": (
                        allowed is False and case["truth"] != "active"
                        if good else None
                    ),
                    "mistaken_release": (
                        allowed is True and case["truth"] == "active"
                        if good else None
                    ),
                    "tokens": tokens(record),
                    "decision": decision if good else None,
                    "record": record,
                })
    groups = []
    for cid in scope:
        for arm in ARMS:
            subset = [r for r in rows if r["case_id"] == cid and r["arm"] == arm]
            good = [r for r in subset if r["valid"]]
            complete = len(good) == repetitions
            labels = [r["predicted_framing"] for r in good]
            approvals = [r["allowed"] for r in good]
            groups.append({
                "case_id": cid, "arm": arm, "valid_repetitions": len(good),
                "expected_repetitions": repetitions,
                "complete": complete,
                "framing_stable": len(set(labels)) == 1 if complete else None,
                "authorization_stable": (
                    len(set(approvals)) == 1 if complete else None
                ),
                "framing_variants": sorted(set(labels)),
                "authorization_variants": sorted(set(approvals)),
            })
    pairs = []
    for cid in scope:
        for rep in range(1, repetitions + 1):
            a = next(r for r in rows if (r["case_id"], r["arm"],
                     r["repetition"]) == (cid, "control", rep))
            b = next(r for r in rows if (r["case_id"], r["arm"],
                     r["repetition"]) == (cid, "recipient_aware", rep))
            pairs.append({
                "case_id": cid, "repetition": rep,
                "both_valid": a["valid"] and b["valid"],
                "control_allowed": a["allowed"],
                "recipient_aware_allowed": b["allowed"],
                "changed_decision": (
                    a["allowed"] != b["allowed"]
                    if a["valid"] and b["valid"] else None
                ),
            })
    by_arm = {}
    for arm in ARMS:
        subset = [r for r in rows if r["arm"] == arm]
        good = [r for r in subset if r["valid"]]
        usage = [r["tokens"] for r in good if r["tokens"] is not None]
        consistent = [g for g in groups if g["arm"] == arm and g["complete"]]
        by_arm[arm] = {
            "requested": len(subset), "valid": len(good),
            "mistaken_releases": sum(r["mistaken_release"] is True for r in good),
            "unnecessary_blocks": sum(r["unnecessary_block"] is True for r in good),
            "framing_correct": sum(
                r["predicted_framing"] == r["expected_framing"] for r in good
            ),
            "stable_authorization_groups": sum(
                g["authorization_stable"] is True for g in consistent
            ),
            "complete_groups": len(consistent),
            "token_total_observed": sum(usage),
            "token_usage_records": len(usage),
        }
    pending = [
        {"case_id": r["case_id"], "arm": r["arm"],
         "repetition": r["repetition"]}
        for r in rows if not r["valid"]
    ]
    return {
        "experiment": "E19", "model": model,
        "mode": "fresh_independent_repetitions_of_E18",
        "repetitions": repetitions,
        "requested_calls": len(rows),
        "valid_calls": len(rows) - len(pending),
        "complete": not pending,
        "pending": pending,
        "metrics_by_arm": by_arm,
        "stability_by_case_arm": groups,
        "paired_comparisons": pairs,
        "rows": rows,
        "real_adk_agent_invocations": 0,
        "limitations": [
            "Small synthetic set, no estimate of production error rates.",
            "Two repeated calls can show flips but cannot establish reliability.",
            "Fresh calls use identical frozen E18 prompts and policies.",
            "Sequential calls are not randomized or independent in every sense.",
            "Each repetition has a separate request, without E18 history reuse.",
            "Model backend may change without model identifier change.",
            "Differences in token use are descriptive; no monetary estimate.",
            "No legal agent invoked and no custom OCR/extractor.",
        ],
    }


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="E19: repetibilidade pareada E18")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--folder", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=HISTORY)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--retry-invalid", action="store_true")
    args = parser.parse_args()
    if not 2 <= args.repetitions <= 5:
        parser.error("--repetitions precisa estar entre 2 e 5")
    if args.output.resolve() == args.report.resolve():
        parser.error("Histórico e relatório devem ser arquivos diferentes")
    scope = (list(dict.fromkeys(args.case_id)) if args.case_id
             else list(ORDER if args.all_cases else DEFAULT))
    if not scope or set(scope) - set(ORDER):
        parser.error("Cenário desconhecido")
    if args.output.exists() and any(
        not (args.folder / f"E18_{cid}.pdf").is_file() for cid in ORDER
    ):
        parser.error("Histórico existe, PDFs faltando: não regenerar")
    cases = generate(args.folder)
    try:
        latest = load(args.output, cases, args.model)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.prepare_only:
        print("E19 casos:", scope, "repetições:", args.repetitions)
        print("Chamadas previstas:", len(scope) * len(ARMS) * args.repetitions)
        return 0
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        parser.error("Configure GEMINI_API_KEY ou GOOGLE_API_KEY")
    from google import genai

    client = genai.Client(
        api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    for rep in range(1, args.repetitions + 1):
        for cid in scope:
            for arm in ARMS:
                old = latest.get((cid, arm, rep))
                if valid(old) or (old and not args.retry_invalid):
                    continue
                row = {
                    **fingerprint(cases[cid], cid, arm, rep, args.model),
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    row.update(
                        classify_native(client, cases[cid], args.model)
                        if arm == "control"
                        else classify_new(client, cases[cid], args.model)
                    )
                except Exception as exc:
                    row.update({
                        "status": "error", "contract_valid": False,
                        "parsed": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                with args.output.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                latest[(cid, arm, rep)] = row
                args.report.write_text(
                    json.dumps(report(cases, latest, scope, args.repetitions,
                                      args.model), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print("E19", rep, cid, arm, row["status"],
                      row.get("contract_valid"))
                if row["status"] == "error":
                    return 1
    summary = report(cases, latest, scope, args.repetitions, args.model)
    args.report.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("E19 concluído:", summary["complete"])
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
