"""A09 — Testes offline não dependem de instalação local do Tesseract."""
import fitz

from experiments.pdf_representation.a09_legitimate_layouts import (
    _make_page,
    create_fixture,
)


def test_four_fixture_layouts(tmp_path):
    for case_id in ("A09_SINGLE", "A09_COLUMNS", "A09_TABLE", "A09_LOWRES"):
        path = create_fixture(case_id, tmp_path)
        assert path.is_file()
        with fitz.open(path) as doc:
            page = doc[0]
            assert len(page.get_text("text").splitlines()) == len(_make_page(case_id))
            assert all(span["type"] == 3 for span in page.get_texttrace())


def test_benign_control_amounts(tmp_path):
    with fitz.open(create_fixture("A09_SINGLE", tmp_path)) as doc:
        text = doc[0].get_text("text")
        assert "JAN-2026" in text
        assert "FEV-2026" in text
        assert "MAR-2026" in text
        assert "R$ 6.000,00" in text
