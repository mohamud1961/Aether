from types import SimpleNamespace

from runner.aether2.compactor import build_fact_ledger, rebase, should_rebase
from runner.aether2.context import ContextManager
from runner.aether2.delta import build_evidence_ledger, record_check_results, record_verifier_report


class FakeModelClient:
    def call(self, messages, tools, *, cache_prefix_len):
        assert isinstance(messages, list)
        assert tools == []
        assert cache_prefix_len == 0
        return {"output_text": "Done: inspected logs. Next: verify artifact. Risk: timeout."}


def test_should_rebase_fires_at_threshold_or_model_request() -> None:
    assert should_rebase(0.60, False) is True
    assert should_rebase(0.59, True) is True
    assert should_rebase(0.59, False) is False


def test_build_fact_ledger_contains_written_files_and_hashes() -> None:
    evidence_ledger = build_evidence_ledger(["task complete"])
    evidence_ledger = record_check_results(
        evidence_ledger,
        requirement="task complete",
        check_results=[
            SimpleNamespace(
                command="pytest -q",
                exit_code=1,
                stdout="",
                stderr="failed",
                cwd="/workspace",
                duration_sec=0.2,
                timed_out=False,
                error_kind=None,
                error_reason_code=None,
            )
        ],
        step=5,
        raw_log_path="/tmp/check.log",
    )
    evidence_ledger = record_verifier_report(
        evidence_ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="task complete",
                    verdict="unverifiable",
                    evidence="need a stronger semantic verification signal",
                ),
            ),
            reason_codes=("needs_semantic_check",),
            summary="not enough visible proof",
        ),
        verifier_ref="verifier:step=6",
    )
    delta_state = SimpleNamespace(
        files={"a.txt": "sha-a", "b.txt": "sha-b"},
        artifact_registry={"out.txt": {"path": "out.txt"}},
        job_registry={"job-1": {"status": "running", "priority": 2}},
        session_registry={"s1": {"status": "alive", "screen": "ready"}},
        service_registry={"web": {"status": "ready", "port": 80}},
        process_registry={"pid-1": {"status": "alive", "pid": 123}},
        installed_packages=["uv", "python3", "tmux"],
        nonzero_exits=[{"cmd": "z", "exit_code": 2}, {"cmd": "a", "exit_code": 1}],
        evidence_ledger=evidence_ledger,
    )

    ledger = build_fact_ledger(delta_state)

    assert ledger["written_files"] == [
        {"path": "a.txt", "sha256": "sha-a"},
        {"path": "b.txt", "sha256": "sha-b"},
    ]
    assert ledger["artifacts"] == ["out.txt"]
    assert ledger["jobs"]["job-1"]["status"] == "running"
    assert ledger["installed_packages"] == ["python3", "tmux", "uv"]
    assert [item["cmd"] for item in ledger["nonzero_exits"]] == ["a", "z"]
    assert ledger["processes"]["pid-1"]["pid"] == 123
    assert ledger["evidence_ledger"]["requirements"][0]["status"] == "contradicted"
    assert ledger["evidence_ledger"]["requirements"][0]["verifier_blockers"] == [
        "need a stronger semantic verification signal"
    ]
    assert ledger["evidence_ledger"]["repeated_failure_families"][0]["family"] == "check_exit_nonzero"


def test_rebase_builds_small_prefix_and_preserves_recent_turns() -> None:
    context = ContextManager(
        delta_state=SimpleNamespace(
            files={"artifact.txt": "sha-1"},
            artifact_registry={"artifact.txt": {"path": "artifact.txt"}},
            job_registry={},
            session_registry={},
            service_registry={},
            process_registry={},
            installed_packages=["python3"],
            nonzero_exits=[],
            evidence_ledger=build_evidence_ledger(["artifact exists"]),
        )
    )
    context.build_prefix(
        system_prompt="system",
        task_instruction="complete the task",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[{"function": {"name": "run_command"}}],
    )
    for idx in range(15):
        context.append_turn({"role": "assistant", "content": f"turn {idx}"})

    rebased = rebase(context, FakeModelClient())

    assert rebased.prefix is not None
    assert rebased.prefix.token_estimate <= 20000
    prefix_texts = [message["content"] for message in rebased.prefix.messages]
    assert any("artifact.txt" in text for text in prefix_texts)
    assert any("Done: inspected logs." in text for text in prefix_texts)
    assert "turn 4" not in "".join(prefix_texts)
    assert "turn 5" in "".join(prefix_texts)
    assert "turn 14" in "".join(prefix_texts)


def test_rebase_preserves_evidence_ledger_in_fact_ledger_prefix() -> None:
    evidence_ledger = build_evidence_ledger(["artifact exists"])
    evidence_ledger = record_verifier_report(
        evidence_ledger,
        report=SimpleNamespace(
            requirements=(
                SimpleNamespace(
                    requirement="artifact exists",
                    verdict="satisfied",
                    evidence="artifact.txt is present with the expected contents",
                ),
            ),
            reason_codes=(),
            summary="verified",
        ),
        verifier_ref="verifier:step=9",
    )
    context = ContextManager(
        delta_state=SimpleNamespace(
            files={"artifact.txt": "sha-1"},
            artifact_registry={"artifact.txt": {"path": "artifact.txt"}},
            job_registry={},
            session_registry={},
            service_registry={},
            process_registry={},
            installed_packages=[],
            nonzero_exits=[],
            evidence_ledger=evidence_ledger,
        )
    )
    context.build_prefix(
        system_prompt="system",
        task_instruction="complete the task",
        orientation={"cwd": "/tmp/work"},
        tool_schemas=[{"function": {"name": "run_command"}}],
    )
    context.append_turn({"role": "assistant", "content": "verified artifact.txt"})

    rebased = rebase(context, FakeModelClient())

    fact_ledger_blocks = [
        message["content"]
        for message in rebased.prefix.messages
        if "[deterministic_fact_ledger]" in message["content"]
    ]
    assert len(fact_ledger_blocks) == 1
    assert '"evidence_ledger"' in fact_ledger_blocks[0]
    assert '"status":"proven"' in fact_ledger_blocks[0]
    assert '"requirement":"artifact exists"' in fact_ledger_blocks[0]
