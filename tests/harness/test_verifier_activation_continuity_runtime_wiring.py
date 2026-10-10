from __future__ import annotations

from types import SimpleNamespace

import pytest

from aether import harbor_runtime as hr
from aether import model_hooks as mh
from aether.kernel import AetherNextKernel
from aether.model_hooks import ModelHooks
from aether.persistent_runtime import (
    VERIFIER_ACTIVATION_CONTINUITY_CONTROL,
    VERIFIER_ACTIVATION_CONTINUITY_MODES,
    VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    build_persistent_runtime,
)
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.verifier_activation_continuity import (
    FRESH_CONTROL,
    PREVIOUS_RESPONSE_V1,
    SUPPORTED_MODES,
)


def _envmap() -> EnvMap:
    return EnvMap(
        task_prompt="Inspect /app/input.txt and produce the requested artifact.",
        workspace_root="/app",
        visible_files=("/app/input.txt",),
        visible_dirs=("/app",),
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "filesystem", True, ("read_file", "write_file")
            ),
            "shell": CapabilityDescriptor("shell", "shell", True, ("run_command",)),
        },
        task_metadata={"environment_probe": {"schema_version": "environment_probe.v1"}},
        network_scope="unavailable",
        file_tree="/app\n- input.txt",
        file_map_summary={"extension_counts": {".txt": 1}},
    )


def test_runtime_constants_match_provider_continuity_authority() -> None:
    assert VERIFIER_ACTIVATION_CONTINUITY_CONTROL == FRESH_CONTROL
    assert VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1 == PREVIOUS_RESPONSE_V1
    assert VERIFIER_ACTIVATION_CONTINUITY_MODES == SUPPORTED_MODES


def test_control_is_exact_compile_default_and_adds_no_realization_field() -> None:
    env = _envmap()
    implicit = build_persistent_runtime(env)
    explicit = build_persistent_runtime(
        env, verifier_activation_continuity_mode=VERIFIER_ACTIVATION_CONTINUITY_CONTROL
    )
    assert implicit.compiled is not None and explicit.compiled is not None
    assert implicit.compiled == explicit.compiled
    assert "verifier_activation_continuity_mode" not in implicit.compiled.config_realization


def test_treatment_changes_only_runtime_realization() -> None:
    env = _envmap()
    control = build_persistent_runtime(env).compiled
    treated = build_persistent_runtime(
        env,
        verifier_activation_continuity_mode=VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    ).compiled
    assert control is not None and treated is not None
    assert control.prefix_messages() == treated.prefix_messages()
    assert control.stable_prefix_sections == treated.stable_prefix_sections
    assert control.task_prompt == treated.task_prompt
    assert control.task_contract_identity == treated.task_contract_identity
    assert control.env_digest == treated.env_digest
    assert control.action_schema == treated.action_schema
    assert control.selected_capabilities == treated.selected_capabilities
    assert control.model_verifier_policy == treated.model_verifier_policy
    c = dict(control.config_realization)
    t = dict(treated.config_realization)
    assert (
        t.pop("verifier_activation_continuity_mode")
        == VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1
    )
    assert t == c


def test_invalid_runtime_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Verifier activation continuity mode"):
        build_persistent_runtime(_envmap(), verifier_activation_continuity_mode="invented")
    with pytest.raises(ValueError, match="unsupported Verifier activation continuity mode"):
        AetherNextKernel(verifier_activation_continuity_mode="invented")


class _ActivationRecordingVerifier:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def begin_verifier_activation(self, mode: str, *, run_id: str, task_id: str, activation_id: str) -> None:
        self.events.append(("begin", mode, run_id, task_id, activation_id))

    def reject_verifier_activation_candidate(self, *, run_id: str, task_id: str, activation_id: str) -> bool:
        self.events.append(("reject", run_id, task_id, activation_id))
        return False

    def end_verifier_activation(self, *, run_id: str, task_id: str, activation_id: str) -> None:
        self.events.append(("end", run_id, task_id, activation_id))

    def __call__(self, _messages, *, max_output_tokens=None) -> str:  # pragma: no cover
        raise AssertionError("provider call should be intercepted in this lifecycle test")


def test_model_hooks_activation_lifecycle_only_materializes_for_treatment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mh, "_verify_with_inspector_impl", lambda *_args, **_kwargs: "fixed")
    verifier = _ActivationRecordingVerifier()
    hooks = ModelHooks(
        verifier, verifier, run_id="run-a", task_id="task-a",
        solver_max_output_tokens=16, verifier_max_output_tokens=16,
    )
    ledger = SimpleNamespace(all_receipts=lambda: ())
    inspector = lambda _requests: []

    control = build_persistent_runtime(_envmap()).compiled
    treated = build_persistent_runtime(
        _envmap(),
        verifier_activation_continuity_mode=VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    ).compiled
    assert control is not None and treated is not None

    assert hooks.verify_with_inspector({}, control, ledger, inspector) == "fixed"  # type: ignore[arg-type]
    assert verifier.events == []

    assert hooks.verify_with_inspector({}, treated, ledger, inspector) == "fixed"  # type: ignore[arg-type]
    assert verifier.events == [
        (
            "begin",
            VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
            "run-a",
            "task-a",
            "verifier-activation-2",
        ),
        ("reject", "run-a", "task-a", "verifier-activation-2"),
        ("end", "run-a", "task-a", "verifier-activation-2"),
    ]


def test_harbor_selector_is_default_off_production_only_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(hr.VERIFIER_ACTIVATION_CONTINUITY_ENV, raising=False)
    assert (
        hr.selected_verifier_activation_continuity_mode(hr.build_selected_frontier_models)
        == hr.VERIFIER_ACTIVATION_CONTINUITY_CONTROL
    )
    monkeypatch.setenv(
        hr.VERIFIER_ACTIVATION_CONTINUITY_ENV,
        hr.VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    )
    assert (
        hr.selected_verifier_activation_continuity_mode(hr.build_selected_frontier_models)
        == hr.VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1
    )

    def offline_factory():
        raise AssertionError("factory should not be invoked")

    assert (
        hr.selected_verifier_activation_continuity_mode(offline_factory)
        == hr.VERIFIER_ACTIVATION_CONTINUITY_CONTROL
    )
    monkeypatch.setenv(hr.VERIFIER_ACTIVATION_CONTINUITY_ENV, "invented")
    with pytest.raises(RuntimeError, match=hr.VERIFIER_ACTIVATION_CONTINUITY_ENV):
        hr.selected_verifier_activation_continuity_mode(hr.build_selected_frontier_models)


def test_runtime_identity_records_verifier_arm_only_when_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Env:
        task_metadata = {}
        def digest(self) -> str:
            return "env-digest"

    class Context:
        metadata = {}
        context_id = "ctx"

    monkeypatch.delenv(hr.VERIFIER_ACTIVATION_CONTINUITY_ENV, raising=False)
    baseline = hr._runtime_identity(Context(), Env(), model_factory=hr.build_selected_frontier_models)
    assert "research_verifier_activation_continuity" not in baseline

    monkeypatch.setenv(
        hr.VERIFIER_ACTIVATION_CONTINUITY_ENV,
        hr.VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    )
    treated = hr._runtime_identity(Context(), Env(), model_factory=hr.build_selected_frontier_models)
    assert (
        treated["research_verifier_activation_continuity"]
        == hr.VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1
    )
    assert (
        treated["research_verifier_activation_continuity_authority"]
        == hr.VERIFIER_ACTIVATION_CONTINUITY_ENV
    )
