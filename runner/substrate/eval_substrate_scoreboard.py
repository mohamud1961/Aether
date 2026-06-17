"""Aggregate eval substrate result rows into scoreboard counts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

from runner.eval_substrate_contracts import result_row_verdict, validate_result_row

GROUP_FIELDS = (
    "family",
    "surface_type",
    "admission_level",
    "contamination_status",
    "failure_class",
)


def build_scoreboard_from_result_files(result_row_files: Sequence[str | Path]) -> dict[str, Any]:
    rows = list(_load_rows(result_row_files))
    return aggregate_result_rows(rows)


def aggregate_result_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals = _empty_counts()
    grouped: dict[str, dict[str, dict[str, int]]] = {field: {} for field in GROUP_FIELDS}
    cost_summary = _empty_cost_summary()
    row_count = 0

    for row in rows:
        validate_result_row(row)
        row_count += 1
        verdict = _normalize_verdict(row)
        _inc_counts(totals, verdict)
        _accumulate_cost_summary(cost_summary, row)

        for field in GROUP_FIELDS:
            bucket = str(row.get(field) or "unknown")
            group_bucket = grouped[field].setdefault(bucket, _empty_counts())
            _inc_counts(group_bucket, verdict)

    cost_summary["run_count"] = row_count
    cost_summary["pricing_model_ids"] = sorted({model_id for model_id in cost_summary["pricing_model_ids"] if model_id})
    return {
        "row_count": row_count,
        "totals": totals,
        "cost_summary": cost_summary,
        "by_family": grouped["family"],
        "by_surface_type": grouped["surface_type"],
        "by_admission_level": grouped["admission_level"],
        "by_contamination_status": grouped["contamination_status"],
        "by_failure_class": grouped["failure_class"],
    }


def _load_rows(paths: Sequence[str | Path]) -> Iterable[dict[str, Any]]:
    for path_like in paths:
        path = Path(path_like)
        if path.suffix == ".jsonl":
            yield from _read_jsonl(path)
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict):
                    yield row
            continue
        if isinstance(payload, dict):
            if isinstance(payload.get("rows"), list):
                for row in payload["rows"]:
                    if isinstance(row, dict):
                        yield row
            else:
                yield payload


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            yield row


def _normalize_verdict(row: dict[str, Any]) -> str:
    return result_row_verdict(row)


def _empty_counts() -> dict[str, int]:
    return {"pass": 0, "fail": 0, "invalid": 0, "total": 0}


def _empty_cost_summary() -> dict[str, Any]:
    return {
        "run_count": 0,
        "model_backed_run_count": 0,
        "total_input_messages": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "billable_input_tokens": 0,
        "total_output_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "usd": 0.0,
        "usd_estimate": 0.0,
        "cost_breakdown_usd": {
            "input_cost": 0.0,
            "cached_input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
        },
        "pricing_model_ids": [],
    }


def _accumulate_cost_summary(summary: dict[str, Any], row: dict[str, Any]) -> None:
    cost = _row_cost_summary(row)
    total_input_messages = _coerce_int(cost.get("total_input_messages"))
    input_tokens = _coerce_int(cost.get("input_tokens"))
    if input_tokens <= 0:
        input_tokens = _coerce_int(cost.get("prompt_tokens"))
    cached_input_tokens = _coerce_int(cost.get("cached_input_tokens"))
    if cached_input_tokens <= 0:
        details = cost.get("prompt_tokens_details")
        if not isinstance(details, dict):
            details = cost.get("input_tokens_details")
        if isinstance(details, dict):
            cached_input_tokens = _coerce_int(details.get("cached_tokens"))
    output_tokens = _coerce_int(cost.get("output_tokens"))
    if output_tokens <= 0:
        output_tokens = _coerce_int(cost.get("completion_tokens"))
    total_output_tokens = _coerce_int(cost.get("total_output_tokens"))
    if total_output_tokens <= 0:
        total_output_tokens = output_tokens
    total_tokens = _coerce_int(cost.get("total_tokens"))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    billable_input_tokens = _coerce_int(cost.get("billable_input_tokens"))
    if billable_input_tokens <= 0 and (input_tokens > 0 or cached_input_tokens > 0):
        billable_input_tokens = max(input_tokens - cached_input_tokens, 0)
    row_has_usage = _cost_summary_has_usage(
        total_input_messages=total_input_messages,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        billable_input_tokens=billable_input_tokens,
        total_output_tokens=total_output_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        usd=_first_positive_float(cost, ("usd", "usd_estimate")),
        usd_estimate=_first_positive_float(cost, ("usd_estimate", "usd")),
        pricing_model_ids=cost.get("pricing_model_ids"),
    )

    summary["total_input_messages"] += total_input_messages
    summary["input_tokens"] += max(input_tokens, 0)
    summary["cached_input_tokens"] += max(cached_input_tokens, 0)
    summary["billable_input_tokens"] += max(billable_input_tokens, 0)
    summary["total_output_tokens"] += max(total_output_tokens, 0)
    summary["output_tokens"] += max(output_tokens, 0)
    summary["total_tokens"] += max(total_tokens, 0)

    breakdown = cost.get("cost_breakdown_usd")
    if not isinstance(breakdown, dict):
        breakdown = {}
    input_cost = _cost_value(breakdown, ("input_cost", "input_cost_usd"))
    cached_input_cost = _cost_value(breakdown, ("cached_input_cost", "cached_input_cost_usd"))
    output_cost = _cost_value(breakdown, ("output_cost", "output_cost_usd"))
    total_cost = _cost_value(breakdown, ("total_cost", "total_cost_usd", "usd", "usd_estimate"))
    if total_cost <= 0:
        total_cost = _first_positive_float(cost, ("usd", "usd_estimate"))

    summary["cost_breakdown_usd"]["input_cost"] += input_cost
    summary["cost_breakdown_usd"]["cached_input_cost"] += cached_input_cost
    summary["cost_breakdown_usd"]["output_cost"] += output_cost
    summary["cost_breakdown_usd"]["total_cost"] += total_cost

    usd = _first_positive_float(cost, ("usd", "usd_estimate"))
    usd_estimate = _first_positive_float(cost, ("usd_estimate", "usd"))
    summary["usd"] += usd
    summary["usd_estimate"] += usd_estimate

    pricing_model_ids = cost.get("pricing_model_ids")
    if isinstance(pricing_model_ids, list):
        for model_id in pricing_model_ids:
            if isinstance(model_id, str) and model_id:
                summary["pricing_model_ids"].append(model_id)

    if row_has_usage:
        summary["model_backed_run_count"] += 1


def _row_cost_summary(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("token_and_cost_summary")
    if not isinstance(payload, dict) or not payload:
        payload = row.get("cost_summary")
    return payload if isinstance(payload, dict) else {}


def _cost_summary_has_usage(
    *,
    total_input_messages: int,
    input_tokens: int,
    cached_input_tokens: int,
    billable_input_tokens: int,
    total_output_tokens: int,
    output_tokens: int,
    total_tokens: int,
    usd: float,
    usd_estimate: float,
    pricing_model_ids: Any,
) -> bool:
    if total_input_messages > 0:
        return True
    if input_tokens > 0 or cached_input_tokens > 0 or billable_input_tokens > 0:
        return True
    if total_output_tokens > 0 or output_tokens > 0 or total_tokens > 0:
        return True
    if usd > 0.0 or usd_estimate > 0.0:
        return True
    return bool(pricing_model_ids)


def _cost_value(payload: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        value = payload.get(key)
        coerced = _coerce_float(value)
        if coerced > 0.0:
            return coerced
    return 0.0


def _first_positive_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        value = payload.get(key)
        coerced = _coerce_float(value)
        if coerced > 0.0:
            return coerced
    return 0.0


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return 0.0
    return 0.0


def _inc_counts(counts: dict[str, int], verdict: str) -> None:
    counts["total"] += 1
    counts[verdict] += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_row_files", nargs="+", help="Result-row JSON/JSONL files")
    args = parser.parse_args()
    scoreboard = build_scoreboard_from_result_files(args.result_row_files)
    print(json.dumps(scoreboard, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
