"""Harbor ``BaseAgent`` for Aether Core.

Configuration comes from the launcher's environment only:
- provider: the GLM research profile's endpoint / key / deployment variables;
- ``AETHER_CORE_REVIEW``: ``off`` or ``reviewer`` (required; no silent default);
- ``AETHER_CORE_REASONING_EFFORT``: reasoning effort (default ``high``).
A missing or invalid setting stops the run before any model call.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any

from .loop import Trace, default_review_call, run_agent
from .provider import ChatProvider, azure_base_url

try:  # Harbor is only present on the qualified runner interpreter.
    from harbor.agents.base import BaseAgent
except ImportError:  # pragma: no cover - exercised only off the runner
    class BaseAgent:  # type: ignore[no-redef]
        def __init__(self, logs_dir: Path, model_name: str | None = None, **kwargs: Any) -> None:
            self.logs_dir = Path(logs_dir)
            self.model_name = model_name

REVIEW_ENV = "AETHER_CORE_REVIEW"
REVIEW_MODES = ("off")
ENDPOINT_ENV = "AETHER_FW_GLM_53_FLASH_ENDPOINT"
KEY_ENV = "AETHER_FW_GLM_53_FLASH_KEY"
DEPLOYMENT_ENV = "AETHER_FW_GLM_53_FLASH_DEPLOYMENT"
EFFORT_ENV = "AETHER_CORE_REASONING_EFFORT"
SAMPLING = {"temperature": 1.0, "top_p": 0.95}  # identical to the previous solver solver for a fair comparison


class ConfigError(RuntimeError):
    """The launcher did not provide a valid Aether Core configuration."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def build_provider() -> ChatProvider:
    from openai import AsyncOpenAI
    import httpx

    effort = os.environ.get(EFFORT_ENV, "high").strip() or "high"
    client = AsyncOpenAI(api_key=_required(KEY_ENV), base_url=azure_base_url(_required(ENDPOINT_ENV)),
                         max_retries=0, timeout=httpx.Timeout(connect=30.0, read=240.0, write=60.0, pool=30.0))
    params = {**SAMPLING, "reasoning_effort": effort, "tool_choice": "required", "parallel_tool_calls": False}
    return ChatProvider(client, model=_required(DEPLOYMENT_ENV), params=params)


def build_review(logs_dir: Path):
    mode = os.environ.get(REVIEW_ENV, "").strip()
    if mode not in REVIEW_MODES:
        raise ConfigError(f"{REVIEW_ENV} must be one of {REVIEW_MODES}, got {mode!r}")
    if mode == "off":
        return None
    from .review import REVIEW_MODEL



async def discover_workdir(environment: Any) -> str:
    result = await environment.exec(command="pwd; for d in /app /workspace; do test -d $d && echo $d; done",
                                    cwd=None, env=None, timeout_sec=30)
    lines = [ln.strip() for ln in str(getattr(result, "stdout", "") or "").splitlines() if ln.strip()]
    if not lines:
        raise ConfigError("could not determine the task working directory")
    pwd, candidates = lines[0], lines[1:]
    return candidates[0] if pwd == "/" and candidates else pwd


class AetherCoreAgent(BaseAgent):
    SUPPORTS_ATIF = False

    def __init__(self, logs_dir: Path, model_name: str | None = None,
                 agent_timeout_sec: float | None = None, **kwargs: Any) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self._agent_timeout_sec = agent_timeout_sec

    @staticmethod
    def name() -> str:
        return "aether-core"

    def version(self) -> str:
        return "core-v1"

    async def setup(self, environment: Any) -> None:
        return None

    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        if not self._agent_timeout_sec or self._agent_timeout_sec <= 0:
            raise ConfigError("Harbor did not provide agent_timeout_sec")
        logs = Path(self.logs_dir)
        provider = build_provider()
        transport = build_review(logs)
        workdir = await discover_workdir(environment)
        started = time.time()
        result = None
        try:
            result = await run_agent(env=environment, task=instruction, workdir=workdir, provider=provider,
                                     timeout_s=float(self._agent_timeout_sec), trace=Trace(logs / "core_trace.jsonl"),
                                     review_transport=transport,
                                     review_call=default_review_call if transport is not None else None)
        finally:
            _write_record(logs, result, started=started, workdir=workdir,
                          review=os.environ.get(REVIEW_ENV), provider=provider)
            if result is not None:
                for attr, key in (("n_input_tokens", "input"), ("n_cache_tokens", "cached"),
                                  ("n_output_tokens", "output")):
                    if hasattr(context, attr):
                        setattr(context, attr, int(result.usage.get(key, 0)))


def _write_record(logs: Path, result, *, started: float, workdir: str, review: str | None,
                  provider: ChatProvider) -> None:
    chars = result.request_chars if result else []
    reviews = result.reviews if result else []
    record = {
        "schema": "aether.core.run_record.v1",
        "status": result.status if result else "crashed",
        "error": result.error if result else "run raised before returning; see the Harbor trial exception",
        "steps": result.steps if result else None,
        "workdir": workdir,
        "elapsed_s": round(time.time() - started, 1),
        "config": {"review": review, "model": provider.model, "params": provider.params},
        "reviews": reviews,
        "run_metrics": {
            "provider_usage_row_count": result.calls if result else 0,
            "provider_attempt_count": result.calls if result else 0,
            "provider_failed_attempt_count": result.failed_attempts if result else None,
            "provider_input_tokens": result.usage.get("input") if result else None,
            "provider_cached_input_tokens": result.usage.get("cached") if result else None,
            "provider_output_tokens": result.usage.get("output") if result else None,
            "provider_reasoning_tokens": result.usage.get("reasoning") if result else None,
            "mean_request_chars": round(sum(chars) / len(chars)) if chars else None,
            "max_request_chars": max(chars) if chars else None,
            "review_count": len(reviews),
            "review_holds": sum(r["status"] == "hold" for r in reviews),
            "review_errors": sum(r["status"] == "error" for r in reviews),
        },
    }
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "aether_run_record.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
