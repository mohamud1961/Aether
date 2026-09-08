from __future__ import annotations

from types import SimpleNamespace

from aether.execution import MemoryExecutor
from aether.kernel_actions import handle_kernel_owned_action
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger, Receipt
from aether.pcr_provider_protocol import PCR_DIRECT_PROVIDER_TOOLS
from aether.runtime_ir import ActionRequest, EnvMap


def _action(kind: str, arguments: dict, action_id: str = "a") -> ActionRequest:
    return ActionRequest(
        action_id=action_id, kind=kind, capability_id="kernel",
        arguments=arguments, intent="", expected_observation="", if_fail_next="",
    )


def _env() -> EnvMap:
    return EnvMap(task_prompt="truth", workspace_root="/app", capabilities={})


def test_text_file_size_and_paging_units_are_truthful_for_unicode() -> None:
    executor = MemoryExecutor(files={"unicode.txt": "é🙂z"}, workspace_root="/app")
    ledger = ExecutionLedger()
    [whole] = dispatch_action(SimpleNamespace(), _action("read_file", {"path": "unicode.txt"}), 1, SimpleNamespace(), executor, _env(), ledger)
    assert whole.payload["chars"] == 3
    assert whole.payload["bytes"] == len("é🙂z".encode("utf-8"))

    [page] = dispatch_action(SimpleNamespace(), _action("read_file_page", {"path": "unicode.txt", "offset": 0, "span": 2}), 2, SimpleNamespace(), executor, _env(), ledger)
    assert page.payload["paging_unit"] == "characters"
    assert page.payload["total_chars"] == 3
    assert page.payload["returned_chars"] == 2
    assert page.payload["bytes"] == len("é🙂z".encode("utf-8"))
    assert page.payload["more_available"] is True
    assert "characters" in page.summary


def test_read_output_reports_character_paging_and_exact_utf8_bytes() -> None:
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        "source", 0, "run_command", True, "source",
        payload={"stdout_handle": "h:stdout", "stdout_full": "é🙂z", "stderr_handle": "h:stderr", "stderr_full": ""},
    ))
    [page] = dispatch_action(SimpleNamespace(), _action("read_output", {"handle": "h:stdout", "offset": 1, "span": 1}), 1, SimpleNamespace(), MemoryExecutor(workspace_root="/app"), _env(), ledger)
    assert page.payload["paging_unit"] == "characters"
    assert page.payload["total_chars"] == 3
    assert page.payload["returned_chars"] == 1
    assert page.payload["bytes"] == len("é🙂z".encode("utf-8"))
    assert page.payload["more_available"] is True
    assert page.payload["chunk"] == "🙂"


def test_grep_output_declares_match_cap_and_remaining_matches() -> None:
    full = "\n".join(f"MATCH {i}" for i in range(250))
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        "source", 0, "run_command", True, "source",
        payload={"stdout_handle": "h:stdout", "stdout_full": full, "stderr_handle": "h:stderr", "stderr_full": ""},
    ))
    [grep] = dispatch_action(SimpleNamespace(), _action("grep_output", {"handle": "h:stdout", "pattern": "MATCH"}), 1, SimpleNamespace(), MemoryExecutor(workspace_root="/app"), _env(), ledger)
    assert grep.payload["matches"] == 250
    assert grep.payload["returned_matches"] == 200
    assert grep.payload["match_cap"] == 200
    assert grep.payload["more_available"] is True
    assert grep.payload["coverage"] == "first_matching_lines_in_stream_order"
    assert "returned 200/250" in grep.summary


def test_artifact_history_and_diff_declare_bounded_return_coverage() -> None:
    ledger = ExecutionLedger()
    for i in range(20):
        ledger.record(Receipt(
            f"w{i}", i, "write_file", True, f"write {i}", state_change=True,
            payload={"path": "x.txt", "before_content_hash": str(i), "after_content_hash": str(i + 1)},
        ))
    history = handle_kernel_owned_action(
        _action("query_artifact_history", {"path": "x.txt"}), 21,
        SimpleNamespace(), MemoryExecutor(workspace_root="/app"), _env(), ledger,
    )
    assert history is not None
    assert history.payload["total_events"] == 20
    assert history.payload["returned_events"] == 12
    assert history.payload["more_available"] is True

    diff = handle_kernel_owned_action(
        _action("inspect_diff", {"path": "x.txt"}), 22,
        SimpleNamespace(), MemoryExecutor(workspace_root="/app"), _env(), ledger,
    )
    assert diff is not None
    assert diff.payload["event_count"] == 20
    assert diff.payload["returned_event_count"] == 12
    assert diff.payload["more_available"] is True
    assert diff.payload["filesystem_diff"] is False


def test_provider_descriptions_disclose_bounded_retrieval_semantics() -> None:
    tools = {row["name"]: row for row in PCR_DIRECT_PROVIDER_TOOLS}
    assert "character" in tools["read_file_page"]["description"].lower()
    assert "whether more" in tools["read_output"]["description"].lower()
    assert "200" in tools["grep_output"]["description"]
    assert "12" in tools["query_artifact_history"]["description"]
    assert "not a current filesystem diff" in tools["inspect_diff"]["description"].lower()
