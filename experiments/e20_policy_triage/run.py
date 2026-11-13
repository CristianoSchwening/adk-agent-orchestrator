"""E20: no-API replay of E18/E19 classifier outputs with triage semantics.

Reads existing histories without creating PDFs, modifying prompts or calling AI.
Keeps E18 and E19 observations separate; repeats are not independent cases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.e14b_native_provenance.run import CLASSIFY, MODEL, SYSTEM
from experiments.e15_native_pdf_gate.policy import VERSION as E15_VERSION
from experiments.e18_recipient_aware.generate import SPECS
from experiments.e18_recipient_aware.run import (
    ARMS, NEW_PROMPT, NEW_VERSION, new_decision, valid,
)
from experiments.e15_native_pdf_gate.policy import decide as decide_e15
from .policy import triage

E18_HISTORY = Path("data/executions/e18/paired.jsonl")
E19_HISTORY = Path("data/executions/e19/replications.jsonl")
OUTPUT = Path("data/executions/e20/triage_report.json")


def sha_text(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expected_identity(arm: str, model: str) -> dict:
    return {
        "model": model,
        "system_sha256": sha_text(SYSTEM),
        "prompt_sha256": sha_text(CLASSIFY if arm == "control" else NEW_PROMPT),
        "policy_version": E15_VERSION if arm == "control" else NEW_VERSION,
    }


def read_records(path: Path, experiment: str, model: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Historical source missing: {path}")
    latest = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        cid, arm = row.get("case_id"), row.get("arm")
        rep = row.get("repetition", 0)
        if (row.get("experiment") != experiment
                or cid not in SPECS or arm not in ARMS
                or (experiment == "E19" and (type(rep) is not int or rep < 1))):
            raise ValueError(f"{path}:{number}: invalid experiment/case/arm/repetition")
        expected = _expected_identity(arm, model)
        if any(row.get(field) != value for field, value in expected.items()):
            raise ValueError(f"{path}:{number}: model/prompt/policy fingerprint mismatch")
        if not isinstance(row.get("pdf_sha256"), str) or len(row["pdf_sha256"]) != 64:
            raise ValueError(f"{path}:{number}: missing PDF fingerprint")
        key = (cid, arm, rep if experiment == "E19" else 0)
        prev = latest.get(key)
        if prev is not None and prev["pdf_sha256"] != row["pdf_sha256"]:
            raise ValueError(f"{path}:{number}: conflicting PDF hashes")
        if valid(row) or prev is None or not valid(prev):
            latest[key] = row
    return latest


def original_allowed(record: dict, arm: str) -> bool:
    decision = (
        decide_e15(record["parsed"], status="ok", contract_valid=True)
        if arm == "control" else new_decision(record["parsed"])
    )
    return decision["allowed"]


def analyze(histories: dict[str, dict], *, model: str) -> dict:
    rows = []
    hashes = {}
    for origin, history in histories.items():
        for (cid, arm, rep), record in sorted(history.items()):
            previous = hashes.get(cid)
            if previous is not None and previous != record["pdf_sha256"]:
                raise ValueError(f"PDF hash mismatch across experiments: {cid}")
            hashes[cid] = record["pdf_sha256"]
            good = valid(record)
            decision = triage(record, arm)
            allowed = decision["automatic_agent_authorized"]
            truth = SPECS[cid][0]
            rows.append({
                "source_experiment": origin, "case_id": cid,
                "arm": arm, "repetition": rep if rep else None,
                "synthetic_truth": truth,
                "valid_source_response": good,
                "old_binary_allowed": original_allowed(record, arm) if good else None,
                "triage": decision,
                "automatic_allow": allowed if good else None,
                "unsafe_automatic_release": allowed and truth == "active" if good else None,
                "false_containment_of_legitimate": (
                    decision["disposition"] == "contain" and truth != "active"
                    if good else None
                ),
                "legitimate_sent_to_review": (
                    decision["disposition"] == "review" and truth != "active"
                    if good else None
                ),
            })
    metrics = {}
    for origin in histories:
        metrics[origin] = {}
        for arm in ARMS:
            subset = [r for r in rows
                      if r["source_experiment"] == origin and r["arm"] == arm]
            usable = [r for r in subset if r["valid_source_response"]]
            metrics[origin][arm] = {
                "records": len(subset), "valid_records": len(usable),
                "automatic_allow": sum(r["automatic_allow"] is True for r in usable),
                "contain": sum(r["triage"]["disposition"] == "contain" for r in usable),
                "review": sum(r["triage"]["disposition"] == "review" for r in usable),
                "technical_hold": sum(
                    r["triage"]["disposition"] == "technical_hold" for r in subset
                ),
                "unsafe_automatic_release": sum(
                    r["unsafe_automatic_release"] is True for r in usable
                ),
                "false_containment_of_legitimate": sum(
                    r["false_containment_of_legitimate"] is True for r in usable
                ),
                "legitimate_sent_to_review": sum(
                    r["legitimate_sent_to_review"] is True for r in usable
                ),
                "authorization_changed_vs_original": sum(
                    r["automatic_allow"] != r["old_binary_allowed"] for r in usable
                ),
            }
    return {
        "experiment": "E20", "model": model,
        "mode": "offline_policy_replay_no_model_or_agent_calls",
        "sources": sorted(histories),
        "complete_for_available_history": bool(rows),
        "metrics_by_source_and_arm": metrics,
        "rows": rows,
        "methodology": {
            "allow": "only previously allowed document is authorized",
            "contain": "active redirection classified consistently",
            "review": "contradictory or uncertain classification; no authorization",
            "technical_hold": "invalid or absent response; retry infrastructure not human security review",
        },
        "limitations": [
            "No model calls: replay only; outcomes are not new AI observations.",
            "The review category does not unlock automatic processing.",
            "Triage improves operational diagnosis but does not remove false blocks.",
            "Unreviewed synthetic labels are not human judicial adjudications.",
            "E19 repeated records are correlated; do not infer population rates.",
            "A self-consistent false negative still passes the gate.",
            "No human-review workflow implemented; no ADK or OCR.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E20: replay deterministico")
    parser.add_argument("--e18", type=Path, default=E18_HISTORY)
    parser.add_argument("--e19", type=Path, default=E19_HISTORY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--e18-only", action="store_true")
    args = parser.parse_args()
    sources = {"E18": args.e18}
    if not args.e18_only:
        sources["E19"] = args.e19
    if args.output.resolve() in {p.resolve() for p in sources.values()}:
        parser.error("Do not overwrite historical input")
    try:
        histories = {
            experiment: read_records(path, experiment, args.model)
            for experiment, path in sources.items()
        }
        if not any(histories.values()):
            parser.error("No historical records available")
        result = analyze(histories, model=args.model)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("E20: offline replay complete; source rows:", len(result["rows"]))
    print("Report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
