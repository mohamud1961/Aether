"""The run record Aether Core leaves next to its trace, and the finish report taken from it."""

from __future__ import annotations

import json
from pathlib import Path
import time

from .jev import jev_calls
from .loop import CoreConfig
from .provider import ChatProvider

JEV_JOURNAL = "core_jev_journal.jsonl"


def write_record(
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
            "evidence_presentation": config.evidence_presentation,
            "verify": config.verify, "self_check": config.self_check, "state": config.state,
            "fork": config.fork,
            "model": provider.model,
            "params": provider.params,
            "limit_field": provider.limit_field,
        },
        "reviews": reviews,
        "run_metrics": {
            # Every provider call from every role (worker, llm, checkpoint), from the call
            # log; token totals are lower bounds when usage_unknown > 0 or open > 0. JEV is not a provider
            # call: its own journal is counted alongside, so the two can be reconciled with the reviews.
            "model_calls": provider.log.totals(),
            "jev_calls": jev_calls(logs / JEV_JOURNAL),
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
    # The run's delivered account is the report, not the model's summary alone (see loop.RunResult.final_account).
    account = result.final_account if result else ""
    if account:
        (logs / "finish_report.md").write_text(account, encoding="utf-8")
