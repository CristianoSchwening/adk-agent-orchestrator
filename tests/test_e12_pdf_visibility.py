"""E12: confirmação de falso negativo E11 e controles negativos."""
from experiments.e12_pdf_visibility.diagnostic import inspect, run
from experiments.e12_pdf_visibility.generate import generate


def test_tcu_inspired_visibility_vectors(tmp_path):
    report = run(tmp_path)
    assert all(report["checks"].values())
    assert report["cases"]["render_mode_3"]["signals"] == [
        "non_rendered_text_operation"
    ]
    white = report["cases"]["white_on_white"]
    assert white["signals"] == ["low_contrast_on_known_white_background"]
    assert white["flagged_spans"][0]["render_type"] == 0


def test_benign_hidden_text_is_not_concluded_malicious(tmp_path):
    report = run(tmp_path)
    assert report["cases"]["white_benign"]["human_review_required"]
    assert not report["cases"]["quoted_visible"]["human_review_required"]
    assert not report["cases"]["white_benign"]["automatic_release"]
    assert not report["observations"]["real_attack_identification_validated"]


def test_originals_preserved_and_no_agent_invoked(tmp_path):
    paths = generate(tmp_path)
    for pdf in paths.values():
        result = inspect(pdf)
        assert len(result["pdf_sha256"]) == 64
        assert result["all_facts_preserved"]
        assert not result["safe_to_send_to_legal_agent"]
    assert run(tmp_path)["observations"]["legal_agent_invoked"] is False
