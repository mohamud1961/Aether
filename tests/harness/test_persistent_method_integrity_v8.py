from pathlib import Path
import tempfile

from aether.envmap_builder import build_envmap_from_task
from aether.persistent_runtime import (
    PERSISTENT_VERIFIER_CONSTITUTION,
    PRIMARY_AGENT_CONSTITUTION,
    build_persistent_runtime,
)


def _runtime_for(prompt: str):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "instruction.md").write_text(prompt, encoding="utf-8")
        env = build_envmap_from_task(
            str(root),
            prompt,
            workspace_root="/app",
            projection_mode="factual_only",
        )
    resolved = build_persistent_runtime(env)
    assert resolved.compiled is not None
    return resolved.compiled


def test_primary_constitution_makes_task_method_constraints_global_invariants() -> None:
    assert "method, interface boundary, and stated unknown as a global invariant" in PRIMARY_AGENT_CONSTITUTION
    assert "do not inspect or use implementation internals, hidden ground truth" in PRIMARY_AGENT_CONSTITUTION
    assert "Verification must use evidence admissible under the same task-defined method" in PRIMARY_AGENT_CONSTITUTION


def test_verifier_constitution_rejects_method_dirty_completion() -> None:
    assert "Method integrity is correctness" in PERSISTENT_VERIFIER_CONSTITUTION
    assert "actions bypass it" in PERSISTENT_VERIFIER_CONSTITUTION
    assert "Inspect history if unsure" in PERSISTENT_VERIFIER_CONSTITUTION


def test_method_integrity_rules_are_visible_without_semantic_compilation() -> None:
    prompt = (
        "You can query a function through its public API. "
        "Recover the result using only that interface; internal weights are unknown."
    )
    runtime = _runtime_for(prompt)
    prefix = "\n".join(row["content"] for row in runtime.prefix_messages())
    assert prompt in prefix
    assert "do not inspect or use implementation internals, hidden ground truth" in prefix
    assert runtime.config_realization["task_semantic_compiler"] is False
    assert runtime.verifier_identity_prompt == PERSISTENT_VERIFIER_CONSTITUTION
