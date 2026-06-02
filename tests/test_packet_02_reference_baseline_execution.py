import json

from blocks.context import full_history
from blocks.execution import flat_loop
from blocks.tools import raw_bash
from runner.agent import resolve_model_client, run_reference_baseline
from runner.docker_sandbox import DockerSandbox
from runner.model_client import (
    CodexSubscriptionModelClient,
    LocalStubModelClient,
    ModelClientError,
    OpenAIAPIKeyModelClient,
    make_codex_subscription_route,
    make_no_model_route,
    make_openai_chat_completions_route,
)
from runner.packet04_route_manifest import PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE, build_packet04_route_manifest


class _FakeHTTPResponse:
    def __init__(self, status_code: int, body: bytes):
        self._status_code = status_code
        self._body = body

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self._status_code

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def close(self) -> None:
        return None


class _ScriptedModel:
    def __init__(self, responses):
        self._responses = list(responses)

    def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        if self._responses:
            return self._responses.pop(0)
        return {"text": "", "tool_calls": []}


def test_flat_loop_executes_raw_bash_tool_path(tmp_path):
    model = _ScriptedModel(
        [
            {
                "text": "running tool",
                "tool_calls": [{"name": "raw_bash", "arguments": {"command": "echo packet02"}}],
            },
            {"text": "done", "tool_calls": []},
        ]
    )
    with DockerSandbox(cwd=tmp_path, sandbox_type="none", timeout_sec=10) as sandbox:
        result = flat_loop.run_loop(
            model=model,
            tools={"raw_bash": lambda call: raw_bash.execute_tool_call(call, sandbox)},
            context={"history": [{"role": "user", "content": "hi"}], "manage_history": full_history.manage},
            max_steps=3,
        )

    assert result["status"] == "completed"
    assert result["step_count"] == 2
    first_tool_result = result["steps"][0]["results"][0]
    assert first_tool_result["exit_code"] == 0
    assert "packet02" in first_tool_result["stdout"]


def test_flat_loop_records_assistant_tool_call_before_tool_observation(tmp_path):
    model = _ScriptedModel(
        [
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "name": "raw_bash",
                        "arguments": {"command": "echo packet02"},
                    }
                ],
            },
            {"text": "done", "tool_calls": []},
        ]
    )
    with DockerSandbox(cwd=tmp_path, sandbox_type="none", timeout_sec=10) as sandbox:
        result = flat_loop.run_loop(
            model=model,
            tools={"raw_bash": lambda call: raw_bash.execute_tool_call(call, sandbox)},
            context={"history": [{"role": "user", "content": "hi"}], "manage_history": full_history.manage},
            max_steps=3,
        )

    assistant_row = result["history"][1]
    tool_row = result["history"][2]
    assert assistant_row["role"] == "assistant"
    assert assistant_row["tool_calls"][0]["id"] == "call_1"
    assert tool_row["role"] == "tool"
    assert tool_row["tool_call_id"] == "call_1"


def test_flat_loop_blocks_blind_retry_and_triggers_autopsy():
    class _RetryModel:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages, **_kwargs):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls == 1:
                return {"text": "", "tool_calls": [{"name": "raw_bash", "arguments": {"command": "false"}}]}
            if self.calls == 2:
                return {"text": "", "tool_calls": [{"name": "raw_bash", "arguments": {"command": "false"}}]}
            return {"text": "done", "tool_calls": []}

    tool_exec_calls: list[str] = []

    def _failing_tool(call):  # type: ignore[no-untyped-def]
        tool_exec_calls.append(call["arguments"]["command"])
        return {
            "tool_name": "raw_bash",
            "command": call["arguments"]["command"],
            "exit_code": 1,
            "stdout": "",
            "stderr": "failed",
            "timed_out": False,
            "reason_code": "tool_runtime_nonzero_exit",
        }

    result = flat_loop.run_loop(
        model=_RetryModel(),
        tools={"raw_bash": _failing_tool},
        context={"history": [{"role": "user", "content": "retry"}], "manage_history": full_history.manage},
        max_steps=4,
    )

    assert tool_exec_calls == ["false"]
    second_result = result["steps"][1]["results"][0]
    assert second_result["reason_code"] == "blind_retry_blocked_same_failed_command"
    assert result["autopsy"]["triggered"] is True
    assert result["autopsy"]["replan_required"] is True


def test_packet02_local_stub_run_emits_required_artifacts(tmp_path):
    run_dir = tmp_path / "run-local-stub"
    route = LocalStubModelClient.create(response_text="local stub done").route

    result = run_reference_baseline(
        run_id="run-local-stub",
        run_dir=run_dir,
        task_id="task-local-stub",
        task_prompt="Print hello",
        benchmark_family="smoke",
        model_route=route,
        max_steps=2,
        timeout_sec=10,
    )

    header_path = run_dir / "run_header.json"
    events_path = run_dir / "run_events.jsonl"
    score_path = run_dir / "score_envelope.json"

    assert header_path.exists()
    assert events_path.exists()
    assert score_path.exists()

    header = json.loads(header_path.read_text(encoding="utf-8"))
    assert header["model_route"]["provider_route"] == "local_stub"
    assert "access_token" not in header_path.read_text(encoding="utf-8")
    assert "refresh_token" not in header_path.read_text(encoding="utf-8")

    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [event["seq"] for event in events] == list(range(len(events)))
    assert events[-1]["event_type"] == "score_envelope_ready"
    completion_events = [event for event in events if event["event_type"] == "model_completion"]
    assert len(completion_events) == 1
    assert (
        completion_events[0]["payload"]["details"]["assistant_text"]
        == result["execution"]["last_completion"]["text"]
    )
    assert completion_events[0]["payload"]["details"]["tool_call_count"] == 0

    score = json.loads(score_path.read_text(encoding="utf-8"))
    assert score["aggregate"]["final_verdict"] in {"pass", "fail", "unresolved", "blocked_non_promotable"}
    assert result["score_envelope"]["run_id"] == "run-local-stub"


def test_packet02_none_route_is_supported_for_local_execution(tmp_path):
    run_dir = tmp_path / "run-no-model"
    result = run_reference_baseline(
        run_id="run-no-model",
        run_dir=run_dir,
        task_id="task-no-model",
        task_prompt="No model route",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        max_steps=1,
        timeout_sec=10,
    )
    assert result["run_header"]["model_route"]["provider_route"] == "none"


def test_resolve_model_client_keeps_existing_codex_subscription_adapter():
    client = resolve_model_client(make_codex_subscription_route(model_name="gpt-5.4-mini"))
    assert isinstance(client, CodexSubscriptionModelClient)


def test_packet02_records_model_client_error_details(monkeypatch, tmp_path):
    class _FailingModel:
        def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            raise ModelClientError(
                "codex_subscription request failed with status 400",
                status_code=400,
                response_body='{"error":{"message":"tools payload invalid"}}',
                error_kind="http_error",
            )

    monkeypatch.setattr("runner.agent.resolve_model_client", lambda route, **kwargs: _FailingModel())

    run_dir = tmp_path / "run-model-error"
    run_reference_baseline(
        run_id="run-model-error",
        run_dir=run_dir,
        task_id="task-model-error",
        task_prompt="exercise model error logging",
        benchmark_family="smoke",
        model_route=make_codex_subscription_route(model_name="gpt-5.4-mini"),
        max_steps=1,
        timeout_sec=10,
    )

    events = [
        json.loads(line)
        for line in (run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    model_error = next(event for event in events if event["event_type"] == "model_client_error")
    recovery = next(
        event
        for event in events
        if event["event_type"] in {"no_recovery", "recovery_action"}
    )

    assert model_error["payload"]["details"]["status_code"] == 400
    assert "tools payload invalid" in model_error["payload"]["details"]["response_body"]
    assert recovery["payload"]["details"]["error_type"] == "ModelClientError"
    assert recovery["payload"]["details"]["error_details"]["status_code"] == 400


def test_packet02_active_kernel_surfaces_internal_model_client_error(monkeypatch, tmp_path):
    class _FailingModel:
        def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            raise ModelClientError(
                "azure openai request failed with status 400",
                status_code=400,
                response_body='{"error":{"message":"bad request"}}',
                error_kind="http_error",
            )

    monkeypatch.setattr("runner.agent.resolve_model_client", lambda route, **kwargs: _FailingModel())

    run_dir = tmp_path / "run-active-model-error"
    route_manifest = build_packet04_route_manifest(
        "active_evidence_kernel_v1",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    run_reference_baseline(
        run_id="run-active-model-error",
        run_dir=run_dir,
        task_id="task-active-model-error",
        task_prompt="exercise active kernel model error logging",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        route_manifest=route_manifest,
        max_steps=2,
        timeout_sec=10,
    )

    events = [
        json.loads(line)
        for line in (run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    model_error = next(event for event in events if event["event_type"] == "model_client_error")
    assert model_error["payload"]["details"]["status_code"] == 400
    assert model_error["payload"]["details"]["error_kind"] == "http_error"


def test_packet02_logs_model_completion_tool_call_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "runner.agent.resolve_model_client",
        lambda route, **kwargs: _ScriptedModel(
            [
                {
                    "text": "running tool",
                    "reasoning_summary": "Checked current workspace path and selected raw_bash.",
                    "reasoning_token_count": 6,
                    "provider_reasoning": {
                        "source": "responses.output.reasoning",
                        "summary_count": 1,
                        "encrypted_item_count": 1,
                    },
                    "reasoning_artifact": {
                        "type": "encrypted_reasoning_continuity",
                        "encoding": "provider_encrypted",
                        "encrypted_content_char_count": 640,
                        "encrypted_content_hashes": [
                            "hash_1",
                            "hash_2",
                            "hash_3",
                            "hash_4",
                        ],
                    },
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "raw_bash",
                            "arguments": {"command": "echo packet02"},
                        }
                    ],
                },
                {"text": "done", "tool_calls": []},
            ]
        ),
    )

    run_dir = tmp_path / "run-model-completion"
    run_reference_baseline(
        run_id="run-model-completion",
        run_dir=run_dir,
        task_id="task-model-completion",
        task_prompt="exercise model completion logging",
        benchmark_family="smoke",
        model_route=make_no_model_route(),
        max_steps=3,
        timeout_sec=10,
    )

    events = [
        json.loads(line)
        for line in (run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    completion_events = [event for event in events if event["event_type"] == "model_completion"]

    assert len(completion_events) == 2
    first = completion_events[0]["payload"]["details"]
    second = completion_events[1]["payload"]["details"]
    assert first["assistant_text"] == "running tool"
    assert first["tool_call_count"] == 1
    assert first["tool_calls"] == [
        {"id": "call_1", "name": "raw_bash", "arguments": {"command": "echo packet02"}}
    ]
    assert first["reasoning_summary"] == "Checked current workspace path and selected raw_bash."
    assert first["reasoning_summary_char_count"] == len(
        "Checked current workspace path and selected raw_bash."
    )
    assert first["reasoning_token_count"] == 6
    assert first["provider_reasoning"] == {
        "source": "responses.output.reasoning",
        "summary_count": 1,
        "encrypted_item_count": 1,
    }
    assert first["reasoning_artifact"] == {
        "type": "encrypted_reasoning_continuity",
        "encoding": "provider_encrypted",
        "encrypted_content_char_count": 640,
        "encrypted_content_hash_count": 4,
        "encrypted_content_hashes_preview": ["hash_1", "hash_2", "hash_3"],
    }
    assert second["assistant_text"] == "done"
    assert second["tool_call_count"] == 0


def test_openai_api_client_preserves_assistant_tool_call_and_tool_message_shape(monkeypatch):
    route = make_openai_chat_completions_route(model_name="gpt-5.4-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai-key")
    seen_request = {}

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        seen_request["url"] = request.full_url
        seen_request["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen_request["payload"] = json.loads(request.data.decode("utf-8"))
        body = {
            "choices": [{"finish_reason": "stop", "message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
        }
        return _FakeHTTPResponse(200, json.dumps(body).encode("utf-8"))

    monkeypatch.setattr("runner.model_client.urllib_request.urlopen", fake_urlopen)

    client = OpenAIAPIKeyModelClient(route=route)
    result = client.complete(
        messages=[
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "name": "raw_bash",
                        "arguments": "{\"command\":\"pwd\"}",
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "raw_bash",
                "content": "raw_bash exit=0",
            },
        ],
        tools=[
            {
                "name": "raw_bash",
                "description": "run command",
                "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}},
            }
        ],
    )

    assert seen_request["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen_request["headers"]["authorization"] == "Bearer secret-openai-key"
    assert seen_request["payload"]["messages"][1] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "raw_bash", "arguments": "{\"command\":\"pwd\"}"},
            }
        ],
    }
    assert seen_request["payload"]["messages"][2] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "raw_bash",
        "content": "raw_bash exit=0",
    }
    assert result["text"] == "ok"
