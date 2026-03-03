from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict, List, Mapping

from ..utils.hashes import stable_hash
from .sandbox import FixtureBuilder


FixtureBuilderFn = Callable[[FixtureBuilder], None]


DEFAULT_ENUM_REGISTRY: Dict[str, List[str]] = {
    "event_type": [
        "BUDGET_CHECK",
        "CONTEXTSLICE_BINDING",
        "EXPLORATION_FLOOR_EVAL",
        "PHASE_TRANSITION_DENIED",
    ],
    "phase_reason_code": [
        "allowlist",
        "default_allow",
        "default_deny",
    ],
    "summary_reason_code": [
        "audit_tamper_detected",
        "benchify_detected",
        "commit_success",
        "dlp_blocked",
        "external_side_effect_rollback_limitation",
        "fail_budget",
        "fail_stuck",
        "manifest_missing",
        "model_call_timeout",
        "replay_mismatch_detected",
        "toctou_denied",
        "unknown_enum_value",
        "verifier_timeout",
        "verifier_missing_or_failed",
        "tool_timeout",
    ],
    "deny_reason_code": [
        "PATH_TRAVERSAL",
        "PLAN_MISMATCH",
        "REPEAT_FAILED_ATTEMPT",
        "RETRY_NO_PROGRESS",
        "SCRIPT_HASH_NOT_ALLOWLISTED",
        "STALE_STATE_HASH",
    ],
    "violation_code": [
        "BENCHIFY_STATIC_ROUTE",
        "DLP_BLOCK",
        "MISSING_MANIFEST",
        "OVERRIDE_ATTEMPT",
        "UNKNOWN_ENUM",
        "UNTRUSTED_WITHOUT_DELIMITERS",
    ],
    "approval_type": [
        "BUDGET_EXTENSION",
        "DLP_OVERRIDE",
        "EXTERNAL_EFFECT_WAIVER",
        "PLAN_WAIVER",
    ],
    "approval_reason_code": [
        "ALLOWLIST_APPROVAL",
        "BUDGET_EXTENSION_APPROVED",
        "EXTERNAL_EFFECT_ACCEPTED",
    ],
    "reanchor_trigger_code": [
        "REANCHOR_REPEAT_SIGNATURE",
        "REANCHOR_TOOL_ERROR_STREAK",
    ],
    "risk_class": ["LOW", "MED", "HIGH"],
    "tool_category": ["EXECUTION", "FILESYSTEM", "NETWORK", "VERIFIER"],
    "trust_level": ["LOW", "TRUSTED", "UNTRUSTED"],
    "truncation_flags": ["NONE", "STDERR_TrunCATED", "STDOUT_TrunCATED", "UNKNOWN"],
    "plan_status": ["APPROVED", "COMPLETE", "DRAFT", "UPDATED_REQUIRED"],
    "plan_update_reason_code": ["PLAN_MISMATCH", "REANCHOR_REPEAT"],
    "verifier_stage": ["A", "B", "C"],
}


def _run_id(builder: FixtureBuilder) -> str:
    return f"run::{builder.fixture_name}"


def _enum_registry_hash() -> str:
    return stable_hash({"enums": DEFAULT_ENUM_REGISTRY})


def _seed_core(
    builder: FixtureBuilder,
    *,
    profile: str = "eval",
    include_intent: bool = True,
    include_contract: bool = True,
    include_plan: bool = True,
    include_context: bool = True,
    plan_status: str = "APPROVED",
    workspace_hash: str = "ws_fp_1",
) -> Dict[str, str | int]:
    run_id = _run_id(builder)

    builder.append_event(
        "run_START",
        run_id=run_id,
        policy_profile=profile,
        policy_hash=builder.policy_hash,
        enum_registry_hash=_enum_registry_hash(),
        model_profile_id=f"{profile}_model_v1",
        workspace_fingerprint_hash=workspace_hash,
        tool_surface_profile={
            "tools": ["run", "request_phase_transition"],
            "interpreters": [],
            "policy_profile": profile,
        },
    )

    state: Dict[str, str | int] = {
        "run_id": run_id,
        "workspace_hash": workspace_hash,
        "plan_id": "plan::v1",
        "plan_version_id": 1,
        "completion_contract_id": "completion_contract::v1",
        "manifest_ref": "",
        "context_ref": "",
    }

    if include_intent:
        intent_schema = {
            "goal_statement": "Implement deterministic eval flow",
            "deliverables": ["events", "receipts", "manifests"],
            "acceptance_criteria": ["verifier pass", "hash chain valid"],
            "risk_profile": "workspace_write",
            "environment_assumptions": ["repo_present", "sandboxed"],
        }
        intent_contract_id = f"intent::{builder.fixture_name}"
        builder.append_event(
            "INTENT_CONTRACT_DEFINED",
            run_id=run_id,
            intent_contract_id=intent_contract_id,
            intent_contract=intent_schema,
            schema_hash=stable_hash(intent_schema),
            artifact_refs=[builder.put_json(intent_schema)],
        )
        builder.append_event(
            "INTENT_COMPLETENESS_CHECK",
            run_id=run_id,
            **{"pass": True},
            missing_fields=[],
        )

    if include_contract:
        completion_contract = {
            "requires": ["VERIFIER_RESULT", "COMPLETION_EVIDENCE_BUNDLE_CREATED"],
            "outcome": "SUCCESS",
        }
        builder.append_event(
            "CONTRACT_DEFINED",
            run_id=run_id,
            completion_contract_id=state["completion_contract_id"],
            schema_hash=stable_hash(completion_contract),
            artifact_refs=[builder.put_json(completion_contract)],
        )

    if include_plan:
        plan_payload = {
            "plan_id": state["plan_id"],
            "plan_version_id": state["plan_version_id"],
            "status": plan_status,
            "required_verifiers": ["verifier.stage_b"],
            "steps": [
                {"id": 1, "name": "run verifier", "risk": "MED"},
                {"id": 2, "name": "commit", "risk": "LOW"},
            ],
        }
        builder.append_event(
            "PLAN_DEFINED",
            run_id=run_id,
            plan_id=state["plan_id"],
            plan_version_id=state["plan_version_id"],
            status=plan_status,
            required_verifiers=plan_payload["required_verifiers"],
            plan_hash=stable_hash(plan_payload),
            artifact_refs=[builder.put_json(plan_payload)],
        )
        builder.append_event(
            "PLAN_STATUS_CHANGED",
            run_id=run_id,
            plan_id=state["plan_id"],
            from_status="DRAFT",
            to_status=plan_status,
            reason_code="allowlist",
        )

    if include_context:
        context_pack = {
            "doctrine": [{"source_ref": "doctrine:v1", "content": "Verifier-backed completion only"}],
            "task": [{"source_ref": "task:fixture", "content": builder.fixture_name}],
            "verification": [{"source_ref": "verifier:plan", "content": "python3 -m unittest"}],
            "untrusted": [],
            "conflicts": [],
        }
        manifest = {
            "selected": ["doctrine:v1", "task:fixture"],
            "dropped": [],
            "conflicts": [],
        }

        context_ref = builder.put_json(context_pack)
        manifest_ref = builder.put_json(manifest)
        state["context_ref"] = context_ref
        state["manifest_ref"] = manifest_ref

        slice_hash = stable_hash({"source_ref": "task:fixture", "content": builder.fixture_name})
        builder.append_event(
            "CONTEXTPACK_COMPILED",
            run_id=run_id,
            manifest_id=f"manifest::{builder.fixture_name}",
            context_pack_ref=context_ref,
            context_pack_hash=stable_hash(context_pack),
            manifest_ref=manifest_ref,
            manifest_hash=stable_hash(manifest),
            slice_list=[
                {
                    "id": "slice::task",
                    "trust_level": "TRUSTED",
                    "hash": slice_hash,
                    "token_est": 24,
                    "truncation_flags": "NONE",
                    "layer": "TASK",
                    "content_preview": builder.fixture_name,
                }
            ],
            compiler_mode="normal",
            reasons=[],
            artifact_refs=[context_ref, manifest_ref],
            workspace_fingerprint_hash=workspace_hash,
        )

    return state


def _append_verifier_pass(builder: FixtureBuilder, state: Mapping[str, str | int]) -> Dict[str, object]:
    run_id = str(state["run_id"])
    verifier_id = "verifier.stage_b"

    builder.append_event(
        "VERIFIER_run",
        run_id=run_id,
        verifier_id=verifier_id,
        params_hash=stable_hash({"suite": "unit", "stage": "B"}),
        verifier_stage="B",
    )

    stdout_ref = builder.put_text("ok\n")
    stderr_ref = builder.put_text("")
    args = ["python3", "-m", "unittest"]
    builder.append_event(
        "TOOL_CALL",
        run_id=run_id,
        tool_name="python3 -m unittest",
        tool_category="VERIFIER",
        args_hash=stable_hash({"argv": args}),
        start_ts="2026-02-08T00:00:01Z",
        end_ts="2026-02-08T00:00:02Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref,
        stderr_hash=stderr_ref,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 3, "stderr": 0},
        side_effects=[],
        side_effect_scope="NONE",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state.get("plan_id"),
        plan_version_id=state.get("plan_version_id"),
        plan_step_id=1,
        artifact_refs=[stdout_ref, stderr_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )

    builder.append_event(
        "VERIFIER_RESULT",
        run_id=run_id,
        verifier_id=verifier_id,
        **{"pass": True},
        evidence_receipt_ids=[stdout_ref, stderr_ref],
        verifier_stage="B",
        verifier_run=True,
        verifier_result="pass",
        artifact_refs=[stdout_ref, stderr_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )

    return {
        "verifier_id": verifier_id,
        "receipt_ids": [stdout_ref, stderr_ref],
    }


def _append_step_commit(
    builder: FixtureBuilder,
    state: Mapping[str, str | int],
    *,
    valid: bool,
    missing_components: List[str] | None = None,
) -> None:
    missing = list(missing_components or [])
    builder.append_event(
        "STEP_COMMIT",
        run_id=str(state["run_id"]),
        valid=valid,
        missing_components=missing,
        workspace_hash=str(state["workspace_hash"]),
        workspace_hash_full=str(state["workspace_hash"]),
        workspace_hash_incremental=str(state["workspace_hash"]),
        commit_status="valid" if valid else "missing_components",
    )


def _append_completion_bundle(
    builder: FixtureBuilder,
    state: Mapping[str, str | int],
    *,
    receipt_ids: List[str],
) -> str:
    bundle_id = f"bundle::{builder.fixture_name}"
    builder.append_event(
        "COMPLETION_EVIDENCE_BUNDLE_CREATED",
        run_id=str(state["run_id"]),
        completion_evidence_bundle_id=bundle_id,
        completion_contract_id=str(state["completion_contract_id"]),
        plan_version_id=state.get("plan_version_id"),
    )
    return bundle_id


def _append_log_check(
    builder: FixtureBuilder,
    state: Mapping[str, str | int],
    *,
    ok: bool,
    first_bad_event_id: str | None = None,
) -> None:
    builder.append_event(
        "LOG_INTEGRITY_CHECK",
        run_id=str(state["run_id"]),
        **{"pass": ok},
        first_bad_event_id=first_bad_event_id,
    )


def _append_run_end(
    builder: FixtureBuilder,
    state: Mapping[str, str | int],
    *,
    terminal_outcome: str,
    summary_reason_code: str,
    completion_evidence_bundle_id: str | None,
    required_receipt_ids: List[str],
    required_manifest_ids: List[str],
    final_report_artifact_id: str | None = None,
) -> None:
    report_ref = final_report_artifact_id
    if report_ref is None and terminal_outcome == "SUCCESS":
        report_payload = {
            "schema_version": "final_report_v1_1",
            "run_id": str(state["run_id"]),
            "terminal_outcome": terminal_outcome,
            "claims": [
                {
                    "claim_id": "claim::completion",
                    "statement": "run completed with verifier-backed evidence.",
                    "evidence_refs": sorted(
                        {
                            *[ref for ref in required_receipt_ids if isinstance(ref, str)],
                            *[ref for ref in required_manifest_ids if isinstance(ref, str)],
                        }
                    ),
                }
            ],
        }
        report_ref = builder.put_json(report_payload)

    builder.append_event(
        "run_END",
        run_id=str(state["run_id"]),
        terminal_outcome=terminal_outcome,
        summary_reason_code=summary_reason_code,
        completion_evidence_bundle_id=completion_evidence_bundle_id,
        required_receipt_ids=list(required_receipt_ids),
        required_manifest_ids=list(required_manifest_ids),
        final_report_artifact_id=report_ref,
        artifact_refs=[report_ref] if isinstance(report_ref, str) else [],
        termination_reason=summary_reason_code,
    )


def _fixture_contract_success(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="prod", workspace_hash="ws_fp_contract")
    verifier = _append_verifier_pass(builder, state)
    _append_step_commit(builder, state, valid=True)

    builder.append_event(
        "PLAN_STATUS_CHANGED",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        from_status="APPROVED",
        to_status="COMPLETE",
        reason_code="allowlist",
    )

    bundle_id = _append_completion_bundle(builder, state, receipt_ids=list(verifier["receipt_ids"]))
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=list(verifier["receipt_ids"]),
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_missing_verifier_blocks_success(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_missing_verifier")
    _append_step_commit(builder, state, valid=False, missing_components=["VERIFIER_RESULT"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="verifier_missing_or_failed",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_missing_manifest_fails(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", include_context=False, workspace_hash="ws_fp_missing_manifest")

    context_pack = {"task": builder.fixture_name, "note": "manifest intentionally missing"}
    context_ref = builder.put_json(context_pack)
    builder.append_event(
        "CONTEXTPACK_COMPILED",
        run_id=str(state["run_id"]),
        manifest_id=None,
        context_pack_ref=context_ref,
        context_pack_hash=stable_hash(context_pack),
        slice_list=[],
        compiler_mode="normal",
        reasons=["manifest_missing"],
        artifact_refs=[context_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "POLICY_VIOLATION",
        run_id=str(state["run_id"]),
        violation_code="MISSING_MANIFEST",
    )

    _append_step_commit(builder, state, valid=False, missing_components=["manifest_ref"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="manifest_missing",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[],
    )


def _fixture_replay_divergence_detected(builder: FixtureBuilder) -> None:
    state = _seed_core(
        builder,
        profile="eval",
        include_context=False,
        include_plan=False,
        include_contract=False,
        include_intent=False,
        workspace_hash="ws_fp_replay",
    )
    replay_id = f"replay::{builder.fixture_name}"
    builder.append_event(
        "REPLAY_START",
        run_id=str(state["run_id"]),
        replay_id=replay_id,
        policy_hash=builder.policy_hash,
    )
    builder.append_event(
        "MODEL_ROUTE_DECISION",
        run_id=str(state["run_id"]),
        from_model_id="planner-v1",
        to_model_id="planner-v1",
        reason_codes=["allowlist"],
        signals_hash=stable_hash({"fixture": builder.fixture_name, "route": "stable"}),
    )
    builder.append_event(
        "TOOL_DENY",
        run_id=str(state["run_id"]),
        tool_name="python3 -m unittest",
        deny_reason_code="PLAN_MISMATCH",
        attempted_action_fingerprint=stable_hash({"fixture": builder.fixture_name, "deny": 1}),
    )
    builder.append_event(
        "VERIFIER_run",
        run_id=str(state["run_id"]),
        verifier_id="verifier.stage_b",
        params_hash=stable_hash({"fixture": builder.fixture_name, "stage": "B"}),
        verifier_stage="B",
    )
    builder.append_event(
        "DIVERGENCE_DETECTED",
        run_id=str(state["run_id"]),
        replay_id=replay_id,
        step_id=4,
        divergence_type="decision",
        decision_event_type="MODEL_ROUTE_DECISION",
        recorded_value_hash="a" * 64,
        replay_value_hash="b" * 64,
    )
    builder.append_event(
        "REPLAY_END",
        run_id=str(state["run_id"]),
        replay_id=replay_id,
        **{"pass": False},
        divergence_rate=1.0,
        first_divergent_step_id=1,
    )
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="replay_mismatch_detected",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[],
    )


def _fixture_replay_zero_divergence(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_replay_zero")
    replay_id = f"replay::{builder.fixture_name}"

    builder.append_event(
        "MODEL_ROUTE_DECISION",
        run_id=str(state["run_id"]),
        from_model_id="planner-v1",
        to_model_id="planner-v1",
        reason_codes=["allowlist"],
        signals_hash=stable_hash({"fixture": builder.fixture_name, "route": "stable"}),
    )
    builder.append_event(
        "TOOL_DENY",
        run_id=str(state["run_id"]),
        tool_name="python3 -m unittest",
        deny_reason_code="PLAN_MISMATCH",
        attempted_action_fingerprint=stable_hash({"fixture": builder.fixture_name, "deny": 1}),
    )
    builder.append_event(
        "VERIFIER_run",
        run_id=str(state["run_id"]),
        verifier_id="verifier.stage_b",
        params_hash=stable_hash({"fixture": builder.fixture_name, "stage": "B"}),
        verifier_stage="B",
    )
    model_call = builder.append_event(
        "MODEL_CALL",
        run_id=str(state["run_id"]),
        model_id="planner-v1",
        input_tokens_est=120,
        output_tokens=48,
        latency_ms=800,
        timeout=False,
    )
    builder.append_event(
        "CONTEXTSLICE_BINDING",
        run_id=str(state["run_id"]),
        step_id=model_call["step_id"],
        context_pack_hash=stable_hash({"context_ref": str(state["context_ref"])}),
        manifest_hash=stable_hash({"manifest_ref": str(state["manifest_ref"])}),
        model_request_hash=stable_hash({"fixture": builder.fixture_name, "request": 1}),
        artifact_refs=[str(state["context_ref"])],
    )

    builder.append_event(
        "REPLAY_START",
        run_id=str(state["run_id"]),
        replay_id=replay_id,
        policy_hash=builder.policy_hash,
    )
    builder.append_event(
        "REPLAY_END",
        run_id=str(state["run_id"]),
        replay_id=replay_id,
        **{"pass": True},
        divergence_rate=0.0,
        first_divergent_step_id=None,
    )
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_UNKNOWN",
        summary_reason_code="fail_stuck",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_static_scan_no_benchify(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_static_ok")
    verifier = _append_verifier_pass(builder, state)
    builder.append_event(
        "MODEL_ROUTE_DECISION",
        run_id=str(state["run_id"]),
        from_model_id="planner-v1",
        to_model_id="planner-v1",
        reason_codes=["allowlist"],
        signals_hash=stable_hash({"risk": "LOW", "compiler_mode": "normal"}),
    )
    _append_step_commit(builder, state, valid=True)
    bundle_id = _append_completion_bundle(builder, state, receipt_ids=list(verifier["receipt_ids"]))
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=list(verifier["receipt_ids"]),
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_static_scan_dynamic_randomization(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_static_dynamic")
    verifier = _append_verifier_pass(builder, state)

    signal_payload = {
        "seed": "v1_1_static_scan_seed_42",
        "risk": "LOW",
        "compiler_mode": "normal",
    }
    signals_hash = stable_hash(signal_payload)
    builder.append_event(
        "MODEL_ROUTE_DECISION",
        run_id=str(state["run_id"]),
        from_model_id="planner-v1",
        to_model_id="planner-v1",
        reason_codes=["allowlist"],
        signals_hash=signals_hash,
        randomization_seed=signal_payload["seed"],
    )
    builder.append_event(
        "MODEL_ROUTE_DECISION",
        run_id=str(state["run_id"]),
        from_model_id="planner-v1",
        to_model_id="planner-v1",
        reason_codes=["allowlist"],
        signals_hash=signals_hash,
        randomization_seed=signal_payload["seed"],
    )

    _append_step_commit(builder, state, valid=True)
    bundle_id = _append_completion_bundle(builder, state, receipt_ids=list(verifier["receipt_ids"]))
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=list(verifier["receipt_ids"]),
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_static_scan_fail(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_static_fail")
    builder.append_event(
        "POLICY_VIOLATION",
        run_id=str(state["run_id"]),
        violation_code="BENCHIFY_STATIC_ROUTE",
        violation_detail={
            "file": "policy.py",
            "pattern": "task_id",
        },
    )
    _append_step_commit(builder, state, valid=False, missing_components=["policy_clearance"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="benchify_detected",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_plan_mismatch_updated_required(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_plan")
    attempted_action_fingerprint = stable_hash({"tool": "python3 -m unittest", "args": ["-k", "plan"]})

    builder.append_event(
        "TOOL_DENY",
        run_id=str(state["run_id"]),
        tool_name="python3 -m unittest",
        deny_reason_code="PLAN_MISMATCH",
        attempted_action_fingerprint=attempted_action_fingerprint,
    )
    builder.append_event(
        "PLAN_STATUS_CHANGED",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        from_status="APPROVED",
        to_status="UPDATED_REQUIRED",
        reason_code="PLAN_MISMATCH",
    )

    diff_payload = {
        "changes": [{"step": 1, "old": "verify", "new": "verify_then_commit"}],
        "reason": "plan mismatch",
    }
    diff_ref = builder.put_json(diff_payload)
    builder.append_event(
        "PLAN_UPDATE",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        from_plan_version_id=1,
        to_plan_version_id=2,
        diff_artifact_id=diff_ref,
        diff_content_hash=stable_hash(diff_payload),
        update_reason_code="PLAN_MISMATCH",
        artifact_refs=[diff_ref],
    )
    builder.append_event(
        "PLAN_STATUS_CHANGED",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        from_status="UPDATED_REQUIRED",
        to_status="APPROVED",
        reason_code="allowlist",
    )

    state["plan_version_id"] = 2
    verifier = _append_verifier_pass(builder, state)
    builder.append_event(
        "PLAN_STEP_STATUS",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        status="DONE",
        evidence_receipt_ids=list(verifier["receipt_ids"]),
        verifier_ids=[str(verifier["verifier_id"])],
    )
    builder.append_event(
        "PLAN_STATUS_CHANGED",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        from_status="APPROVED",
        to_status="COMPLETE",
        reason_code="allowlist",
    )

    _append_step_commit(builder, state, valid=True)
    bundle_id = _append_completion_bundle(builder, state, receipt_ids=list(verifier["receipt_ids"]))
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=list(verifier["receipt_ids"]),
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_toctou_stale_hash_denies(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_toctou")
    builder.append_event(
        "TOOL_DENY",
        run_id=str(state["run_id"]),
        tool_name="write_file",
        deny_reason_code="STALE_STATE_HASH",
        attempted_action_fingerprint=stable_hash({"tool": "write_file", "path": "main.py"}),
        expected_preimage_hash="a" * 64,
        observed_preimage_hash="b" * 64,
    )
    _append_step_commit(builder, state, valid=False, missing_components=["workspace_hash_freshness"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="toctou_denied",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_reanchor_repeat_breaker(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_reanchor")
    signature = stable_hash({"fixture": builder.fixture_name, "kind": "reanchor_repeat"})

    builder.append_event(
        "REANCHOR_START",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_REPEAT_SIGNATURE",
        state_hash_before="state_before_1",
        workspace_hash=str(state["workspace_hash"]),
        verifier_status_digest="digest_1",
        reanchor_signature=signature,
    )
    builder.append_event(
        "REANCHOR_END",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_REPEAT_SIGNATURE",
        state_hash_after="state_after_1",
        workspace_hash=str(state["workspace_hash"]),
        rebuilt_components=["planner"],
        cleared_components=["stale_hypothesis"],
        reanchor_summary_artifact_id=builder.put_json({"summary": "first reanchor"}),
    )
    builder.append_event(
        "REANCHOR_START",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_REPEAT_SIGNATURE",
        state_hash_before="state_after_1",
        workspace_hash=str(state["workspace_hash"]),
        verifier_status_digest="digest_2",
        reanchor_signature=signature,
    )
    builder.append_event(
        "REANCHOR_REPEAT_DETECTED",
        run_id=str(state["run_id"]),
        reanchor_signature=signature,
        count=2,
        window_steps=5,
        action_taken="PLAN_UPDATE",
    )

    diff_ref = builder.put_json({"reason": "reanchor repeat", "update": "force plan refresh"})
    builder.append_event(
        "PLAN_UPDATE",
        run_id=str(state["run_id"]),
        plan_id=state["plan_id"],
        from_plan_version_id=1,
        to_plan_version_id=2,
        diff_artifact_id=diff_ref,
        diff_content_hash=stable_hash({"reason": "reanchor repeat", "update": "force plan refresh"}),
        update_reason_code="REANCHOR_REPEAT",
        artifact_refs=[diff_ref],
    )

    _append_step_commit(builder, state, valid=False, missing_components=["loop_resolution"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_STUCK",
        summary_reason_code="fail_stuck",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_log_tamper_detected(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_tamper")
    _append_log_check(builder, state, ok=False, first_bad_event_id="tampered_event")
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="audit_tamper_detected",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )

    # Tamper with the last event after hash computation to force hash-chain failure.
    builder.events[-1]["cwd"] = "/tampered"


def _fixture_dlp_blocks_success(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_dlp")
    stdout_ref = builder.put_text("sk-test1234567890 leaked")
    stderr_ref = builder.put_text("")

    builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="python3 -c print('secret')",
        tool_category="EXECUTION",
        args_hash=stable_hash({"argv": ["python3", "-c", "print('secret')"]}),
        start_ts="2026-02-08T00:00:01Z",
        end_ts="2026-02-08T00:00:02Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref,
        stderr_hash=stderr_ref,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 22, "stderr": 0},
        side_effects=[],
        side_effect_scope="NONE",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=1,
        artifact_refs=[stdout_ref, stderr_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "DLP_SCAN_RESULT",
        run_id=str(state["run_id"]),
        hit_count=1,
        blocked=True,
    )
    builder.append_event(
        "REDACTION_APPLIED",
        run_id=str(state["run_id"]),
        count=1,
        types=["API_KEY"],
    )
    builder.append_event(
        "POLICY_VIOLATION",
        run_id=str(state["run_id"]),
        violation_code="DLP_BLOCK",
    )
    _append_step_commit(builder, state, valid=False, missing_components=["approval_override"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="dlp_blocked",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[stdout_ref],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_unknown_enum_blocks_success(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_unknown_enum")
    builder.append_event(
        "TOOL_DENY",
        run_id=str(state["run_id"]),
        tool_name="python3 -m unittest",
        deny_reason_code="UNKNOWN_NEW_REASON",
        attempted_action_fingerprint=stable_hash({"tool": "python3 -m unittest"}),
    )
    builder.append_event(
        "POLICY_VIOLATION",
        run_id=str(state["run_id"]),
        violation_code="UNKNOWN_ENUM",
    )
    _append_step_commit(builder, state, valid=False, missing_components=["enum_registry_validation"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="unknown_enum_value",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_external_side_effect_rollback_limitation(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="prod", workspace_hash="ws_fp_external")
    stdout_ref = builder.put_text("external write complete")
    stderr_ref = builder.put_text("")

    builder.append_event(
        "REANCHOR_START",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_TOOL_ERROR_STREAK",
        state_hash_before="state_before_external_write",
        workspace_hash=str(state["workspace_hash"]),
        verifier_status_digest="pre_external",
        reanchor_signature=stable_hash({"fixture": builder.fixture_name, "phase": "pre_rollback"}),
    )
    builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="network_call",
        tool_category="NETWORK",
        args_hash=stable_hash({"url": "https://example.com/resource", "method": "POST"}),
        start_ts="2026-02-08T00:00:01Z",
        end_ts="2026-02-08T00:00:02Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref,
        stderr_hash=stderr_ref,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 23, "stderr": 0},
        side_effects=[{"kind": "network_write", "target": "https://example.com/resource"}],
        side_effect_scope="EXTERNAL",
        reversibility="NOT_REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=1,
        artifact_refs=[stdout_ref, stderr_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "ROLLBACK_LIMITATION",
        run_id=str(state["run_id"]),
        limitation_code="EXTERNAL_STATE_IRREVERSIBLE",
        affected_receipt_ids=[stdout_ref],
    )
    builder.append_event(
        "REANCHOR_END",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_TOOL_ERROR_STREAK",
        state_hash_after="state_after_external_write",
        workspace_hash=str(state["workspace_hash"]),
        rebuilt_components=["rollback_assessment"],
        cleared_components=[],
        reanchor_summary_artifact_id=builder.put_json(
            {"summary": "rollback limitation recorded for external side effect"}
        ),
    )
    builder.append_event(
        "APPROVAL_GRANTED",
        run_id=str(state["run_id"]),
        approval_type="PLAN_WAIVER",
        actor_id="user:owner",
        approval_reason_code="EXTERNAL_EFFECT_ACCEPTED",
        actor_role="owner",
    )
    builder.append_event(
        "LOG_ANCHOR_WRITTEN",
        run_id=str(state["run_id"]),
        anchor_ref=builder.put_json({"anchor": builder.fixture_name, "state": "written"}),
    )
    builder.append_event(
        "LOG_ANCHOR_VERIFY",
        run_id=str(state["run_id"]),
        **{"pass": True},
        anchor_ref=builder.put_json({"anchor": builder.fixture_name, "state": "verified"}),
    )

    verifier = _append_verifier_pass(builder, state)
    _append_step_commit(builder, state, valid=True)
    bundle_id = _append_completion_bundle(
        builder,
        state,
        receipt_ids=[stdout_ref, *list(verifier["receipt_ids"])],
    )
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="external_side_effect_rollback_limitation",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=[stdout_ref, *list(verifier["receipt_ids"])],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_timeout_event_correctness(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_timeouts")

    builder.append_event(
        "MODEL_CALL",
        run_id=str(state["run_id"]),
        model_id="planner-v1",
        input_tokens_est=800,
        output_tokens=0,
        latency_ms=30000,
        timeout=True,
        timeout_ms=30000,
    )

    timeout_stdout = builder.put_text("")
    timeout_stderr = builder.put_text("tool timed out")
    builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="python3 -m unittest",
        tool_category="EXECUTION",
        args_hash=stable_hash({"argv": ["python3", "-m", "unittest"]}),
        start_ts="2026-02-08T00:00:10Z",
        end_ts="2026-02-08T00:00:40Z",
        exit_code="TIMEOUT",
        timeout=True,
        timeout_ms=30000,
        stdout_hash=timeout_stdout,
        stderr_hash=timeout_stderr,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 0, "stderr": 14},
        side_effects=[],
        side_effect_scope="NONE",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=1,
        artifact_refs=[timeout_stdout, timeout_stderr],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )

    builder.append_event(
        "VERIFIER_RESULT",
        run_id=str(state["run_id"]),
        verifier_id="verifier.stage_b",
        **{"pass": False},
        timeout=True,
        exit_code="TIMEOUT",
        verifier_stage="B",
        verifier_run=True,
        verifier_result="timeout",
    )

    _append_step_commit(builder, state, valid=False, missing_components=["timeout_recovery"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_ENV",
        summary_reason_code="tool_timeout",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[timeout_stdout, timeout_stderr],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_overdrive_cost_logging(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_overdrive_cost")
    overdrive_context = {
        "task": builder.fixture_name,
        "overdrive": True,
    }
    context_ref = builder.put_json(overdrive_context)
    manifest_ref = str(state["manifest_ref"])
    builder.append_event(
        "CONTEXTPACK_COMPILED",
        run_id=str(state["run_id"]),
        context_pack_ref=context_ref,
        context_pack_hash=stable_hash(overdrive_context),
        manifest_ref=manifest_ref,
        manifest_hash=None,
        slice_list=[
            {
                "id": "slice::task",
                "trust_level": "TRUSTED",
                "hash": stable_hash({"fixture": builder.fixture_name, "slice": "task"}),
                "token_est": 55,
                "token_budget": 100,
                "truncation_flags": "NONE",
                "layer": "TASK",
                "content_preview": builder.fixture_name,
            }
        ],
        compiler_mode="overdrive",
        overdrive_reason_code="EVIDENCE_PRESSURE",
        token_est=55,
        token_budget=100,
        artifact_refs=[context_ref, manifest_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "METRIC_SUMMARY",
        run_id=str(state["run_id"]),
        step_id=builder.events[-1]["step_id"],
        overdrive_cost_delta_usd=0.0142,
        overdrive_token_delta=320,
        overdrive_cost_impact=True,
        judge_type="objective",
        mean=0.8,
        worst=0.7,
        stdev=0.05,
        artifact_refs=[context_ref],
    )
    _append_step_commit(builder, state, valid=False, missing_components=["execution_not_attempted"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_UNKNOWN",
        summary_reason_code="fail_stuck",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_evidence_read_roles_and_verifier_order(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="prod", workspace_hash="ws_fp_audit_roles")
    builder.append_event(
        "VERIFIER_run",
        run_id=str(state["run_id"]),
        verifier_id="verifier.stage_b",
        params_hash=stable_hash({"suite": "unit", "stage": "B"}),
        verifier_stage="B",
    )
    builder.append_event(
        "EVIDENCE_READ",
        run_id=str(state["run_id"]),
        actor_id="op:alice",
        actor_role="operator",
        object_type="cas",
        object_id=str(state["manifest_ref"]),
        redacted=False,
    )
    builder.append_event(
        "EVIDENCE_READ",
        run_id=str(state["run_id"]),
        actor_id="dev:bob",
        actor_role="developer",
        object_type="cas",
        object_id=str(state["context_ref"]),
        redacted=False,
    )
    _append_step_commit(builder, state, valid=False, missing_components=["execution_not_attempted"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_UNKNOWN",
        summary_reason_code="fail_stuck",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_exploration_floor(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_exploration")
    builder.append_event(
        "EXPLORATION_FLOOR_EVAL",
        run_id=str(state["run_id"]),
        **{"pass": False},
        missing_conditions=["workspace_digest", "tool_versions"],
    )
    builder.append_event(
        "PHASE_TRANSITION_DENIED",
        run_id=str(state["run_id"]),
        from_phase="Explore",
        to_phase="Implement",
        reason="exploration_floor_not_met",
    )
    _append_step_commit(builder, state, valid=False, missing_components=["exploration_floor"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="exploration_floor_unmet",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_budget_exceeded(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_budget")
    builder.append_event(
        "BUDGET_CHECK",
        run_id=str(state["run_id"]),
        model_calls_used=99,
        model_calls_max=100,
        tool_calls_used=50,
        tool_calls_max=200,
        exceeded=False,
    )
    builder.append_event(
        "BUDGET_CHECK",
        run_id=str(state["run_id"]),
        model_calls_used=101,
        model_calls_max=100,
        exceeded=True,
        exceeded_field="model_calls",
    )
    _append_step_commit(builder, state, valid=False, missing_components=["budget_exceeded"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_BUDGET",
        summary_reason_code="budget_exceeded",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_phase_transitions(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_phases")
    builder.append_event(
        "PHASE_TRANSITION",
        run_id=str(state["run_id"]),
        from_phase="Orient",
        to_phase="Explore",
        phase_reason_code="allowlist",
    )
    builder.append_event(
        "PHASE_TRANSITION",
        run_id=str(state["run_id"]),
        from_phase="Explore",
        to_phase="Plan",
        phase_reason_code="allowlist",
    )
    builder.append_event(
        "REANCHOR_START",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_REPEAT_SIGNATURE",
        state_hash_before="state_pre",
        workspace_hash=str(state["workspace_hash"]),
        verifier_status_digest="digest_rean",
        reanchor_signature=stable_hash({"fixture": builder.fixture_name, "rean": 1}),
    )
    builder.append_event(
        "REANCHOR_END",
        run_id=str(state["run_id"]),
        trigger_code="REANCHOR_REPEAT_SIGNATURE",
        state_hash_after="state_post",
        workspace_hash=str(state["workspace_hash"]),
        rebuilt_components=["planner"],
        cleared_components=["scratch"],
        reanchor_summary_artifact_id=builder.put_json({"summary": "phase reanchor"}),
    )
    _append_step_commit(builder, state, valid=False, missing_components=["not_final"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_STUCK",
        summary_reason_code="fail_stuck",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_context_slice_binding(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_slices")
    slice_hash = stable_hash({"fixture": builder.fixture_name, "slice": "task"})
    context_pack = {"task": builder.fixture_name}
    context_ref = builder.put_json(context_pack)

    compiled_event = builder.append_event(
        "CONTEXTPACK_COMPILED",
        run_id=str(state["run_id"]),
        context_pack_ref=context_ref,
        context_pack_hash=stable_hash(context_pack),
        manifest_ref=str(state["manifest_ref"]),
        manifest_hash=None,
        slice_list=[
            {
                "id": "slice::task",
                "trust_level": "TRUSTED",
                "hash": slice_hash,
                "token_est": 50,
                "token_budget": 100,
                "truncation_flags": "NONE",
                "layer": "TASK",
                "content_preview": builder.fixture_name,
            }
        ],
        compiler_mode="normal",
        token_est=50,
        token_budget=100,
        artifact_refs=[context_ref, str(state["manifest_ref"])],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    model_call = builder.append_event(
        "MODEL_CALL",
        run_id=str(state["run_id"]),
        step_id=compiled_event["step_id"],
        model_id="planner-v1",
        input_tokens_est=50,
        output_tokens=20,
        latency_ms=450,
        timeout=False,
    )
    model_request_hash = stable_hash({"model": "planner-v1", "context": context_ref})
    builder.append_event(
        "CONTEXTSLICE_BINDING",
        run_id=str(state["run_id"]),
        step_id=model_call["step_id"],
        context_pack_hash=stable_hash(context_pack),
        manifest_hash=stable_hash({"manifest": str(state["manifest_ref"])}),
        model_request_hash=model_request_hash,
        artifact_refs=[context_ref],
    )
    _append_step_commit(builder, state, valid=False, missing_components=["not_final"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_UNKNOWN",
        summary_reason_code="fail_stuck",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_capability_scenario(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_capability")
    verifier = _append_verifier_pass(builder, state)
    stdout_ref = builder.put_text("patch applied successfully")
    stderr_ref = builder.put_text("")

    builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="git apply",
        tool_category="EXECUTION",
        args_hash=stable_hash({"argv": ["git", "apply", "patch.diff"]}),
        start_ts="2026-02-08T00:00:01Z",
        end_ts="2026-02-08T00:00:02Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref,
        stderr_hash=stderr_ref,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 26, "stderr": 0},
        side_effects=[],
        side_effect_scope="WORKSPACE_LOCAL",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=1,
        artifact_refs=[stdout_ref, stderr_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "METRIC_SUMMARY",
        run_id=str(state["run_id"]),
        step_id=builder.events[-1]["step_id"],
        judge_type="objective",
        mean=0.92,
        worst=0.85,
        stdev=0.03,
        efficiency_ceiling_penalty=0.08,
        scenario_family="repo_patch",
        recovery_competence=True,
        artifact_refs=[stdout_ref],
    )
    builder.append_event(
        "METRIC_SUMMARY",
        run_id=str(state["run_id"]),
        step_id=builder.events[-1]["step_id"],
        judge_type="objective",
        mean=0.88,
        worst=0.78,
        stdev=0.04,
        efficiency_ceiling_penalty=0.12,
        scenario_family="repo_patch",
        recovery_competence=True,
        recovery_from_failure=True,
        artifact_refs=[],
    )

    _append_step_commit(builder, state, valid=True)
    bundle_id = _append_completion_bundle(builder, state, receipt_ids=[stdout_ref, *list(verifier["receipt_ids"])])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=[stdout_ref, *list(verifier["receipt_ids"])],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_interpreter_allowlist(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_interp")
    script_content = "import sys; print(sys.version)"
    script_hash = stable_hash({"script": script_content})
    stdout_ref = builder.put_text("3.12.0")
    stderr_ref = builder.put_text("")

    builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="python3",
        tool_category="EXECUTION",
        args_hash=stable_hash({"argv": ["python3", "-c", script_content]}),
        start_ts="2026-02-08T00:00:01Z",
        end_ts="2026-02-08T00:00:02Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref,
        stderr_hash=stderr_ref,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 6, "stderr": 0},
        side_effects=[],
        side_effect_scope="NONE",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=1,
        script_hash_allowlisted=True,
        script_content_hash=script_hash,
        artifact_refs=[stdout_ref, stderr_ref],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "TOOL_DENY",
        run_id=str(state["run_id"]),
        tool_name="bash",
        deny_reason_code="SCRIPT_HASH_NOT_ALLOWLISTED",
        attempted_action_fingerprint=stable_hash({"tool": "bash", "script": "rm -rf /"}),
    )
    _append_step_commit(builder, state, valid=False, missing_components=["denied_tool"])
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="FAIL_POLICY",
        summary_reason_code="script_not_allowlisted",
        completion_evidence_bundle_id=None,
        required_receipt_ids=[stdout_ref],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


def _fixture_multi_step_run(builder: FixtureBuilder) -> None:
    state = _seed_core(builder, profile="eval", workspace_hash="ws_fp_multistep")

    # Step 1: successful tool call + commit
    stdout_ref_1 = builder.put_text("step 1 output")
    stderr_ref_1 = builder.put_text("")
    builder.append_event(
        "PHASE_TRANSITION",
        run_id=str(state["run_id"]),
        from_phase="Plan",
        to_phase="Implement",
        phase_reason_code="allowlist",
    )
    first_call = builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="python3 -m pytest",
        tool_category="EXECUTION",
        args_hash=stable_hash({"argv": ["python3", "-m", "pytest", "test_step1.py"]}),
        start_ts="2026-02-08T00:00:01Z",
        end_ts="2026-02-08T00:00:02Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref_1,
        stderr_hash=stderr_ref_1,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 14, "stderr": 0},
        side_effects=[],
        side_effect_scope="WORKSPACE_LOCAL",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=1,
        artifact_refs=[stdout_ref_1, stderr_ref_1],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "STEP_COMMIT",
        run_id=str(state["run_id"]),
        step_id=first_call["step_id"],
        valid=True,
        missing_components=[],
        workspace_hash=str(state["workspace_hash"]),
        workspace_hash_full=str(state["workspace_hash"]),
        workspace_hash_incremental=str(state["workspace_hash"]),
        commit_status="valid",
    )

    # Step 2: another tool call + commit
    stdout_ref_2 = builder.put_text("step 2 output")
    stderr_ref_2 = builder.put_text("")
    second_call = builder.append_event(
        "TOOL_CALL",
        run_id=str(state["run_id"]),
        tool_name="python3 -m pytest",
        tool_category="EXECUTION",
        args_hash=stable_hash({"argv": ["python3", "-m", "pytest", "test_step2.py"]}),
        start_ts="2026-02-08T00:00:03Z",
        end_ts="2026-02-08T00:00:04Z",
        exit_code=0,
        timeout=False,
        stdout_hash=stdout_ref_2,
        stderr_hash=stderr_ref_2,
        truncation_flags="NONE",
        persisted_byte_counts={"stdout": 14, "stderr": 0},
        side_effects=[],
        side_effect_scope="WORKSPACE_LOCAL",
        reversibility="REVERSIBLE",
        observed_workspace_hash_before=str(state["workspace_hash"]),
        expected_preimage_hash=str(state["workspace_hash"]),
        observed_preimage_hash=str(state["workspace_hash"]),
        re_read_required=False,
        plan_id=state["plan_id"],
        plan_version_id=state["plan_version_id"],
        plan_step_id=2,
        artifact_refs=[stdout_ref_2, stderr_ref_2],
        workspace_fingerprint_hash=str(state["workspace_hash"]),
    )
    builder.append_event(
        "STEP_COMMIT",
        run_id=str(state["run_id"]),
        step_id=second_call["step_id"],
        valid=True,
        missing_components=[],
        workspace_hash=str(state["workspace_hash"]),
        workspace_hash_full=str(state["workspace_hash"]),
        workspace_hash_incremental=str(state["workspace_hash"]),
        commit_status="valid",
    )

    # Verify + complete
    before_verifier_idx = len(builder.events)
    verifier = _append_verifier_pass(builder, state)
    verifier_calls = [
        event
        for event in builder.events[before_verifier_idx:]
        if event.get("event_type") == "TOOL_CALL"
    ]
    if verifier_calls:
        verifier_call = verifier_calls[-1]
        builder.append_event(
            "STEP_COMMIT",
            run_id=str(state["run_id"]),
            step_id=verifier_call["step_id"],
            valid=True,
            missing_components=[],
            workspace_hash=str(state["workspace_hash"]),
            workspace_hash_full=str(state["workspace_hash"]),
            workspace_hash_incremental=str(state["workspace_hash"]),
            commit_status="valid",
        )
    builder.append_event(
        "PHASE_TRANSITION",
        run_id=str(state["run_id"]),
        from_phase="Implement",
        to_phase="Verify",
        phase_reason_code="allowlist",
    )
    builder.append_event(
        "REPLAY_START",
        run_id=str(state["run_id"]),
        replay_id=f"replay::{builder.fixture_name}",
        policy_hash=builder.policy_hash,
    )
    builder.append_event(
        "REPLAY_END",
        run_id=str(state["run_id"]),
        replay_id=f"replay::{builder.fixture_name}",
        **{"pass": True},
        divergence_rate=0.0,
        first_divergent_step_id=None,
    )
    bundle_id = _append_completion_bundle(
        builder,
        state,
        receipt_ids=[stdout_ref_1, stdout_ref_2, *list(verifier["receipt_ids"])],
    )
    _append_log_check(builder, state, ok=True)
    _append_run_end(
        builder,
        state,
        terminal_outcome="SUCCESS",
        summary_reason_code="commit_success",
        completion_evidence_bundle_id=bundle_id,
        required_receipt_ids=[stdout_ref_1, stdout_ref_2, *list(verifier["receipt_ids"])],
        required_manifest_ids=[str(state["manifest_ref"])],
    )


FIXTURE_BUILDERS: Dict[str, FixtureBuilderFn] = {
    "fixture_contract_success": _fixture_contract_success,
    "fixture_missing_verifier_blocks_success": _fixture_missing_verifier_blocks_success,
    "fixture_missing_manifest_fails": _fixture_missing_manifest_fails,
    "fixture_replay_divergence_detected": _fixture_replay_divergence_detected,
    "fixture_replay_zero_divergence": _fixture_replay_zero_divergence,
    "fixture_static_scan_no_benchify": _fixture_static_scan_no_benchify,
    "fixture_static_scan_dynamic_randomization": _fixture_static_scan_dynamic_randomization,
    "fixture_static_scan_fail": _fixture_static_scan_fail,
    "fixture_plan_mismatch_updated_required": _fixture_plan_mismatch_updated_required,
    "fixture_toctou_stale_hash_denies": _fixture_toctou_stale_hash_denies,
    "fixture_reanchor_repeat_breaker": _fixture_reanchor_repeat_breaker,
    "fixture_log_tamper_detected": _fixture_log_tamper_detected,
    "fixture_dlp_blocks_success": _fixture_dlp_blocks_success,
    "fixture_unknown_enum_blocks_success": _fixture_unknown_enum_blocks_success,
    "fixture_external_side_effect_rollback_limitation": _fixture_external_side_effect_rollback_limitation,
    "fixture_timeout_event_correctness": _fixture_timeout_event_correctness,
    "fixture_overdrive_cost_logging": _fixture_overdrive_cost_logging,
    "fixture_evidence_read_roles_and_verifier_order": _fixture_evidence_read_roles_and_verifier_order,
    "fixture_exploration_floor": _fixture_exploration_floor,
    "fixture_budget_exceeded": _fixture_budget_exceeded,
    "fixture_phase_transitions": _fixture_phase_transitions,
    "fixture_context_slice_binding": _fixture_context_slice_binding,
    "fixture_capability_scenario": _fixture_capability_scenario,
    "fixture_interpreter_allowlist": _fixture_interpreter_allowlist,
    "fixture_multi_step_run": _fixture_multi_step_run,
}


def list_fixtures() -> List[str]:
    return sorted(FIXTURE_BUILDERS)


def materialize_fixture(name: str, out_root: str | Path) -> Path:
    if name not in FIXTURE_BUILDERS:
        raise KeyError(f"Unknown fixture: {name}")

    root = Path(out_root)
    fixture_dir = root / name

    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    builder = FixtureBuilder(fixture_dir, name)
    FIXTURE_BUILDERS[name](builder)

    enum_registry = dict(DEFAULT_ENUM_REGISTRY)
    if name == "fixture_unknown_enum_blocks_success":
        # Keep strict closed enum behavior by excluding the unknown reason.
        enum_registry = dict(DEFAULT_ENUM_REGISTRY)

    builder.finalize(enum_registry)
    return fixture_dir
