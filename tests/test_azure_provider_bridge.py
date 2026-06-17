from __future__ import annotations

import subprocess
import sys

import yaml

from runner.benchmark_adapter_letta_native import native_preflight, write_azure_equivalent_suite
from runner.model_client import AZURE_ENV_ENDPOINT, AZURE_ENV_GPT54_MINI_DEPLOYMENT, AZURE_ENV_GPT54_MINI_KEY


def test_letta_native_preflight_separates_azure_judge_from_letta_service_creds(monkeypatch, tmp_path):
    suite_yaml = tmp_path / "filesystem_code.yaml"
    suite_yaml.write_text(
        "\n".join(
            [
                "name: filesystem-code",
                "description: test suite",
                "dataset: datasets/filesystem_code.jsonl",
                "target:",
                "  kind: letta_code",
                "  base_url: https://api.letta.com/",
                "  working_dir: files",
                "graders:",
                "  rubric_check:",
                "    kind: model_judge",
                "    prompt_path: rubric.txt",
                "    model: gpt-5-mini",
                "    provider: openai",
                "gate:",
                "  kind: simple",
                "  metric_key: rubric_check",
                "  aggregation: avg_score",
                "  op: gte",
                "  value: 0.7",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("runner.benchmark_adapter_letta_native.shutil.which", lambda _: "/tmp/letta-evals")
    monkeypatch.setattr(
        "runner.benchmark_adapter_letta_native.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout="ok\n", stderr=""),
    )
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.delenv("LETTA_PROJECT_ID", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv(AZURE_ENV_ENDPOINT, "https://example-resource.openai.azure.com")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_DEPLOYMENT, "custom-mini-deployment")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_KEY, "secret")

    preflight = native_preflight(upstream_root=tmp_path, suite_yaml=suite_yaml, python_executable=sys.executable)

    assert preflight["official_native"]["ready"] is False
    assert "missing_env_letta_api_key" in preflight["official_native"]["blockers"]
    assert "missing_env_letta_project_id" in preflight["official_native"]["blockers"]
    assert "missing_official_openai_judge_credentials" in preflight["official_native"]["blockers"]
    assert preflight["azure_equivalent"]["ready"] is False
    assert "missing_azure_openai_judge_route" not in preflight["azure_equivalent"]["blockers"]
    assert preflight["azure_openai_judge_route"]["available"] is True


def test_write_azure_equivalent_suite_overrides_only_judge_model(tmp_path):
    suite_dir = tmp_path / "suite"
    (suite_dir / "datasets").mkdir(parents=True)
    (suite_dir / "files").mkdir()
    (suite_dir / "datasets" / "filesystem_code.jsonl").write_text("{}", encoding="utf-8")
    (suite_dir / "rubric.txt").write_text("prompt", encoding="utf-8")
    suite_yaml = suite_dir / "filesystem_code.yaml"
    suite_yaml.write_text(
        "\n".join(
            [
                "name: filesystem-code",
                "description: Test suite",
                "dataset: datasets/filesystem_code.jsonl",
                "target:",
                "  kind: letta_code",
                "  base_url: https://api.letta.com/",
                "  working_dir: files",
                "graders:",
                "  rubric_check:",
                "    kind: model_judge",
                "    prompt_path: rubric.txt",
                "    model: gpt-5-mini",
                "    provider: openai",
                "gate:",
                "  kind: simple",
                "  metric_key: rubric_check",
                "  aggregation: avg_score",
                "  op: gte",
                "  value: 0.7",
            ]
        ),
        encoding="utf-8",
    )

    generated_path = write_azure_equivalent_suite(
        suite_yaml=suite_yaml,
        output_path=tmp_path / "generated" / "filesystem_code.azure_equivalent.yaml",
        azure_deployment="gpt-5.4-mini",
    )
    generated = yaml.safe_load(generated_path.read_text(encoding="utf-8"))

    assert generated["name"] == "filesystem-code-azure-equivalent"
    assert generated["dataset"] == str((suite_dir / "datasets" / "filesystem_code.jsonl").resolve())
    assert generated["target"]["working_dir"] == str((suite_dir / "files").resolve())
    assert generated["graders"]["rubric_check"]["prompt_path"] == str((suite_dir / "rubric.txt").resolve())
    assert generated["graders"]["rubric_check"]["model"] == "gpt-5.4-mini"
