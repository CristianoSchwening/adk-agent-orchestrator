"""E21 offline experiment checks; no network calls."""
import pytest

from experiments.e21_tcu_indirect.generate import ORDER, REFERENCE, generate
from experiments.e21_tcu_indirect.run import fingerprint, load, summarize


def test_paired_corpus_is_synthetic_and_frozen(tmp_path):
    cases = generate(tmp_path)
    assert len(cases) == 8
    assert len(set(c["family"] for c in cases.values())) == 4
    for family in {c["family"] for c in cases.values()}:
        assert sorted(
            c["truth"] for c in cases.values() if c["family"] == family
        ) == ["active", "none"]
    assert all(c["path"].endswith(".pdf") for c in cases.values())
    assert "thematic_inspiration" in REFERENCE["relationship"]
    before = {
        cid: fingerprint(c, cid, "control", "fake")["pdf_sha256"]
        for cid, c in cases.items()
    }
    after = generate(tmp_path)
    assert before == {
        cid: fingerprint(c, cid, "control", "fake")["pdf_sha256"]
        for cid, c in after.items()
    }


def test_no_missing_response_is_counted_as_success(tmp_path):
    cases = generate(tmp_path)
    report = summarize(cases, {}, list(ORDER), "fake")
    assert not report["complete"]
    assert len(report["pending"]) == 16
    assert report["valid_calls"] == 0
    assert report["metrics_by_arm"]["control"]["false_negative_permissions"] == 0


def test_attack_false_negative_detected(tmp_path):
    cases = generate(tmp_path)
    cid = "source_omission_attack"
    history = {
        (cid, "control"): {
            "status": "ok",
            "contract_valid": True,
            "parsed": {
                "detected": False, "framing": "none",
                "evidence": None, "page": None, "notes": "teste",
            },
        },
    }
    summary = summarize(cases, history, [cid], "fake")
    assert summary["metrics_by_arm"]["control"]["false_negative_permissions"] == 1
    assert summary["pending"] == [{
        "case_id": cid, "arm": "recipient_aware"
    }]


def test_history_fingerprint_mismatch(tmp_path):
    cases = generate(tmp_path / "pdf")
    file = tmp_path / "history.jsonl"
    file.write_text(
        '{"experiment":"E21","case_id":"source_omission_attack",'
        '"arm":"control"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fingerprint"):
        load(file, cases, "fake")
