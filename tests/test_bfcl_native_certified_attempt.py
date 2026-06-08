from __future__ import annotations

import json
import importlib.util

from runner.model_client import AZURE_ENV_ENDPOINT, AZURE_ENV_GPT54_MINI_DEPLOYMENT, AZURE_ENV_GPT54_MINI_KEY
from tools.run_bfcl_native_certified_attempt import (
    _provider_env_check,
    _upstream_import_check,
    run_bfcl_native_certified_attempt,
)


def test_bfcl_native_certified_attempt_emits_blocked_artifacts(tmp_path):
    summary = run_bfcl_native_certified_attempt(tmp_path)
    assert summary["status"] in {"blocked", "ready_for_runtime_execution"}

    preflight = json.loads((tmp_path / "certified_runtime_preflight.json").read_text(encoding="utf-8"))
    row = json.loads((tmp_path / "result_rows" / "certified_attempt.json").read_text(encoding="utf-8"))
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert "dependency_checks" in preflight
    assert "docker_check" in preflight
    assert row["family"] == "bfcl_native_adapter"
    assert row["authority_label"] == "native"
    assert scoreboard["row_count"] == 1


def test_bfcl_native_certified_attempt_blocked_row_is_invalid_when_blockers_present(tmp_path):
    run_bfcl_native_certified_attempt(tmp_path)
    preflight = json.loads((tmp_path / "certified_runtime_preflight.json").read_text(encoding="utf-8"))
    row = json.loads((tmp_path / "result_rows" / "certified_attempt.json").read_text(encoding="utf-8"))
    if preflight["blockers"]:
        assert row["closure_status"] == "invalid"
        assert row["task_truth_status"] == "invalid"
        assert row["score"] == 0.0


def test_bfcl_upstream_import_check_registers_module_for_exec(monkeypatch):
    calls: dict[str, object] = {}

    class _Loader:
        def exec_module(self, module):
            calls["module_present"] = module.__name__ in __import__("sys").modules
            module.BFCL_V3_CASES = [1, 2, 3]

    class _Spec:
        loader = _Loader()
        name = "deepagents_external_benchmarks_probe"

    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *args, **kwargs: _Spec())
    monkeypatch.setattr(importlib.util, "module_from_spec", lambda spec: type("M", (), {"__name__": spec.name})())

    result = _upstream_import_check()

    assert calls["module_present"] is True
    assert result["import_ok"] is True
    assert result["stdout"] == "OK 3"


def test_bfcl_provider_env_check_detects_azure_route(monkeypatch):
    for env_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(AZURE_ENV_ENDPOINT, "https://example-resource.openai.azure.com")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_DEPLOYMENT, "gpt-5.4-mini")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_KEY, "secret")

    provider_check = _provider_env_check()

    assert provider_check["any_provider_env_present"] is True
    assert "azure_openai_gpt54_mini" in provider_check["available_provider_routes"]
    assert provider_check["present_standard_provider_envs"] == []
    assert AZURE_ENV_GPT54_MINI_KEY in provider_check["present_provider_envs"]
