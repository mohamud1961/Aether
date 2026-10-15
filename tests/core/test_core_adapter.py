"""Adapter configuration/accounting contracts, independent of optional Harbor installation."""

import asyncio
import json

import pytest

from aether.core import harbor_agent as adapter
from aether.core.calls import CallLog
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, chunk, tool_chunk


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


def test_turn_mode_defaults_to_the_baseline_and_rejects_unknown_values(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv(adapter.TURN_ENV, raising=False)
    assert adapter.build_config().turn == "tool"
    monkeypatch.setenv(adapter.TURN_ENV, "analysis")
    assert adapter.build_config().turn == "analysis"
    monkeypatch.setenv(adapter.TURN_ENV, "chatty")
    with pytest.raises(adapter.ConfigError):
        adapter.build_config()
    with pytest.raises(ValueError):
        CoreConfig(turn="chatty")


def test_analysis_turns_use_auto_tool_choice_and_the_baseline_stays_required(
    monkeypatch,
):
    for name in (adapter.ENDPOINT_ENV, adapter.KEY_ENV, adapter.DEPLOYMENT_ENV):
        monkeypatch.setenv(
            name, "https://example.invalid" if name == adapter.ENDPOINT_ENV else "x"
        )
    monkeypatch.delenv(adapter.TURN_ENV, raising=False)
    assert adapter.build_provider().params["tool_choice"] == "required"
    monkeypatch.setenv(adapter.TURN_ENV, "analysis")
    assert adapter.build_provider().params["tool_choice"] == "auto"


@pytest.mark.parametrize("turn", ["tool", "analysis"])
def test_analysis_turn_prompt_is_added_only_in_analysis_mode_and_written_text_is_kept(
    tmp_path, turn
):
    from aether.core.tools import ANALYSIS_DOC

    work = tmp_path / "work"
    work.mkdir()
    script = [
        [
            chunk(content="Results show nothing yet; next: finish, expecting done."),
            tool_chunk("finish", {"summary": "done"}),
            chunk(finish="tool_calls"),
            chunk(usage={"prompt_tokens": 12, "completion_tokens": 3}),
        ]
    ]
    client = ScriptedClient(script)
    provider = ChatProvider(
        client, model="scripted", params={}, log=CallLog(tmp_path / "calls")
    )
    result = asyncio.run(
        run_agent(
            env=LocalEnv(work),
            task="task",
            workdir=str(work),
            provider=provider,
            timeout_s=60,
            trace=Trace(tmp_path / "trace.jsonl"),
            config=CoreConfig(control_dir=str(tmp_path / "ctl"), turn=turn),
        )
    )
    assert result.status == "finished"
    system = client.requests[0]["messages"][0]["content"]
    assert (ANALYSIS_DOC in system) == (turn == "analysis")
    rows = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert [r for r in rows if r["event"] == "model"][0]["content"].startswith(
        "Results show"
    )
    assert [r for r in rows if r["event"] == "start"][0]["turn"] == turn


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


def test_several_calls_per_turn_are_an_explicit_opt_in(monkeypatch):
    """The API flag that lets the model batch calls is its own switch, not a side effect of concurrent reads."""
    seen = {}

    class Client:
        def __init__(self, **kw):
            pass

    monkeypatch.setattr("openai.AsyncOpenAI", Client)
    env = {
        adapter.ENDPOINT_ENV: "https://x.openai.azure.com/",
        adapter.KEY_ENV: "k",
        adapter.DEPLOYMENT_ENV: "GPT-6-Luna",
        adapter.REQUEST_ENV: "responses",
    }
    seen["one"] = adapter.build_provider(environ=env).params["parallel_tool_calls"]
    seen["many"] = adapter.build_provider(
        environ={**env, adapter.CALLS_ENV: "many"}
    ).params["parallel_tool_calls"]
    assert seen == {"one": False, "many": True}
    with pytest.raises(adapter.ConfigError):
        adapter.build_provider(environ={**env, adapter.CALLS_ENV: "all"})


def test_replaying_all_reasoning_needs_responses_and_clm(monkeypatch):
    base = {
        adapter.REVIEW_ENV: "off",
        adapter.CONTEXT_ENV: "clm",
        adapter.REPL_ENV: "off",
        adapter.IMAGES_ENV: "off",
    }
    assert adapter.build_config(environ=base).clm.replay_reasoning == "newest"
    full = {**base, adapter.REQUEST_ENV: "responses", adapter.REASONING_ENV: "all"}
    assert adapter.build_config(environ=full).clm.replay_reasoning == "all"
    for bad in (
        {**full, adapter.REQUEST_ENV: "chat"},
        {**full, adapter.CONTEXT_ENV: "project"},
        {**full, adapter.REASONING_ENV: "some"},
    ):
        with pytest.raises(adapter.ConfigError):
            adapter.build_config(environ=bad)


def test_verify_and_self_check_are_explicit_opt_ins(monkeypatch):
    _base_env(monkeypatch)
    for name in (
        adapter.VERIFY_ENV,
        adapter.SELF_CHECK_ENV,
        adapter.EVIDENCE_ENV,
        adapter.LEDGER_ENV,
        adapter.READBACK_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    config = adapter.build_config()
    assert (config.verify, config.self_check, config.evidence, config.ledger, config.readback) == (
        False,
    ) * 5
    monkeypatch.setenv(adapter.VERIFY_ENV, "once")
    monkeypatch.setenv(adapter.SELF_CHECK_ENV, "on")
    monkeypatch.setenv(adapter.EVIDENCE_ENV, "on")
    monkeypatch.setenv(adapter.LEDGER_ENV, "on")
    monkeypatch.setenv(adapter.READBACK_ENV, "on")
    config = adapter.build_config()
    assert (config.verify, config.self_check, config.evidence, config.ledger, config.readback) == (
        True,
    ) * 5
    for name, bad in (
        (adapter.VERIFY_ENV, "twice"),
        (adapter.SELF_CHECK_ENV, "yes"),
        (adapter.EVIDENCE_ENV, "yes"),
        (adapter.LEDGER_ENV, "yes"),
        (adapter.READBACK_ENV, "yes"),
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
        (CoreConfig(contract=True), ("harbor", "env")),
        (CoreConfig(), None),
    ):
        assert adapter.with_clones(config, "env").make_clone == expected


def test_the_run_record_names_the_verify_and_self_check_switches(tmp_path):
    from aether.core.calls import CallLog

    provider = ChatProvider(
        ScriptedClient([]), model="m", params={}, log=CallLog(tmp_path / "c")
    )
    config = CoreConfig(verify=True, self_check=True, evidence=True, readback=True)
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
    assert record["config"]["evidence"] is True and record["config"]["readback"] is True


def test_the_read_back_paragraph_is_in_the_solver_prompt_only_when_on():
    from aether.core.tools import READBACK_DOC, system_prompt

    off = system_prompt(python_version="3.12", clm=True)
    on = system_prompt(python_version="3.12", clm=True, readback=True)
    assert READBACK_DOC not in off and READBACK_DOC in on
    assert on.replace(READBACK_DOC, "") == off  # the baseline prompt is otherwise unchanged
