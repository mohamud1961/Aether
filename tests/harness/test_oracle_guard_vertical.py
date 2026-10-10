"""Adapter env -> runtime config -> thin loop -> model-visible request (real shell edits)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import aether.research_glm_harbor_agent as mod
from aether.envmap_builder import build_envmap_from_task
from aether.real_executor import SubprocessExecutor
from aether.runtime_ir import ActionRequest, SolverTurn
from aether.thin_loop import ThinLoopConfig, run_thin_loop

VERIFY_FAIL = "import sys\nprint('[FAIL] case')\nsys.exit(1)\n"
VERIFY_PASS = "print('ALL PASS')\n"
RUN = "python3 verify.py"
OLD = "verify_old = 1\n"


def _cmd(n: int, command: str) -> ActionRequest:
    return ActionRequest(
        action_id=f"a-{n}", kind="run_command", capability_id="shell",
        arguments={"command": command}, intent="step", expected_observation="out",
        if_fail_next="inspect",
    )


def _write(n: int, path: str, content: str) -> ActionRequest:
    return ActionRequest(
        action_id=f"a-{n}", kind="write_file", capability_id="filesystem",
        arguments={"path": path, "content": content}, intent="edit",
        expected_observation="written", if_fail_next="inspect",
    )


class _Scripted:
    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.messages: list[list[dict[str, Any]]] = []

    def solve(self, messages: list[dict[str, Any]], _compiled: Any) -> SolverTurn:
        self.messages.append(messages)
        action = self.script[len(self.messages) - 1]
        return SolverTurn(kind="act", summary="s", evidence_gap="g", actions=(action,))


def _packets(messages: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out = []
    for msgs in messages:
        for m in msgs:
            c = str(m.get("content", ""))
            if c.startswith("[context_packet]\n"):
                out.append(json.loads(c[len("[context_packet]\n"):]))
    return out


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: list[Any],
         mode: str | None, seed: dict[str, str]) -> list[dict[str, Any]]:
    root = tmp_path / "ws"
    root.mkdir(parents=True)
    for name, text in seed.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    profile = mod.g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)
    if mode is None:
        monkeypatch.delenv(mod.G4_COMPLETION_SIGNAL_ENV, raising=False)
    else:
        monkeypatch.setenv(mod.G4_COMPLETION_SIGNAL_ENV, mode)
    runtime = mod.g4_runtime_config(state_root=tmp_path / "state")
    hooks = _Scripted(script)
    envmap = build_envmap_from_task(
        str(tmp_path / "none"), "fix the program", workspace_root=str(root),
        projection_mode="factual_only",
    )
    n = len(script)
    run_thin_loop(envmap, SubprocessExecutor(str(root)), hooks, config=ThinLoopConfig(
        max_steps=n, max_solver_turns=n, max_accepted_task_actions=n,
        runtime_identity={"task_id": "t", "run_id": "v", "primary_agent_id": "primary",
                          "budgets": {"max_kernel_steps": n, "max_solver_turns": n,
                                      "max_accepted_task_actions": n}},
        solver_completion_signal_mode=runtime.solver_completion_signal_mode,
    ))
    return _packets(hooks.messages)




def _signals(tmp_path, monkeypatch, script, mode, seed):
    # one extra scripted no-op turn so the request after the last action is captured
    packets = _run(tmp_path, monkeypatch, script + [_cmd(99, "true")], mode, seed)
    return packets[len(script)].get("completion_signal")


GUARD = "verification_oracle_guard_v1"
EDIT_SCRIPT = [
    _cmd(1, RUN),
    _cmd(2, f"printf '%s\\n' \"print('ALL PASS')\" > verify.py"),
    _cmd(3, RUN),
]


def test_env_selector_validates_and_runtime_records_identity(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(mod.G4_COMPLETION_SIGNAL_ENV, raising=False)
    assert mod.g4_completion_signal_mode() == "control"
    monkeypatch.setenv(mod.G4_COMPLETION_SIGNAL_ENV, "verification_oracle_guard_v2")
    with pytest.raises(RuntimeError, match="must be one of"):
        mod.g4_completion_signal_mode()
    profile = mod.g4_kh_profile()
    monkeypatch.setenv(profile.endpoint_env, "https://example.openai.azure.com/")
    monkeypatch.setenv(profile.deployment_env, profile.model_id)
    monkeypatch.setenv(mod.G4_COMPLETION_SIGNAL_ENV, GUARD)
    runtime = mod.g4_runtime_config(state_root=tmp_path)
    assert runtime.solver_completion_signal_mode == GUARD
    assert runtime.manifest()["solver_completion_signal_mode"] == GUARD
    assert "--solver-completion-signal-mode" in runtime.cli_args()


def test_real_shell_edit_of_failing_check_reaches_model_visible_request(
    tmp_path, monkeypatch
) -> None:
    signal = _signals(tmp_path, monkeypatch, EDIT_SCRIPT, GUARD, {"verify.py": VERIFY_FAIL, "app.py": "x=1\n"})
    assert signal is not None and signal["mode"] == GUARD
    edit = signal["verification_edit_observation"]
    assert edit["verification_files_changed"] == ["verify.py"]
    assert edit["other_files_changed"] == []
    from tests.harness.test_model_visible_hygiene import _hits
    assert _hits(json.dumps(signal)) == set()


def test_production_file_also_changed_has_no_observation(tmp_path, monkeypatch) -> None:
    script = [
        _cmd(1, RUN),
        _cmd(2, "echo 'x=2' > app.py"),
        _cmd(3, f"printf '%s\\n' \"print('ALL PASS')\" > verify.py"),
        _cmd(4, RUN),
    ]
    signal = _signals(tmp_path, monkeypatch, script, GUARD, {"verify.py": VERIFY_FAIL, "app.py": "x=1\n"})
    assert signal is not None and "verification_edit_observation" not in signal


def test_write_file_tool_edit_plus_production_write_has_no_observation(tmp_path, monkeypatch) -> None:
    script = [_cmd(1, RUN), _write(2, "app.py", "x=2\n"), _write(3, "verify.py", VERIFY_PASS), _cmd(4, RUN)]
    signal = _signals(tmp_path, monkeypatch, script, GUARD, {"verify.py": VERIFY_FAIL, "app.py": "x=1\n"})
    assert signal is not None and "verification_edit_observation" not in signal


def test_write_file_tool_edit_of_check_only_is_reported(tmp_path, monkeypatch) -> None:
    script = [_cmd(1, RUN), _write(2, "verify.py", VERIFY_PASS), _cmd(3, RUN)]
    signal = _signals(tmp_path, monkeypatch, script, GUARD, {"verify.py": VERIFY_FAIL})
    assert signal["verification_edit_observation"]["verification_files_changed"] == ["verify.py"]


def test_never_failing_check_has_no_observation(tmp_path, monkeypatch) -> None:
    script = [_cmd(1, RUN), _write(2, "verify.py", VERIFY_PASS + "# t\n"), _cmd(3, RUN)]
    signal = _signals(tmp_path, monkeypatch, script, GUARD, {"verify.py": VERIFY_PASS})
    assert signal is not None and "verification_edit_observation" not in signal


def test_control_emits_nothing_and_v2_has_no_observation(tmp_path, monkeypatch) -> None:
    seed = {"verify.py": VERIFY_FAIL}
    assert _signals(tmp_path / "c", monkeypatch, EDIT_SCRIPT, None, seed) is None
    v2 = _signals(tmp_path / "v", monkeypatch, EDIT_SCRIPT, "verification_authority_v2", seed)
    assert v2 is not None and v2["mode"] == "verification_authority_v2"
    assert "verification_edit_observation" not in v2


def test_new_solver_authored_arbitrary_named_oracle_reaches_model_visible_request(
    tmp_path, monkeypatch
) -> None:
    script = [
        _write(1, "repro_probe.py", "import sys\nprint('PASS setup')\nsys.exit(1)\n"),
        _cmd(2, "python3 repro_probe.py"),
        _write(3, "repro_probe.py", "print('PASS setup')\nprint('FAILURES: none')\n"),
        _cmd(4, "python3 repro_probe.py"),
    ]
    signal = _signals(
        tmp_path, monkeypatch, script, GUARD, {"app.py": "x=1\n"}
    )
    assert signal is not None
    edit = signal["verification_edit_observation"]
    assert edit["verification_files_changed"] == ["repro_probe.py"]
    assert edit["other_files_changed"] == []
