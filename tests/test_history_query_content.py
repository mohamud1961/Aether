from aether.context_views import receipt_inline_view
from aether.history_query import query_history
from aether.ledger import Receipt
from aether.pcr_evidence import is_pcr_completion_evidence, is_pcr_primary_action_result


def _receipt(
    receipt_id: str,
    step: int,
    *,
    stdout: str = "",
    stderr: str = "",
    summary: str = "",
    stdout_overflow_path: str = "",
    stderr_overflow_path: str = "",
) -> Receipt:
    payload = {
        "command": f"cmd-{step}",
        "stdout_full": stdout,
        "stderr_full": stderr,
        "stdout_handle": f"{step}:stdout",
        "stderr_handle": f"{step}:stderr",
    }
    if stdout_overflow_path:
        payload["stdout_overflow_path"] = stdout_overflow_path
    if stderr_overflow_path:
        payload["stderr_overflow_path"] = stderr_overflow_path
    return Receipt(
        receipt_id=receipt_id,
        step=step,
        kind="run_command",
        success=True,
        summary=summary or f"command {step}",
        payload=payload,
    )


def _authorized_spool(tmp_path, filename: str):
    directory = tmp_path / "aether_output_spool_test"
    directory.mkdir(exist_ok=True)
    return directory / filename


def test_query_history_finds_literal_text_inside_captured_stdout() -> None:
    receipts = [
        _receipt("r1", 1, stdout="ordinary output"),
        _receipt("r2", 2, stdout="the monitored command dumped core after launch"),
    ]
    result = query_history(receipts, "dumped core")
    assert result["total_matches"] == 1
    row = result["results"][0]
    assert row["receipt_id"] == "r2"
    assert row["content_matches"][0]["field"] == "stdout_full"
    assert row["content_matches"][0]["handle"] == "2:stdout"
    assert "dumped core" in row["content_matches"][0]["excerpt"]
    assert row["content_matches"][0]["historical_observation"] is True
    assert result["historical_results_are_current_state"] is False


def test_query_history_content_search_remains_case_insensitive_and_newest_first() -> None:
    receipts = [
        _receipt("r1", 1, stderr="CONTRADICTION detected"),
        _receipt("r2", 3, stdout="later contradiction detected"),
    ]
    result = query_history(receipts, "Contradiction")
    assert [row["receipt_id"] for row in result["results"]] == ["r2", "r1"]
    assert result["match_mode"] == "case_insensitive_literal_substring"


def test_empty_history_query_does_not_inline_large_content_matches() -> None:
    result = query_history([_receipt("r1", 1, stdout="x" * 10000)], "")
    assert result["total_matches"] == 1
    assert "content_matches" not in result["results"][0]


def test_query_history_searches_omitted_middle_of_spooled_stdout(tmp_path) -> None:
    spool = _authorized_spool(tmp_path, "000001_stdout.txt")
    full = "A" * 70000 + "\nUNIQUE-MIDDLE-NEEDLE\n" + "Z" * 70000
    spool.write_text(full, encoding="utf-8")
    # Simulate RealExecutor's bounded head+tail inline projection. The sought
    # phrase exists only in the complete spooled stream.
    inline = full[:4000] + "\n... omitted ...\n" + full[-4000:]
    receipt = _receipt(
        "r-spooled-out",
        4,
        stdout=inline,
        stdout_overflow_path=str(spool),
    )

    result = query_history([receipt], "unique-middle-needle")

    assert result["total_matches"] == 1
    match = result["results"][0]["content_matches"][0]
    assert match["field"] == "stdout_full"
    assert match["handle"] == "4:stdout"
    assert match["source"] == "overflow_stream"
    assert match["complete_stream_searched"] is True
    assert "UNIQUE-MIDDLE-NEEDLE" in match["excerpt"]
    assert result["complete_spooled_stream_search"] is True


def test_query_history_searches_spooled_stderr_across_chunk_boundary(tmp_path) -> None:
    spool = _authorized_spool(tmp_path, "000001_stderr.txt")
    # Place the literal across the implementation's 64 KiB read boundary to
    # prove the overlap logic does not miss split matches.
    prefix = "x" * (64 * 1024 - 5)
    full = prefix + "SplitBoundaryNeedle" + "y" * 1000
    spool.write_text(full, encoding="utf-8")
    receipt = _receipt(
        "r-spooled-err",
        5,
        stderr="head ... tail",
        stderr_overflow_path=str(spool),
    )

    result = query_history([receipt], "splitboundaryneedle")

    assert result["total_matches"] == 1
    match = result["results"][0]["content_matches"][0]
    assert match["field"] == "stderr_full"
    assert match["handle"] == "5:stderr"
    assert match["source"] == "overflow_stream"
    assert "SplitBoundaryNeedle" in match["excerpt"]


def test_spooled_projection_metadata_is_not_searchable_and_head_matches_use_full_stream(tmp_path) -> None:
    spool = _authorized_spool(tmp_path, "000001_stdout.txt")
    full = "HEAD-NEEDLE\n" + "x" * 70000 + "\nTAIL-NEEDLE\n"
    spool.write_text(full, encoding="utf-8")
    inline = (
        full[:4000]
        + f"\n... [omitted {len(full) - 8000} chars inline; full {len(full)}-char stream spooled to {spool}]\n"
        + full[-4000:]
    )
    receipt = _receipt(
        "r-spooled-marker",
        6,
        stdout=inline,
        stdout_overflow_path=str(spool),
    )

    assert query_history([receipt], "omitted")["total_matches"] == 0
    result = query_history([receipt], "head-needle")
    match = result["results"][0]["content_matches"][0]
    assert match["source"] == "overflow_stream"
    assert match["complete_stream_searched"] is True


def test_missing_overflow_spool_does_not_invent_match(tmp_path) -> None:
    receipt = _receipt(
        "r-missing-spool",
        6,
        stdout="bounded inline projection",
        stdout_overflow_path=str(tmp_path / "does-not-exist.txt"),
    )

    result = query_history([receipt], "not-present")

    assert result["total_matches"] == 0
    assert result["results"] == []
    assert result["complete_spooled_stream_search"] is False


def test_untrusted_overflow_path_is_not_read(tmp_path) -> None:
    outside = tmp_path / "not-an-aether-spool.txt"
    outside.write_text("PRIVATE-NEEDLE", encoding="utf-8")
    receipt = _receipt(
        "r-untrusted-spool",
        7,
        stdout="bounded inline projection",
        stdout_overflow_path=str(outside),
    )

    result = query_history([receipt], "private-needle")

    assert result["total_matches"] == 0
    assert result["complete_spooled_stream_search"] is False


def test_overlong_query_is_rejected_before_history_scan() -> None:
    result = query_history([_receipt("r1", 1, stdout="needle")], "n" * 513)

    assert result["query_rejected"] is True
    assert result["query_truncated"] is True
    assert result["total_matches"] == 0
    assert result["results"] == []


def test_query_history_receipt_is_visible_as_primary_result_but_not_completion_evidence() -> None:
    receipt = Receipt(
        receipt_id="step-2:history:query",
        step=2,
        kind="query_history",
        success=True,
        summary="literal history query: 1/1 matches",
        payload={"historical_results_are_current_state": False},
    )
    assert is_pcr_primary_action_result(receipt) is True
    assert is_pcr_completion_evidence(receipt) is False


def test_query_history_inline_view_exposes_bounded_match_excerpt_and_handle() -> None:
    source = _receipt(
        "r-source", 1,
        stdout="before TRACE_VISIBLE:abc123 after",
    )
    payload = query_history([source], "TRACE_VISIBLE:")
    receipt = Receipt(
        receipt_id="step-2:history:query", step=2, kind="query_history",
        success=True, summary="literal history query 'TRACE_VISIBLE:': 1/1 matches",
        payload=payload,
    )
    view = receipt_inline_view(receipt)
    assert view["total_matches"] == 1
    assert view["historical_results_are_current_state"] is False
    match = view["results"][0]["content_matches"][0]
    assert "TRACE_VISIBLE:abc123" in match["excerpt"]
    assert match["handle"] == "1:stdout"
    assert match["historical_observation"] is True
    assert "stdout_full" not in view["results"][0]


def test_query_history_inline_view_reports_projection_truncation() -> None:
    sources = [_receipt(f"r-{step}", step, stdout="needle") for step in range(1, 21)]
    payload = query_history(sources, "needle", limit=20)
    receipt = Receipt(
        receipt_id="step-21:history:query", step=21, kind="query_history",
        success=True, summary="literal history query 'needle': 20/20 matches",
        payload=payload,
    )

    view = receipt_inline_view(receipt)

    assert len(view["results"]) == 8
    assert view["more_available"] is False
    assert view["results_projection_count"] == 8
    assert view["results_projection_limit"] == 8
    assert view["results_projection_more_available"] is True
