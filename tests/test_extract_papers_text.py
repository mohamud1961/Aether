from pathlib import Path

from research.tools.extract_papers_text import (
    classify_quality,
    infer_title,
    normalize_page,
    paper_key_for,
    render_text_output,
    synthesis_policy_for,
)


def test_paper_key_for_captured_source() -> None:
    path = Path("/tmp/research/sources/papers/src_pap_deadbeef/artifact.pdf")
    assert paper_key_for(path) == "src_pap_deadbeef"


def test_paper_key_for_flat_pdf() -> None:
    path = Path("/tmp/research/sources/papers/Arxiv_2512.16970.pdf")
    assert paper_key_for(path) == "Arxiv_2512.16970"


def test_render_text_output_uses_page_headers() -> None:
    assert render_text_output(["alpha", "", "gamma"]) == (
        "--- PAGE 1 ---\nalpha\n\n--- PAGE 3 ---\ngamma\n"
    )


def test_render_text_output_handles_empty_extract() -> None:
    text = render_text_output(["", ""])
    assert "No extractable text" in text


def test_normalize_page_replaces_surrogates() -> None:
    assert normalize_page("alpha\ud835beta") == "alpha\ufffdbeta"


def test_infer_title_prefers_capture_title() -> None:
    title, source = infer_title("Known Title", ["First page title"])
    assert title == "Known Title"
    assert source == "capture"


def test_infer_title_falls_back_to_first_line() -> None:
    title, source = infer_title(None, ["\n\nFirst page title\nSecond line"])
    assert title == "First page title"
    assert source == "extracted_first_line"


def test_infer_title_skips_page_number_and_abstract_tail() -> None:
    title, source = infer_title(
        None,
        ["1\nBrain-Inspired Graph Multi-Agent Systems for LLM Reasoning\nAbstract stuff"],
    )
    assert title == "Brain-Inspired Graph Multi-Agent Systems for LLM Reasoning"
    assert source == "extracted_first_line"


def test_classify_quality_clean() -> None:
    quality_flag, reasons = classify_quality(
        page_count=8,
        total_chars=20000,
        characters_per_page=2500.0,
        nonempty_pages=8,
        parser_warning_count=0,
        page_error_count=0,
        replacement_character_count=0,
        open_error=None,
    )
    assert quality_flag == "clean"
    assert reasons == ["text extracted without parser or page-level errors"]


def test_classify_quality_noisy() -> None:
    quality_flag, reasons = classify_quality(
        page_count=8,
        total_chars=20000,
        characters_per_page=2500.0,
        nonempty_pages=8,
        parser_warning_count=2,
        page_error_count=0,
        replacement_character_count=0,
        open_error=None,
    )
    assert quality_flag == "usable_with_caveats"
    assert "parser warnings" in reasons[0]


def test_classify_quality_ocr_needed() -> None:
    quality_flag, reasons = classify_quality(
        page_count=12,
        total_chars=400,
        characters_per_page=33.33,
        nonempty_pages=2,
        parser_warning_count=0,
        page_error_count=0,
        replacement_character_count=0,
        open_error=None,
    )
    assert quality_flag == "ocr_needed"
    assert reasons


def test_classify_quality_failed() -> None:
    quality_flag, reasons = classify_quality(
        page_count=0,
        total_chars=0,
        characters_per_page=0.0,
        nonempty_pages=0,
        parser_warning_count=0,
        page_error_count=0,
        replacement_character_count=0,
        open_error="broken pdf",
    )
    assert quality_flag == "failed"
    assert reasons == ["broken pdf"]


def test_synthesis_policy_for_clean() -> None:
    readable, allowed_use = synthesis_policy_for("clean")
    assert readable is True
    assert allowed_use == "full_formal_source_use"


def test_synthesis_policy_for_usable_with_caveats() -> None:
    readable, allowed_use = synthesis_policy_for("usable_with_caveats")
    assert readable is True
    assert allowed_use == "formal_source_use_with_caveats"


def test_synthesis_policy_for_ocr_needed() -> None:
    readable, allowed_use = synthesis_policy_for("ocr_needed")
    assert readable is False
    assert allowed_use == "not_substantively_read"
