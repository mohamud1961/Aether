from __future__ import annotations

from aether.history_query import query_history
from aether.ledger import Receipt


def _receipt(
    receipt_id: str,
    step: int,
    *,
    stdout: str = "",
    stderr: str = "",
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
        summary=f"command {step}",
        payload=payload,
    )


def _authorized_spool(tmp_path, filename: str):
    directory = tmp_path / "aether_output_spool_test"
    directory.mkdir(exist_ok=True)
    return directory / filename


def test_query_history_searches_complete_spool_and_reports_completion(tmp_path) -> None:
    spool = _authorized_spool(tmp_path, "000001_stdout.txt")
    full = "A" * 70000 + "\nUNIQUE-MIDDLE-NEEDLE\n" + "Z" * 70000
    spool.write_text(full, encoding="utf-8")
    inline = full[:4000] + "\n... [omitted metadata removed] ...\n" + full[-4000:]
    receipt = _receipt(
        "r-spooled", 4, stdout=inline, stdout_overflow_path=str(spool)
    )

    result = query_history([receipt], "unique-middle-needle")

    assert result["total_matches"] == 1
    match = result["results"][0]["content_matches"][0]
    assert match["source"] == "overflow_stream"
    assert match["complete_stream_searched"] is True
    assert "UNIQUE-MIDDLE-NEEDLE" in match["excerpt"]
    assert result["complete_spooled_stream_search"] is True


def test_query_history_handles_chunk_boundary_in_spooled_stream(tmp_path) -> None:
    spool = _authorized_spool(tmp_path, "000001_stderr.txt")
    full = "x" * (64 * 1024 - 5) + "SplitBoundaryNeedle" + "y" * 1000
    spool.write_text(full, encoding="utf-8")
    receipt = _receipt(
        "r-boundary", 5, stderr="head ... tail", stderr_overflow_path=str(spool)
    )

    result = query_history([receipt], "splitboundaryneedle")

    assert result["total_matches"] == 1
    match = result["results"][0]["content_matches"][0]
    assert match["source"] == "overflow_stream"
    assert "SplitBoundaryNeedle" in match["excerpt"]


def test_query_history_does_not_search_executor_spool_metadata(tmp_path) -> None:
    spool = _authorized_spool(tmp_path, "000001_stdout.txt")
    full = "HEAD-NEEDLE\n" + "x" * 70000 + "\nTAIL-NEEDLE\n"
    spool.write_text(full, encoding="utf-8")
    inline = (
        full[:4000]
        + f"\n... [omitted {len(full) - 8000} chars inline; full {len(full)}-char stream spooled to {spool}]\n"
        + full[-4000:]
    )
    receipt = _receipt(
        "r-marker", 6, stdout=inline, stdout_overflow_path=str(spool)
    )

    assert query_history([receipt], "omitted") ["total_matches"] == 0
    result = query_history([receipt], "head-needle")
    assert result["results"][0]["content_matches"][0]["source"] == "overflow_stream"


def test_query_history_marks_missing_or_forged_spool_incomplete(tmp_path) -> None:
    missing = _receipt(
        "r-missing", 6, stdout="bounded inline", stdout_overflow_path=str(tmp_path / "missing.txt")
    )
    outside = tmp_path / "not-an-aether-spool.txt"
    outside.write_text("PRIVATE-NEEDLE", encoding="utf-8")
    forged = _receipt(
        "r-forged", 7, stdout="bounded inline", stdout_overflow_path=str(outside)
    )

    missing_result = query_history([missing], "not-present")
    forged_result = query_history([forged], "private-needle")

    assert missing_result["total_matches"] == 0
    assert missing_result["complete_spooled_stream_search"] is False
    assert forged_result["total_matches"] == 0
    assert forged_result["complete_spooled_stream_search"] is False


def test_query_history_rejects_overlong_queries_before_scanning() -> None:
    result = query_history([_receipt("r1", 1, stdout="needle")], "n" * 513)

    assert result["query_rejected"] is True
    assert result["query_truncated"] is True
    assert result["total_matches"] == 0
    assert result["results"] == []
