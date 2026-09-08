from aether.compiler_prefix import protocol_card_sections


def test_solver_keeps_only_aether_specific_bootstrap_and_lifecycle_semantics() -> None:
    sections = dict(protocol_card_sections())
    semantics = sections["tool_semantics"]
    assert "Use bootstrap_acquire for dependency installation" in semantics
    assert "launch_process" in semantics
    assert "start_job for a detached/persistent job or service" in semantics
    assert "probe_job" in semantics
    assert "nohup" in semantics
    assert "task strategy" not in semantics.lower()


def test_production_parser_rejects_retired_capability_id() -> None:
    import json
    import pytest
    from aether.model_hooks import ModelOutputError
    from aether.model_parse import parse_solver_turn
    payload = {
        "kind": "act",
        "action": {
            "kind": "read_file",
            "capability_id": "filesystem",
            "arguments": {"path": "README.md"},
        },
    }
    with pytest.raises(ModelOutputError):
        parse_solver_turn(json.dumps(payload))


def test_report_blocker_requires_facts_not_harness_design() -> None:
    import json
    from aether.model_parse import parse_solver_turn
    turn = parse_solver_turn(json.dumps({
        "kind": "act",
        "action": {
            "kind": "report_blocker",
            "arguments": {
                "blocker": "required executable is unavailable",
                "evidence": "command lookup returned missing",
            },
        },
    }))
    assert turn.actions[0].arguments == {
        "blocker": "required executable is unavailable",
        "evidence": "command lookup returned missing",
    }


def test_terminal_actions_restore_persistent_terminal_mechanical_owner() -> None:
    import json
    from aether.model_parse import parse_solver_turn

    cases = {
        "start_terminal_session": {"session_name": "vm", "command": "sh"},
        "terminal_send": {"session_id": "session-1", "data": "root"},
        "terminal_read": {"session_id": "session-1"},
        "terminal_wait": {"session_id": "session-1"},
        "terminal_interrupt": {"session_id": "session-1"},
        "terminal_close": {"session_id": "session-1"},
    }
    for kind, arguments in cases.items():
        turn = parse_solver_turn(json.dumps({
            "kind": "act",
            "action": {"kind": kind, "arguments": arguments},
        }))
        assert turn.actions[0].capability_id == "persistent_terminal", kind


def test_solver_prefix_does_not_duplicate_native_action_schema() -> None:
    """Provider-native strict tool schema is the sole model-visible action catalogue."""
    from aether.pcr_runtime import build_pcr_runtime
    from aether.runtime_ir import EnvMap

    env = EnvMap(task_prompt="Create result.txt", workspace_root="/app")
    # Preserve this test's purpose without relying on task semantics: use the
    # normal factual capability population helper when the bare EnvMap has none.
    from aether.envmap_builder import build_envmap_from_task
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "instruction.md").write_text("Create result.txt", encoding="utf-8")
        observed = build_envmap_from_task(str(root), "Create result.txt", workspace_root="/app", projection_mode="factual_only")
    resolved = build_pcr_runtime(observed)
    assert resolved.compiled is not None
    prefix = resolved.compiled.prefix_messages()
    assert not any("[action_schema]" in row["content"] for row in prefix)
    assert any("provided native function schemas" in row["content"] for row in prefix)


def test_solver_prefix_does_not_duplicate_native_turn_schema() -> None:
    from aether.envmap_builder import build_envmap_from_task
    from aether.pcr_runtime import build_pcr_runtime
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); (root / "instruction.md").write_text("Create result.txt", encoding="utf-8")
        env=build_envmap_from_task(str(root), "Create result.txt", workspace_root="/app", projection_mode="factual_only")
    resolved=build_pcr_runtime(env); assert resolved.compiled is not None
    prefix=resolved.compiled.prefix_messages()
    assert not any("[solver_turn_contract]" in row["content"] for row in prefix)
    assert any("[completion_controls]" in row["content"] for row in prefix)


def test_solver_prefix_does_not_duplicate_kernel_identity_contract() -> None:
    from aether.envmap_builder import build_envmap_from_task
    from aether.pcr_runtime import build_pcr_runtime
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); (root / "instruction.md").write_text("Create result.txt", encoding="utf-8")
        env=build_envmap_from_task(str(root), "Create result.txt", workspace_root="/app", projection_mode="factual_only")
    resolved=build_pcr_runtime(env); assert resolved.compiled is not None
    prefix=resolved.compiled.prefix_messages()
    assert not any("[kernel_contract]" in row["content"] for row in prefix)
    assert any("The Kernel executes actions and preserves reality. It does not choose your strategy." in row["content"] for row in prefix)
