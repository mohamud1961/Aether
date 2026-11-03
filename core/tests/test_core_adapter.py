"""Adapter configuration/accounting contracts, independent of optional Harbor installation."""

import asyncio
import json

import pytest

from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk


def test_missing_usage_is_null_in_saved_record_but_reported_fields_remain_known(
    tmp_path,
):
    work = tmp_path / "work"
    work.mkdir()
    script = [
        [
            tool_chunk("finish", {"summary": "done"}),
            chunk(finish="tool_calls"),
            chunk(usage={"prompt_tokens": 12, "completion_tokens": 3}),
        ]
    ]
    provider = ChatProvider(
        ScriptedClient(script),
        model="scripted",
        params={},
        log=CallLog(tmp_path / "calls"),
    )
    config = CoreConfig(control_dir=str(tmp_path / "ctl"))
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=60,
            trace=Trace(tmp_path / "trace"),
            config=config,
        )
    )
    adapter._write_record(
        tmp_path,
        result,
        started=0,
        workdir=str(work),
        config=config,
        review="off",
        provider=provider,
    )
    record = json.loads((tmp_path / "aether_run_record.json").read_text())
    metrics = record["run_metrics"]
    assert (
        metrics["provider_input_tokens"] == 12
        and metrics["provider_output_tokens"] == 3
    )
    assert (
        metrics["provider_cached_input_tokens"] is None
        and metrics["provider_reasoning_tokens"] is None
    )
    assert record["run_metrics"]["model_calls"]["all"]["missing_cached"] == 1


def test_optional_parallel_reads_are_explicit_and_default_off(monkeypatch):
    for name, value in (
        (adapter.REVIEW_ENV, "off"),
        (adapter.CONTEXT_ENV, "project"),
        (adapter.REPL_ENV, "off"),
        (adapter.IMAGES_ENV, "off"),
    ):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(adapter.PARALLEL_ENV, raising=False)
    assert adapter.build_config().parallel_reads is False
    monkeypatch.setenv(adapter.PARALLEL_ENV, "on")
    assert adapter.build_config().parallel_reads is True
    monkeypatch.setenv(adapter.PARALLEL_ENV, "maybe")
    with pytest.raises(adapter.ConfigError):
        adapter.build_config()


@pytest.mark.parametrize("value", ["nan", "inf", "-1"])
def test_invalid_deadline_never_reaches_a_model_call(monkeypatch, value):
    monkeypatch.setenv(adapter.DEADLINE_ENV, value)
    with pytest.raises(adapter.ConfigError):
        adapter.agent_timeout(None)


def test_version_from_a_source_checkout_is_reported_not_a_launch_crash(monkeypatch):
    # B1: run from the research tree without the wheel installed, version() raised and every row failed at launch
    import importlib.metadata as md

    def missing(name):
        raise md.PackageNotFoundError(name)

    monkeypatch.setattr(md, "version", missing)
    assert adapter.AetherCoreAgent.version(None) == "core-unpackaged"
    monkeypatch.setattr(md, "version", lambda name: "0.2.0")
    assert adapter.AetherCoreAgent.version(None) == "core-0.2.0"


def _base_env(monkeypatch):
    for name, value in (
        (adapter.REVIEW_ENV, "off"),
        (adapter.CONTEXT_ENV, "project"),
        (adapter.REPL_ENV, "off"),
        (adapter.IMAGES_ENV, "off"),
    ):
        monkeypatch.setenv(name, value)


def test_run_end_keeps_processes_by_default_and_stop_stays_selectable(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv(adapter.END_PROCESSES_ENV, raising=False)
    assert adapter.build_config().end_processes == "keep"
    assert CoreConfig().end_processes == "keep"
    monkeypatch.setenv(adapter.END_PROCESSES_ENV, "stop")
    assert adapter.build_config().end_processes == "stop"
    monkeypatch.setenv(adapter.END_PROCESSES_ENV, "kill")
    with pytest.raises(adapter.ConfigError):
        adapter.build_config()


def _provider_env(monkeypatch):
    for name in (adapter.ENDPOINT_ENV, adapter.KEY_ENV, adapter.DEPLOYMENT_ENV):
        monkeypatch.setenv(
            name, "https://example.invalid" if name == adapter.ENDPOINT_ENV else "x"
        )


def test_request_shape_defaults_to_the_unchanged_glm_request(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.delenv(adapter.REQUEST_ENV, raising=False)
    provider = adapter.build_provider()
    request = provider._request([{"role": "user", "content": "hi"}], None, 123, None)
    assert request["max_tokens"] == 123 and "max_completion_tokens" not in request
    assert (
        request["params"]["temperature"] == 1.0 and request["params"]["top_p"] == 0.95
    )


def test_api_selects_the_base_url(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.delenv(adapter.API_ENV, raising=False)
    assert str(adapter.build_provider()._client.base_url) == "https://example.invalid/openai/v1/"
    monkeypatch.setenv(adapter.ENDPOINT_ENV, "https://flint.example.invalid/v1")
    monkeypatch.setenv(adapter.API_ENV, "openai")
    assert str(adapter.build_provider()._client.base_url) == "https://flint.example.invalid/v1/"
    monkeypatch.setenv(adapter.API_ENV, "bogus")
    with pytest.raises(adapter.ConfigError):
        adapter.build_provider()


def test_strict_tools_close_every_schema_only_when_on(monkeypatch):
    from aether.core.tools import tools

    _provider_env(monkeypatch)
    sent = tools(python=False)
    monkeypatch.delenv("AETHER_CORE_STRICT_TOOLS", raising=False)
    plain = adapter.build_provider()._request([], sent, 1, None)["tools"]
    assert plain == sent and not any("strict" in t["function"] for t in plain)
    monkeypatch.setenv("AETHER_CORE_STRICT_TOOLS", "on")
    strict = adapter.build_provider()._request([], sent, 1, None)["tools"]
    assert all(t["function"]["strict"] is True for t in strict)
    assert all(t["function"]["parameters"]["additionalProperties"] is False for t in strict)
    assert not any("strict" in t["function"] for t in sent)  # the caller's list is untouched
    assert adapter.build_provider()._request([], None, 1, None).get("tools") is None


def test_reasoning_request_shape_sends_what_an_openai_reasoning_model_accepts(
    monkeypatch,
):
    _provider_env(monkeypatch)
    monkeypatch.setenv(adapter.REQUEST_ENV, "reasoning")
    provider = adapter.build_provider()
    request = provider._request([{"role": "user", "content": "hi"}], None, 123, None)
    assert request["max_completion_tokens"] == 123 and "max_tokens" not in request
    assert "temperature" not in request["params"] and "top_p" not in request["params"]
    assert request["params"]["reasoning_effort"] == "high"


def test_unknown_request_shape_or_limit_field_is_refused(monkeypatch):
    _provider_env(monkeypatch)
    monkeypatch.setenv(adapter.REQUEST_ENV, "fast")
    with pytest.raises(adapter.ConfigError):
        adapter.build_provider()
    with pytest.raises(ValueError):
        ChatProvider(object(), model="m", params={}, limit_field="max_output")


def test_responses_request_shape_builds_the_responses_provider(monkeypatch):
    from aether.core.responses import ResponsesProvider

    _provider_env(monkeypatch)
    monkeypatch.setenv(adapter.REQUEST_ENV, "responses")
    provider = adapter.build_provider()
    assert isinstance(provider, ResponsesProvider)
    assert provider.limit_field == "max_output_tokens"
    assert (
        "temperature" not in provider.params
        and provider.params["reasoning_effort"] == "high"
    )


def test_replaying_all_reasoning_needs_clm_on_either_request_shape(monkeypatch):
    base = {
        adapter.REVIEW_ENV: "off",
        adapter.CONTEXT_ENV: "clm",
        adapter.REPL_ENV: "off",
        adapter.IMAGES_ENV: "off",
    }
    assert adapter.build_config(environ=base).clm.replay_reasoning == "newest"
    full = {**base, adapter.REQUEST_ENV: "responses", adapter.REASONING_ENV: "all"}
    assert adapter.build_config(environ=full).clm.replay_reasoning == "all"
    chat = {**full, adapter.REQUEST_ENV: "chat"}
    assert adapter.build_config(environ=chat).clm.replay_reasoning == "all"
    for bad in (
        {**full, adapter.CONTEXT_ENV: "project"},
        {**chat, adapter.CONTEXT_ENV: "project"},
        {**full, adapter.REASONING_ENV: "some"},
    ):
        with pytest.raises(adapter.ConfigError):
            adapter.build_config(environ=bad)


def test_verify_and_self_check_are_explicit_opt_ins(monkeypatch):
    _base_env(monkeypatch)
    for name in (
        adapter.VERIFY_ENV,
        adapter.SELF_CHECK_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    config = adapter.build_config()
    assert (config.verify, config.self_check) == (False,) * 2
    monkeypatch.setenv(adapter.VERIFY_ENV, "once")
    monkeypatch.setenv(adapter.SELF_CHECK_ENV, "on")
    config = adapter.build_config()
    assert (config.verify, config.self_check) == (True,) * 2
    for name, bad in (
        (adapter.VERIFY_ENV, "twice"),
        (adapter.SELF_CHECK_ENV, "yes"),
    ):
        monkeypatch.setenv(name, bad)
        with pytest.raises(adapter.ConfigError):
            adapter.build_config()
        monkeypatch.delenv(name)


def test_a_verifying_run_gets_the_harbor_clone_of_the_task_container(monkeypatch):
    """A verifier on a default clone could commit the wrong container (the compose-routing bug, e4c334830)."""
    monkeypatch.setattr(
        adapter, "harbor_clone", lambda environment: ("harbor", environment)
    )
    for config, expected in (
        (CoreConfig(verify=True), ("harbor", "env")),
        (CoreConfig(card=True, card_challenge="attack"), ("harbor", "env")),
        (CoreConfig(card=True, card_challenge="challenge"), None),
        (CoreConfig(), None),
    ):
        assert adapter.with_clones(config, "env").make_clone == expected


def test_the_run_record_names_the_verify_and_self_check_switches(tmp_path):
    from aether.core.calls import CallLog

    provider = ChatProvider(
        ScriptedClient([]), model="m", params={}, log=CallLog(tmp_path / "c")
    )
    config = CoreConfig(verify=True, self_check=True)
    adapter._write_record(
        tmp_path,
        None,
        started=0,
        workdir="/w",
        config=config,
        review="off",
        provider=provider,
    )
    record = json.loads((tmp_path / "aether_run_record.json").read_text())
    assert record["config"]["verify"] is True and record["config"]["self_check"] is True


def test_removed_settings_stop_the_run_and_only_their_baseline_value_is_accepted(monkeypatch):
    _base_env(monkeypatch)
    for name, baseline in adapter.REMOVED_ENV.items():
        monkeypatch.setenv(name, "json" if baseline is None else "experiment")
        with pytest.raises(adapter.ConfigError, match=name):
            adapter.build_config()
        if baseline is not None:
            monkeypatch.setenv(name, baseline)
            adapter.build_config()
        monkeypatch.delenv(name)
    monkeypatch.setenv("AETHER_CORE_REVIEW", "contract")
    with pytest.raises(adapter.ConfigError):
        adapter.build_config()


def test_top_k_is_sent_only_when_set_and_a_bad_value_stops_the_run(monkeypatch):
    # P2 (10-22): Flint's kit recommends top_k=20; the OpenAI request set has no top_k, so it goes in extra_body
    _provider_env(monkeypatch)
    monkeypatch.delenv("AETHER_CORE_TOP_K", raising=False)
    assert "extra_body" not in adapter.build_provider()._request([], None, 1, None)["params"]
    monkeypatch.setenv("AETHER_CORE_TOP_K", "20")
    params = adapter.build_provider()._request([], None, 1, None)["params"]
    assert params["extra_body"] == {"top_k": 20} and params["temperature"] == 1.0
    for bad in ("0", "twenty", "-5"):
        monkeypatch.setenv("AETHER_CORE_TOP_K", bad)
        with pytest.raises(ValueError):
            adapter.build_provider()
