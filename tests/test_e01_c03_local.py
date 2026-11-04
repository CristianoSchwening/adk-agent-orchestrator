"""C03: verificacoes offline de preparacao de PDFs locais."""
from pathlib import Path

from experiments.e01_prompt_injection import c03_local


def test_prepare_cases_uses_actual_extraction(monkeypatch):
    def fake_load(path: Path):
        if path.name == "controle.pdf":
            return "JAN-2026 R$ 2.000,00", "sha-controle", [b"pixels"]
        return "JAN-2026 R$ 2.000,00; MARCADOR", "sha-ataque", [b"pixels"]

    monkeypatch.setattr(c03_local, "load_pdf", fake_load)
    cases, report = c03_local.prepare_cases(
        Path("controle.pdf"), Path("adversarial.pdf")
    )
    assert [case["id"] for case in cases] == ["C03_CTRL", "C03"]
    assert report["visible_render_identical"]
    assert not report["extracted_text_identical"]
    assert cases[0]["documents"][0]["source_id"] == "P-003"
    assert "MARCADOR" in cases[1]["documents"][0]["text"]
