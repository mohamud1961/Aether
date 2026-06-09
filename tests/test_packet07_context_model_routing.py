from __future__ import annotations

import pytest

from runner.model_client import (
    AZURE_ENV_API_VERSION,
    AZURE_ENV_ENDPOINT,
    AZURE_ENV_GPT53_CODEX_DEPLOYMENT,
    AZURE_ENV_GPT53_CODEX_KEY,
    AZURE_ENV_GPT54_MINI_DEPLOYMENT,
    AZURE_ENV_GPT54_MINI_KEY,
)


def _set_azure_env(monkeypatch):
    monkeypatch.setenv(AZURE_ENV_ENDPOINT, "https://example-resource.openai.azure.com")
    monkeypatch.setenv(AZURE_ENV_API_VERSION, "2024-12-01-preview")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_KEY, "secret-mini-key")
    monkeypatch.setenv(AZURE_ENV_GPT54_MINI_DEPLOYMENT, "dep-gpt54-mini")
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_KEY, "secret-codex-key")
    monkeypatch.setenv(AZURE_ENV_GPT53_CODEX_DEPLOYMENT, "dep-gpt53-codex")


def test_packet07_context_model_route_defaults_to_azure_gpt54_mini(monkeypatch):
    _set_azure_env(monkeypatch)
    mod = pytest.importorskip("runner.packet07_cycle1_context_targeted_autoresearch")

    route = mod.resolve_packet07_context_model_route()

    assert route["provider_route"] == "openai_api"
    assert route["request_settings"]["pricing_model_id"] == "gpt-5.4-mini"
    assert route["request_settings"]["api_key_env_var"] == AZURE_ENV_GPT54_MINI_KEY


def test_packet07_context_model_route_allows_promotion_tier_override(monkeypatch):
    _set_azure_env(monkeypatch)
    mod = pytest.importorskip("runner.packet07_cycle1_context_targeted_autoresearch")

    route = mod.resolve_packet07_context_model_route(model_tier_selector="promotion_tier")

    assert route["provider_route"] == "openai_api"
    assert route["request_settings"]["pricing_model_id"] == "gpt-5.3-codex"
    assert route["request_settings"]["api_key_env_var"] == AZURE_ENV_GPT53_CODEX_KEY


def _patch_execute_path(mod, monkeypatch, seen):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None, raising=False)
    monkeypatch.setattr(
        mod,
        "_route_availability_check",
        lambda: {"status": "pass", "blockers": [], "rows": []},
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "_azure_dns_network_preflight",
        lambda: {"status": "pass", "blockers": []},
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "_docker_or_fallback_preflight",
        lambda specs: {
            "status": "pass",
            "blockers": [],
            "docker_available": False,
            "requires_docker_for_locked_board": False,
        },
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "_eval_row_availability_check",
        lambda locked_eval_rows, specs: {"status": "pass", "blockers": []},
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "_grader_availability_check",
        lambda specs: {"status": "pass", "blockers": []},
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "_adapter_validity_check",
        lambda specs: {"status": "pass", "blockers": []},
        raising=False,
    )
    monkeypatch.setattr(
        mod,
        "_execution_mode_disclosure",
        lambda: {"status": "pass", "blockers": []},
        raising=False,
    )

    def fake_execute_board(*args, **kwargs):
        seen["selector"] = kwargs["model_tier_selector"]
        return [], []

    monkeypatch.setattr(mod, "_execute_board", fake_execute_board, raising=False)
    monkeypatch.setattr(mod, "_write_artifacts", lambda *args, **kwargs: {"blocked": False}, raising=False)
    monkeypatch.setattr(mod, "_write_success_artifacts", lambda **kwargs: {"blocked": False}, raising=False)


@pytest.mark.parametrize(
    ("module_name", "launch_name"),
    [
        ("runner.packet07_context_continuation", "launch_continuation"),
        ("runner.packet07_cycle1_context_continuation", "launch_continuation"),
        ("runner.packet07_cycle1_context_targeted_autoresearch", "launch_packet07_cycle1"),
        ("runner.packet07_cycle1_parser_continuation", "launch_parser_continuation"),
        ("runner.packet07_cycle1_anchor_window_continuation", "launch_anchor_window_continuation"),
        ("runner.packet07_cycle1_anchor_tool_continuation", "launch_anchor_tool_continuation"),
        ("runner.packet07_cycle1_linked_query_continuation", "launch_linked_query_continuation"),
    ],
)
@pytest.mark.parametrize(
    ("model_tier_selector", "expected_selector"),
    [
        ("screening_default", "screening_default"),
        ("promotion_tier", "promotion_tier"),
    ],
)
def test_packet07_launchers_thread_model_tier_selector(
    tmp_path,
    monkeypatch,
    module_name: str,
    launch_name: str,
    model_tier_selector: str,
    expected_selector: str,
):
    mod = pytest.importorskip(module_name)
    seen: dict[str, str] = {}
    _patch_execute_path(mod, monkeypatch, seen)

    launch = getattr(mod, launch_name)
    launch(output_dir=tmp_path, execute=True, model_tier_selector=model_tier_selector)

    assert seen["selector"] == expected_selector
