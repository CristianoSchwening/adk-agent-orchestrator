"""E22: strict singleton adapter tests; no network or PDF parsing."""
from copy import deepcopy

from experiments.e22_json_contract_normalization.policy import normalize
from experiments.e22_json_contract_normalization.run import summarize


def observation(framing="active", redirects=True):
    return {
        "detected": framing in {"active", "quoted"},
        "recipient": "agent" if framing != "none" else "none",
        "framing": framing,
        "redirects_analyst": redirects,
        "evidence": "TEXTO" if framing != "none" else None,
        "page": 2 if framing != "none" else None,
        "notes": "synthetic",
    }


def test_recover_only_one_e18_object_and_keep_original_unchanged():
    entry = {
        "status": "ok", "contract_valid": False,
        "parsed": [observation()],
    }
    untouched = deepcopy(entry)
    outcome = normalize(entry, "recipient_aware")
    assert outcome["status"] == "recovered"
    assert not outcome["automatic_agent_authorized"]
    assert entry == untouched


def test_refuse_zero_many_and_invalid_elements():
    cases = [
        [], [observation(), observation()],
        [42], [{"framing": "active"}],
    ]
    for value in cases:
        entry = {"status": "ok", "contract_valid": False, "parsed": value}
        result = normalize(entry, "recipient_aware")
        assert result["status"] == "not_normalized"


def test_inner_semantic_conflict_still_blocks():
    entry = {
        "status": "ok", "contract_valid": False,
        "parsed": [observation("quoted", redirects=True)],
    }
    outcome = normalize(entry, "recipient_aware")
    assert outcome["status"] == "recovered"
    assert outcome["semantic_gate"]["reason"] == "uncertain_or_inconsistent"
    assert not outcome["automatic_agent_authorized"]


def test_no_recovery_on_error_or_on_control_arm():
    entry = {"status": "error", "contract_valid": False,
             "parsed": [observation()]}
    assert normalize(entry, "recipient_aware")["status"] == "not_normalized"
    entry["status"] = "ok"
    assert normalize(entry, "control")["status"] == "not_normalized"


def test_replay_earliest_recoverable_case_without_cherry_picking():
    original_list = {"status": "ok", "contract_valid": False,
                     "parsed": [observation()]}
    second_list = {"status": "ok", "contract_valid": False,
                   "parsed": [observation("none", redirects=False)]}
    attempts = {(
        "priority_override_attack", "recipient_aware"
    ): [original_list, second_list]}
    report = summarize(attempts, "fake")
    row = next(r for r in report["rows"]
               if r["case_id"] == "priority_override_attack"
               and r["arm"] == "recipient_aware")
    assert row["selected_attempt"] == 1
    assert row["candidate_authorized"] is False
    assert row["recovered_all_same_authorization"] is False


def test_semantic_unchanged_when_original_record_valid():
    entry = {
        "status": "ok",
        "contract_valid": True,
        "parsed": observation("none", redirects=False),
    }
    result = normalize(entry, "recipient_aware")
    assert result["status"] == "original_valid"
    assert result["automatic_agent_authorized"] is None
