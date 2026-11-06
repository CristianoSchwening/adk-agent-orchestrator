"""E08: invariantes de ingestão, controle e preservação de origem."""
import hashlib
from pathlib import Path

from experiments.e08_pdf_ingestion.diagnostic import inspect
from experiments.e08_pdf_ingestion.run import run


def test_invariants_and_signals(tmp_path):
    report = run(tmp_path)
    assert all(report["invariants"].values())
    diagnostics = report["diagnostics"]
    assert diagnostics["hidden_active"]["ingestion_anomaly"]
    assert diagnostics["image_only"]["ingestion_anomaly"]
    assert not diagnostics["control"]["ingestion_anomaly"]
    assert not diagnostics["visible_quoted"]["ingestion_anomaly"]


def test_anomaly_is_not_treated_as_attack(tmp_path):
    report = run(tmp_path)
    decisions = report["policy_demo"]
    assert decisions["hidden_active"]["human_review_required"]
    assert decisions["hidden_active"]["instruction_disposition"] == "data_only"
    assert decisions["image_only"]["instruction_disposition"] == "undetermined"
    assert decisions["image_only"]["human_review_required"]
    assert not decisions["visible_quoted"]["human_review_required"]
    for result in decisions.values():
        assert not result["operational_authority_granted"]
        assert result["classification_mode"] == "synthetic_fixture_not_gemini"


def test_source_hashes_are_reproducible(tmp_path):
    report = run(tmp_path)
    for diagnostic in report["diagnostics"].values():
        assert len(diagnostic["pdf_sha256"]) == 64
        page = diagnostic["pages"][0]
        assert page["text_sha256"] == hashlib.sha256(
            page["extracted_text"].encode("utf-8")
        ).hexdigest()
        assert inspect(Path(diagnostic["path"]))["pdf_sha256"] == (
            diagnostic["pdf_sha256"]
        )
