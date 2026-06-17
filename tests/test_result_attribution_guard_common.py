from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blocks.tools import result_attribution_guard_common as mod


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_no_call_guard_canonicalizes_visible_policy_request(tmp_path):
    _write(
        tmp_path / "answer.json",
        {
            "adapter_kind": "bfcl_native_adapter",
            "tool_calls": [{"name": "lookup_customer_order", "arguments": {"customer_id": "C-204"}}],
            "no_call": False,
            "result_attribution": {"status": "tool_calls_ready", "reason_code": "identity_not_verified"},
        },
    )
    _write(tmp_path / "request.json", {"request_type": "cancellation_status_check", "customer_verified": False})
    _write(tmp_path / "policy.json", {"do_not_call_external_tools_until_identity_verified": True})

    result = mod.apply_answer_json_guard(tmp_path, mode=mod.NO_CALL_GUARD)
    updated = json.loads((tmp_path / "answer.json").read_text(encoding="utf-8"))

    assert result == {"changed": True, "applied": [mod.NO_CALL_GUARD]}
    assert updated["tool_calls"] == []
    assert updated["no_call"] is True
    assert updated["result_attribution"] == {"status": "no_call_required", "reason_code": "identity_not_verified"}


def test_ignored_result_ids_guard_keeps_only_stale_ids_and_repairs_call_source(tmp_path):
    _write(
        tmp_path / "answer.json",
        {
            "adapter_kind": "bfcl_native_adapter",
            "tool_calls": [
                {"call_id": "call_001", "name": "lookup_customer_order", "arguments": {"customer_id": "C-204"}},
                {"call_id": "call_002", "name": "create_return_label", "arguments": {"order_id": "RET-204-19"}},
            ],
            "no_call": False,
            "result_attribution": {
                "final_result_from_call_id": "call_001",
                "final_result_id": "label_RET-204-19_WH-N-7",
                "ignored_result_ids": ["stale_label_RET-204-17", "history_RET-204-19"],
            },
        },
    )
    _write(tmp_path / "tool_results" / "call_001_result.json", {"result_id": "history_RET-204-19", "status": "ok"})
    _write(tmp_path / "tool_results" / "call_002_result.json", {"result_id": "label_RET-204-19_WH-N-7", "status": "ok"})
    _write(tmp_path / "tool_results" / "stale_result.json", {"result_id": "stale_label_RET-204-17", "status": "stale"})

    result = mod.apply_answer_json_guard(tmp_path, mode=mod.IGNORED_IDS_GUARD)
    updated = json.loads((tmp_path / "answer.json").read_text(encoding="utf-8"))

    assert result == {"changed": True, "applied": [mod.IGNORED_IDS_GUARD]}
    assert updated["result_attribution"]["final_result_from_call_id"] == "call_002"
    assert updated["result_attribution"]["ignored_result_ids"] == ["stale_label_RET-204-17"]


def test_combined_guard_is_noop_for_multi_required_order_sentinel(tmp_path):
    _write(
        tmp_path / "answer.json",
        {
            "adapter_kind": "bfcl_native_adapter",
            "tool_calls": [{"name": "lookup_customer_order", "arguments": {"customer_id": "C-204"}}],
            "no_call": False,
            "result_attribution": {"status": "tool_calls_ready", "reason_code": "return_label_ready"},
        },
    )

    result = mod.apply_answer_json_guard(tmp_path, mode=mod.COMBINED_GUARD)

    assert result == {"changed": False, "applied": []}
