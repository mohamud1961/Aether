from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aether.runners import docker_runner
from aether.runners.result_admission import evaluate_run_admission


_SHA_A = "a" * 64
_SHA_B = "b" * 64


def _decision(**updates):
    values = {
        "source_identity": {"clean": True},
        "provider_valid": True,
        "protocol_valid": True,
        "grader_error": None,
        "reward_source": "reward_txt",
        "task_package_sha256_start": _SHA_A,
        "task_package_sha256_grader": _SHA_A,
        "runtime_image_sha256_expected": _SHA_B,
        "runtime_image_sha256_container": _SHA_B,
        "teardown_verified_absent": True,
        "evidence_surfaces_clean": True,
    }
    values.update(updates)
    return evaluate_run_admission(**values)


def test_valid_pass_or_fail_grader_row_is_admitted() -> None:
    decision = _decision()
    assert decision.run_valid is True
    assert decision.performance_row_admitted is True
    assert decision.grader_status == "valid"
    assert decision.process_leak is False
    assert decision.reasons == ()


def test_missing_reward_is_invalid_not_a_task_failure() -> None:
    decision = _decision(
        grader_error="reward.txt missing or empty",
        reward_source="reward_txt_missing",
    )
    assert decision.run_valid is False
    assert decision.performance_row_admitted is False
    assert decision.grader_status == "invalid"
    assert "grader_invalid" in decision.reasons
    assert "grader_reward_source_invalid" in decision.reasons


def test_task_change_makes_grader_stale() -> None:
    decision = _decision(task_package_sha256_grader="c" * 64)
    assert decision.grader_status == "stale"
    assert decision.performance_row_admitted is False
    assert "grader_task_package_stale" in decision.reasons


def test_unverified_teardown_is_a_process_leak() -> None:
    decision = _decision(teardown_verified_absent=False)
    assert decision.process_leak is True
    assert decision.performance_row_admitted is False
    assert "container_teardown_unverified" in decision.reasons


def test_hidden_surface_or_image_mismatch_fails_closed() -> None:
    decision = _decision(
        evidence_surfaces_clean=False,
        runtime_image_sha256_container="d" * 64,
    )
    assert decision.performance_row_admitted is False
    assert "agent_visible_hidden_surface" in decision.reasons
    assert "runtime_image_identity_mismatch" in decision.reasons


def test_docker_identity_normalization() -> None:
    assert docker_runner._normalise_docker_sha256("sha256:" + _SHA_A) == _SHA_A
    assert docker_runner._normalise_docker_sha256(_SHA_B.upper()) == _SHA_B
    assert docker_runner._normalise_docker_sha256("not-a-digest") == ""


def test_remove_container_requires_verified_absence(monkeypatch) -> None:
    remove = subprocess.CompletedProcess(
        args=["docker", "rm"], returncode=0, stdout="cid\n", stderr=""
    )
    inspect = subprocess.CompletedProcess(
        args=["docker", "inspect"], returncode=1, stdout="", stderr="not found"
    )

    monkeypatch.setattr(
        docker_runner,
        "_checked_process",
        lambda *_args, **_kwargs: (remove, None),
    )
    monkeypatch.setattr(docker_runner.subprocess, "run", lambda *_args, **_kwargs: inspect)

    evidence = docker_runner._remove_container_with_evidence("cid")
    assert evidence["verified_absent"] is True
    assert evidence["remove_exit"] == 0
    assert evidence["inspect_exit"] == 1


def test_successful_remove_without_inspect_proof_is_not_admitted(monkeypatch) -> None:
    remove = subprocess.CompletedProcess(
        args=["docker", "rm"], returncode=0, stdout="cid\n", stderr=""
    )

    monkeypatch.setattr(
        docker_runner,
        "_checked_process",
        lambda *_args, **_kwargs: (remove, None),
    )

    def fail_inspect(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="docker inspect", timeout=15)

    monkeypatch.setattr(docker_runner.subprocess, "run", fail_inspect)
    evidence = docker_runner._remove_container_with_evidence("cid")
    assert evidence["verified_absent"] is False
    assert "TimeoutExpired" in evidence["inspect_error"]


def test_hidden_surface_probe_reports_visible_paths(monkeypatch) -> None:
    probe = subprocess.CompletedProcess(
        args=["docker", "exec"], returncode=0, stdout="/tests\n/solution\n", stderr=""
    )
    monkeypatch.setattr(
        docker_runner,
        "_checked_process",
        lambda *_args, **_kwargs: (probe, None),
    )
    result = docker_runner._probe_agent_hidden_surfaces("cid")
    assert result["clean"] is False
    assert result["visible_paths"] == ["/tests", "/solution"]


def test_provider_and_protocol_validity_are_separate() -> None:
    provider_valid, protocol_valid = docker_runner._provider_protocol_validity(
        record_error="", classifier_label="none", model_parse_errors=["bad solver JSON"],
    )
    assert provider_valid is True
    assert protocol_valid is False

    provider_valid, protocol_valid = docker_runner._provider_protocol_validity(
        record_error="multiple_distinct_assistant_outputs",
        classifier_label="provider_protocol_failure",
        model_parse_errors=[],
    )
    assert provider_valid is False
    assert protocol_valid is False


def test_reward_txt_zero_serializes_as_admitted_task_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        docker_runner, "_read_container_text_artifact",
        lambda *_args, **_kwargs: ("0\n", None),
    )
    reward, grader_error, reward_source = docker_runner._resolve_grader_reward(
        container_id="cid",
        task_dir=str(tmp_path),
        grader_exit=1,
        grader_error=None,
    )
    decision = _decision(grader_error=grader_error, reward_source=reward_source)
    record = json.loads(json.dumps({
        "reward": reward,
        "grader_error": grader_error,
        "reward_source": reward_source,
        **decision.to_dict(),
    }))
    assert record["reward"] == 0.0
    assert record["grader_error"] is None
    assert record["reward_source"] == "reward_txt"
    assert record["grader_status"] == "valid"
    assert record["run_valid"] is True
    assert record["performance_row_admitted"] is True


def test_malformed_reward_txt_is_invalid_not_task_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        docker_runner, "_read_container_text_artifact",
        lambda *_args, **_kwargs: ("0.5\n", None),
    )
    reward, grader_error, reward_source = docker_runner._resolve_grader_reward(
        container_id="cid",
        task_dir=str(tmp_path),
        grader_exit=0,
        grader_error=None,
    )
    decision = _decision(grader_error=grader_error, reward_source=reward_source)
    assert reward == 0.0
    assert grader_error is not None and "invalid value" in grader_error
    assert reward_source == "reward_txt_invalid"
    assert decision.grader_status == "invalid"
    assert decision.performance_row_admitted is False


def test_persistent_docker_kernel_builder_selects_persistent_primary() -> None:
    kernel = docker_runner._build_kernel_for_architect_mode(
        architect_mode="persistent_v0",
        architect_model=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Architect must not be constructed for PERSISTENT")
        ),
        hooks=None,
        max_steps=7,
        snapshot_callback=None,
        snapshot_steps=(),
        runtime_identity={"task_id": "t", "run_id": "r", "primary_agent_id": "p"},
    )
    assert kernel.persistent_primary is True
    assert kernel.architect_v3_architect is None
    assert kernel.runtime_identity["task_id"] == "t"
    assert kernel.max_steps == 7


def test_reward_artifact_transport_failure_is_not_mislabeled_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        docker_runner, "_read_container_text_artifact",
        lambda *_args, **_kwargs: (None, "docker_cp_exit_1: daemon unavailable"),
    )
    reward, error, source = docker_runner._resolve_grader_reward(
        container_id="cid", task_dir=str(tmp_path), grader_exit=0, grader_error=None,
    )
    assert reward == 0.0
    assert source == "reward_txt_error"
    assert error is not None and "artifact read failed" in error
    assert "daemon unavailable" in error


def test_reward_artifact_true_absence_remains_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        docker_runner, "_read_container_text_artifact",
        lambda *_args, **_kwargs: (None, "missing"),
    )
    reward, error, source = docker_runner._resolve_grader_reward(
        container_id="cid", task_dir=str(tmp_path), grader_exit=0, grader_error=None,
    )
    assert reward == 0.0
    assert error == "reward.txt missing or empty"
    assert source == "reward_txt_missing"


def test_container_artifact_reader_uses_docker_cp_without_exec(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(list(args))
        assert args[:2] == ["docker", "cp"]
        Path(args[-1]).write_text("0\n", encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(docker_runner.subprocess, "run", fake_run)
    text, error = docker_runner._read_container_text_artifact(
        "cid", "/logs/verifier/reward.txt"
    )
    assert text == "0\n"
    assert error is None
    assert calls == [[
        "docker", "cp", "cid:/logs/verifier/reward.txt", calls[0][-1]
    ]]


def test_container_artifact_reader_distinguishes_missing_from_transport_error(monkeypatch) -> None:
    responses = iter([
        subprocess.CompletedProcess(
            args=["docker", "cp"], returncode=1, stdout="",
            stderr="Could not find the file /logs/verifier/reward.txt in container cid",
        ),
        subprocess.CompletedProcess(
            args=["docker", "cp"], returncode=1, stdout="",
            stderr="error from daemon: connection reset",
        ),
    ])
    monkeypatch.setattr(docker_runner.subprocess, "run", lambda *_a, **_k: next(responses))
    text, error = docker_runner._read_container_text_artifact("cid", "/logs/verifier/reward.txt")
    assert text is None and error == "missing"
    text, error = docker_runner._read_container_text_artifact("cid", "/logs/verifier/reward.txt")
    assert text is None and error is not None and error.startswith("docker_cp_exit_1")
