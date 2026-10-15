"""Harbor ``BaseAgent`` for Aether Core.

Configuration comes from the launcher's environment only:
- provider: the GLM research profile's endpoint / key / deployment variables;
- ``AETHER_CORE_REVIEW``: ``off``, ``reviewer`` (finish review), ``reviewer_progress`` (finish review plus
  progress reviews at 35% and 70% of the time limit and a final review near the deadline) or ``contract``
  (acceptance checks written before the work, offered as information; see ``contract``);
- ``AETHER_CORE_CONTEXT``: ``project`` (C1 view) or ``clm`` (model-managed context, CLM method);
- ``AETHER_CORE_REPL``: ``on`` or ``off`` (persistent Python REPL tool);
- ``AETHER_CORE_IMAGES``: ``on`` or ``off`` (view_image tool);
  all four are required; there is no silent default;
- ``AETHER_CORE_REASONING_EFFORT``: reasoning effort (default ``high``);
- ``AETHER_AGENT_DEADLINE_SEC``: the task's agent timeout, when Harbor does not pass one.
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

from .calls import CallLog
from .clm import REPLAY_MODES, ClmSettings
from .clone import Clone, compose_clone
from .loop import CONTEXT_MODES, CoreConfig, Trace, default_review_call, run_agent
from .oversight import ReviewPlan
from .provider import ChatProvider, azure_base_url
from .tools import TURN_MODES

HARBOR_IMPORT_ERROR = None
try:  # Utility configuration functions remain importable without the optional framework.
    from harbor.agents.base import BaseAgent
except (
    ImportError
) as exc:  # actual agent construction fails; never pretend Harbor is present
    HARBOR_IMPORT_ERROR = exc

    class BaseAgent:  # type: ignore[no-redef]
        def __init__(
            self, logs_dir: Path, model_name: str | None = None, **kwargs: Any
        ) -> None:
            raise RuntimeError(
                "Harbor adapter unavailable; install aether-core[harbor]"
            ) from HARBOR_IMPORT_ERROR


REVIEW_ENV = "AETHER_CORE_REVIEW"
REVIEW_MODES = ("off", "contract")
CONTEXT_ENV = "AETHER_CORE_CONTEXT"
REPL_ENV = "AETHER_CORE_REPL"
REPL_MODES = ("on", "off")
IMAGES_ENV = "AETHER_CORE_IMAGES"
TURN_ENV = "AETHER_CORE_TURN"  # optional; unset means "tool", the unchanged baseline
FINISH_ENV = "AETHER_CORE_FINISH"  # optional; unset means "direct", the baseline
FINISH_MODES = ("direct", "receipt")
PARALLEL_ENV = "AETHER_CORE_PARALLEL_READS"
# optional; unset means "one" (one tool call per model turn, the baseline). "many" lets the model send several calls in
# one turn; they still run in order, as a JSON turn's actions do. GPT-6-Luna on the Responses API made 61% more calls than
# on JSON turns (L2 vs L1) only because the API forbade batching, and each call resends the whole context.
CALLS_ENV = "AETHER_CORE_CALLS"
# optional; unset means "newest" (only the latest turn's reasoning is sent back). "all" sends every turn's back, so the
# history only grows at its end and the provider's prompt cache keeps extending (Responses API with CLM only).
REASONING_ENV = "AETHER_CORE_REASONING"
CALLS_MODES = ("one", "many")
# optional; unset means "off". "once": one independent check of the first finish by the same model in a fresh
# context on a clone (see verify). AETHER_CORE_SELF_CHECK=on adds the self-check paragraph (tools.SELF_CHECK_DOC).
VERIFY_ENV, VERIFY_MODES = "AETHER_CORE_VERIFY", ("off", "once")
SELF_CHECK_ENV, EVIDENCE_ENV, LEDGER_ENV = (
    "AETHER_CORE_SELF_CHECK",
    "AETHER_CORE_EVIDENCE",
    "AETHER_CORE_LEDGER",
)  # on/off; see evidence and ledger
# optional; unset means "chat" (the GLM request, unchanged). "reasoning" is the request an OpenAI reasoning model
# accepts: max_completion_tokens and no sampling parameters (GPT-6-Luna rejects max_tokens and top_p).
REQUEST_ENV = "AETHER_CORE_REQUEST"
REQUEST_SHAPES = (
    "chat",
    "reasoning",
    "responses",
)  # responses: /v1/responses, native tools + reasoning replay
PROGRESS_AT = (0.35, 0.70)
ENDPOINT_ENV = "AETHER_FW_GLM_53_FLASH_ENDPOINT"
KEY_ENV = "AETHER_FW_GLM_53_FLASH_KEY"
DEPLOYMENT_ENV = "AETHER_FW_GLM_53_FLASH_DEPLOYMENT"
EFFORT_ENV = "AETHER_CORE_REASONING_EFFORT"
DEADLINE_ENV = "AETHER_AGENT_DEADLINE_SEC"
SAMPLING = {
    "temperature": 1.0,
    "top_p": 0.95,
}  # identical to the previous solver solver for a fair comparison
CALLS_FILE = "core_calls.jsonl"  # every provider request and response (see calls)


class ConfigError(RuntimeError):
    """The launcher did not provide a valid Aether Core configuration."""


def _required(name: str, environ: Mapping[str, str]) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


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
    params = {
        **(SAMPLING if shape == "chat" else {}),
        "reasoning_effort": effort,
        # analysis turns need "auto": with a forced tool call the model wrote nothing (S2 replay)
        "tool_choice": "auto" if _turn(environ) == "analysis" else "required",
        "parallel_tool_calls": _parallel_reads(environ) or _calls(environ) == "many",
    }
    log = CallLog(logs_dir / CALLS_FILE if logs_dir is not None else None)
    client = AsyncOpenAI(
        api_key=key,
        base_url=azure_base_url(endpoint),
        max_retries=0,
        timeout=httpx.Timeout(connect=30.0, read=240.0, write=60.0, pool=30.0),
    )
    if shape == "responses":
        from .responses import ResponsesProvider

        return ResponsesProvider(client, model=model, params=params, log=log)
    return ChatProvider(
        client,
        model=model,
        params=params,
        log=log,
        limit_field="max_tokens" if shape == "chat" else "max_completion_tokens",
    )


def build_review(logs_dir: Path, *, environ: Mapping[str, str] | None = None):
    environ = os.environ if environ is None else environ
    mode = environ.get(REVIEW_ENV, "").strip()
    if mode not in REVIEW_MODES:
        raise ConfigError(f"{REVIEW_ENV} must be one of {REVIEW_MODES}, got {mode!r}")
    if mode in (
        "off",
        "contract",
    ):  # contract runs on the solver's own provider (see contract)
        return None
    from .review import REVIEW_MODEL



def build_config(*, environ: Mapping[str, str] | None = None) -> CoreConfig:
    environ = os.environ if environ is None else environ
    review = environ.get(REVIEW_ENV, "").strip()
    context = environ.get(CONTEXT_ENV, "").strip()
    repl = environ.get(REPL_ENV, "").strip()
    if review not in REVIEW_MODES:
        raise ConfigError(f"{REVIEW_ENV} must be one of {REVIEW_MODES}, got {review!r}")
    if context not in CONTEXT_MODES:
        raise ConfigError(
            f"{CONTEXT_ENV} must be one of {CONTEXT_MODES}, got {context!r}"
        )
    if repl not in REPL_MODES:
        raise ConfigError(f"{REPL_ENV} must be one of {REPL_MODES}, got {repl!r}")
    see = environ.get(IMAGES_ENV, "").strip()
    if see not in REPL_MODES:
        raise ConfigError(f"{IMAGES_ENV} must be one of {REPL_MODES}, got {see!r}")
    plan = ReviewPlan(finish=False)
    return CoreConfig(
        context=context,
        repl=repl == "on",
        images=see == "on",
        reviews=plan,
        clm=ClmSettings(replay_reasoning=_replay(environ, context)),
        contract=review == "contract",
        parallel_reads=_parallel_reads(environ),
        turn=_turn(environ),
        receipt=_finish_mode(environ) == "receipt",
        verify=_choice(environ, VERIFY_ENV, VERIFY_MODES, "off") == "once",
        self_check=_choice(environ, SELF_CHECK_ENV, REPL_MODES, "off") == "on",
        evidence=_choice(environ, EVIDENCE_ENV, REPL_MODES, "off") == "on",
        ledger=_choice(environ, LEDGER_ENV, REPL_MODES, "off") == "on",
    )


def _choice(
    environ: Mapping[str, str], name: str, modes: tuple[str, ...], unset: str
) -> str:
    """An optional setting: unset means ``unset`` (the baseline); anything outside ``modes`` stops the run."""
    value = environ.get(name, unset).strip() or unset
    if value not in modes:
        raise ConfigError(f"{name} must be one of {', '.join(modes)}, got {value!r}")
    return value


def _request_shape(environ: Mapping[str, str]) -> str:
    return _choice(environ, REQUEST_ENV, REQUEST_SHAPES, "chat")


def _finish_mode(environ: Mapping[str, str]) -> str:
    return _choice(environ, FINISH_ENV, FINISH_MODES, "direct")


def _turn(environ: Mapping[str, str]) -> str:
    return _choice(environ, TURN_ENV, TURN_MODES, "tool")


def _replay(environ: Mapping[str, str], context: str) -> str:
    value = environ.get(REASONING_ENV, "newest").strip() or "newest"
    if value not in REPLAY_MODES:
        raise ConfigError(f"{REASONING_ENV} must be one of {', '.join(REPLAY_MODES)}")
    if value == "all" and (context != "clm" or _request_shape(environ) != "responses"):
        raise ConfigError(
            f"{REASONING_ENV}=all needs the Responses API and model-managed context (clm)"
        )
    return value


def _calls(environ: Mapping[str, str]) -> str:
    return _choice(environ, CALLS_ENV, CALLS_MODES, "one")


def _parallel_reads(environ: Mapping[str, str]) -> bool:
    return _choice(environ, PARALLEL_ENV, REPL_MODES, "off") == "on"


def harbor_clone(environment: Any):
    """Clone factory for a Harbor docker environment: its ``main`` service, found by compose project on the host."""
    from harbor.environments.docker.docker import _sanitize_docker_compose_project_name

    project = _sanitize_docker_compose_project_name(environment.session_id)

    async def make(env: Any, timeout_s: float | None = None, read_only=False) -> Clone:
        return await compose_clone(
            env, project, timeout_s=timeout_s, read_only=read_only
        )

    return make


def with_clones(config: CoreConfig, environment: Any) -> CoreConfig:
    """Contract checks and the finish check work on clones of the task container: give them Harbor's."""
    needed = config.contract or config.verify
    return replace(config, make_clone=harbor_clone(environment)) if needed else config


def agent_timeout(
    passed: float | None, *, environ: Mapping[str, str] | None = None
) -> float:
    environ = os.environ if environ is None else environ
    if passed and math.isfinite(float(passed)) and float(passed) > 0:
        return float(passed)
    raw = environ.get(DEADLINE_ENV, "").strip()
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(
            f"no agent timeout: Harbor passed none and {DEADLINE_ENV}={raw!r}"
        )
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
        provider, config, result, workdir = None, None, None, None
        try:
            timeout_s = agent_timeout(self._agent_timeout_sec, environ=environ)
            config = build_config(environ=environ)
            provider = build_provider(logs, environ=environ)
            transport = build_review(logs, environ=environ)
            workdir = await discover_workdir(environment)
            config = with_clones(config, environment)
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
            if result.status in (
                "provider_error",
                "environment_error",
                "context_error",
                "cancelled",
            ):
                raise RuntimeError(
                    f"Aether runtime failed ({result.status}): {result.error}"
                )
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


def _write_record(
    logs: Path,
    result,
    *,
    started: float,
    workdir: str,
    config: CoreConfig,
    review: str | None,
    provider: ChatProvider,
) -> None:
    chars = result.request_chars if result else []
    reviews = result.reviews if result else []
    record = {
        "schema": "aether.core.run_record.v1",
        "status": result.status if result else "crashed",
        "error": result.error
        if result
        else "run raised before returning; see the Harbor trial exception",
        "steps": result.steps if result else None,
        "workdir": workdir,
        "elapsed_s": round(time.time() - started, 1),
        "config": {
            "review": review,
            "context": config.context,
            "repl": config.repl,
            "images": config.images,
            "reviews": config.reviews.__dict__,
            "clm": config.clm.__dict__,
            "parallel_reads": config.parallel_reads,
            "turn": config.turn,
            "receipt": config.receipt,
            "verify": config.verify,
            "self_check": config.self_check,
            "evidence": config.evidence,
            "model": provider.model,
            "params": provider.params,
            "limit_field": provider.limit_field,
        },
        "reviews": reviews,
        "run_metrics": {
            # Every provider call from every role (worker, llm, checkpoint, contract_writer), from the call
            # log; token totals are lower bounds when usage_unknown > 0 or open > 0. The reviewer is not a provider
            # call: its own journal is counted alongside, so the two can be reconciled with the reviews.
            "model_calls": provider.log.totals(),
            "worker_turns": result.calls if result else None,
            "provider_attempt_count": provider.log.totals()["all"]["attempts"],
            "provider_failed_attempt_count": provider.log.totals()["all"]["failed"],
            "provider_input_tokens": provider.log.usage()["input"],
            "provider_cached_input_tokens": provider.log.usage()["cached"],
            "provider_output_tokens": provider.log.usage()["output"],
            "provider_reasoning_tokens": provider.log.usage()["reasoning"],
            "mean_request_chars": round(sum(chars) / len(chars)) if chars else None,
            "max_request_chars": max(chars) if chars else None,
            "review_count": len(reviews),
            "review_holds": 0,  # advice never blocked execution
            "review_objections": sum(r["status"] == "hold" for r in reviews),
            "review_errors": sum(r["status"] == "error" for r in reviews),
            "review_kinds": [r.get("at", r.get("kind")) for r in reviews],
            "sub_model_usage": result.sub_usage if result else None,
            **(result.extras if result else {}),
        },
    }
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "aether_run_record.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
