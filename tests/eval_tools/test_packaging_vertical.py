"""Behavioral proofs of actual tool execution, grading and falsification boundaries."""

import json, shutil
from pathlib import Path
import pytest
from harness_evals.task import load_task, discover
from harness_evals.sandbox import LocalSandbox, DockerSandbox
from harness_evals.grading import grade
from harness_evals.agents.minimal import MinimalAgent
from harness_evals.agents.command import CommandAgent
from harness_evals.trials import Arm, run_trials, read_traces, trace_path_for
from harness_evals.mutation import audit
from harness_evals.verifier_bench import build_cases, evaluate
from harness_evals import prereg, tournament

ROOT = Path(__file__).resolve().parents[2]


def example():
    return load_task(ROOT / "tests/eval_tools/fixtures/config_repair")


REPAIR = 'python3 -c \'import json; p="config.json"; d=json.load(open(p)); d.update(port=8080,log_level="info"); open(p,"w").write(json.dumps(d))\''


def test_model_loop_executes_real_tools_and_wrong_state_still_fails(tmp_path):
    requests = []

    def transport(payload, timeout):
        requests.append(payload)
        if len(requests) == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call1",
                                    "type": "function",
                                    "function": {
                                        "name": "bash",
                                        "arguments": json.dumps({"command": REPAIR}),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 5},
            }
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "complete"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3},
        }

    agent = MinimalAgent("scripted-test", transport=transport)
    rows = run_trials(
        [example()],
        [Arm("loop", agent, "scripted")],
        1,
        "local",
        tmp_path / "rows.jsonl",
        "test",
    )
    assert (
        rows[0].valid
        and rows[0].passed
        and rows[0].tokens_in == 15
        and rows[0].tool_calls == 1
    )
    assert requests[1]["messages"][-1]["role"] == "tool"
    assert "grader/" not in json.dumps(requests)
    assert read_traces(trace_path_for(tmp_path / "rows.jsonl"))[rows[0].key].trace
    bad = run_trials(
        [example()],
        [Arm("bad", CommandAgent("echo complete"), "cli")],
        1,
        "local",
        tmp_path / "bad.jsonl",
        "bad",
    )
    assert bad[0].valid and not bad[0].passed


def test_cli_real_artifact_and_provider_failure(tmp_path):
    rows = run_trials(
        [example()],
        [Arm("cli", CommandAgent(REPAIR), "cli")],
        1,
        "local",
        tmp_path / "rows.jsonl",
        "cli",
    )
    assert rows[0].passed

    def broken(payload, timeout):
        raise ConnectionError("do not include arbitrary secret body")

    rows = run_trials(
        [example()],
        [Arm("provider", MinimalAgent("scripted", transport=broken), "scripted")],
        1,
        "local",
        tmp_path / "errors.jsonl",
        "err",
    )
    assert not rows[0].valid and rows[0].invalid_reason == "provider_error"


def test_mcp_candidate_token_cannot_move_grader_truth():
    task = load_task(ROOT / "evals/tooling/tasks/mcp_registry_contract")
    sandbox = LocalSandbox(task, trusted=True)
    try:
        assert sandbox.exec('bash "$TASK_ROOT/reference/solve.sh"', 60).code == 0
        assert grade(task, sandbox.root).passed
        (sandbox.root / "challenge.txt").write_text("planted")
        for name in ["mcp_audit.json", "mcp_registry_trace.json"]:
            p = sandbox.root / name
            data = json.loads(p.read_text())
            data["challenge_response"] = "payload=planted"
            p.write_text(json.dumps(data))
        assert not grade(task, sandbox.root).passed
    finally:
        sandbox.close()
    assert all(task.admission == "capability" for task in discover(ROOT / "evals"))
    assert (
        sum(
            task.admission == "smoke"
            for task in discover(ROOT / "evals", include_smoke=True)
        )
        == 0
    )


def test_mutants_and_verifier_inputs_are_discriminating(tmp_path):
    result = audit([example()])
    assert result["mutants"] == result["killed"] == 1
    cases = tmp_path / "cases"
    build_cases([example()], cases)
    # Always trusting completion claims must miss every declared bad state.
    result = evaluate(cases, "printf met")
    assert all(
        s["catch_rate"]["successes"] == 0 and s["false_hold_rate"]["successes"] == 0
        for s in result["summaries"]
    )
    # Independently checks the concrete config, not case labels or grader files.
    verifier = tmp_path / "verify.py"
    verifier.write_text(
        'import json,sys,pathlib\np=json.load(sys.stdin); d=json.loads((pathlib.Path(p["workspace"])/"config.json").read_text()); print("met" if type(d.get("port")) is int and d["port"]==8080 and d.get("log_level")=="info" else "not_met")\n'
    )
    result = evaluate(cases, f"python3.11 {verifier}")
    assert all(
        s["catch_rate"]["rate"] == 1 and s["false_hold_rate"]["rate"] == 0
        for s in result["summaries"]
    )


@pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="Docker unavailable; candidate Linux isolation unproven",
)
def test_docker_candidate_cannot_read_truth():
    task = example()
    sandbox = DockerSandbox(task)
    try:
        result = sandbox.exec(
            'test -z "$TASK_ROOT" && test ! -e /task/grader && test ! -e /task/reference && test ! -e /task/known_bad && cat config.json',
            120,
        )
        assert result.code == 0
    finally:
        sandbox.close()


def test_sealed_lift_executes_both_arms_and_refuses_drift(tmp_path):
    task = example()
    shutil.copytree(task.root, tmp_path / "config_repair")
    meta = tmp_path / "config_repair/task.yaml"
    meta.write_text(
        meta.read_text().replace("admission: smoke", "admission: capability")
    )
    plan = tmp_path / "plan.yaml"
    seal = tmp_path / "seal.json"
    out = tmp_path / "rows.jsonl"
    plan.write_text(
        'question: Does the oracle outperform the floor?\narms:\n  - "name=baseline agent=noop"\n  - "name=candidate agent=reference"\nbaseline: baseline\ncandidate: candidate\ntasks:\n  - config_repair\nsentinels:\n  - config_repair\nk: 1\nprimary_metric: pass_rate\nfalsifier: candidate_rate <= baseline_rate\npromotion_bar: candidate_rate > baseline_rate\n'
    )
    prereg.seal(plan, at="2026-10-13T12:00:00+00:00", seal_path=seal)
    text = tournament.run(plan, seal, out, 2, "local")
    assert "SUPPORTED" in text
    (tmp_path / "config_repair/prompt.md").write_text("changed")
    with pytest.raises(ValueError, match="seal drift"):
        tournament.run(plan, seal, out, 2, "local")


def test_http_transport_and_no_retry_contract(tmp_path, monkeypatch):
    """A scripted local HTTP endpoint exercises the actual REST client and tools."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    requests = []
    mode = {"rate_limit": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(payload)
            assert self.path == "/v1/chat/completions"
            assert self.headers["Authorization"] == "Bearer scripted-test-key"
            if mode["rate_limit"]:
                self.send_response(429)
                self.end_headers()
                return
            if len(requests) == 1:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "http-call",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": json.dumps({"command": REPAIR}),
                            },
                        }
                    ],
                }
                finish = "tool_calls"
            else:
                message = {"role": "assistant", "content": "complete"}
                finish = "stop"
            body = json.dumps(
                {
                    "choices": [{"message": message, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OPENAI_API_KEY", "scripted-test-key")
    agent = MinimalAgent(
        "scripted-http", endpoint=f"http://127.0.0.1:{server.server_port}/v1"
    )
    try:
        rows = run_trials(
            [example()],
            [Arm("http", agent, "scripted")],
            1,
            "local",
            tmp_path / "http.jsonl",
            "http",
        )
        assert rows[0].passed and rows[0].tokens_in == 20
        mode["rate_limit"] = True
        before = len(requests)
        rows = run_trials(
            [example()],
            [Arm("http", agent, "scripted")],
            1,
            "local",
            tmp_path / "limited.jsonl",
            "limited",
        )
        assert len(requests) == before + 1
        assert not rows[0].valid and rows[0].invalid_reason == "rate_limit"
        assert (
            "scripted-test-key"
            not in trace_path_for(tmp_path / "http.jsonl").read_text()
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
