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
