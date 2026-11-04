"""Testes unitários de pareamento A10 sem chamadas ao OCR ou Gemini."""
from experiments.pdf_representation.a10_spatial import match_spatial


def word(text, x, y):
    return {"text": text, "bbox": [x, y, x+10, y+8]}


def test_reverse_order():
    result = match_spatial(
        [word("MES", 10, 10), word("VALOR", 200, 10)],
        [word("VALOR", 200, 10), word("MES", 10, 10)],
    )
    assert result["matched_count"] == 2
    assert result["review_items"] == 0


def test_invisible_extra_remains_unmatched():
    result = match_spatial(
        [word("JAN", 10, 10)],
        [word("JAN", 10, 10), word("INVISIVEL", 10, 50)],
    )
    assert len(result["unmatched_extracted"]) == 1


def test_similar_word_is_reported():
    result = match_spatial(
        [word("FEW-2026", 10, 10)], [word("FEV-2026", 10, 10)]
    )
    assert result["matched_count"] == 1
    assert len(result["approximate_matches"]) == 1


def test_same_word_far_away_is_not_matched():
    result = match_spatial(
        [word("JAN-2026", 10, 10)], [word("JAN-2026", 400, 400)]
    )
    assert result["matched_count"] == 0


def test_punctuation_token_matches():
    result = match_spatial([word("|", 10, 10)], [word("|", 10, 10)])
    assert result["matched_count"] == 1
    assert result["review_items"] == 0
