"""Harbor ``BaseAgent`` for Aether Core.
Configuration comes from the launcher's environment only:
- provider: the GLM research profile's endpoint / key / deployment variables;
- ``AETHER_CORE_REVIEW``: ``off``, ``jev`` (finish review), ``jev_progress`` (finish review plus
  progress reviews at 35% and 70% of the time limit and a final review near the deadline);
- ``AETHER_CORE_CONTEXT``: ``project`` (C1 view) or ``clm`` (model-managed context, CLM method);
- ``AETHER_CORE_REPL`` / ``AETHER_CORE_IMAGES``: ``on`` or ``off`` (Python REPL / view_image tool);
  all four are required; there is no silent default;
- ``AETHER_TB4_REASONING_EFFORT``: effort (default ``high``); ``AETHER_AGENT_DEADLINE_SEC``: the task's time limit.
A missing or invalid setting stops the run before any model call.
"""

from __future__ import annotations

from dataclasses import replace
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Mapping

from . import browser, continuation, keep_final, route_modality, start_archive
from .calls import CallLog
from .reasoning_wire import WIRES
from .clone import Clone, compose_clone
from .loop import CoreConfig, Trace, default_review_call, run_agent
from .provider import ChatProvider, base_url
from .runrecord import JEV_JOURNAL, write_record as _write_record
from .strict import StrictChatProvider, extra_sampling, proxy_headers

from .harbor_config import (  # noqa: F401  (re-exported: launchers and tests import them from here)
    API_ENV,
    BUDGET_ENV,
    CALLS_ENV,
    CALLS_FILE,
    CALLS_MODES,
    CHAIN_ENV,
    CONTEXT_ENV,
    CONTEXT_EVIDENCE_ENV,
    ConfigError,
    DEADLINE_ENV,
    DEPLOYMENT_ENV,
    EFFORT_ENV,
    ENDPOINT_ENV,
    END_PROCESSES_ENV,
    END_PROCESSES_MODES,
    FACTS_MODES,
    FORK_ENV,
    HYGIENE_ENV,
    IMAGES_ENV,
    INTENT_ENV,
    JEV_CAP_GBP,
    JEV_MAX_CALLS,
    JEV_TIMEOUT_S,
    KEY_ENV,
    MAX_OUTPUT_ENV,
    NATIVE_COMPACTION_ENV,
    NOTES_ENV,
    PARALLEL_ENV,
    PROGRESS_AT,
    REASONING_ENV,
    REMOVED_ENV,
    REPL_ENV,
    REPL_MODES,
    REQUEST_ENV,
    REQUEST_SHAPES,
    REVIEW_ENV,
    REVIEW_MODES,
    SAMPLING,
    SELF_CHECK_ENV,
    STATE_ENV,
    VERIFY_ENV,
    VERIFY_MODES,
    WIRE_ENV,
    _budget,
    _calls,
    _choice,
    _fork,
    _max_output,
    _native_compaction,
    _parallel_reads,
    _record,
    _refuse_removed,
    _replay,
    _request_shape,
    _required,
    build_config,
)

HARBOR_IMPORT_ERROR = None
try:  # Utility configuration functions remain importable without the optional framework.
    from harbor.agents.base import BaseAgent
except ImportError as exc:  # actual agent construction fails; never pretend Harbor is present
    HARBOR_IMPORT_ERROR = exc

    class BaseAgent:  # type: ignore[no-redef]
        def __init__(self, logs_dir: Path, model_name: str | None = None, **kwargs: Any) -> None:
            raise RuntimeError("Harbor adapter unavailable; install aether-core[harbor]") from HARBOR_IMPORT_ERROR


def build_provider(
    logs_dir: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> ChatProvider:
    environ = os.environ if environ is None else environ
    from openai import AsyncOpenAI
    import httpx

    endpoint, key, model = (
        _required(name, environ) for name in (ENDPOINT_ENV, KEY_ENV, DEPLOYMENT_ENV)
    )
    effort = environ.get(EFFORT_ENV, "high").strip() or "high"
    shape = _request_shape(environ)
    calls = _calls(environ)
    parallel_reads = _parallel_reads(environ)
    sampling = {**SAMPLING, **extra_sampling(environ)}
    params = {
        **(sampling if shape == "chat" else {}),
        "reasoning_effort": None if effort == "none" else effort,  # none: never sent (no effort levels)
        "tool_choice": "required",
        "parallel_tool_calls": calls == "many" or parallel_reads,
    }
    log = CallLog(logs_dir / CALLS_FILE if logs_dir is not None else None)
    client = AsyncOpenAI(
        api_key=key, default_headers=proxy_headers(environ),
        base_url=base_url(endpoint, _choice(environ, API_ENV, ("azure", "openai"), "azure")),
        max_retries=0,
        timeout=httpx.Timeout(connect=30.0, read=240.0, write=60.0, pool=30.0),
    )
    native = _native_compaction(environ)
    if shape == "responses":
        from .responses import ResponsesProvider

        chain = _choice(environ, CHAIN_ENV, REPL_MODES, "off") == "on"
        return ResponsesProvider(client, model=model, params=params, log=log, chain=chain, native_compaction=native)
    if native is not None:
        raise ValueError(f"{NATIVE_COMPACTION_ENV} needs the Responses request shape")
    return (StrictChatProvider if _choice(environ, "AETHER_CORE_STRICT_TOOLS", REPL_MODES, "off") == "on" else ChatProvider)(
        client,
        model=model,
        params=params,
        log=log,
        limit_field="max_tokens" if shape == "chat" else "max_completion_tokens",
        reasoning_wire=_choice(environ, WIRE_ENV, WIRES, "reasoning_content"),
    )


def build_review(logs_dir: Path, *, environ: Mapping[str, str] | None = None):
    environ = os.environ if environ is None else environ
    mode = environ.get(REVIEW_ENV, "").strip()
    if mode not in REVIEW_MODES:
        raise ConfigError(f"{REVIEW_ENV} must be one of {REVIEW_MODES}, got {mode!r}")
    if mode == "off":
        return None
    from .jev import TypeSafeEvaluator
    from .review import JEV_MODEL

    return TypeSafeEvaluator(
        model=JEV_MODEL,
        journal=logs_dir / JEV_JOURNAL,
        max_calls=JEV_MAX_CALLS,
        cap_gbp=JEV_CAP_GBP,
        input_gbp_per_million="0.10",
        timeout_s=JEV_TIMEOUT_S,
        api_key=environ.get("TYPESAFE_API_KEY", ""),
        calls_allowed=environ.get("AETHER_JEV_CALLS_ALLOWED") == "1",
    )


def harbor_clone(environment: Any):
    """Clone factory for a Harbor docker environment: its ``main`` service, found by compose project on the host."""
    from harbor.environments.docker.docker import _sanitize_docker_compose_project_name

    project = _sanitize_docker_compose_project_name(environment.session_id)

    async def make(env: Any, timeout_s: float | None = None, read_only=False, egress=False) -> Clone:
        return await compose_clone(env, project, timeout_s=timeout_s, read_only=read_only, egress=egress)

    return make


def with_clones(config: CoreConfig, environment: Any, environ: Mapping[str, str] = {}) -> CoreConfig:
    """Contract checks and the finish check work on clones of the task container: give them Harbor's."""
    config = browser.configure(config, environment, environ)  # AETHER_CORE_BROWSER=on: a browser beside it
    needed = config.verify or config.diffcheck or config.card_challenge in ("attack", "observe", "forks")
    return replace(config, make_clone=harbor_clone(environment)) if needed else config


def agent_timeout(passed: float | None, *, environ: Mapping[str, str] | None = None) -> float:
    environ = os.environ if environ is None else environ
    if passed and math.isfinite(float(passed)) and float(passed) > 0:
        return float(passed)
    raw = environ.get(DEADLINE_ENV, "").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"no agent timeout: Harbor passed none and {DEADLINE_ENV}={raw!r}")
    return value


async def discover_workdir(environment: Any) -> str:
    result = await environment.exec(
        command="pwd; for d in /app /workspace; do test -d $d && echo $d; done",
        cwd=None,
        env=None,
        timeout_sec=30,
    )
    lines = [
        ln.strip()
        for ln in str(getattr(result, "stdout", "") or "").splitlines()
        if ln.strip()
    ]
    if not lines:
        raise ConfigError("could not determine the task working directory")
    pwd, candidates = lines[0], lines[1:]
    return candidates[0] if pwd == "/" and candidates else pwd


class AetherCoreAgent(BaseAgent):
    SUPPORTS_ATIF = False

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        agent_timeout_sec: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._agent_timeout_sec = agent_timeout_sec

    @property
    def extra_env(self) -> dict[str, str]:
        """Harbor forwards this mapping to sandbox commands; provider credentials stay on the host."""
        host_only = {
            KEY_ENV,
            "TYPESAFE_API_KEY",
            "OPENAI_API_KEY",
            "AZURE_OPENAI_API_KEY",
        }
        return {
            key: value for key, value in self._extra_env.items() if key not in host_only
        }

    @staticmethod
    def name() -> str:
        return "aether-core"

    def version(self) -> str:
        """The installed package version. Run from a source checkout (the research launcher puts the tree on
        sys.path without installing it) there is no package metadata: that is reported, never invented, and the
        launcher's manifest records the exact source commit. Raising here failed every B1 row at launch."""
        from importlib.metadata import PackageNotFoundError, version

        try:
            return "core-" + version("aether-core")
        except PackageNotFoundError:
            return "core-unpackaged"

    async def setup(self, environment: Any) -> None:
        return None

    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        environ = {**os.environ, **self._extra_env}
        logs, started = Path(self.logs_dir), time.time()
        provider, config, result, workdir, pending = None, None, None, None, None
        try:
            timeout_s = agent_timeout(self._agent_timeout_sec, environ=environ)
            config = build_config(environ=environ)
            route = route_modality.check(environ, deployment=environ.get(DEPLOYMENT_ENV, ""), images=config.images)
            if route:
                logs.mkdir(parents=True, exist_ok=True)
                (logs / "route_modality.txt").write_text(route)
            provider = build_provider(logs, environ=environ)
            transport = build_review(logs, environ=environ)
            workdir = await discover_workdir(environment)
            config = with_clones(config, environment, environ)
            if _choice(environ, "AETHER_CORE_SKILLS", REPL_MODES, "off") == "on" and getattr(self, "skills_dir", None):
                config = replace(config, skills_dir=str(self.skills_dir))  # Harbor's declared task skills
            if _choice(environ, "AETHER_CORE_MCP", REPL_MODES, "off") == "on" and getattr(self, "mcp_servers", None):
                from . import mcp

                config = replace(config, mcp_servers=tuple(mcp.normalize(self.mcp_servers)))  # declared MCP servers
            instruction, pending = await continuation.begin(environment, environ, logs, instruction, workdir)
            instruction, archive_status = await start_archive.add(environment, environ, workdir, instruction)
            (logs / "start_archive.txt").write_text(archive_status)
            result = await run_agent(
                env=environment,
                task=instruction,
                workdir=workdir,
                provider=provider,
                timeout_s=timeout_s,
                trace=Trace(logs / "core_trace.jsonl"),
                review_transport=transport,
                review_call=default_review_call if transport is not None else None,
                config=config,
            )
            if result.status == "timeout":
                raise TimeoutError(result.error or "Core work deadline exceeded")
            if result.status in ("provider_error", "environment_error", "context_error", "cancelled"):
                raise RuntimeError(
                    f"Aether runtime failed ({result.status}): {result.error}"
                )
        finally:
            try:
                # Core's own cleanup must run even if capture is cancelled or raises.
                writers = None
                if result is not None:
                    writers = (getattr(result, "extras", None) or {}).get("left_running")
                await continuation.finish(environment, logs, pending, active_writers=writers)
                await keep_final.keep(environment, environ, logs)
            finally:
                try:
                    if provider is not None and config is not None:
                        _write_record(
                            logs,
                            result,
                            started=started,
                            workdir=workdir,
                            config=config,
                            review=environ.get(REVIEW_ENV),
                            provider=provider,
                        )
                    else:
                        logs.mkdir(parents=True, exist_ok=True)
                        (logs / "aether_run_record.json").write_text(
                            json.dumps(
                                {
                                    "schema": "aether.core.run_record.v1",
                                    "status": "configuration_error",
                                    "error": "adapter configuration failed before provider construction; see trial exception",
                                    "elapsed_s": round(time.time() - started, 3),
                                    "run_metrics": {"model_calls": None},
                                }
                            )
                        )
                    if provider is not None:
                        for attr, key in (
                            ("n_input_tokens", "input"),
                            ("n_cache_tokens", "cached"),
                            ("n_output_tokens", "output"),
                        ):
                            if hasattr(context, attr):
                                value = provider.log.usage().get(key)
                                setattr(
                                    context, attr, None if value is None else int(value)
                                )
                finally:
                    if provider is not None:
                        await provider.aclose()
