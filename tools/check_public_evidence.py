#!/usr/bin/env python3
"""Fail closed if the public evidence index drifts from its referenced receipts."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
MANIFEST = EVIDENCE / "MANIFEST.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class EvidenceManifestError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise EvidenceManifestError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - publication gate should explain malformed evidence
        _fail(f"cannot parse JSON {path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
    if not isinstance(value, dict):
        _fail(f"JSON root must be an object: {path.relative_to(ROOT)}")
    return value


def _resolve_public_path(raw: str) -> Path:
    path = (EVIDENCE / raw).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        _fail(f"evidence path escapes repository: {raw}")
    if not path.exists():
        _fail(f"evidence manifest references missing path: {raw}")
    return path


def _walk_sha256(value: Any, *, context: str = "root") -> int:
    count = 0
    if isinstance(value, dict):
        for key, child in value.items():
            child_context = f"{context}.{key}"
            if key.endswith("sha256") and child is not None:
                if not isinstance(child, str) or not SHA256_RE.fullmatch(child):
                    _fail(f"invalid SHA-256 field {child_context}: {child!r}")
                count += 1
            count += _walk_sha256(child, context=child_context)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            count += _walk_sha256(child, context=f"{context}[{index}]")
    return count


def _eq(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        _fail(f"{label} drift: manifest={actual!r} source={expected!r}")


def _entry(entries: dict[str, dict[str, Any]], entry_id: str) -> dict[str, Any]:
    try:
        return entries[entry_id]
    except KeyError:
        _fail(f"required evidence entry missing: {entry_id}")


def _check_h10(entry: dict[str, Any], machine: dict[str, Any]) -> int:
    aggregate = machine.get("aggregate") or {}
    governance = machine.get("governance") or {}
    verdict = machine.get("readiness_verdict") or {}
    declared_aggregate = entry.get("aggregate") or {}
    declared_governance = entry.get("governance") or {}
    declared_verdict = entry.get("verdict") or {}
    pairs = [
        ("h10.aggregate.raw_tasks", declared_aggregate.get("raw_tasks"), aggregate.get("raw_task_count")),
        ("h10.aggregate.valid_rows", declared_aggregate.get("valid_rows"), aggregate.get("valid_rows")),
        ("h10.aggregate.valid_passes", declared_aggregate.get("valid_passes"), aggregate.get("valid_passes")),
        ("h10.aggregate.invalid_rows", declared_aggregate.get("invalid_rows"), aggregate.get("invalid_rows")),
        ("h10.governance.one_attempt_per_task", declared_governance.get("one_attempt_per_task"), governance.get("one_attempt_per_task")),
        ("h10.governance.benchmark_retries", declared_governance.get("benchmark_retries"), governance.get("benchmark_retries")),
        ("h10.governance.reruns", declared_governance.get("reruns"), governance.get("reruns_performed")),
        ("h10.governance.substitutions", declared_governance.get("substitutions"), governance.get("substitutions_performed")),
        ("h10.governance.mid_campaign_tuning_or_repair", declared_governance.get("mid_campaign_tuning_or_repair"), governance.get("mid_h10_tuning_or_repair")),
        ("h10.verdict.runtime_mechanical_integrity", declared_verdict.get("runtime_mechanical_integrity"), verdict.get("aether_runtime_mechanical_integrity")),
        ("h10.verdict.benchmark_competitiveness", declared_verdict.get("benchmark_competitiveness"), verdict.get("benchmark_competitiveness")),
        ("h10.verdict.performance", declared_verdict.get("performance"), verdict.get("performance_verdict")),
    ]
    for label, actual, expected in pairs:
        _eq(label, actual, expected)
    return len(pairs)


def _check_luna(entry: dict[str, Any], machine: dict[str, Any]) -> int:
    sha = machine.get("sha256") or {}
    pairs = [
        ("luna.run_id", entry.get("run_id"), machine.get("run_id")),
        ("luna.model", entry.get("model"), machine.get("model")),
        ("luna.official_reward", entry.get("official_reward"), machine.get("official_reward")),
        ("luna.aether_terminal_status", entry.get("aether_terminal_status"), machine.get("aether_terminal_status")),
        ("luna.preserved_trajectory_sha256", entry.get("preserved_trajectory_sha256"), sha.get("trajectory")),
    ]
    for label, actual, expected in pairs:
        _eq(label, actual, expected)
    return len(pairs)


def _check_boundary(entry: dict[str, Any], machine: dict[str, Any]) -> int:
    pairs = [
        ("boundary.task_id", entry.get("task_id"), machine.get("task_id")),
        ("boundary.official_reward", entry.get("official_reward"), machine.get("official_reward")),
        ("boundary.forensics_sha256", entry.get("forensics_sha256"), machine.get("forensics_sha256")),
    ]
    for label, actual, expected in pairs:
        _eq(label, actual, expected)
    source = machine.get("source") or {}
    if machine.get("projection_status") != "derived_from_sealed_public_h10_record":
        _fail("boundary projection no longer declares sealed-H10 derivation")
    if source.get("row_ordinal") != 5:
        _fail("boundary projection source row drifted from H10 row 5")
    return len(pairs) + 2


def main() -> int:
    manifest = _load_json(MANIFEST)
    if manifest.get("schema_version") != "aether.public.evidence_manifest.v1":
        _fail(f"unexpected evidence manifest schema: {manifest.get('schema_version')!r}")

    policy = manifest.get("evidence_policy")
    if not isinstance(policy, dict):
        _fail("evidence_policy must be an object")
    required_policy = {
        "selected_cases_are_labelled": True,
        "invalid_runs_remain_invalid": True,
        "different_model_agent_pairs_are_not_causal_ab": True,
        "hidden_evaluation_state_visible_to_agent": False,
        "raw_model_trajectory_publication_requires_redaction_review": True,
        "reconstructed_or_synthetic_traces_presented_as_raw": False,
    }
    for key, expected in required_policy.items():
        _eq(f"evidence_policy.{key}", policy.get(key), expected)

    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        _fail("evidence manifest entries must be a non-empty list")
    entries: dict[str, dict[str, Any]] = {}
    referenced_paths: dict[str, Path] = {}
    for index, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            _fail(f"evidence entry {index} must be an object")
        entry_id = str(item.get("id") or "").strip()
        if not entry_id:
            _fail(f"evidence entry {index} has no id")
        if entry_id in entries:
            _fail(f"duplicate evidence id: {entry_id}")
        if not str(item.get("kind") or "").strip():
            _fail(f"evidence entry {entry_id} has no kind")
        if not str(item.get("selection_status") or "").strip():
            _fail(f"evidence entry {entry_id} has no selection_status")
        if item.get("raw_model_trace_public") is False and "raw_trace_path" in item:
            _fail(f"entry {entry_id} declares raw trace unavailable but also supplies raw_trace_path")
        entries[entry_id] = item
        for key, raw in item.items():
            if key.endswith("_path") and isinstance(raw, str) and raw.strip():
                referenced_paths[f"{entry_id}.{key}"] = _resolve_public_path(raw)

    crosschecks = 0
    h10 = _entry(entries, "h10-held-out-qualification")
    h10_machine = _load_json(referenced_paths["h10-held-out-qualification.machine_path"])
    crosschecks += _check_h10(h10, h10_machine)

    luna = _entry(entries, "configure-git-webserver-luna-aether")
    luna_machine = _load_json(referenced_paths["configure-git-webserver-luna-aether.machine_path"])
    crosschecks += _check_luna(luna, luna_machine)

    boundary = _entry(entries, "workspace-boundary-rejection")
    boundary_machine = _load_json(referenced_paths["workspace-boundary-rejection.machine_path"])
    crosschecks += _check_boundary(boundary, boundary_machine)

    external = _entry(entries, "terra-codex-external-source")
    if external.get("causal_claim_allowed") is not False:
        _fail("external comparator entry must keep causal_claim_allowed=false")
    if not external.get("pending_scope"):
        _fail("external comparator must preserve pending-scope disclosure")
    crosschecks += 2

    sha_fields = _walk_sha256(manifest, context="manifest")
    print(
        "PUBLIC_EVIDENCE_VALID "
        f"entries={len(entries)} referenced_paths={len(referenced_paths)} "
        f"sha256_fields={sha_fields} crosschecks={crosschecks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
