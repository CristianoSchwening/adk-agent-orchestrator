"""E24 independent reviewer workflow, fully offline."""
import json

import pytest

from experiments.e24_semantic_boundaries.adjudicate import compare, prepare


def test_blind_review_packet_excludes_labels_and_model_outputs(tmp_path):
    destination = tmp_path / "review"
    paths = prepare(tmp_path / "pdfs", destination)
    assert len(paths) == 3
    contents = [p.read_text(encoding="utf-8") for p in paths]
    for content in contents:
        assert "provisional_author_label" not in content
        assert '"truth"' not in content
        assert '"pair"' not in content
        assert '"observation"' not in content
    with pytest.raises(ValueError, match="overwrite"):
        prepare(tmp_path / "pdfs", destination)


def _complete(directory):
    for slot in ("R1", "R2"):
        path = directory / f"review_{slot}.json"
        sheet = json.loads(path.read_text(encoding="utf-8"))
        sheet["reviewer_id"] = f"human-{slot}"
        for case in sheet["cases"]:
            case.update({"label": "none", "recipient": "none",
                         "justification": "No operative instruction to agent",
                         "evidence": None, "page": None})
        path.write_text(json.dumps(sheet), encoding="utf-8")


def test_comparison_requires_two_completed_independent_reviews(tmp_path):
    directory = tmp_path / "review"
    prepare(tmp_path / "pdfs", directory)
    with pytest.raises(ValueError, match="reviewer_id"):
        compare(directory / "manifest.json", directory, directory / "result.json")
    _complete(directory)
    output = compare(directory / "manifest.json", directory,
                     directory / "result.json")
    assert output["cases"] == 12
    assert output["exact_agreements"] == 12
    assert not output["human_adjudication_completed"]
    assert all(row["adjudicated_label"] is None for row in output["rows"])


def test_disagreement_not_silently_resolved(tmp_path):
    directory = tmp_path / "review"
    prepare(tmp_path / "pdfs", directory)
    _complete(directory)
    path = directory / "review_R2.json"
    sheet = json.loads(path.read_text(encoding="utf-8"))
    sheet["cases"][0].update({
        "label": "active", "recipient": "agent",
        "evidence": "example", "page": 1, "justification": "Disagreement",
    })
    path.write_text(json.dumps(sheet), encoding="utf-8")
    result = compare(directory / "manifest.json", directory,
                     directory / "result.json")
    assert result["disagreements"] == 1
    assert result["adjudication_pending"] == 1
    assert result["rows"][0]["adjudicated_label"] is None
