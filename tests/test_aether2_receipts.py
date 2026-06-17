from dataclasses import dataclass
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace


receipts_module = importlib.import_module("harness.aether2.traces.receipts")
receipts_compat_module = importlib.import_module("runner.aether2.receipts")

assert receipts_compat_module is receipts_module
ReceiptWriter = receipts_module.ReceiptWriter


@dataclass
class SampleRequest:
    prompt: Path
    metadata: SimpleNamespace


@dataclass
class SampleResponse:
    status: str
    payload: bytes


def test_receipt_writer_records_per_step_files(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    receipt_path = writer.record_step(
        4,
        request={"prompt": "hello"},
        response={"status": "ok"},
        action="raw_bash",
        raw_output={"stdout": "stdout text", "stderr": "stderr text"},
    )

    assert receipt_path.exists()
    assert receipt_path.name == "0004_action_raw_bash.json"

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["step"] == 4
    assert payload["action"] == "raw_bash"
    assert payload["request"] == {"prompt": "hello"}
    assert payload["response"] == {"status": "ok"}
    assert payload["raw_output"] == {"stdout": "stdout text", "stderr": "stderr text"}

    stdout_path = tmp_path / "host_receipts" / "raw" / "0004_action_raw_bash" / "stdout"
    stderr_path = tmp_path / "host_receipts" / "raw" / "0004_action_raw_bash" / "stderr"
    assert stdout_path.read_text(encoding="utf-8") == "stdout text"
    assert stderr_path.read_text(encoding="utf-8") == "stderr text"


def test_receipt_writer_normalizes_non_json_payloads_stably(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    receipt_path = writer.record_step(
        7,
        request=SampleRequest(
            prompt=Path("/tmp/input.txt"),
            metadata=SimpleNamespace(priority=3, tags=["alpha", "beta"]),
        ),
        response=SampleResponse(status="ok", payload=b"\x01\x02"),
        action="raw_bash",
        raw_output={"stdout": b"stdout bytes", "stderr": Path("/var/log/stderr")},
    )

    request_type = f"{SampleRequest.__module__}.{SampleRequest.__qualname__}"
    response_type = f"{SampleResponse.__module__}.{SampleResponse.__qualname__}"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload == {
        "action": "raw_bash",
        "raw_output": {
            "stderr": "/var/log/stderr",
            "stdout": {"__type__": "builtins.bytes", "base64": "c3Rkb3V0IGJ5dGVz"},
        },
        "receipt_id": "0007_action_raw_bash",
        "request": {
            "__type__": request_type,
            "fields": {
                "metadata": {
                    "__type__": "types.SimpleNamespace",
                    "fields": {"priority": 3, "tags": ["alpha", "beta"]},
                },
                "prompt": "/tmp/input.txt",
            },
        },
        "response": {
            "__type__": response_type,
            "fields": {
                "payload": {"__type__": "builtins.bytes", "base64": "AQI="},
                "status": "ok",
            },
        },
        "step": 7,
    }

    stdout_path = tmp_path / "host_receipts" / "raw" / "0007_action_raw_bash" / "stdout"
    stderr_path = tmp_path / "host_receipts" / "raw" / "0007_action_raw_bash" / "stderr"
    assert stdout_path.read_bytes() == b"stdout bytes"
    assert stderr_path.read_text(encoding="utf-8") == "/var/log/stderr"


def test_receipt_writer_caps_filename_for_unnamed_action_with_large_content(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    large_action = {"content": "x" * 100_000}
    receipt_path = writer.record_step(
        9,
        request={"prompt": "hello"},
        response={"status": "ok"},
        action=large_action,
        raw_output={"stdout": "stdout text", "stderr": "stderr text"},
    )

    assert receipt_path.exists()
    assert len(receipt_path.name) < 100
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["step"] == 9
    assert payload["action"] == large_action


def test_record_model_exchange_writes_full_messages_and_response(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    tool_schemas = [{"function": {"name": "run_command", "parameters": {"type": "object"}}}]
    tool_schema_json = json.dumps(tool_schemas, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    tool_schema_digest = hashlib.sha256(tool_schema_json.encode("utf-8")).hexdigest()
    orientation_snapshot = {
        "cwd": "/app",
        "env_contract_version": "aether2_env_contract_v1",
        "env_contract_digest": "env-digest-123",
        "env_contract": {
            "contract_version": "aether2_env_contract_v1",
            "contract_digest": "env-digest-123",
        },
    }
    request_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "do the thing"},
        {
            "role": "system",
            "content": "[orientation_snapshot]\n"
            + json.dumps(orientation_snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        },
        {"role": "system", "content": "[tool_schemas]\n" + tool_schema_json},
        {"role": "system", "content": "[deterministic_fact_ledger]\n" + json.dumps({"written_files": ["a.txt"]})},
        {
            "role": "system",
            "content": "[tail_telemetry]\n"
            + json.dumps({"plan": "inspect", "derived_state": {"no_delta_streak": 1}}, sort_keys=True),
        },
        {"role": "assistant", "content": "previous turn", "tool_calls": [{"id": "call-1", "name": "run_command"}]},
    ]
    response = SimpleNamespace(
        text="here is my plan",
        tool_calls=({"id": "call-2", "name": "write_file", "arguments": {"path": "out.txt"}},),
    )

    receipt_path = writer.record_model_exchange(3, request_messages, response)

    assert receipt_path.exists()
    assert receipt_path.name == "model_exchange_3.json"

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["call_idx"] == 3
    assert payload["call_role"] == "normal"
    assert payload["request_messages"] == request_messages
    assert payload["request_context"] == {
        "env_contract": {"digest": "env-digest-123", "version": "aether2_env_contract_v1"},
        "ledger_state": {"written_files": ["a.txt"]},
        "tail_state": {"derived_state": {"no_delta_streak": 1}, "plan": "inspect"},
        "tool_schema_digest": tool_schema_digest,
        "tool_schemas": tool_schemas,
    }
    assert payload["response"]["text"] == "here is my plan"
    assert payload["response"]["tool_calls"] == [
        {"id": "call-2", "name": "write_file", "arguments": {"path": "out.txt"}}
    ]


def test_record_model_exchange_supports_explicit_roles_and_redacts_credentials(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    request_messages = [
        {"role": "system", "content": "Authorization: Bearer super-secret-token"},
        {"role": "user", "content": "OPENAI_API_KEY=sk-secret-value"},
    ]
    response = SimpleNamespace(
        text="token=abc123",
        tool_calls=({"id": "call-9", "name": "run_command", "arguments": {"env": {"api_key": "shh"}}},),
    )

    receipt_path = writer.record_model_exchange(
        9,
        request_messages,
        response,
        call_role="verifier",
        tool_schemas=[{"function": {"name": "read_file"}}],
        tail_state={"plan": "verify"},
        ledger_state={"api_key": "secret"},
    )

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["call_role"] == "verifier"
    assert payload["request_messages"][0]["content"] == "Authorization=[REDACTED]"
    assert payload["request_messages"][1]["content"] == "OPENAI_API_KEY=[REDACTED]"
    assert payload["response"]["text"] == "token=[REDACTED]"
    assert payload["response"]["tool_calls"][0]["arguments"]["env"]["api_key"] == "[REDACTED]"
    assert payload["request_context"]["ledger_state"]["api_key"] == "[REDACTED]"


def test_record_model_exchange_accepts_explicit_env_contract_metadata(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    receipt_path = writer.record_model_exchange(
        10,
        [{"role": "system", "content": "system prompt"}],
        SimpleNamespace(text="ok", tool_calls=()),
        env_contract={
            "contract_version": "aether2_env_contract_v1",
            "contract_digest": "digest-from-arg",
        },
    )

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["request_context"]["env_contract"] == {
        "digest": "digest-from-arg",
        "version": "aether2_env_contract_v1",
    }


def test_record_model_exchange_infers_closing_and_repair_roles(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    closing_path = writer.record_model_exchange(
        1,
        [
            {"role": "system", "content": "Wall-clock deadline reached. This is your final turn."},
            {"role": "user", "content": "{}"},
        ],
        SimpleNamespace(text="closing", tool_calls=()),
    )
    repair_path = writer.record_model_exchange(
        2,
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "{\"verification_report\":{\"summary\":\"fix it\"}}"},
        ],
        SimpleNamespace(text="repair", tool_calls=()),
    )

    closing_payload = json.loads(closing_path.read_text(encoding="utf-8"))
    repair_payload = json.loads(repair_path.read_text(encoding="utf-8"))
    assert closing_payload["call_role"] == "closing"
    assert repair_payload["call_role"] == "repair"


def test_record_model_exchange_accepts_explicit_compaction_role(tmp_path: Path) -> None:
    writer = ReceiptWriter(tmp_path / "host_receipts")

    receipt_path = writer.record_model_exchange(
        4,
        [{"role": "system", "content": "summarize the run for compaction"}],
        SimpleNamespace(text="handoff", tool_calls=()),
        call_role="compaction",
        ledger_state={"written_files": ["artifact.txt"]},
    )

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["call_role"] == "compaction"
    assert payload["request_context"]["ledger_state"] == {"written_files": ["artifact.txt"]}


def test_receipts_module_does_not_expose_model_facing_tool_names_or_constants() -> None:
    banned_terms = {
        "search_receipts",
        "view_receipt",
        "view_file_cache",
        "search_files",
        "probe_service",
    }

    exported_names = set(getattr(receipts_module, "__all__", ()))
    assert exported_names == {"ReceiptWriter"}

    module_string_values = []
    for name, value in vars(receipts_module).items():
        if name.startswith("__"):
            continue
        if isinstance(value, str):
            module_string_values.append(value)

    for term in banned_terms:
        assert term not in exported_names
        assert all(term not in value for value in module_string_values)
