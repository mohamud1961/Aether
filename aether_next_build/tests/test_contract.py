"""Tests for aether_next.task_contract and aether_next.contract_compile."""
from __future__ import annotations

import json

import pytest

from aether_next.contract_compile import (
    contract_to_eval_index,
    contract_to_objective_graph,
)
from aether_next.runtime_ir import EnvMap
from aether_next.task_contract import (
    ContractCheck,
    ContractDeliverable,
    ContractSchema,
    ContractThreshold,
    TaskContract,
    parse_task_contract,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_envmap() -> EnvMap:
    return EnvMap(
        task_prompt="Build an app.",
        workspace_root="/app",
    )


def _sample_contract() -> TaskContract:
    return TaskContract(
        task_understanding="Build a JSON results file.",
        deliverables=(
            ContractDeliverable(path="results.json", description="output"),
        ),
        output_schemas=(
            ContractSchema(
                target="results.json",
                required_keys=("G", "2D"),
                value_types={"G": "float", "2D": "float"},
            ),
        ),
        thresholds=(
            ContractThreshold(
                name="model_size",
                comparator="<",
                target=150.0,
                unit="MB",
                source="file_size_bytes:/app/model.bin",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# test_parse_minimal_contract
# ---------------------------------------------------------------------------

class TestParseMinimalContract:
    def test_basic_parse(self) -> None:
        raw = json.dumps({
            "task_understanding": "Build a results file.",
            "deliverables": [
                {"path": "/app/results.json", "kind": "file", "required": True}
            ],
            "output_schemas": [
                {
                    "target": "/app/results.json",
                    "required_keys": ["G", "2D"],
                    "value_types": {"G": "float"},
                }
            ],
            "thresholds": [
                {
                    "name": "model_size",
                    "comparator": "<",
                    "target": 150,
                    "unit": "MB",
                    "source": "file_size_bytes:/app/model.bin",
                }
            ],
            "workflow": "direct_build",
            "capabilities": ["shell", "filesystem"],
            "success_definition": "results.json exists with G and 2D keys.",
        })
        contract = parse_task_contract(raw, workspace_root="/app")

        assert isinstance(contract, TaskContract)
        assert contract.task_understanding == "Build a results file."
        assert len(contract.deliverables) == 1
        assert contract.deliverables[0].path == "results.json"
        assert contract.deliverables[0].required is True

        assert len(contract.output_schemas) == 1
        assert contract.output_schemas[0].required_keys == ("G", "2D")
        assert contract.output_schemas[0].target == "results.json"

        assert len(contract.thresholds) == 1
        th = contract.thresholds[0]
        assert th.name == "model_size"
        assert th.comparator == "<"
        assert th.target == 150.0
        assert th.unit == "MB"
        assert th.source == "file_size_bytes:/app/model.bin"

        assert contract.workflow == "direct_build"
        assert "shell" in contract.capabilities

    def test_tolerates_fenced_json(self) -> None:
        raw = "```json\n" + json.dumps({
            "task_understanding": "Do something.",
            "deliverables": [],
        }) + "\n```"
        contract = parse_task_contract(raw)
        assert contract.task_understanding == "Do something."

    def test_rejects_missing_understanding(self) -> None:
        raw = json.dumps({"deliverables": []})
        with pytest.raises(Exception, match="task_understanding"):
            parse_task_contract(raw)


# ---------------------------------------------------------------------------
# test_contract_to_objective_graph_populates_deliverables
# ---------------------------------------------------------------------------

class TestContractToObjectiveGraph:
    def test_deliverables_and_schema(self) -> None:
        contract = _sample_contract()
        envmap = _minimal_envmap()
        og = contract_to_objective_graph(contract, envmap)

        assert len(og.deliverables) == 1
        assert og.deliverables[0].path == "results.json"
        assert og.deliverables[0].required is True

        assert og.output_schema_target == "results.json"
        # Schema maps required keys.
        assert "G" in og.output_schema
        assert "2D" in og.output_schema

    def test_integrity_obligation_always_present(self) -> None:
        contract = _sample_contract()
        og = contract_to_objective_graph(contract, _minimal_envmap())
        ids = [o.obligation_id for o in og.obligations]
        assert "integrity:clean" in ids
        assert "artifact:results.json" in ids

    def test_skips_test_paths(self) -> None:
        contract = TaskContract(
            task_understanding="Build.",
            deliverables=(
                ContractDeliverable(path="tests/test_foo.py"),
                ContractDeliverable(path="output.json"),
            ),
        )
        og = contract_to_objective_graph(contract, _minimal_envmap())
        paths = [d.path for d in og.deliverables]
        assert "output.json" in paths
        assert not any("tests/" in p for p in paths)


# ---------------------------------------------------------------------------
# test_contract_to_eval_index_generates_checks
# ---------------------------------------------------------------------------

class TestContractToEvalIndex:
    def test_generates_existence_and_schema_checks(self) -> None:
        contract = _sample_contract()
        envmap = _minimal_envmap()
        ei = contract_to_eval_index(contract, envmap)

        commands = [c.command for c in ei.checks]
        # File existence check.
        assert any("test -e results.json" in cmd for cmd in commands), (
            f"expected file existence check, got: {commands}"
        )
        # Schema key check.
        assert any("'G'" in cmd and "'2D'" in cmd for cmd in commands), (
            f"expected schema key check, got: {commands}"
        )
        # All authoritative.
        for check in ei.checks:
            assert check.authoritative is True
            assert check.origin == "contract"

    def test_csv_schema_check_uses_csv_headers_not_json(self) -> None:
        contract = TaskContract(
            task_understanding="Build a CSV summary.",
            deliverables=(ContractDeliverable(path="summary.csv"),),
            output_schemas=(
                ContractSchema(
                    target="summary.csv",
                    required_keys=("date", "count"),
                    value_types={"date": "str", "count": "int"},
                ),
            ),
        )
        ei = contract_to_eval_index(contract, _minimal_envmap())

        schema_checks = [check for check in ei.checks if check.label == "schema:summary.csv"]
        assert len(schema_checks) == 1
        assert "csv.DictReader" in schema_checks[0].command
        assert "json.load" not in schema_checks[0].command


# ---------------------------------------------------------------------------
# test_command_check_rejects_unsafe
# ---------------------------------------------------------------------------

class TestCommandChecksAreNotCompiled:
    """Model-authored command checks are unreliable (may contain literal
    placeholders like ``<html_file>``).  The harness must never compile
    kind=="command" ContractChecks into gate checks."""

    def test_command_checks_are_not_compiled(self) -> None:
        """A contract with a command check AND a deliverable should produce
        only the harness-constructed existence check, not the command."""
        contract = TaskContract(
            task_understanding="Filter HTML files.",
            deliverables=(
                ContractDeliverable(path="out.txt", description="output"),
            ),
            required_checks=(
                ContractCheck(
                    kind="command",
                    command="python /app/filter.py <html_file>",
                    detail="run filter",
                ),
            ),
        )
        ei = contract_to_eval_index(contract, _minimal_envmap())
        commands = [c.command for c in ei.checks]
        # Existence check for the deliverable must be present.
        assert any("test -e out.txt" in cmd for cmd in commands), (
            f"expected existence check for out.txt, got: {commands}"
        )
        # The model's free-form command must NOT appear.
        assert not any("filter.py" in cmd for cmd in commands), (
            f"model command check should not be compiled, got: {commands}"
        )
        assert not any("<html_file>" in cmd for cmd in commands), (
            f"placeholder should not appear in checks, got: {commands}"
        )

    def test_safe_command_also_not_compiled(self) -> None:
        """Even a safe-looking command check must not be compiled."""
        contract = TaskContract(
            task_understanding="Safe but still model-authored.",
            deliverables=(),
            required_checks=(
                ContractCheck(
                    kind="command",
                    command="test -f /app/out.txt",
                ),
            ),
        )
        ei = contract_to_eval_index(contract, _minimal_envmap())
        assert len(ei.checks) == 0

    def test_non_command_required_checks_are_not_compiled(self) -> None:
        """All model-authored required_checks are advisory, including
        non-command kinds that previously leaked as explicit checks."""
        contract = TaskContract(
            task_understanding="Write a CSV.",
            deliverables=(),
            required_checks=(
                ContractCheck(
                    kind="schema_keys",
                    target="summary.csv",
                    detail="Authoritative evaluation check visible in the environment.",
                ),
                ContractCheck(
                    kind="file_exists",
                    target="summary.csv",
                    detail="summary.csv exists",
                ),
            ),
        )

        ei = contract_to_eval_index(contract, _minimal_envmap())

        assert ei.checks == ()


# ---------------------------------------------------------------------------
# test_size_threshold_to_check
# ---------------------------------------------------------------------------

class TestSizeThresholdToCheck:
    def test_mb_threshold_generates_check(self) -> None:
        contract = TaskContract(
            task_understanding="Size limited.",
            deliverables=(
                ContractDeliverable(path="model.bin"),
            ),
            thresholds=(
                ContractThreshold(
                    name="model_size",
                    comparator="<",
                    target=150.0,
                    unit="MB",
                    source="file_size_bytes:/app/model.bin",
                ),
            ),
        )
        ei = contract_to_eval_index(contract, _minimal_envmap())
        # Find the size check.
        size_checks = [c for c in ei.checks if "stat" in c.command]
        assert len(size_checks) == 1
        cmd = size_checks[0].command
        # 150 MB = 150 * 1024 * 1024 = 157286400
        assert "157286400" in cmd
        assert "-lt" in cmd
        assert "model.bin" in cmd


# ---------------------------------------------------------------------------
# test_threshold_measurability_filter
# ---------------------------------------------------------------------------

class TestThresholdMeasurabilityFilter:
    def test_non_measurable_threshold_excluded_from_og(self) -> None:
        """An accuracy threshold (non-measurable, no file_size_bytes: source)
        must NOT appear in og.thresholds, but a file_size one must."""
        contract = TaskContract(
            task_understanding="Build something.",
            deliverables=(
                ContractDeliverable(path="model.bin"),
            ),
            thresholds=(
                ContractThreshold(
                    name="accuracy",
                    comparator=">=",
                    target=0.95,
                    unit="",
                    source="eval_metric:accuracy",
                ),
                ContractThreshold(
                    name="model_size",
                    comparator="<",
                    target=150.0,
                    unit="MB",
                    source="file_size_bytes:/app/model.bin",
                ),
            ),
        )
        og = contract_to_objective_graph(contract, _minimal_envmap())

        threshold_names = [t.name for t in og.thresholds]
        assert "model_size" in threshold_names, (
            f"file_size threshold missing from og.thresholds: {threshold_names}"
        )
        assert "accuracy" not in threshold_names, (
            f"non-measurable 'accuracy' threshold should NOT be in og.thresholds: {threshold_names}"
        )
