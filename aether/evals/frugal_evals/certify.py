from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from aether.evals.utils.artifacts import open_artifact_store
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash

from .chop_shop_search import (
    BASELINE_PREDICTOR_ID,
    build_t1_search_tasks,
    generate_baseline_search_predictions,
    score_search_predictions,
)
from .episodes import extract_and_write_episodes
from .ingest import summarize_harness_run
from .tamper_fuzz import run_tamper_fuzz_suite
from .zombie import run_zombie_batch


class CertificationError(RuntimeError):
    pass


COST_LEDGER_SCHEMA_VERSION = "frugal_cost_ledger.v1"
EVIDENCE_INDEX_SCHEMA_VERSION = "frugal_evidence_index.v1"
CERT_REPORT_SCHEMA_VERSION = "frugal_certification_report.v1"
CORPUS_SELECTION_SCHEMA_VERSION = "frugal_corpus_selection.v1"
STAGE_NAMES = (
    "ingestion",
    "episode_extraction",
    "zombie",
    "chop_shop",
    "fuzzing",
    "cert",
)
REQUIRED_STAGE_COST_FIELDS = ("wall_clock_s", "model_calls", "input_tokens", "output_tokens", "cost_usd_est")


def run_certification(
    *,
    out_dir: str | Path,
    runs_root: str | Path | None = None,
    run_dirs: Sequence[str | Path] | None = None,
    selection_prefix: str = "frugal-cert-fixture_",
    max_runs: int | None = None,
    zombie_model_id: str = "mock-zombie-v1",
    zombie_adapter: str = "mock",
    zombie_limit: int | None = None,
    zombie_offset: int = 0,
    pricing_path: str | Path | None = None,
    k_values: Sequence[int] = (5, 10, 20),
    max_repo_files: int = 2000,
    truncate_events: int = 1,
) -> Dict[str, Any]:
    selected_run_dirs, selection_payload = _select_run_dirs(
        runs_root=runs_root,
        run_dirs=run_dirs,
        selection_prefix=selection_prefix,
        max_runs=max_runs,
    )

    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    selection_path = out_root / "run_selection.json"
    _write_json(selection_path, selection_payload)

    pipeline_run_id = stable_hash(
        {
            "schema_version": "frugal_certification_pipeline.v0_1_1",
            "selected_run_dirs": [path.resolve().as_posix() for path in selected_run_dirs],
            "zombie_model_id": zombie_model_id,
            "zombie_adapter": zombie_adapter,
            "zombie_limit": zombie_limit,
            "zombie_offset": zombie_offset,
            "k_values": [int(value) for value in k_values],
            "max_repo_files": int(max_repo_files),
            "truncate_events": int(truncate_events),
        }
    )

    corpus_root = _prepare_corpus_root(out_root=out_root, run_dirs=selected_run_dirs)

    stage_costs: Dict[str, Dict[str, Any]] = {name: _zero_stage_cost() for name in STAGE_NAMES}
    selection_entries_by_dir = {
        str(item.get("run_dir")): item
        for item in selection_payload.get("selected_runs", [])
        if isinstance(item, Mapping) and isinstance(item.get("run_dir"), str)
    }

    ingestion_summaries: List[Dict[str, Any]] = []
    ingest_start = time.perf_counter()
    for run_dir in selected_run_dirs:
        summary = summarize_harness_run(run_dir)
        run_provenance = selection_entries_by_dir.get(run_dir.as_posix(), {})
        if isinstance(run_provenance, Mapping):
            summary["source_tier"] = str(run_provenance.get("source_tier", "T1"))
            summary["provider"] = run_provenance.get("provider")
            summary["task_name"] = run_provenance.get("task_name")
            summary["run_name"] = run_provenance.get("run_name")
            summary["missing_cas_roots"] = list(run_provenance.get("missing_cas_roots", []))
            summary["expected_cas_roots"] = list(run_provenance.get("expected_cas_roots", []))
        if not summary.get("hash_chain_ok", False):
            raise CertificationError(
                f"Hash-chain validation failed for run {run_dir} (first_bad_event_id={summary.get('first_bad_event_id')})"
            )
        ingestion_summaries.append(summary)
        ingest_summary_name = f"ingest_summary_{run_dir.name}.txt"
        _write_text(out_root / ingest_summary_name, canonical_json_dumps(summary) + "\n")
    stage_costs["ingestion"]["wall_clock_s"] = _nonzero_elapsed(ingest_start)

    episode_start = time.perf_counter()
    episodes_path = out_root / "episodes.jsonl"
    episode_index_path = out_root / "episode_index.json"
    episode_result = extract_and_write_episodes(
        runs_root=corpus_root,
        out_path=episodes_path,
        index_out_path=episode_index_path,
    )
    stage_costs["episode_extraction"]["wall_clock_s"] = _nonzero_elapsed(episode_start)

    zombie_start = time.perf_counter()
    zombie_result = run_zombie_batch(
        episodes_path=episodes_path,
        out_root=out_root / "zombie",
        model_id=zombie_model_id,
        adapter_mode=zombie_adapter,
        limit=zombie_limit,
        offset=zombie_offset,
        pricing_path=pricing_path,
    )
    zombie_summary_path = Path(zombie_result["batch_summary_path"])
    zombie_summary = _read_json(zombie_summary_path)
    zombie_stage_totals = _derive_zombie_stage_totals(zombie_summary)
    stage_costs["zombie"].update(zombie_stage_totals)
    stage_costs["zombie"]["wall_clock_s"] = _nonzero_elapsed(zombie_start)

    chop_shop_start = time.perf_counter()
    chop_shop_tasks_path = out_root / "chop_shop_tasks.jsonl"
    chop_shop_predictions_path = out_root / "chop_shop_predictions.jsonl"
    chop_shop_report_path = out_root / "chop_shop_report.json"
    build_t1_search_tasks(
        runs_root=corpus_root,
        out_path=chop_shop_tasks_path,
        k_values=k_values,
        max_repo_files=max_repo_files,
    )
    generate_baseline_search_predictions(
        tasks_path=chop_shop_tasks_path,
        out_path=chop_shop_predictions_path,
    )
    chop_shop_score_summary = score_search_predictions(
        predictions_path=chop_shop_predictions_path,
        tasks_path=chop_shop_tasks_path,
        report_path=chop_shop_report_path,
    )
    stage_costs["chop_shop"]["wall_clock_s"] = _nonzero_elapsed(chop_shop_start)

    fuzz_start = time.perf_counter()
    fuzz_summary = run_tamper_fuzz_suite(
        run_dir=selected_run_dirs[0],
        out_dir=out_root / "fuzz",
        truncation_events=truncate_events,
    )
    fuzz_report_path = Path(fuzz_summary["report_path"])
    fuzz_report = _read_json(fuzz_report_path)
    stage_costs["fuzzing"]["wall_clock_s"] = _nonzero_elapsed(fuzz_start)

    cert_start = time.perf_counter()
    evidence_index = _build_evidence_index(selected_run_dirs)
    evidence_index_path = out_root / "evidence_index.json"
    _write_json(evidence_index_path, evidence_index)

    stage_report_hashes = _compute_stage_report_hashes(
        ingestion_summaries=ingestion_summaries,
        episodes_path=episodes_path,
        episode_index_path=episode_index_path,
        zombie_summary=zombie_summary,
        chop_shop_report_path=chop_shop_report_path,
        fuzz_report=fuzz_report,
        evidence_index=evidence_index,
    )

    stage_costs["cert"]["wall_clock_s"] = _nonzero_elapsed(cert_start)

    cost_ledger = _build_cost_ledger(
        pipeline_run_id=pipeline_run_id,
        stage_costs=stage_costs,
    )
    _validate_cost_ledger(cost_ledger)
    _reconcile_zombie_totals(cost_ledger=cost_ledger, zombie_summary=zombie_summary)
    cost_ledger_path = out_root / "cost_ledger.json"
    _write_json(cost_ledger_path, cost_ledger)

    chop_shop_report = _read_json(chop_shop_report_path)
    replay_decision = _build_replay_decision_summary(zombie_summary)
    certification_report_payload: Dict[str, Any] = {
        "schema_version": CERT_REPORT_SCHEMA_VERSION,
        "pipeline_run_id": pipeline_run_id,
        "generated_at": _utc_now_iso(),
        "artifacts": {
            "run_selection_path": selection_path.as_posix(),
            "episodes_path": episodes_path.as_posix(),
            "episode_index_path": episode_index_path.as_posix(),
            "zombie_batch_summary_path": zombie_summary_path.as_posix(),
            "chop_shop_report_path": chop_shop_report_path.as_posix(),
            "tamper_fuzz_report_path": fuzz_report_path.as_posix(),
            "evidence_index_path": evidence_index_path.as_posix(),
            "cost_ledger_path": cost_ledger_path.as_posix(),
        },
        "stage_report_hashes": stage_report_hashes,
        "corpus": selection_payload,
        "cost_ledger": cost_ledger,
        "evidence_index": evidence_index,
        "modes": {
            "REAL": {
                "executed": True,
                "description": "Source harness runs (tools/verifiers) were ingested and hash-chain validated.",
                "run_count": len(ingestion_summaries),
                "hash_chain_ok_count": sum(1 for item in ingestion_summaries if bool(item.get("hash_chain_ok"))),
                "runs": ingestion_summaries,
            },
            "REPLAY": {
                "executed": True,
                "description": "Read-only replay analysis stages: episode extraction and Chop Shop scoring.",
                "episodes_extracted": int(episode_result["episodes_written"]),
                "episode_ids": _read_episode_ids(episodes_path),
                "chop_shop": {
                    "tasks_scored": int(chop_shop_score_summary["tasks_scored"]),
                    "tier_reports": chop_shop_report.get("tier_reports", {}),
                    "baseline_predictor": BASELINE_PREDICTOR_ID,
                    "gold_blind": True,
                },
            },
            "REPLAY_DECISION": replay_decision,
            "SIM": {
                "executed": False,
                "run_count": 0,
                "description": "No simulated-world evaluation performed in this certification run.",
            },
        },
        "tamper_fuzz": {
            "case_count": int(fuzz_summary["case_count"]),
            "passed_cases": int(fuzz_summary["passed_cases"]),
            "failed_cases": int(fuzz_summary["case_count"]) - int(fuzz_summary["passed_cases"]),
            "report_hash": str(fuzz_summary["report_hash"]),
        },
        "compliance_notes": [
            "Mode separation is explicit: REAL, REPLAY, REPLAY_DECISION, SIM.",
            "No synthetic-only success claim is made; REPLAY and REPLAY_DECISION metrics are diagnostic signals.",
        ],
    }

    normalized_payload = _normalize_certification_payload(certification_report_payload)
    evidence_bearing_hash = stable_hash(normalized_payload)
    certification_report = {
        **certification_report_payload,
        "evidence_bearing_hash": evidence_bearing_hash,
        "report_hash": evidence_bearing_hash,
    }

    certification_report_path = out_root / "certification_report.json"
    _write_json(certification_report_path, certification_report)
    certification_report_md_path = out_root / "certification_report.md"
    _write_text(
        certification_report_md_path,
        _render_report_markdown(report=certification_report),
    )

    return {
        "pipeline_run_id": pipeline_run_id,
        "out_dir": out_root.as_posix(),
        "evidence_bearing_hash": evidence_bearing_hash,
        "certification_report_path": certification_report_path.as_posix(),
        "certification_report_md_path": certification_report_md_path.as_posix(),
        "evidence_index_path": evidence_index_path.as_posix(),
        "cost_ledger_path": cost_ledger_path.as_posix(),
    }


def _zero_stage_cost() -> Dict[str, Any]:
    return {
        "wall_clock_s": 0.0,
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd_est": 0.0,
    }


def _build_cost_ledger(*, pipeline_run_id: str, stage_costs: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    for stage in STAGE_NAMES:
        if stage not in stage_costs:
            raise CertificationError(f"Missing required stage in cost ledger: {stage}")

    normalized_stages: Dict[str, Dict[str, Any]] = {}
    total_cost = 0.0
    for stage in STAGE_NAMES:
        raw_stage = stage_costs[stage]
        stage_entry = {
            "wall_clock_s": float(raw_stage.get("wall_clock_s", 0.0)),
            "model_calls": int(raw_stage.get("model_calls", 0)),
            "input_tokens": int(raw_stage.get("input_tokens", 0)),
            "output_tokens": int(raw_stage.get("output_tokens", 0)),
            "cost_usd_est": float(raw_stage.get("cost_usd_est", 0.0)),
        }
        total_cost += stage_entry["cost_usd_est"]
        normalized_stages[stage] = stage_entry

    return {
        "schema_version": COST_LEDGER_SCHEMA_VERSION,
        "pipeline_run_id": pipeline_run_id,
        "timestamp": _utc_now_iso(),
        "stages": normalized_stages,
        "total_cost_usd_est": round(total_cost, 10),
    }


def _validate_cost_ledger(cost_ledger: Mapping[str, Any]) -> None:
    missing_top = [key for key in ("schema_version", "pipeline_run_id", "timestamp", "stages", "total_cost_usd_est") if key not in cost_ledger]
    if missing_top:
        raise CertificationError(f"Cost ledger missing required top-level field(s): {', '.join(missing_top)}")

    timestamp = cost_ledger.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        raise CertificationError("Cost ledger timestamp must be a non-empty UTC ISO8601 string")

    stages = cost_ledger.get("stages")
    if not isinstance(stages, Mapping):
        raise CertificationError("Cost ledger stages must be an object")

    for stage_name in STAGE_NAMES:
        if stage_name not in stages:
            raise CertificationError(f"Cost ledger missing stage: {stage_name}")
        stage_payload = stages[stage_name]
        if not isinstance(stage_payload, Mapping):
            raise CertificationError(f"Cost ledger stage {stage_name} must be an object")
        for field in REQUIRED_STAGE_COST_FIELDS:
            if field not in stage_payload:
                raise CertificationError(f"Cost ledger stage {stage_name} missing required field: {field}")
        wall_clock = float(stage_payload["wall_clock_s"])
        if wall_clock <= 0.0:
            raise CertificationError(f"Cost ledger stage {stage_name} must have wall_clock_s > 0 for executed stage")

    summed = round(
        sum(float(stages[stage]["cost_usd_est"]) for stage in STAGE_NAMES),
        10,
    )
    declared = float(cost_ledger["total_cost_usd_est"])
    if abs(summed - declared) > 1e-9:
        raise CertificationError(
            f"Cost ledger total_cost_usd_est mismatch: declared={declared} computed={summed}"
        )


def _reconcile_zombie_totals(*, cost_ledger: Mapping[str, Any], zombie_summary: Mapping[str, Any]) -> None:
    stages = cost_ledger["stages"]
    zombie_stage = stages["zombie"]
    cumulative = zombie_summary.get("cumulative_cost_line")
    if not isinstance(cumulative, Mapping):
        raise CertificationError("Zombie batch summary missing cumulative_cost_line")

    expected_model_calls = int(zombie_summary.get("episode_count", 0))
    expected_input_tokens = int(cumulative.get("total_input_tokens", 0))
    expected_output_tokens = int(cumulative.get("total_output_tokens", 0))
    expected_cost = float(cumulative.get("total_cost_usd_est", 0.0))

    if int(zombie_stage["model_calls"]) != expected_model_calls:
        raise CertificationError(
            f"Zombie model_calls mismatch: ledger={zombie_stage['model_calls']} batch_summary={expected_model_calls}"
        )
    if int(zombie_stage["input_tokens"]) != expected_input_tokens:
        raise CertificationError(
            f"Zombie input_tokens mismatch: ledger={zombie_stage['input_tokens']} batch_summary={expected_input_tokens}"
        )
    if int(zombie_stage["output_tokens"]) != expected_output_tokens:
        raise CertificationError(
            f"Zombie output_tokens mismatch: ledger={zombie_stage['output_tokens']} batch_summary={expected_output_tokens}"
        )
    if abs(float(zombie_stage["cost_usd_est"]) - expected_cost) > 1e-9:
        raise CertificationError(
            f"Zombie cost_usd_est mismatch: ledger={zombie_stage['cost_usd_est']} batch_summary={expected_cost}"
        )


def _derive_zombie_stage_totals(batch_summary: Mapping[str, Any]) -> Dict[str, Any]:
    cumulative = batch_summary.get("cumulative_cost_line")
    if not isinstance(cumulative, Mapping):
        raise CertificationError("Zombie batch summary missing cumulative_cost_line")
    return {
        "model_calls": int(batch_summary.get("episode_count", 0)),
        "input_tokens": int(cumulative.get("total_input_tokens", 0)),
        "output_tokens": int(cumulative.get("total_output_tokens", 0)),
        "cost_usd_est": float(cumulative.get("total_cost_usd_est", 0.0)),
    }


def _build_replay_decision_summary(zombie_summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "executed": True,
        "description": "Zombie tool-free decision replay over fixed episode subset.",
        "episode_count": int(zombie_summary.get("episode_count", 0)),
        "agreement_rate": float(zombie_summary.get("agreement_rate", 0.0)),
        "behavioral_distribution": dict(zombie_summary.get("behavioral_distribution", {})),
        "behavioral_distribution_over_reliance": bool(zombie_summary.get("behavioral_distribution_over_reliance", False)),
        "coherence_rate": float(zombie_summary.get("coherence_rate", 0.0)),
        "cumulative_cost_line": dict(zombie_summary.get("cumulative_cost_line", {})),
    }


def _compute_stage_report_hashes(
    *,
    ingestion_summaries: Sequence[Mapping[str, Any]],
    episodes_path: Path,
    episode_index_path: Path,
    zombie_summary: Mapping[str, Any],
    chop_shop_report_path: Path,
    fuzz_report: Mapping[str, Any],
    evidence_index: Mapping[str, Any],
) -> Dict[str, str]:
    return {
        "ingestion_report_hash": stable_hash(_normalize_ingestion_payload(ingestion_summaries)),
        "episode_report_hash": stable_hash(
            {
                "episodes": _normalize_episodes_payload(_read_jsonl(episodes_path)),
                "episode_index": _normalize_episode_index_payload(_read_json(episode_index_path)),
            }
        ),
        "zombie_report_hash": stable_hash(_normalize_zombie_batch_payload(zombie_summary)),
        "chop_shop_report_hash": stable_hash(_normalize_chop_shop_payload(_read_json(chop_shop_report_path))),
        "fuzz_report_hash": stable_hash(_normalize_fuzz_payload(fuzz_report)),
        "evidence_index_hash": stable_hash(_normalize_evidence_index_payload(evidence_index)),
    }


def _normalize_ingestion_payload(summaries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    normalized = []
    for summary in summaries:
        normalized.append(
            {
                "run_id": summary.get("run_id"),
                "event_count": int(summary.get("event_count", 0)),
                "first_step_id": summary.get("first_step_id"),
                "last_step_id": summary.get("last_step_id"),
                "hash_chain_ok": bool(summary.get("hash_chain_ok", False)),
                "first_bad_event_id": summary.get("first_bad_event_id"),
                "compat_issues": list(summary.get("compat_issues", [])),
            }
        )
    normalized.sort(key=lambda item: (str(item.get("run_id")), int(item.get("event_count", 0))))
    return {"runs": normalized}


def _normalize_episodes_payload(episodes: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for episode in episodes:
        item = dict(episode)
        item.pop("run_dir", None)
        normalized.append(item)
    normalized.sort(
        key=lambda item: (
            str(item.get("run_id", "")),
            int(item.get("step_id", -1)),
            str(item.get("episode_id", "")),
        )
    )
    return normalized


def _normalize_episode_index_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    normalized.pop("runs_root", None)
    episodes = normalized.get("episodes")
    if isinstance(episodes, list):
        cleaned = []
        for episode in episodes:
            if not isinstance(episode, Mapping):
                continue
            item = dict(episode)
            item.pop("run_dir", None)
            cleaned.append(item)
        cleaned.sort(
            key=lambda item: (
                str(item.get("run_id", "")),
                int(item.get("step_id", -1)),
                str(item.get("episode_id", "")),
            )
        )
        normalized["episodes"] = cleaned
    return normalized


def _normalize_zombie_batch_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = {
        "schema_version": payload.get("schema_version"),
        "mode": payload.get("mode"),
        "model_id": payload.get("model_id"),
        "episode_count": int(payload.get("episode_count", 0)),
        "agreement_rate": float(payload.get("agreement_rate", 0.0)),
        "behavioral_distribution": dict(payload.get("behavioral_distribution", {})),
        "behavioral_distribution_over_reliance": bool(payload.get("behavioral_distribution_over_reliance", False)),
        "coherence_rate": float(payload.get("coherence_rate", 0.0)),
        "cumulative_cost_line": dict(payload.get("cumulative_cost_line", {})),
    }
    return normalized


def _normalize_chop_shop_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = {
        "schema_version": payload.get("schema_version"),
        "tier_reports": payload.get("tier_reports", {}),
        "all_tiers_combined_labeled": payload.get("all_tiers_combined_labeled", {}),
    }
    per_task = payload.get("per_task")
    if isinstance(per_task, list):
        rows: List[Dict[str, Any]] = []
        for item in per_task:
            if not isinstance(item, Mapping):
                continue
            rows.append(
                {
                    "task_id": item.get("task_id"),
                    "source_tier": item.get("source_tier"),
                    "gold_count": int(item.get("gold_count", 0)),
                    "prediction_count": int(item.get("prediction_count", 0)),
                    "metrics": item.get("metrics", {}),
                }
            )
        rows.sort(key=lambda row: (str(row.get("source_tier", "")), str(row.get("task_id", ""))))
        normalized["per_task"] = rows
    return normalized


def _normalize_fuzz_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    cases = payload.get("cases")
    normalized_cases: List[Dict[str, Any]] = []
    if isinstance(cases, list):
        for case in cases:
            if not isinstance(case, Mapping):
                continue
            normalized_cases.append(
                {
                    "case_id": case.get("case_id"),
                    "fuzz_category": case.get("fuzz_category"),
                    "mutation_description": case.get("mutation_description"),
                    "expected_outcome": case.get("expected_outcome"),
                    "actual_outcome": case.get("actual_outcome"),
                    "pass": bool(case.get("pass")),
                }
            )
    normalized_cases.sort(key=lambda item: str(item.get("case_id", "")))
    return {
        "schema_version": payload.get("schema_version"),
        "run_id": payload.get("run_id"),
        "summary": payload.get("summary", {}),
        "cases": normalized_cases,
    }


def _normalize_evidence_index_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    refs = payload.get("cas_refs")
    if isinstance(refs, list):
        normalized_refs = sorted({str(ref) for ref in refs if isinstance(ref, str)})
    else:
        normalized_refs = []
    return {
        "schema_version": payload.get("schema_version"),
        "cas_refs": normalized_refs,
    }


def _normalize_certification_payload(report: Mapping[str, Any]) -> Dict[str, Any]:
    cost_ledger = report.get("cost_ledger", {})
    if not isinstance(cost_ledger, Mapping):
        cost_ledger = {}
    stages = cost_ledger.get("stages", {})
    normalized_stages: Dict[str, Dict[str, Any]] = {}
    if isinstance(stages, Mapping):
        for stage_name in STAGE_NAMES:
            stage_payload = stages.get(stage_name, {})
            if not isinstance(stage_payload, Mapping):
                stage_payload = {}
            normalized_stages[stage_name] = {
                "model_calls": int(stage_payload.get("model_calls", 0)),
                "input_tokens": int(stage_payload.get("input_tokens", 0)),
                "output_tokens": int(stage_payload.get("output_tokens", 0)),
                "cost_usd_est": float(stage_payload.get("cost_usd_est", 0.0)),
            }

    modes = report.get("modes", {})
    normalized_modes: Dict[str, Any] = {}
    if isinstance(modes, Mapping):
        for mode_name in ("REAL", "REPLAY", "REPLAY_DECISION", "SIM"):
            mode_payload = modes.get(mode_name, {})
            if not isinstance(mode_payload, Mapping):
                continue
            normalized_modes[mode_name] = _remove_pathlike_fields(dict(mode_payload))

    return {
        "schema_version": report.get("schema_version"),
        "pipeline_run_id": report.get("pipeline_run_id"),
        "stage_report_hashes": report.get("stage_report_hashes", {}),
        "corpus": {
            "n": report.get("corpus", {}).get("n") if isinstance(report.get("corpus"), Mapping) else None,
            "selection_rule": report.get("corpus", {}).get("selection_rule") if isinstance(report.get("corpus"), Mapping) else None,
            "selected_run_names": report.get("corpus", {}).get("selected_run_names") if isinstance(report.get("corpus"), Mapping) else None,
            "selected_run_dirs": report.get("corpus", {}).get("selected_run_dirs") if isinstance(report.get("corpus"), Mapping) else None,
            "tier_labels": report.get("corpus", {}).get("tier_labels") if isinstance(report.get("corpus"), Mapping) else None,
            "missing_cas_roots_total": report.get("corpus", {}).get("missing_cas_roots_total") if isinstance(report.get("corpus"), Mapping) else None,
        },
        "cost_ledger": {
            "schema_version": cost_ledger.get("schema_version"),
            "pipeline_run_id": cost_ledger.get("pipeline_run_id"),
            "stages": normalized_stages,
            "total_cost_usd_est": float(cost_ledger.get("total_cost_usd_est", 0.0)),
        },
        "evidence_index_hash": stable_hash(_normalize_evidence_index_payload(report.get("evidence_index", {}))),
        "modes": normalized_modes,
        "tamper_fuzz": report.get("tamper_fuzz", {}),
        "compliance_notes": list(report.get("compliance_notes", [])),
    }


def _remove_pathlike_fields(payload: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    path_keys = {
        "run_dir",
        "events_path",
        "cas_roots",
        "summary_path",
        "batch_dir",
        "tasks_path",
        "predictions_path",
    }
    for key in list(payload.keys()):
        value = payload[key]
        if key in path_keys:
            payload.pop(key, None)
            continue
        if isinstance(value, Mapping):
            payload[key] = _remove_pathlike_fields(dict(value))
            continue
        if isinstance(value, list):
            cleaned: List[Any] = []
            for item in value:
                if isinstance(item, Mapping):
                    cleaned.append(_remove_pathlike_fields(dict(item)))
                else:
                    cleaned.append(item)
            payload[key] = cleaned
    return payload


def _select_run_dirs(
    *,
    runs_root: str | Path | None,
    run_dirs: Sequence[str | Path] | None,
    selection_prefix: str,
    max_runs: int | None,
) -> Tuple[List[Path], Dict[str, Any]]:
    if runs_root is None and not run_dirs:
        raise CertificationError("Provide either --runs-root or --run-dirs")
    if runs_root is not None and run_dirs:
        raise CertificationError("Use either --runs-root or --run-dirs, not both")

    selected: List[Path]
    selection_rule: str

    if run_dirs:
        selected = []
        for raw in run_dirs:
            candidate = Path(raw)
            if not candidate.exists() or not candidate.is_dir():
                raise CertificationError(f"Run directory does not exist: {candidate}")
            if not _has_events_file(candidate):
                raise CertificationError(f"Run directory is missing telemetry file: {candidate}")
            selected.append(candidate)
        selected = sorted(selected, key=lambda item: item.resolve().as_posix())
        selection_rule = "explicit_run_dirs_sorted_by_name"
    else:
        root = Path(runs_root)  # type: ignore[arg-type]
        if not root.exists() or not root.is_dir():
            raise CertificationError(f"runs_root does not exist or is not a directory: {root}")
        discovered = _discover_run_dirs(root)
        if not discovered:
            raise CertificationError(f"No run directories with telemetry files found in {root}")

        prefixed = [path for path in discovered if selection_prefix and path.name.startswith(selection_prefix)]
        if prefixed:
            selected = prefixed
            selection_rule = f"recursive_sorted_with_prefix_{selection_prefix}"
        else:
            selected = discovered
            selection_rule = "all_sorted_runs_recursive_in_runs_root"

    if max_runs is not None:
        if max_runs < 1:
            raise CertificationError("max_runs must be >= 1 when provided")
        selected = selected[:max_runs]
        selection_rule = f"{selection_rule}_limited_to_{max_runs}"

    if not selected:
        raise CertificationError("Selection resolved to zero run directories")

    selected_runs = []
    missing_cas_root_count = 0
    for run_dir in selected:
        cas_status = _cas_root_status(run_dir)
        if not cas_status["existing_cas_roots"]:
            raise CertificationError(
                f"Run directory is missing required CAS roots: {run_dir} expected={cas_status['expected_cas_roots']}"
            )
        provider, task_name = _infer_provider_and_task(run_dir)
        selected_runs.append(
            {
                "run_dir": run_dir.as_posix(),
                "run_name": run_dir.name,
                "source_tier": "T1",
                "provider": provider,
                "task_name": task_name,
                "expected_cas_roots": cas_status["expected_cas_roots"],
                "existing_cas_roots": cas_status["existing_cas_roots"],
                "missing_cas_roots": cas_status["missing_cas_roots"],
            }
        )
        missing_cas_root_count += len(cas_status["missing_cas_roots"])

    return selected, {
        "schema_version": CORPUS_SELECTION_SCHEMA_VERSION,
        "runs_root": Path(runs_root).as_posix() if runs_root is not None else None,
        "n": len(selected),
        "selected_run_names": [path.name for path in selected],
        "selected_run_dirs": [path.as_posix() for path in selected],
        "selection_rule": selection_rule,
        "tier_labels": {"T1": len(selected), "T2": 0},
        "selected_runs": selected_runs,
        "missing_cas_roots_total": missing_cas_root_count,
    }


def _cas_root_status(run_dir: Path) -> Dict[str, List[str]]:
    artifact_store = open_artifact_store(run_dir)
    expected = [path.as_posix() for path in artifact_store.cas_roots]
    existing = [path.as_posix() for path in artifact_store.cas_roots if path.exists() and path.is_dir()]
    missing = [path for path in expected if path not in existing]
    return {
        "expected_cas_roots": expected,
        "existing_cas_roots": existing,
        "missing_cas_roots": missing,
    }


def _infer_provider_and_task(run_dir: Path) -> Tuple[str | None, str | None]:
    provider: str | None = None
    parts = list(run_dir.parts)
    for index in range(0, len(parts) - 2):
        if parts[index] == "results" and parts[index + 2] == "runs":
            provider = parts[index + 1]
            break

    task_name: str | None = None
    match = re.match(r"^(?P<task>.+)_\d{8}_\d{6}$", run_dir.name)
    if match is not None:
        task_name = match.group("task")

    return provider, task_name


def _prepare_corpus_root(*, out_root: Path, run_dirs: Sequence[Path]) -> Path:
    corpus_root = out_root / "corpus_runs"
    if corpus_root.exists():
        shutil.rmtree(corpus_root)
    corpus_root.mkdir(parents=True, exist_ok=True)

    used_names: Dict[str, int] = {}
    for source in run_dirs:
        base_name = source.name
        used_count = used_names.get(base_name, 0)
        used_names[base_name] = used_count + 1
        target_name = base_name if used_count == 0 else f"{base_name}__{used_count:02d}"
        target = corpus_root / target_name

        try:
            os.symlink(source.resolve(), target, target_is_directory=True)
        except OSError:
            shutil.copytree(source, target)
    return corpus_root


def _build_evidence_index(run_dirs: Sequence[Path]) -> Dict[str, Any]:
    cas_refs: set[str] = set()
    for run_dir in run_dirs:
        events_path = _resolve_events_file(run_dir)
        for event in _read_jsonl(events_path):
            if not isinstance(event, Mapping):
                continue
            artifact_refs = event.get("artifact_refs")
            if isinstance(artifact_refs, list):
                for ref in artifact_refs:
                    if _is_cas_ref(ref):
                        cas_refs.add(str(ref))
            for key, value in event.items():
                if key.endswith("_ref") and _is_cas_ref(value):
                    cas_refs.add(str(value))
    return {
        "schema_version": EVIDENCE_INDEX_SCHEMA_VERSION,
        "cas_refs": sorted(cas_refs),
    }


def _render_report_markdown(*, report: Mapping[str, Any]) -> str:
    modes = report["modes"]
    replay_decision = modes["REPLAY_DECISION"]
    replay = modes["REPLAY"]
    fuzz = report["tamper_fuzz"]
    lines = [
        "# FEP v0.1.1 Certification Report",
        "",
        f"- Evidence-bearing hash: `{report['evidence_bearing_hash']}`",
        f"- Report hash: `{report['report_hash']}`",
        f"- Corpus selection file: `{report['artifacts']['run_selection_path']}`",
        f"- Cost ledger: `{report['artifacts']['cost_ledger_path']}`",
        f"- Evidence index: `{report['artifacts']['evidence_index_path']}`",
        "",
        "## Mode Separation",
        "### REAL",
        f"- Executed: `{modes['REAL']['executed']}`",
        f"- Description: {modes['REAL']['description']}",
        f"- Runs: `{modes['REAL']['run_count']}` (hash chain OK: `{modes['REAL']['hash_chain_ok_count']}`)",
        "",
        "### REPLAY",
        f"- Executed: `{replay['executed']}`",
        f"- Description: {replay['description']}",
        f"- Episodes extracted: `{replay['episodes_extracted']}`",
        f"- Chop Shop tasks scored: `{replay['chop_shop']['tasks_scored']}`",
        "",
        "### REPLAY_DECISION",
        f"- Executed: `{replay_decision['executed']}`",
        f"- Description: {replay_decision['description']}",
        f"- Episodes evaluated: `{replay_decision['episode_count']}`",
        f"- Agreement rate: `{replay_decision['agreement_rate']}`",
        f"- Coherence rate: `{replay_decision['coherence_rate']}`",
        f"- Behavioral distribution: `{replay_decision['behavioral_distribution']}`",
        f"- Over-reliance flag (>80% same action shape): `{replay_decision['behavioral_distribution_over_reliance']}`",
        "",
        "### SIM",
        f"- Executed: `{modes['SIM']['executed']}`",
        f"- Description: {modes['SIM']['description']}",
        f"- Runs: `{modes['SIM']['run_count']}`",
        "",
        "## Fuzzing",
        f"- Cases: `{fuzz['case_count']}`",
        f"- Passed: `{fuzz['passed_cases']}`",
        f"- Failed: `{fuzz['failed_cases']}`",
        f"- Report hash: `{fuzz['report_hash']}`",
        "",
        "## Compliance Notes",
    ]
    for note in report.get("compliance_notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _discover_run_dirs(root: Path) -> List[Path]:
    candidates: set[Path] = set()
    if _has_events_file(root):
        candidates.add(root)
    for event_name in ("event_log.jsonl", "events.jsonl"):
        for event_path in root.rglob(event_name):
            parent = event_path.parent
            if parent.is_dir():
                candidates.add(parent)
    return sorted(candidates, key=lambda item: item.resolve().as_posix())


def _has_events_file(path: Path) -> bool:
    return (path / "event_log.jsonl").exists() or (path / "events.jsonl").exists()


def _resolve_events_file(path: Path) -> Path:
    for name in ("event_log.jsonl", "events.jsonl"):
        candidate = path / name
        if candidate.exists() and candidate.is_file():
            return candidate
    raise CertificationError(f"Missing telemetry file in {path}")


def _read_episode_ids(path: Path) -> List[str]:
    ids: List[str] = []
    for payload in _read_jsonl(path):
        if isinstance(payload, Mapping) and isinstance(payload.get("episode_id"), str):
            ids.append(str(payload["episode_id"]))
    return ids


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CertificationError(f"Expected JSON object in {path}")
    return payload


def _read_jsonl(path: Path) -> List[Any]:
    rows: List[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json_dumps(dict(payload)) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json_dumps(dict(row)))
            handle.write("\n")


def _is_cas_ref(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nonzero_elapsed(start: float) -> float:
    elapsed = time.perf_counter() - start
    return max(round(elapsed, 6), 0.000001)
