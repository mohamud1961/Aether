"""Evidence packet construction for model-led verification."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from hashlib import sha256
from typing import Any, Mapping

from .runtime_ir import stable_json
from .raw_task_authority import (
    build_binding,
    task_contract_payload,
    validate_verifier_packet,
)

from .ledger import TASK_STATE_SNAPSHOT_BINDING_VERSION, ExecutionLedger
from .pcr_context import receipt_exact_handle
from .runtime_ir import CompiledRuntime
from .task_contract import TaskContract


class _FrozenDict(dict):
    """JSON-serialisable immutable mapping used for model-facing packets."""

    def _blocked(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("verifier packet is immutable")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _blocked


class _FrozenList(list):
    """JSON-serialisable immutable sequence used inside a verifier packet."""

    def _blocked(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("verifier packet is immutable")

    __setitem__ = __delitem__ = append = extend = insert = pop = remove = reverse = sort = _blocked


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return deepcopy(value)


def _merged_config_realization(compiled: CompiledRuntime, ledger: ExecutionLedger) -> dict[str, Any]:
    realization = dict(compiled.config_realization)
    latest = ledger.latest_receipt("config_realization")
    if latest is not None:
        payload = latest.payload.get("config_realization", {})
        if isinstance(payload, dict):
            realization.update(payload)
    return realization


def _local_verification_limits(compiled: CompiledRuntime, realization: dict[str, Any]) -> list[dict[str, str]]:
    structured = realization.get("local_verification_limits")
    if isinstance(structured, list):
        normalized: list[dict[str, str]] = []
        for item in structured:
            if not isinstance(item, dict):
                continue
            statement = str(item.get("statement", "")).strip()
            if not statement:
                continue
            normalized.append({
                "source": str(item.get("source", "runtime_config")).strip() or "runtime_config",
                "statement": statement,
            })
        if normalized:
            return normalized
    return [
        {"source": "runtime_config", "statement": item}
        for item in compiled.local_verification_limits
        if str(item).strip()
    ]


def _config_realization_summary(realization: dict[str, Any]) -> dict[str, Any]:
    context_policy = realization.get("configured_context_policy")
    if not isinstance(context_policy, dict):
        context_policy = {
            "mode": realization.get("context_policy_mode", ""),
            "include_sections": realization.get("context_sections_declared", []),
            "compression_trigger_ratio": realization.get("context_compression_ratio"),
        }
    verification_policy = realization.get("configured_verification_policy")
    if not isinstance(verification_policy, dict):
        verification_policy = {
            "check_plan_ids": realization.get("checks_compiled", []),
        }
    verification_authority = realization.get("verification_authority")
    if isinstance(verification_authority, dict):
        official_grader = str(verification_authority.get("official_grader", "")).strip()
        if official_grader and "official_grader_authority" not in verification_policy:
            verification_policy = dict(verification_policy)
            verification_policy["official_grader_authority"] = official_grader

    summary = {
        "tools_visible_to_solver": realization.get("tools_visible_to_solver", []),
        "tools_runtime_allowed": realization.get("tools_runtime_allowed", []),
        "context_policy": context_policy,
        "verification_policy": verification_policy,
    }
    optional_keys = (
        "verification_authority",
    )
    for key in optional_keys:
        if key in realization:
            summary[key] = realization[key]
    return summary


def _raw_state_candidates(realization: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    raw = realization.get("verifier_raw_state_candidates", ())
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        if not path:
            continue
        rows.append({
            "path": path,
            "source": str(item.get("source", "config_realization")).strip() or "config_realization",
            "authority": "candidate_only",
        })
    return rows[:8]


def _task_contract_payload(compiled: CompiledRuntime, contract: TaskContract | None) -> dict[str, Any]:
    """Return immutable task truth in one explicitly scoped payload.

    The production kernel currently compiles from ``EnvMap`` and therefore
    does not always have a clause extractor result at this boundary.  When a
    typed :class:`TaskContract` is available it is the sole authority.  The
    compatibility fallback keeps the prompt inside the contract envelope and
    never exposes it as an independent model-facing field.
    """
    return deepcopy(task_contract_payload(compiled, contract))


def _stable_envmap_payload(envmap: Any | None, compiled: CompiledRuntime) -> dict[str, Any]:
    if envmap is not None and hasattr(envmap, "to_payload"):
        return deepcopy(envmap.to_payload())
    if envmap is not None and isinstance(envmap, Mapping):
        facts = deepcopy(dict(envmap))
    elif envmap is not None and hasattr(envmap, "workspace_root"):
        capabilities: dict[str, Any] = {}
        for key, value in sorted(dict(getattr(envmap, "capabilities", {}) or {}).items()):
            capabilities[str(key)] = asdict(value) if is_dataclass(value) else deepcopy(value)
        facts = {
            "workspace_root": str(getattr(envmap, "workspace_root")),
            "visible_files": sorted(str(item) for item in getattr(envmap, "visible_files", ()) or ()),
            "visible_dirs": sorted(str(item) for item in getattr(envmap, "visible_dirs", ()) or ()),
            "capabilities": capabilities,
            "services": deepcopy(dict(getattr(envmap, "services", {}) or {})),
            "resource_limits": deepcopy(dict(getattr(envmap, "resource_limits", {}) or {})),
            "permissions": deepcopy(dict(getattr(envmap, "permissions", {}) or {})),
            "interactive_features": deepcopy(dict(getattr(envmap, "interactive_features", {}) or {})),
            "network_scope": str(getattr(envmap, "network_scope", "unknown")),
            "file_tree": str(getattr(envmap, "file_tree", "")),
            "file_map_summary": deepcopy(dict(getattr(envmap, "file_map_summary", {}) or {})),
        }
    else:
        raise ValueError("stable EnvMap payload unavailable; refusing digest-only verifier state")
    from .world import StableEnvMap
    return StableEnvMap.create(facts).to_payload()


_STATE_TOP_LEVEL_KEYS = frozenset({
    "schema_version", "state_version", "installed_packages", "runtime_facts",
    "files", "services", "jobs", "artifacts", "processes", "named_sections",
    "latest_result", "active_findings", "removed_files", "removed_artifacts",
    "removed_services", "removed_jobs",
})
_STATE_FORBIDDEN_KEYS = frozenset({
    "architect_verifier_prompt", "architect_prompt", "verifier_prompt", "verifier_system_prompt",
    "solver_prompt", "solver_system_prompt", "task_prompt", "architect_strategy",
    "solver_journey", "journey", "strategy", "verifier_strategy", "recent_actions",
    "recent_receipts", "recent_command_receipts", "command_results", "stdout", "stderr",
    "content", "raw_output", "raw_log", "command", "solver_reported_blockers",
})
_NORMALIZED_FORBIDDEN_KEYS = frozenset(
    "".join(character for character in key.lower() if character.isalnum())
    for key in _STATE_FORBIDDEN_KEYS
) | frozenset({
    "solverjourney", "solvernotes", "commandresult", "commandresults",
    "commandoutput", "inspectionstrategy", "rawcommand", "rawcommands",
    "stdouttext", "stderrtext", "stdoutoutput", "stderroutput",
    "solverprompt", "verifierprompt", "architectprompt", "modelprompt",
    "transcript", "conversation", "prompt", "strategy", "journey",
})


def _normalized_key(value: Any) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _state_only_projection(value: Any, *, key: str = "") -> Any:
    """Project supplied dynamic state to compact, non-journey metadata.

    The production world already emits compact snapshots, but this boundary is
    also called by compatibility adapters.  Do not trust an adapter to omit
    raw command output or model-authored journey fields.
    """
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            name = str(raw_key)
            if _normalized_key(name) in _NORMALIZED_FORBIDDEN_KEYS:
                continue
            result[name] = _state_only_projection(item, key=name)
        return result
    if isinstance(value, list):
        return [_state_only_projection(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [_state_only_projection(item, key=key) for item in value]
    # Tool outputs may be captured as bytes (for example binary artifact or
    # subprocess streams).  Keep the packet JSON-serialisable and compact in
    # exactly the same way as large text values; the exact bytes remain
    # available through the receipt/output handle rather than being replayed
    # inline into the Verifier context.
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return {
            "status": "present",
            "bytes": len(raw),
            "sha256": sha256(raw).hexdigest(),
        }
    if isinstance(value, str) and len(value) > 512:
        return {
            "status": "present",
            "chars": len(value),
            "sha256": sha256(value.encode("utf-8", "surrogateescape")).hexdigest(),
        }
    return deepcopy(value)


def _dynamic_state_payload(ledger: ExecutionLedger, dynamic_state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build compact current state without replaying receipt payloads."""
    if dynamic_state is not None:
        projected = _state_only_projection(dynamic_state)
        # Keep the state envelope explicit and reject adapter-only journey keys.
        return {
            str(key): value
            for key, value in projected.items()
            if str(key) in _STATE_TOP_LEVEL_KEYS
        }
    return {
        "schema_version": "dynamic_world_state.v1",
        "artifacts": {path: {"status": "present"} for path in sorted(ledger.current_artifacts())},
        "processes": ledger.live_processes(),
        "state_version": len(ledger.all_receipts()),
    }


def _collect_state_handles(ledger: ExecutionLedger) -> list[dict[str, Any]]:
    """Collect stable navigation handles, deduplicated by kind/handle."""
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for receipt in ledger.all_receipts():
        payload = receipt.payload or {}

        # A stable file navigation handle must never carry a pre-mutation
        # identity across an opaque shell/tool mutation. Invalidate known
        # metadata for modified/created paths, and remove handles entirely for
        # deleted paths. A same-receipt write/read with a file_handle below then
        # replaces the invalidated row with its fresh observed identity.
        changed_paths = (
            {
                str(path).strip()
                for field in ("modified_paths", "artifact_paths")
                for path in (payload.get(field, ()) or ())
                if str(path).strip()
            }
            if receipt.state_change else set()
        )
        removed_paths = (
            {
                str(path).strip()
                for path in (payload.get("removed_paths", ()) or ())
                if str(path).strip()
            }
            if receipt.state_change else set()
        )
        if changed_paths or removed_paths:
            for key, row in list(by_key.items()):
                if key[0] != "file":
                    continue
                row_path = str(row.get("path", "") or "").strip()
                if row_path in removed_paths:
                    by_key.pop(key, None)
                elif row_path in changed_paths:
                    # Reinsert to make recency ordering reflect the mutation.
                    # Plain dict replacement preserves the original insertion
                    # position, which can evict a newly changed old handle from
                    # the packet's newest-32 window.
                    refreshed = dict(row)
                    refreshed["bytes"] = None
                    refreshed["content_hash"] = ""
                    by_key.pop(key, None)
                    by_key[key] = refreshed

        if payload.get("file_handle"):
            handle = str(payload["file_handle"])
            # File handles are stable per path (``file:<path>``), so later
            # reads/writes must replace older metadata.  Keeping the first
            # sighting would expose a stale hash after the same file changed.
            # A write's authoritative post-mutation identity is
            # ``after_content_hash``; page reads intentionally project an
            # empty hash rather than preserving an older full-file identity.
            file_key = ("file", handle)
            by_key.pop(file_key, None)
            by_key[file_key] = {
                "kind": "file", "handle": handle,
                "path": str(payload.get("path", "")),
                "bytes": payload.get("bytes"),
                "content_hash": str(
                    payload.get("content_hash")
                    or payload.get("after_content_hash")
                    or ""
                ),
            }
        for key, stream in (("stdout_handle", "stdout"), ("stderr_handle", "stderr")):
            if payload.get(key):
                handle = str(payload[key])
                by_key.setdefault(("output", handle), {
                    "kind": "output", "handle": handle, "stream": stream,
                    "bytes": payload.get(f"{stream}_bytes", 0),
                    "content_hash": str(payload.get(f"{stream}_hash", "")),
                })
    for path in sorted(ledger.current_artifacts()):
        by_key.setdefault(("file", path), {"kind": "file", "handle": path, "path": path})
    return list(by_key.values())[-32:]


def _pcr_primary_submission_payload(
    ledger: ExecutionLedger,
    *,
    strict_snapshot_binding: bool = False,
) -> dict[str, Any] | None:
    claim_receipt = ledger.latest_receipt("primary_submission_claim")
    if claim_receipt is None:
        return None
    payload = claim_receipt.payload if isinstance(claim_receipt.payload, dict) else {}
    receipt_by_id = {receipt.receipt_id: receipt for receipt in ledger.all_receipts()}
    binding_rows = payload.get("evidence_bindings", ()) or ()
    binding_by_receipt = {
        str(row.get("receipt_id", "")): dict(row)
        for row in binding_rows
        if isinstance(row, Mapping) and str(row.get("receipt_id", "")).strip()
    }
    snapshot_binding_version = str(
        payload.get("snapshot_binding_version", "")
    ).strip()
    if strict_snapshot_binding:
        if snapshot_binding_version != TASK_STATE_SNAPSHOT_BINDING_VERSION:
            raise ValueError(
                "PCR Primary Agent claim lacks the canonical task-state snapshot binding version"
            )
        if not ledger.receipt_payload_is_intact(claim_receipt):
            raise ValueError("PCR Primary Agent claim payload drifted after recording")
        try:
            claim_generation = int(payload.get("task_state_generation", -1))
        except (TypeError, ValueError):
            claim_generation = -1
        claim_digest = str(payload.get("task_state_snapshot_digest", "")).strip()
        claim_known = payload.get("task_state_snapshot_known") is True
        if (
            claim_generation != ledger.task_state_generation()
            or not claim_digest
            or claim_digest != ledger.task_state_snapshot_digest()
            or claim_known != ledger.task_state_snapshot_known()
        ):
            raise ValueError(
                "PCR Primary Agent claim is not exactly bound to the current task-state boundary"
            )
    cited: list[dict[str, Any]] = []
    for receipt_id in payload.get("evidence_receipt_ids", ()) or ():
        receipt = receipt_by_id.get(str(receipt_id))
        if receipt is None:
            continue
        if strict_snapshot_binding:
            if not ledger.receipt_payload_is_intact(receipt):
                raise ValueError(
                    f"PCR cited receipt payload drifted after recording: {receipt.receipt_id}"
                )
            if receipt.success is not True:
                raise ValueError(
                    f"PCR cited receipt is not a successful authoritative input: {receipt.receipt_id}"
                )
            if receipt.kind == "inspection_record" and not ledger.receipt_snapshot_binding_is_current(receipt):
                raise ValueError(
                    f"PCR cited inspection is not bound to the current task-state snapshot: {receipt.receipt_id}"
                )
        exact_payload = {
            "receipt_id": receipt.receipt_id,
            "step": receipt.step,
            "kind": receipt.kind,
            "success": receipt.success,
            "summary": receipt.summary,
            "state_change": receipt.state_change,
            "failure_class": receipt.failure_class,
            "payload": receipt.payload,
        }
        binding = binding_by_receipt.get(receipt.receipt_id, {})
        cited.append({
            "receipt_id": receipt.receipt_id,
            "evidence_role": str(binding.get("role", "unclassified")),
            "receipt_task_state_generation": binding.get("task_state_generation"),
            "submission_task_state_generation": payload.get("task_state_generation"),
            **({
                "receipt_payload_sha256": ledger.receipt_payload_sha256(receipt.receipt_id),
                "receipt_payload_intact": ledger.receipt_payload_is_intact(receipt),
            } if strict_snapshot_binding else {}),
            "kind": receipt.kind,
            "success": receipt.success,
            "summary": receipt.summary,
            "state_change": receipt.state_change,
            "failure_class": receipt.failure_class,
            "exact_receipt_handle": receipt_exact_handle(receipt.receipt_id),
            "exact_receipt_sha256": sha256(
                stable_json(exact_payload).encode("utf-8")
            ).hexdigest(),
            "current_payload_projection": _state_only_projection(receipt.payload),
        })
    return {
        "claim_id": str(payload.get("claim_id", "")),
        "claim": str(payload.get("claim", "")),
        "evidence_refs": list(payload.get("evidence_refs", ()) or ()),
        "evidence_receipt_ids": list(payload.get("evidence_receipt_ids", ()) or ()),
        "evidence_bindings": [dict(row) for row in binding_rows if isinstance(row, Mapping)],
        "current_anchor_count": int(payload.get("current_anchor_count", 0) or 0),
        "historical_support_count": int(payload.get("historical_support_count", 0) or 0),
        "evidence_set_sha256": str(payload.get("evidence_set_sha256", "")),
        "task_state_generation": payload.get("task_state_generation"),
        **({
            "task_state_snapshot_digest": str(payload.get("task_state_snapshot_digest", "")),
            "snapshot_binding_version": snapshot_binding_version,
            "task_state_snapshot_known": payload.get("task_state_snapshot_known") is True,
        } if strict_snapshot_binding else {}),
        "task_id": str(payload.get("task_id", "")),
        "run_id": str(payload.get("run_id", "")),
        "workspace_id": str(payload.get("workspace_id", "")),
        "cited_evidence": cited,
        "semantic_sufficiency_judged_by_kernel": False,
    }


def build_verifier_packet(
    compiled: CompiledRuntime | None = None,
    ledger: ExecutionLedger | None = None,
    *,
    step: int = 0,
    reason: str = "",
    contract: TaskContract | None = None,
    envmap: Any | None = None,
    dynamic_state: Mapping[str, Any] | None = None,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Build the sole neutral PCR Verifier packet.

    The raw task remains semantic authority. The packet exposes current factual
    state and the exact bound Primary submission without reconstructing a second
    objective/proof plan or leaking Solver journey narrative.
    """
    if compiled is None or ledger is None:
        raise TypeError("compiled and ledger are required")
    contract_payload = _task_contract_payload(compiled, contract)
    raw_task_binding = build_binding(compiled.task_prompt, contract_payload)
    packet = {
        "schema_version": "verifier_packet.v3",
        "verifier_evidence_admissibility_version": "v3",
        "snapshot_id": str(snapshot_id or f"step-{step}"),
        "reason": reason,
        "step": step,
        "task_contract": contract_payload,
        "raw_user_task": compiled.task_prompt,
        "raw_task_sha256": raw_task_binding["raw_task_sha256"],
        "task_contract_sha256": raw_task_binding["contract_sha256"],
        "raw_task_binding": raw_task_binding,
        "stable_envmap": _stable_envmap_payload(envmap, compiled),
        "dynamic_state": _dynamic_state_payload(ledger, dynamic_state),
        "open_obligations": [],
        "active_findings": [],
        "state_inspection_handles": _collect_state_handles(ledger),
        "authoritative_check_ids": [],
        "compiled_evidence_requirements": [],
        "inspection_evidence_ceilings": {},
        "evidence_requirements": {
            "required": [],
            "minimum_completion": [],
            "false_positive_risks": [],
            "re_derivable_claims": [],
            "local_limits": [],
        },
        "raw_state_candidates": [],
        "task_state_snapshot_digest": ledger.task_state_snapshot_digest(),
        "task_state_snapshot_known": ledger.task_state_snapshot_known(),
    }
    if getattr(compiled, "task_contract_identity", ""):
        packet["task_contract_identity"] = compiled.task_contract_identity
    primary_submission = _pcr_primary_submission_payload(
        ledger, strict_snapshot_binding=True,
    )
    if primary_submission is None:
        raise ValueError("PCR Verifier activation requires a bound Primary Agent claim")
    claim_snapshot = str(primary_submission.get("task_state_snapshot_digest", ""))
    if str(primary_submission.get("snapshot_binding_version", "")) != TASK_STATE_SNAPSHOT_BINDING_VERSION:
        raise ValueError("PCR Primary Agent claim has an invalid task-state snapshot schema")
    if not claim_snapshot or claim_snapshot != packet["task_state_snapshot_digest"]:
        raise ValueError("PCR Primary Agent claim is bound to a stale task-state snapshot")
    if (primary_submission.get("task_state_snapshot_known") is True) != packet["task_state_snapshot_known"]:
        raise ValueError("PCR Primary Agent claim task-state knowledge flag is stale")
    packet["primary_submission"] = primary_submission
    packet["runtime_identity"] = deepcopy(
        dict(getattr(ledger, "runtime_identity", {}) or {})
    )
    forbidden = {
        "solver_claim", "submit_summary", "privileged_solver_proof",
        "solver_proof", "proof_contract", "proof_contract_analysis",
        "solver_authored_evidence", "recent_actions", "recent_receipts",
        "latest_file_reads", "command_results", "memory_loop_feedback",
        "automatic_memory_findings", "no_progress_controls", "artifact_history",
        "memory_events", "observations", "solver_system_prompt",
    }
    leaked = forbidden.intersection(packet)
    if leaked:
        raise AssertionError(f"verifier packet leaked solver journey fields: {sorted(leaked)}")
    validate_verifier_packet(packet, expected_raw_task=compiled.task_prompt)
    return _freeze(packet)

def packet_state_signature(packet: Mapping[str, Any]) -> str:
    """Stable signature of the packet's MATERIAL state.

    Volatile bookkeeping (step counters, finding ages, handle ids embedding
    step numbers) is excluded: two packets with the same signature describe
    the same world, so re-judging the second is pure waste.
    """
    handles = []
    for handle in packet.get("state_inspection_handles") or ():
        if isinstance(handle, Mapping):
            handles.append({
                "kind": handle.get("kind"),
                "path": handle.get("path", ""),
                "stream": handle.get("stream", ""),
                "bytes": handle.get("bytes"),
                "content_hash": handle.get("content_hash", ""),
            })
    def _material(value: Any) -> Any:
        """Normalize packet content while dropping only volatile counters.

        Finding and obligation IDs are not sufficient identity: a verifier can
        revise the summary, evidence, status, or target while retaining the
        same ID.  Keep every material field in the signature, but ignore age
        bookkeeping so repeated judgments of unchanged state still coalesce.
        """
        if isinstance(value, Mapping):
            return {
                str(key): _material(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                if str(key) not in {"age_steps", "stale_cycles"}
            }
        if isinstance(value, (list, tuple)):
            return [_material(item) for item in value]
        return deepcopy(value)

    material = {
        "schema_version": packet.get("schema_version", ""),
        "verifier_evidence_admissibility_version": packet.get(
            "verifier_evidence_admissibility_version", ""
        ),
        "reason": packet.get("reason", ""),
        "task_contract": packet.get("task_contract", {}),
        "task_contract_identity": packet.get("task_contract_identity", ""),
        "raw_user_task": packet.get("raw_user_task", ""),
        "raw_task_sha256": packet.get("raw_task_sha256", ""),
        "task_contract_sha256": packet.get("task_contract_sha256", ""),
        "stable_envmap": packet.get("stable_envmap", {}),
        "dynamic_state": packet.get("dynamic_state", {}),
        "task_state_snapshot_digest": packet.get("task_state_snapshot_digest", ""),
        "task_state_snapshot_known": packet.get("task_state_snapshot_known", False),
        "handles": handles,
        "obligations": sorted(
            (_material(o) for o in (packet.get("open_obligations") or ()) if isinstance(o, Mapping)),
            key=stable_json,
        ),
        "findings": sorted(
            (_material(f) for f in (packet.get("active_findings") or ()) if isinstance(f, Mapping)),
            key=stable_json,
        ),
        "evidence_requirements": packet.get("evidence_requirements", {}),
        "compiled_evidence_requirements": packet.get("compiled_evidence_requirements", ()),
        "inspection_evidence_ceilings": packet.get("inspection_evidence_ceilings", {}),
        "raw_state_candidates": packet.get("raw_state_candidates", ()),
        "authoritative_check_ids": packet.get("authoritative_check_ids", ()),
        "primary_submission": packet.get("primary_submission", {}),
        "runtime_identity": packet.get("runtime_identity", {}),
    }
    if packet.get("compiled_proof_requirements"):
        material["compiled_proof_requirements"] = packet.get("compiled_proof_requirements")
        material["proof_requirements_identity"] = packet.get("proof_requirements_identity", "")
    return sha256(stable_json(material).encode("utf-8")).hexdigest()[:16]
