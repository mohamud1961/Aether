"""Host-side Harbor bridge for MLPCP v2.

This keeps MLPCP orchestration on the host and uses Harbor's environment API
for workspace interaction, avoiding any requirement that task images provide
Python.
"""

from __future__ import annotations
from .mlpcp_v2.lean_cockpit import build_lean_cockpit

import fnmatch
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from fnmatch import fnmatch
from typing import Any

from harbor.environments.base import BaseEnvironment

from runner.model_client import make_azure_gpt54_mini_route_from_env, make_azure_gpt53_codex_route_from_env, make_model_client_from_route

from .mlpcp_v2.capability_mapping import capability_conditions
from .mlpcp_v2.execute_plan import (
    ActionResult,
    ExecutePlanAction,
    ExecutePlanPolicy,
    ExecutePlanRequest,
    ExecutePlanResult,
    PathGuard,
)
from .mlpcp_v2.failure_classes import FailureClass
from .mlpcp_v2.finalization import FinalizationDecision, FinalizationGate
from .mlpcp_v2.final_completion import (
    COMPLETE_INTERNAL,
    REPAIR_REQUIRED,
    EVIDENCE_INSUFFICIENT,
    FinalCompletionDecision,
    RequiredRepair,
    build_final_verification_pack,
    validate_final_completion_decision,
    repair_packet_from_final_completion,
)
from .mlpcp_v2.integration import NoModelIntegrationSession
from .mlpcp_v2.live_model import RepoModelClientBridge
from .mlpcp_v2.model_io import (
    ModelCallRequest,
    ModelIOError,
    ModelMessage,
    parse_execute_plan_request,
    parse_success_contract,
)
from .mlpcp_v2.model_loop import ModelLoopConfig, ModelLoopRunResult, ModelLoopStep
from .mlpcp_v2.receipts import text_hash
from .mlpcp_v2.references import Reference
from .mlpcp_v2.verifier_critic import VerifierCriticRequest, VerifierCriticResult, VerifierCriticStub
from runner.mlpcp_v2_harbor_remote_env import build_remote_context, compact_remote_context_for_model
from runner.mlpcp_v2_harbor_compact import compact_execute_result_for_cockpit


REMOTE_WORKSPACE_ROOT = "/app"


from runner.mlpcp_v2.finalization import FinalizationDecision
from runner.mlpcp_v2.failure_classes import FailureClass, validate_failure_class

@dataclass
class HarborHostRunner:
    """Run MLPCP against a Harbor environment from the host side."""

    environment: BaseEnvironment
    run_id: str
    row_id: str
    workspace_root: Path
    receipt_root: Path
    model_config: dict[str, Any] | None = None
    loop_config: ModelLoopConfig | None = None
    execute_policy: ExecutePlanPolicy | None = None

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.resolve()
        self.receipt_root = self.receipt_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.receipt_root.mkdir(parents=True, exist_ok=True)
        self.session = NoModelIntegrationSession(
            run_id=self.run_id,
            row_id=self.row_id,
            workspace_root=self.workspace_root,
            receipt_root=self.receipt_root,
        )
        self.guard = PathGuard(self.workspace_root, self.execute_policy or ExecutePlanPolicy())
        self.finalization_gate = FinalizationGate()
        request_settings = {"temperature": 0}
        if isinstance(self.model_config, dict):
            for k, v in self.model_config.items():
                if k in {"model_name", "deployment_name"}:
                    continue
                request_settings[k] = v
        requested_model = ""
        if isinstance(self.model_config, dict):
            requested_model = str(self.model_config.get("model_name") or self.model_config.get("deployment_name") or "")
        requested_model = requested_model or str(__import__("os").environ.get("EVAL_SUITE_WORKER_MODEL") or "")
        if "5.3" in requested_model or "codex" in requested_model.lower():
            route = make_azure_gpt53_codex_route_from_env(request_settings=request_settings)
        else:
            route = make_azure_gpt54_mini_route_from_env(request_settings=request_settings)
        repo_client = make_model_client_from_route(route)
        self.model_client = RepoModelClientBridge(
            repo_client=repo_client,
            completion_kwargs={"temperature": 0, "max_retries": 1},
        )
        self.loop_config = self.loop_config or ModelLoopConfig(max_steps=None)
        self.critic = VerifierCriticStub()
        self._advance_to_orient()

    def _advance_to_orient(self) -> None:
        sm = self.session.adapter.state_machine
        sm.transition("SUBSTRATE_CERTIFY", reason="using Harbor host-side environment bridge")
        sm.transition("ORIENT", reason="visible instruction and Harbor environment metadata gathered")

    async def run(self, *, instruction: str) -> ModelLoopRunResult:
        instruction_path = self.workspace_root / "instruction.md"
        instruction_path.write_text(instruction, encoding="utf-8")
        self._current_instruction = instruction
        steps: list[ModelLoopStep] = []
        last_result: dict | None = None
        current_blocker: dict | None = None
        last_progress_state: dict | None = None
        try:
            contract = None  # model-owned contract mode: no harness-authored semantic contract
            self.session.enter_execute()
            idx = 1
            while True:
                max_steps = self._host_loop_max_steps()
                if max_steps is not None and idx > max_steps:
                    return self._make_step_limit_result(steps=steps)

                cockpit = self._build_cockpit_for_model_or_bootstrap(
                    step=idx,
                    last_result=last_result,
                    current_blocker=current_blocker,
                    active_plan={
                        "plan_id": "model_plan",
                        "current_step_id": f"execute_{idx}",
                        "current_goal": "Continue the test-driven repair loop. If the previous artifact or behavior is invalid, create or run a self-check that fails that invalid behavior, repair or replace the artifact, then rerun the self-check. Do not finalize while open obligations remain. Do not use cannot_complete.",
                    },
                )
                cockpit_payload = cockpit.to_dict()
                if last_progress_state:
                    cockpit_payload["progress_state"] = last_progress_state

                evidence_guard = self._evidence_saturation_packet(step_index=idx, instruction=instruction)
                progress_guard = evidence_guard or self._progress_guard_packet(step_index=idx, instruction=instruction)
                if progress_guard:
                    cockpit_payload["progress_guard"] = progress_guard
                    cockpit_payload["current_blocker"] = progress_guard

                exec_result = await self._run_execute_step(step_index=idx, cockpit=cockpit_payload)
                attempted_finalize = self._execution_requested_finalization(exec_result)
                finalization = exec_result.finalization or self._evaluate_finalization()
                if attempted_finalize:
                    critic_result = self._review_finalization_adversarial(
                        step_index=idx,
                        contract=contract,
                        finalization=finalization,
                        exec_result=exec_result,
                        cockpit=cockpit.to_dict(),
                    )
                    critic_result = self._evidence_claim_gate(
                        step_index=idx,
                        finalization=finalization,
                        critic_result=critic_result,
                    )
                else:
                    critic_result = self._verification_skipped_result(
                        step_index=idx,
                        exec_result=exec_result,
                    )
                progress_entry = self._record_progress_ledger(
                    step_index=idx,
                    instruction=instruction,
                    exec_result=exec_result,
                )
                last_progress_state = self._progress_state_from_ledger(progress_entry)

                steps.append(
                    ModelLoopStep(
                        idx,
                        "EXECUTE",
                        execute_result=exec_result.to_dict(),
                        critic_result=critic_result.to_dict(),
                        cockpit_chars=cockpit.budget.get("estimated_chars") or cockpit.budget.get("chars") or cockpit.budget.get("char_count"),
                    )
                )
                last_result = compact_execute_result_for_cockpit(exec_result.to_dict())
                current_blocker = None
                if not finalization.allowed:
                    current_blocker = {
                        "failure_class": finalization.failure_class.value if hasattr(finalization.failure_class, "value") else str(finalization.failure_class),
                        "summary": finalization.summary,
                        "evidence_refs": [],
                    }

                if finalization.allowed and critic_result.may_claim_complete and idx > 1:
                    if self._final_verifier_authority_enabled():
                        final_completion = self._review_final_completion_authority(
                            step_index=idx,
                            instruction=instruction,
                            finalization=finalization,
                            critic_result=critic_result,
                        )
                        if not final_completion.submit_allowed:
                            current_blocker = {
                                "failure_class": "final_verifier_blocked",
                                "summary": final_completion.summary,
                                "evidence_refs": [ref.to_dict() for ref in final_completion.evidence_refs[:5]],
                                "invalid_reasons": list(final_completion.invalid_reasons),
                            }
                            last_result = {
                                "status": "blocked",
                                "final_completion_decision": final_completion.to_dict(),
                                "message": "Final verifier authority blocked submission; continue repair from the returned evidence.",
                            }
                            idx += 1
                            continue

                    contract_payload = self._load_model_owned_success_contract()
                    return ModelLoopRunResult(self.run_id, self.row_id, "complete", steps, contract_payload, finalization.to_dict())
                if exec_result.status == "blocked" and self.loop_config.stop_on_blocked_finalization:
                    return ModelLoopRunResult(self.run_id, self.row_id, "blocked", steps, contract.to_dict(), finalization.to_dict())
                idx += 1
            return ModelLoopRunResult(self.run_id, self.row_id, "step_limit", steps, self._json_safe_payload(contract), self._json_safe_payload(self._evaluate_finalization()))
        except Exception as exc:
            return ModelLoopRunResult(self.run_id, self.row_id, "error", steps, error=str(exc))

    async def _request_success_contract(self, *, instruction: str):
        remote_context = await self._remote_context()
        self._remote_context_cache = remote_context
        try:
            (self.receipt_root / "remote_context.json").write_text(
                json.dumps(remote_context, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass
        request = ModelCallRequest(
            call_id=f"{self.run_id}_contract",
            run_id=self.run_id,
            row_id=self.row_id,
            phase="PLAN_REQUIRED",
            messages=[
                ModelMessage(
                    "system",
                    (
                        "Return strict JSON containing a success_contract. "
                        "The contract must represent actual request success, not just file existence. It should name concrete required outputs, required inputs/assets, behavioral criteria, required services, required verifier/probe commands when visible, and anti-fake checks such as input influence, non-echoing, non-canned output, and semantic output validation when relevant. "
                        "Required outputs must include functional correctness criteria and behavioral evidence requirements. A contract that only says a file exists, is non-empty, compiles, or has the right format is invalid unless the user request only asks for that. "
                        "If code is required, include a verifier command or self-test procedure when possible. "
                        "Never accept placeholder, stub, mock, or incomplete implementations. "
                        "Do not mention hidden, oracle, solution, or grader assets."
                    ),
                ),
                ModelMessage("user", instruction),
                ModelMessage("user", json.dumps(remote_context, sort_keys=True)),
            ],
        )
        result = self.model_client.call(request)
        try:
            (self.receipt_root / "model_contract.json").write_text(
                json.dumps(result.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as log_exc:
            (self.receipt_root / "model_contract_logging_error.txt").write_text(str(log_exc), encoding="utf-8")
        if result.status != "success" or result.parsed is None:
            raise ModelIOError(result.error or "Model did not return a valid success contract.")
        contract = parse_success_contract(parsed=result.parsed, run_id=self.run_id, row_id=self.row_id)

        weak, reason = self._contract_is_too_weak(contract)
        if weak:
            repair_messages = list(request.messages) + [
                ModelMessage(
                    "user",
                    "The previous success_contract was rejected as too weak: "
                    + reason
                    + ". Return a stricter success_contract with concrete behavioral criteria, required inputs/assets, semantic output validation, anti-echo/anti-canned-output checks, and verifier/self-check procedures derived only from the visible request.",
                )
            ]
            for attempt in range(2):
                retry = ModelCallRequest(
                    call_id=f"{self.run_id}_contract_retry_{attempt + 1}",
                    run_id=self.run_id,
                    row_id=self.row_id,
                    phase="PLAN_REQUIRED",
                    messages=repair_messages,
                )
                result = self.model_client.call(retry)
                try:
                    (self.receipt_root / f"model_contract_retry_{attempt + 1}.json").write_text(
                        json.dumps(result.to_dict(), indent=2, default=str),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                if result.status != "success" or result.parsed is None:
                    reason = result.error or "model did not return valid parsed contract"
                    repair_messages.append(ModelMessage("user", "The contract call failed or did not parse: " + reason + ". Return valid strict JSON only."))
                    continue
                contract = parse_success_contract(parsed=result.parsed, run_id=self.run_id, row_id=self.row_id)
                weak, reason = self._contract_is_too_weak(contract)
                if not weak:
                    break
                repair_messages.append(ModelMessage("user", "Still too weak: " + reason + ". Make it behavior-specific and evidence-specific."))

            if weak:
                raise ModelIOError("success contract remained too weak: " + reason)

        if not contract.required_outputs and not contract.required_services and not contract.required_verifiers:
            raise ModelIOError("Parsed success contract has no required outputs/services/verifiers; refusing zero-obligation finalization.")
        # self.session.install_success_contract(contract)  # disabled: model-owned contract mode
        return contract


    def _contract_is_too_weak(self, contract: Any) -> tuple[bool, str]:
        """Reject contracts that only encode surface-level success."""
        try:
            data = contract.to_dict() if hasattr(contract, "to_dict") else dict(contract)
        except Exception:
            return True, "contract is not serializable"

        text = json.dumps(data, sort_keys=True).lower()
        weak_terms = [
            "file exists", "exists at", "non-empty", "valid c source", "valid source",
            "compiles", "compile", "under 5000", "right format", "format only",
        ]
        strong_terms = [
            "behavior", "functional", "output", "input", "semantic", "generated",
            "uses", "asset", "checkpoint", "vocab", "model", "prompt", "reject",
            "echo", "canned", "padding", "compare", "verifier", "self-check", "edge",
        ]

        has_weak = any(t in text for t in weak_terms)
        has_strong = any(t in text for t in strong_terms)
        required_outputs = data.get("required_outputs") or []
        required_verifiers = data.get("required_verifiers") or []
        done_condition = str(data.get("done_condition") or "").lower()

        if has_weak and not has_strong:
            return True, "contract is surface-level only"
        if required_outputs and not has_strong:
            return True, "required outputs lack behavioral criteria"
        if "gpt" in text and not any(t in text for t in ["checkpoint", "vocab", "prompt", "output", "semantic", "generated"]):
            return True, "model/generator contract lacks input/output semantics"
        if not required_verifiers and not any(t in done_condition for t in ["output", "behavior", "functional", "semantic"]):
            return True, "contract lacks verifier or behavioral done condition"
        return False, ""



    def _demote_environment_prerequisites(self, checklist: dict[str, Any]) -> dict[str, Any]:
        """Move compiler/library/file/tool availability out of required_services.

        required_services should mean daemons, APIs, servers, sockets, or long-running
        runtime services whose behavior must be probed. gcc/libm/files are prerequisites
        and must not become persistent open service gates.
        """
        data = dict(checklist or {})
        services = list(data.get("required_services") or [])
        keep: list[Any] = []
        demoted: list[Any] = list(data.get("environment_prerequisites") or [])

        tool_words = (
            "gcc", "compiler", "compile", "linker", "libm", "-lm",
            "python", "pip", "package", "library", "file", "checkpoint",
            "vocab", "bpe", "ckpt", "path", "readable", "standard library"
        )
        service_words = (
            "server", "daemon", "api", "http", "socket", "port",
            "endpoint", "listener", "service process", "background process"
        )

        for item in services:
            txt = str(item).lower()
            is_tool = any(w in txt for w in tool_words)
            is_real_service = any(w in txt for w in service_words)
            if is_tool and not is_real_service:
                demoted.append(item)
            else:
                keep.append(item)

        data["required_services"] = keep
        data["environment_prerequisites"] = demoted[:20]
        data["service_gate_policy"] = {
            "required_services_mean": "Only real runtime services such as servers, daemons, APIs, sockets, ports, or background processes.",
            "not_services": "Compilers, linkers, libraries, interpreters, package managers, ordinary files, checkpoint files, vocab/tokenizer files, and CLI tools.",
            "completion_rule": "Environment prerequisites can support implementation evidence, but cannot by themselves satisfy the original request.",
        }
        return data




    def _host_loop_max_steps(self) -> int | None:
        """Return the live host-loop max step cap.

        This is separate from model_loop.py because HarborHostRunner.run owns
        the actual while True loop in the live Harbor path.
        """
        raw = __import__("os").environ.get("MLPCP_MAX_STEPS", "30")
        if raw is None:
            return None
        text = str(raw).strip().lower()
        if text in {"", "0", "none", "null", "false", "off", "unlimited"}:
            return None
        try:
            value = int(text)
        except Exception:
            return 30
        return value if value > 0 else None



    def _json_safe_payload(self, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "to_dict"):
            try:
                return self._json_safe_payload(value.to_dict())
            except Exception:
                pass
        if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float, bool)):
            return value.value
        if isinstance(value, dict):
            return {str(k): self._json_safe_payload(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe_payload(item) for item in value]
        try:
            import dataclasses
            if dataclasses.is_dataclass(value):
                return self._json_safe_payload(dataclasses.asdict(value))
        except Exception:
            pass
        return str(value)




    def _latest_critic_dict(self, steps) -> dict:
        for step in reversed(list(steps or [])):
            try:
                critic = getattr(step, "critic_result", None)
                if isinstance(critic, dict):
                    return critic
                if critic is not None and hasattr(critic, "to_dict"):
                    return critic.to_dict()
            except Exception:
                continue
        return {}

    def _blocked_step_limit_finalization(self, *, steps) -> FinalizationDecision:
        progress_entry = self._latest_progress_ledger_entry()
        progress_state = self._progress_state_from_ledger(progress_entry)
        if isinstance(progress_state, dict) and progress_state.get("failure_class") not in {None, "", "none"}:
            failure_value = str(progress_state.get("failure_class") or "unknown")
            try:
                failure_class = validate_failure_class(failure_value)
            except Exception:
                failure_class = FailureClass.UNKNOWN

            missing = progress_state.get("missing_required_artifacts") or []
            obligations = []
            if missing:
                for path in missing[:6]:
                    obligations.append({
                        "failure_class": getattr(failure_class, "value", str(failure_class)),
                        "summary": f"Required artifact remains missing: {path}",
                        "requirement_id": "progress:required_artifact",
                        "check_id": "progress:artifact_exists",
                    })
            else:
                obligations.append({
                    "failure_class": getattr(failure_class, "value", str(failure_class)),
                    "summary": str(progress_state.get("summary") or "Step limit reached without measurable concrete progress."),
                    "requirement_id": "progress:measurable_work",
                    "check_id": "progress:non_progress",
                })

            return FinalizationDecision(
                allowed=False,
                finalization_type="blocked",
                failure_class=failure_class,
                summary=str(progress_state.get("summary") or "Step limit reached before valid internal completion. Finalization is blocked."),
                unresolved_obligations=obligations[:8],
            )

        critic = self._latest_critic_dict(steps)
        critic_failure = critic.get("failure_class") or "unknown"
        try:
            failure_class = validate_failure_class(critic_failure)
        except Exception:
            failure_class = FailureClass.UNKNOWN

        missing = []
        repair_packet = critic.get("repair_packet") if isinstance(critic, dict) else {}
        if isinstance(repair_packet, dict):
            for item in repair_packet.get("missing_evidence") or repair_packet.get("unresolved_obligations") or []:
                missing.append(
                    {
                        "failure_class": getattr(failure_class, "value", str(failure_class)),
                        "summary": str(item),
                        "requirement_id": "step_limit:evidence_gap",
                        "check_id": "step_limit:critic",
                    }
                )

        if not missing:
            missing = [
                {
                    "failure_class": getattr(failure_class, "value", str(failure_class)),
                    "summary": "Step limit reached before a valid completion claim with receipt-backed evidence.",
                    "requirement_id": "step_limit:completion",
                    "check_id": "step_limit:finalization",
                }
            ]

        return FinalizationDecision(
            allowed=False,
            finalization_type="blocked",
            failure_class=failure_class,
            summary="Step limit reached before valid internal completion. Finalization is blocked.",
            unresolved_obligations=missing[:8],
        )


    def _make_step_limit_result(self, *, steps):
        finalization = self._blocked_step_limit_finalization(steps=steps)
        contract = getattr(self, "success_contract", None) or getattr(self, "_success_contract", None)
        contract_payload = self._json_safe_payload(contract) if contract is not None else None

        try:
            return ModelLoopRunResult(
                self.run_id,
                self.row_id,
                "step_limit",
                steps,
                contract_payload,
                self._json_safe_payload(finalization),
            )
        except TypeError:
            # Compatibility for local dataclass field names across snapshots.
            kwargs = {}
            for f in getattr(ModelLoopRunResult, "__dataclass_fields__", {}).values():
                if f.name == "run_id":
                    kwargs[f.name] = self.run_id
                elif f.name == "row_id":
                    kwargs[f.name] = self.row_id
                elif f.name == "status":
                    kwargs[f.name] = "step_limit"
                elif f.name == "steps":
                    kwargs[f.name] = steps
                elif f.name == "success_contract":
                    kwargs[f.name] = contract_payload
                elif f.name == "finalization":
                    kwargs[f.name] = self._json_safe_payload(finalization)
                elif f.name == "error":
                    kwargs[f.name] = None
            return ModelLoopRunResult(**kwargs)


    def _build_cockpit_for_model_or_bootstrap(self, *, step_index: int | None = None, step: int | None = None, **kwargs):
        """Build normal cockpit when the model-owned contract has been installed.

        In model-owned contract mode, the first model call must happen before a
        semantic SuccessContract/CapabilityGraph exists. For that first call,
        return a small bootstrap cockpit that gives the model the schema and
        asks it to author the visible-evidence success_contract.

        This is not a harness-authored semantic contract.
        It must not introduce required_services or task-specific gates.
        """
        if step_index is None:
            step_index = step
        if step_index is None:
            raise ValueError("step_index or step is required for cockpit build")

        try:
            return self.session.build_cockpit(step=step_index, **kwargs)
        except Exception as exc:
            msg = str(exc)
            if "Success contract and capability graph are required before cockpit build" not in msg:
                raise

        class _BootstrapCockpit:
            def __init__(self, payload: dict):
                self._payload = payload
                self.budget = payload.get("budget", {})
                self.packet_id = payload.get("packet_id")

            def to_dict(self) -> dict:
                return self._payload

        model_contract = self._load_model_owned_success_contract()

        payload = {
            "version": "cockpit_packet.v1",
            "packet_id": f"cockpit_bootstrap_{self.row_id}_{step_index}",
            "run_id": self.run_id,
            "row_id": self.row_id,
            "step": step_index,
            "objective": "Author a visible-evidence success_contract, then proceed with focused actions.",
            "visibility": {
                "solver_visible": True,
                "verifier_visible": False,
                "harness_internal": True,
                "offline_only": False,
                "may_enter_solver_context": True,
            },
            "anti_leak": {
                "contains_hidden_oracle_data": False,
                "contains_offline_trace_mining_data": False,
                "contains_prior_benchmark_tactics": False,
            },
            "success_contract_ref": None,
            "success_contract_snapshot": None,
            "model_owned_success_contract": model_contract,
            "model_success_contract_schema": self._model_success_contract_schema(),
            "success_checklist": {
                "mode": "model_owned_contract",
                "status": "no_model_contract_yet" if not model_contract else "stored_model_contract_present",
                "schema": self._model_success_contract_schema(),
                "note": (
                    "No harness-authored success contract is provided. Create a success_contract "
                    "from the original request and visible workspace evidence. Do not use hidden, "
                    "test, solution, oracle, reviewer, or prior benchmark information."
                ),
            },
            "active_plan": {
                "plan_id": "bootstrap_plan",
                "current_step_id": "author_success_contract",
                "current_goal": "Orient from visible evidence and author success_contract before finalization.",
                "last_revision_reason": None,
            },
            "allowed_next_actions": [
                "read_file",
                "write_file",
                "search_files",
                "raw_bash",
                "run_verifier",
                "probe_service",
                "view_receipt",
                "search_receipts",
                "view_file_cache",
            ],
            "current_blocker": {
                "failure_class": "missing_model_success_contract",
                "summary": (
                    "No model-owned success_contract has been installed yet. The next response "
                    "should include success_contract when enough visible evidence is available. "
                    "Finalization is blocked until a model-authored contract and receipt-backed "
                    "evidence exist."
                ),
                "evidence_refs": [],
                "required_next_mode": "orient_or_contract",
                "must_not_actions": ["finalize", "cannot_complete"],
            },
            "open_obligations": [
                {
                    "failure_class": "missing_model_success_contract",
                    "summary": "Create success_contract from visible evidence before finalization.",
                    "requirement_id": "model_contract:required",
                    "check_id": "model_contract:present",
                }
            ],
            "artifact_summary": {},
            "service_summary": {},
            "verifier_summary": {
                "last_run": "not_run",
                "summary": "",
                "failure_class": "none",
                "receipt_ref": None,
            },
            "memory_refs": {
                "available_memory_tools": ["view_receipt", "search_receipts", "view_file_cache"],
                "important_files": [],
                "important_receipts": [],
                "important_services": [],
            },
            "last_result": None,
            "evidence_work_ledger": {
                "measured_work_receipts": [],
                "rule": (
                    "No receipt-linked evidence means the work claim is unsupported. "
                    "Finalize requires args.evidence_refs. Create or revise success_contract before finalization."
                ),
            },
            "budget": {
                "estimated_chars": 0,
                "max_chars": 6000,
                "max_tokens_estimate": 1800,
                "over_budget": False,
                "bootstrap": True,
            },
        }

        if model_contract:
            payload["packet_id"] = f"cockpit_model_contract_ready_{self.row_id}_{step_index}"
            payload["objective"] = (
                "Continue implementation and verification using the model-owned success_contract. "
                "Do not re-author the contract unless visible evidence proves it is wrong."
            )
            payload["success_contract_ref"] = "model_owned_success_contract"
            payload["success_contract_snapshot"] = model_contract
            payload["success_checklist"] = {
                "mode": "model_owned_contract",
                "status": "model_contract_present",
                "contract_ref": "model_owned_success_contract",
                "rule": (
                    "The model-owned success_contract is present. Completion still requires "
                    "receipt-backed evidence for required artifacts, behavior checks, verifier/probe "
                    "results, and finalization evidence_refs."
                ),
            }
            payload["active_plan"] = {
                "plan_id": "model_plan",
                "current_step_id": "implementation_or_verification",
                "current_goal": (
                    "Move from contract definition to implementation, measurement, repair, "
                    "and evidence-backed finalization."
                ),
                "last_revision_reason": "model_owned_success_contract_present",
            }
            payload["current_blocker"] = {
                "failure_class": "missing_receipt_backed_implementation_evidence",
                "summary": (
                    "The model-owned success_contract exists. Finalization remains blocked until "
                    "required outputs and behavior are supported by typed receipt-backed evidence."
                ),
                "evidence_refs": [],
                "required_next_mode": "implement_or_verify",
                "must_not_actions": ["cannot_complete"],
            }
            payload["open_obligations"] = [
                {
                    "failure_class": "missing_receipt_backed_implementation_evidence",
                    "summary": "Produce or verify required artifacts with measured receipt-backed evidence.",
                    "requirement_id": "evidence:required",
                    "check_id": "evidence:receipt_backed",
                }
            ]
            if "finalize" not in payload.get("allowed_next_actions", []):
                payload.setdefault("allowed_next_actions", []).append("finalize")
            payload.setdefault("evidence_work_ledger", {})["contract_transition"] = (
                "model_contract_present; bootstrap missing-contract blocker cleared"
            )


        try:
            import json
            payload["budget"]["estimated_chars"] = len(json.dumps(payload, sort_keys=True, default=str))
            payload["budget"]["over_budget"] = payload["budget"]["estimated_chars"] > payload["budget"]["max_chars"]
        except Exception:
            pass

        return _BootstrapCockpit(payload)




    def _success_checklist_for_model(self) -> dict[str, Any]:
        # In model-owned contract mode, do not project a harness-authored semantic
        # success contract into the cockpit. The model-authored contract is passed
        # separately via model_owned_success_contract + model_success_contract_schema.
        model_contract = self._load_model_owned_success_contract()
        if isinstance(model_contract, dict) and model_contract.get("status") in {"present", "present_but_schema_incomplete"}:
            return {
                "mode": "model_owned_contract",
                "contract": model_contract,
                "note": "This contract was authored by the model. The harness stores it for continuity and validates only structure/evidence refs.",
            }

        contract = getattr(self.session, "success_contract", None)
        if contract is None:
            return {
                "mode": "model_owned_contract",
                "status": "no_model_contract_yet",
                "schema": self._model_success_contract_schema(),
                "note": "No harness-authored success contract is provided. Create success_contract when useful and before finalization.",
            }

        try:
            data = contract.to_dict()
        except Exception:
            data = dict(getattr(contract, "__dict__", {}) or {})

        done_condition = data.get("done_condition") or {}
        extras = data.get("extras") or {}
        raw_contract = extras.get("raw_success_contract") if isinstance(extras, dict) else None

        functional_criteria = []
        verification_procedure = []
        notes = []

        if isinstance(done_condition, dict):
            functional_criteria.extend(done_condition.get("functional_correctness_criteria") or [])
            verification_procedure.extend(done_condition.get("verification_procedure") or [])
            notes.extend(done_condition.get("notes") or [])

        if isinstance(raw_contract, dict):
            functional_criteria.extend(raw_contract.get("functional_correctness_criteria") or [])
            verification_procedure.extend(raw_contract.get("verification_procedure") or [])
            notes.extend(raw_contract.get("acceptance_notes") or raw_contract.get("notes") or [])

        def dedupe(items):
            out = []
            seen = set()
            for item in items:
                text = str(item).strip()
                if text and text not in seen:
                    out.append(text)
                    seen.add(text)
            return out

        checklist = {
            "objective": data.get("objective"),
            "required_outputs": data.get("required_outputs") or [],
            "required_services": data.get("required_services") or [],
            "required_verifiers": data.get("required_verifiers") or [],
            "functional_correctness_criteria": dedupe(functional_criteria)[:20],
            "verification_procedure": dedupe(verification_procedure)[:12],
            "notes": dedupe(notes)[:12],
            "pre_finalize_required_review": [
                "Do all required outputs exist and contain real, non-stub implementations?",
                "Have request-relevant self-checks or required verifiers been run?",
                "Does observed behavior satisfy each functional correctness criterion?",
                "Does the solution use required inputs rather than ignoring them or printing canned output?",
                "Would the final workspace satisfy the user request without another repair turn?",
            ],
            "invalid_solution_patterns": [
                "placeholder/stub/mock/dummy artifact",
                "empty output",
                "compile-only proof",
                "echoes input without implementing required behavior",
                "hardcoded guessed answer",
                "ignores checkpoint/data/config/service inputs required by the user request",
            ],
            "when_current_work_is_invalid": [
                "Do not finalize.",
                "Do not use cannot_complete.",
                "Do not repeatedly inspect or smoke-test the same invalid artifact.",
                "Write or run a self-check that exposes the invalid behavior.",
                "The self-check must validate behavior, not only file existence or compilation.",
                "Replace or repair the artifact.",
                "Run the self-check again and inspect the result.",
                "Continue until the success contract is satisfied by measured evidence.",
            ],
            "self_check_quality_bar": [
                "A self-check should fail the known-bad artifact.",
                "A self-check should validate output or behavior against the visible requirement, not merely non-empty output, deterministic output, compilation, or formatting.",
                "A self-check should be derived only from the visible user request, files, and behavior observed inside the workspace.",
                "A self-check should detect empty, canned, echoed, padded, random-looking, numeric-only, hash-like, fixed-string, or input-ignoring output when those violate the user request.",
                "A self-check should prove required inputs affect behavior when the request requires using them.",
                "A self-check for data, parser, compiler, model, or generator work should compare behavior across changed required inputs and reject simple hashes, RNG, fixed strings, lookup tables, or smoke-test-only behavior.",
            ],
        }
        return self._demote_environment_prerequisites(checklist)





    def _model_success_contract_schema(self) -> dict[str, Any]:
        """Schema only. The harness provides format, not task semantics."""
        return {
            "schema": "model_owned_success_contract_v1",
            "ownership": "The model authors this contract from the original task prompt and visible environment. The harness validates shape only and stores it for continuity.",
            "required_top_level_fields": [
                "objective",
                "required_artifacts",
                "required_behaviors",
                "known_invalid_patterns",
                "verification_plan",
                "finalization_evidence_required",
            ],
            "field_shapes": {
                "objective": "string",
                "required_artifacts": "list of strings",
                "required_behaviors": "list of strings",
                "known_invalid_patterns": "list of strings",
                "verification_plan": "list of strings",
                "finalization_evidence_required": "list of strings",
                "notes": "optional list of strings",
            },
            "contract_policy": [
                "Do not treat environment prerequisites as user-facing task success.",
                "Do not treat file existence, compilation, non-empty output, prompt-dependence, or smoke checks as sufficient unless the original task only asks for that exact thing.",
                "Revise this contract when exploration reveals better evidence.",
                "Finalization must cite receipt-backed evidence against this contract and the original task.",
            ],
        }

    def _model_success_contract_path(self) -> Path:
        return self.receipt_root / "model_owned_success_contract.json"

    def _model_success_contract_history_path(self) -> Path:
        return self.receipt_root / "model_owned_success_contract.history.jsonl"

    def _load_model_owned_success_contract(self) -> dict[str, Any]:
        path = self._model_success_contract_path()
        if not path.exists():
            return {
                "status": "no_contract_yet",
                "guidance": [
                    "Create a top-level success_contract when you have enough context to state what success requires.",
                    "The harness provides only the schema. You own the task interpretation.",
                    "You may revise success_contract as evidence changes.",
                ],
            }
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "status": "contract_read_error",
                "error": str(exc),
            }

    def _capture_model_success_contract(self, parsed: dict[str, Any] | None, *, step_index: int) -> None:
        """Persist optional model-authored success_contract.

        This is schema/continuity capture only. It does not mean the harness agrees
        semantically with the contract.
        """
        if not isinstance(parsed, dict):
            return

        contract = None
        for key in ("success_contract", "contract", "model_success_contract"):
            if isinstance(parsed.get(key), dict):
                contract = parsed.get(key)
                break

        if contract is None:
            return

        required = [
            "objective",
            "required_artifacts",
            "required_behaviors",
            "known_invalid_patterns",
            "verification_plan",
            "finalization_evidence_required",
        ]

        missing = [k for k in required if k not in contract]
        stored = {
            "schema": "model_owned_success_contract_v1",
            "status": "present_but_schema_incomplete" if missing else "present",
            "step_index": step_index,
            "missing_required_fields": missing,
            "contract": contract,
        }

        try:
            self._model_success_contract_path().write_text(
                json.dumps(stored, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
            with self._model_success_contract_history_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps(stored, sort_keys=True, default=str) + "\n")
        except Exception as exc:
            try:
                (self.receipt_root / f"model_success_contract_update_error_{step_index}.txt").write_text(
                    str(exc),
                    encoding="utf-8",
                )
            except Exception:
                pass



    def _action_plain_dict_for_dedup(self, action):
        """Convert ExecutePlanAction or dict into the generic shape used by dedup.

        This keeps the dedup mirror independent of ExecutePlan internals.
        """
        if isinstance(action, dict):
            return action

        args = {}
        for name in ("args", "tool_args", "payload"):
            value = getattr(action, name, None)
            if isinstance(value, dict):
                args.update(value)

        # Most current ExecutePlanAction objects expose action_type/action_id/args.
        action_type = (
            getattr(action, "action_type", None)
            or getattr(action, "type", None)
            or getattr(action, "name", None)
        )
        action_id = getattr(action, "action_id", None) or getattr(action, "id", None)

        return {
            "id": action_id,
            "action_id": action_id,
            "type": action_type,
            "action_type": action_type,
            "args": args,
        }



    def _dedup_execution_ledger_path(self):
        return self.receipt_root / "dedup_execution_ledger.jsonl"


    def _dedup_path_tokens_from_action(self, action):
        """Extract explicit path-like tokens from action args.

        Generic only. No task-name branching, no benchmark-specific paths.
        """
        import shlex
        from pathlib import Path

        args = action.get("args") if isinstance(action.get("args"), dict) else {}
        paths = []

        for key in (
            "path",
            "file",
            "target",
            "target_path",
            "output_path",
            "cwd",
            "candidate_dir",
            "dir",
            "directory",
        ):
            value = args.get(key)
            if isinstance(value, str) and value.strip():
                paths.append(value.strip())

        cmd = str(args.get("cmd") or args.get("command") or "")
        if cmd:
            try:
                tokens = shlex.split(cmd)
            except Exception:
                tokens = cmd.split()

            for tok in tokens:
                tok = str(tok).strip().strip("'\"")
                if not tok or tok.startswith("-"):
                    continue

                looks_path_like = (
                    "/" in tok
                    or tok.startswith(".")
                    or any(tok.endswith(ext) for ext in (
                        ".py", ".js", ".ts", ".tsx", ".jsx", ".c", ".cpp", ".h",
                        ".hpp", ".txt", ".json", ".yaml", ".yml", ".toml", ".sh",
                        ".md", ".html", ".css", ".csv", ".xml", ".ini", ".cfg",
                        ".conf", ".log", ".sql"
                    ))
                )
                if looks_path_like:
                    paths.append(tok)

        out = []
        seen = set()
        for raw in paths:
            text = str(raw).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)

        return out


    def _dedup_state_hash_for_action(self, action):
        """Return a compact, generic state fingerprint for duplicate detection.

        This hashes only action-visible referenced files where possible.
        It does not infer task family or service type.
        """
        import hashlib
        import json
        from pathlib import Path

        paths = self._dedup_path_tokens_from_action(action)
        file_hashes = {}

        for raw_path in sorted(set(paths)):
            try:
                path = Path(raw_path)
                if not path.is_absolute():
                    # Use current process cwd as generic fallback. Do not infer task semantics.
                    path = Path.cwd() / path
                if path.exists() and path.is_file():
                    file_hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            except Exception as exc:
                file_hashes[str(raw_path)] = f"hash_error:{type(exc).__name__}"

        payload = {
            "paths": sorted(set(paths)),
            "file_hashes": file_hashes,
        }
        payload["state_hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        return payload


    def _dedup_action_signature(self, action):
        """Build a stable signature for exact repeated action + unchanged visible state."""
        import hashlib
        import json

        action_type = str(action.get("type") or action.get("action_type") or "")
        args = action.get("args") if isinstance(action.get("args"), dict) else {}

        # Remove only free-text rationale fields, not operational args.
        normalised_args = {
            k: v for k, v in sorted(args.items())
            if k not in {"reason", "comment", "note", "rationale"}
        }

        state = self._dedup_state_hash_for_action(action)

        payload = {
            "action_type": action_type,
            "args": normalised_args,
            "state_hash": state.get("state_hash"),
        }
        signature = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

        return {
            "signature": signature,
            "action_type": action_type,
            "args": normalised_args,
            "state": state,
        }


    def _load_dedup_execution_ledger(self):
        path = self._dedup_execution_ledger_path()
        if not path.exists():
            return []

        rows = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            return []
        return rows


    def _append_dedup_execution_ledger(self, row):
        try:
            path = self._dedup_execution_ledger_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        except Exception:
            pass


    def _find_duplicate_execution(self, action):
        sig = self._dedup_action_signature(action)
        for row in reversed(self._load_dedup_execution_ledger()):
            if row.get("signature") == sig.get("signature"):
                return {
                    "signature": sig,
                    "previous": row,
                }
        return None


    def _record_action_execution_signature(
        self,
        action,
        *,
        step_index,
        result=None,
        receipt_ref=None,
    ):
        sig = self._dedup_action_signature(action)

        row = {
            "signature": sig.get("signature"),
            "step_index": step_index,
            "action_type": sig.get("action_type"),
            "args": sig.get("args"),
            "state": sig.get("state"),
            "receipt_ref": receipt_ref,
            "result_summary": None,
        }

        try:
            if isinstance(result, dict):
                row["result_summary"] = {
                    "status": result.get("status"),
                    "exit_code": result.get("exit_code"),
                    "summary": result.get("summary") or result.get("message"),
                    "receipt_ref": result.get("receipt_ref"),
                }
            elif hasattr(result, "to_dict"):
                data = result.to_dict()
                row["result_summary"] = {
                    "status": data.get("status"),
                    "summary": data.get("message") or data.get("summary"),
                    "receipt_ref": data.get("receipt_ref"),
                }
            else:
                row["result_summary"] = str(result)[:500]
        except Exception:
            row["result_summary"] = None

        self._append_dedup_execution_ledger(row)


    def _duplicate_execution_mirror_result(
        self,
        action,
        *,
        step_index,
        duplicate,
    ):
        previous = duplicate.get("previous") or {}
        sig = duplicate.get("signature") or {}

        return {
            "type": action.get("type") or action.get("action_type"),
            "status": "bypassed_duplicate_execution",
            "failure_class": "duplicate_action_same_state",
            "message": (
                "You already performed this same action against an unchanged relevant state. "
                "This was not rerun because it would not produce new evidence. "
                "Review the previous receipt/result before repeating it."
            ),
            "historical_reference": {
                "previous_step": previous.get("step_index"),
                "previous_receipt_ref": previous.get("receipt_ref") or (previous.get("result_summary") or {}).get("receipt_ref"),
                "previous_result_summary": previous.get("result_summary"),
                "state": previous.get("state"),
            },
            "current_signature": {
                "signature": sig.get("signature"),
                "action_type": sig.get("action_type"),
                "state": sig.get("state"),
            },
            "evidence_policy": (
                "This mirror is an already-known-evidence reminder, not a hard gate. It does not force a specific action "
                "or any specific next action. It only says this repeated action is not new evidence."
            ),
            "step_index": step_index,
        }



    def _dedup_mirror_for_cockpit(self) -> dict[str, Any]:
        """Passive memory mirror: factual repeated-work hints, not commands.

        This does not force mutation. It tells the model what is already known and
        where the evidence lives.
        """
        mirror: dict[str, Any] = {
            "policy": [
                "If you are about to repeat an action against unchanged state, first check the previous receipt.",
                "A repeated action may be valid, but it is not new evidence unless state, input, or purpose changed.",
                "This mirror is an already-known-evidence reminder, not a hard gate. Repeat only if state changed or the follow-up is more specific.",
            ],
            "known_facts": {},
            "recent_repeated_action_signals": [],
        }

        try:
            actions = self._recent_model_actions_compact(limit=60)
        except Exception:
            actions = []

        gpt2_hash = None
        try:
            gpt2_hash = self._workspace_file_hash("/app/gpt2.c")
        except Exception:
            pass

        if gpt2_hash:
            mirror["known_facts"]["/app/gpt2.c.sha256"] = gpt2_hash

        # Group recent command-ish actions by rough canonical signature.
        seen: dict[str, dict[str, Any]] = {}
        repeats: list[dict[str, Any]] = []
        for a in actions:
            cmd = str(a.get("cmd") or "").strip()
            path = str(a.get("path") or "").strip()
            typ = str(a.get("type") or "").strip()
            sig_src = "\n".join([typ, cmd, path, str(gpt2_hash or "")])
            sig = __import__("hashlib").sha256(sig_src.encode()).hexdigest()[:12]

            if sig in seen:
                prev = seen[sig]
                repeats.append({
                    "current_step": a.get("step"),
                    "previous_step": prev.get("step"),
                    "action_type": typ,
                    "path": path,
                    "command_excerpt": cmd[:300],
                    "state_note": "Relevant artifact hash appears unchanged for this repeated action.",
                    "mirror_message": "You already did this before. Review the previous receipt/result before repeating it.",
                })
            else:
                seen[sig] = a

        mirror["recent_repeated_action_signals"] = repeats[-10:]

        # Stable environment prerequisites: factual, not success criteria.
        try:
            receipts = self._recent_action_receipts_compact(limit=80)
        except Exception:
            receipts = []

        joined = "\n".join(
            " ".join(str(r.get(k) or "") for k in ("summary", "stdout", "stderr"))
            for r in receipts
        ).lower()

        env = {}
        if "gcc" in joined and ("exit 0" in joined or "compiled" in joined or "success" in joined):
            env["gcc_readiness_seen"] = True
        if "libm" in joined or "-lm" in joined:
            env["libm_readiness_seen"] = True
        if env:
            mirror["known_facts"]["environment_prerequisites"] = env
            mirror["known_facts"]["environment_prerequisite_policy"] = (
                "These are facts already observed. They are not user-facing success by themselves."
            )

        return mirror


    def _model_plan_path(self) -> Path:
        return self.receipt_root / "model_owned_working_plan.json"

    def _model_plan_history_path(self) -> Path:
        return self.receipt_root / "model_owned_working_plan.history.jsonl"

    def _load_model_owned_plan(self) -> dict[str, Any]:
        path = self._model_plan_path()
        if not path.exists():
            return {
                "status": "no_plan_yet",
                "guidance": [
                    "Use plan_update when the work is multi-step, uncertain, failing, or requires coordinated implementation and verification. The model decides when a stored plan is useful.",
                    "The plan is editable. When revising it, return the full current plan, not just a diff.",
                    "The plan should track objective, evidence, current focus, implementation approach, validation strategy, verification/test strategy, known bad behavior, evidence gaps, risks, and next steps.",
                    "The plan should include what evidence must exist before finalization is allowed.",
                    "The plan should distinguish prerequisites from actual task success.",
                    "The plan is not a lock. You may explore or revise it when evidence changes.",
                ],
            }
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"status": "plan_read_error", "error": str(exc)}
        if not isinstance(obj, dict):
            return {"status": "plan_invalid", "raw_type": type(obj).__name__}
        return obj

    def _capture_model_plan_update(self, parsed: dict[str, Any] | None, *, step_index: int) -> None:
        """Persist optional model-owned plan/checklist/rationale state.

        This is not a tool action and not a hard gate. It gives the model durable
        working memory while preserving freedom to explore, revise, and act.
        """
        if not isinstance(parsed, dict):
            return

        plan_update = None
        for key in ("plan_update", "working_plan", "model_plan", "working_checklist", "checklist_update"):
            if isinstance(parsed.get(key), dict):
                plan_update = parsed.get(key)
                break
            if isinstance(parsed.get(key), list):
                plan_update = {key: parsed.get(key)}
                break

        # Capture action-level plan/checklist updates too. Models often emit:
        # {"type":"plan_update","plan": {...}} rather than top-level plan_update.
        actions = parsed.get("actions") or parsed.get("execute_plan") or []
        if plan_update is None and isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                if action.get("type") not in {"plan_update", "update_plan", "working_checklist", "checklist_update"}:
                    continue
                for key in ("args", "plan", "working_plan", "model_plan", "working_checklist", "checklist_update"):
                    value = action.get(key)
                    if isinstance(value, dict):
                        plan_update = value
                        break
                    if isinstance(value, list):
                        plan_update = {key: value}
                        break
                if plan_update is not None:
                    break

        model_notes = None
        for key in ("model_notes", "action_rationale", "working_memory", "scratchpad"):
            if isinstance(parsed.get(key), dict):
                model_notes = parsed.get(key)
                break

        if model_notes is None and isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict):
                    continue
                for key in ("model_notes", "action_rationale", "working_memory", "scratchpad"):
                    if isinstance(action.get(key), dict):
                        model_notes = action.get(key)
                        break
                if model_notes is not None:
                    break

        if plan_update is None and model_notes is None:
            return

        if plan_update is None:
            plan_update = {}
        if not isinstance(plan_update, dict):
            plan_update = {
                "status": "invalid_plan_update_shape",
                "raw": str(plan_update)[:4000],
            }

        saved = {
            "schema": "model_owned_working_plan_v2",
            "updated_at_step": step_index,
            "updated_at_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
            "plan": plan_update,
            "model_notes": model_notes or {},
            "usage_note": "Model-owned editable working plan/checklist/notes. It supports continuity but does not override the original user request or measured evidence.",
        }

        try:
            self._model_plan_path().write_text(
                json.dumps(saved, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
            with self._model_plan_history_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps(saved, sort_keys=True, default=str) + "\n")
        except Exception as exc:
            try:
                (self.receipt_root / f"model_plan_update_error_{step_index}.txt").write_text(
                    str(exc),
                    encoding="utf-8",
                )
            except Exception:
                pass


    def _original_instruction_for_model(self) -> str:
        """Return the original visible user request/task prompt for every execute call.

        The success contract and cockpit are derived summaries. They must not
        replace the raw user request, because summaries can drift, omit key
        constraints, or over-emphasize weak surrogate gates.
        """
        try:
            text = (self.workspace_root / "instruction.md").read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            text = ""
        return text[:12000]


    def _sanitize_model_visible_cockpit(self, obj: Any) -> Any:
        """Remove/demote false service-gate obligations from model-visible state.

        gcc/libm/files/checkpoints/vocab are prerequisites, not runtime services.
        They must not remain as open service obligations after repeated evidence.
        """
        tool_words = (
            "gcc", "compiler", "compile", "linker", "libm", "-lm",
            "standard_c_runtime", "standard c runtime", "checkpoint", "vocab",
            "bpe", "ckpt", "file", "readable"
        )

        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                lk = str(k).lower()

                # Drop false required_services from success contract snapshots.
                if lk == "required_services" and isinstance(v, list):
                    kept = []
                    demoted = []
                    for item in v:
                        txt = str(item).lower()
                        if any(w in txt for w in tool_words):
                            demoted.append(item)
                        else:
                            kept.append(item)
                    out[k] = kept
                    if demoted:
                        out["environment_prerequisites_demoted_from_services"] = demoted
                    continue

                # Filter open obligations/finalization obligations that are actually tool prerequisites.
                if lk in {"open_obligations", "unresolved_obligations"} and isinstance(v, list):
                    kept = []
                    demoted = []
                    for item in v:
                        txt = str(item).lower()
                        if "service" in txt and any(w in txt for w in tool_words):
                            demoted.append(item)
                        else:
                            kept.append(item)
                    out[k] = kept
                    if demoted:
                        out[f"demoted_{k}"] = demoted
                        out["service_gate_policy"] = {
                            "ruling": "Compiler/linker/library/file readiness is an environment prerequisite, not a persistent runtime service gate.",
                            "completion_rule": "Do not keep probing gcc/libm/file readiness after it has succeeded. Move to implementation and semantic verification."
                        }
                    continue

                # Rewrite finalization summaries that only complain about false service gates.
                if lk in {"failure_class"} and isinstance(v, str) and v == "service_not_ready":
                    out[k] = "environment_prerequisite_not_task_completion"
                    continue

                if lk in {"summary"} and isinstance(v, str) and "service_gate" in v.lower():
                    out[k] = v + " [Sanitized note: compiler/libm/file readiness must not be treated as the task objective or repeated after success.]"
                    continue

                out[k] = self._sanitize_model_visible_cockpit(v)
            return out

        if isinstance(obj, list):
            return [self._sanitize_model_visible_cockpit(x) for x in obj]

        return obj


    def _recent_action_evidence_for_cockpit(self, *, limit: int = 12) -> dict[str, Any]:
        """Summarise real Harbor action receipts for the next model turn."""
        receipts_dir = self.receipt_root / "receipts"
        records: list[dict[str, Any]] = []
        files: dict[str, Any] = {}

        def _short(value: object, n: int = 900) -> str:
            text = "" if value is None else str(value)
            return text if len(text) <= n else text[: n // 2] + "\n...[truncated]...\n" + text[-n // 2 :]

        if receipts_dir.exists():
            for rp in sorted(receipts_dir.glob("*.json")):
                try:
                    obj = json.loads(rp.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue

                tool = str(obj.get("tool_name") or obj.get("tool") or "").strip()
                if not tool or tool.startswith("model_"):
                    continue

                rid = str(obj.get("receipt_id") or obj.get("id") or rp.stem)
                summary = str(obj.get("summary") or obj.get("model_visible_summary") or "")
                status = str(obj.get("status") or "")
                exit_code = obj.get("exit_code")
                args = obj.get("tool_args") or obj.get("args") or {}

                stdout = str(obj.get("stdout") or "")
                stderr = str(obj.get("stderr") or "")

                raw_dir = self.receipt_root / "raw" / rp.stem
                if raw_dir.exists():
                    try:
                        raw_stdout = (raw_dir / "stdout").read_text(encoding="utf-8", errors="replace")
                        if raw_stdout:
                            stdout = raw_stdout
                    except Exception:
                        pass
                    try:
                        raw_stderr = (raw_dir / "stderr").read_text(encoding="utf-8", errors="replace")
                        if raw_stderr:
                            stderr = raw_stderr
                    except Exception:
                        pass

                rec = {
                    "receipt_id": rid,
                    "tool": tool,
                    "status": status,
                    "exit_code": exit_code,
                    "summary": _short(summary, 300),
                    "args": args,
                    "stdout_excerpt": _short(stdout, 900),
                    "stderr_excerpt": _short(stderr, 500),
                }
                records.append(rec)

                if tool == "search_files":
                    try:
                        for item in stdout.splitlines():
                            item = item.strip()
                            if item:
                                files[item] = {"source": rid, "kind": "search_match"}
                    except Exception:
                        pass

                if tool == "raw_bash":
                    low = stdout.lower()
                    for marker in (
                        "alpine.iso",
                        "alpine-disk.qcow2",
                        "qemu-alpine.log",
                        "qemu-alpine.pid",
                        "solution.txt",
                        "report.txt",
                        "summary.json",
                    ):
                        if marker in low:
                            files[marker] = {"source": rid, "kind": "observed_in_stdout"}

        recent = records[-limit:]
        important_refs = [
            Reference(
                ref_type="receipt",
                ref_id=str(r["receipt_id"]),
                summary=f"{r.get('tool')}: {r.get('summary') or r.get('status')}",
            ).to_dict()
            for r in recent[-8:]
            if r.get("receipt_id")
        ]

        last = recent[-1] if recent else {}
        last_summary = ""
        if last:
            last_summary = f"{last.get('tool')} {last.get('status')} exit={last.get('exit_code')}: {last.get('summary')}"

        return {
            "files": files,
            "workspace_inspection": {
                "status": "known" if files else "unknown",
                "evidence_refs": important_refs[:6],
            },
            "important_receipts": important_refs,
            "recent_action_receipts": recent,
            "last_result_summary": last_summary,
            "last_action_types": [r.get("tool") for r in recent[-6:] if r.get("tool")],
        }


    def _prepare_cockpit_for_model(self, cockpit: dict[str, Any]) -> dict[str, Any]:
        """Add concrete repair guidance and hide finalize while obligations remain."""
        prepared = self._sanitize_model_visible_cockpit(dict(cockpit or {}))

        harbor_evidence = self._recent_action_evidence_for_cockpit(limit=16)
        prepared["harbor_recent_evidence"] = harbor_evidence

        known_state = dict(prepared.get("known_state") or {})
        known_state["files"] = harbor_evidence.get("files") or known_state.get("files") or {}
        known_state["workspace_inspection"] = harbor_evidence.get("workspace_inspection") or known_state.get("workspace_inspection") or {}
        prepared["known_state"] = known_state

        memory_refs = dict(prepared.get("memory_refs") or {})
        memory_refs["important_receipts"] = harbor_evidence.get("important_receipts") or memory_refs.get("important_receipts") or []
        memory_refs["full_context_available_via_tools"] = True
        prepared["memory_refs"] = memory_refs

        recent_progress = dict(prepared.get("recent_progress") or {})
        if harbor_evidence.get("last_result_summary"):
            recent_progress["last_result_summary"] = harbor_evidence["last_result_summary"]
        if harbor_evidence.get("last_action_types"):
            recent_progress["last_action_types"] = harbor_evidence["last_action_types"]
        prepared["recent_progress"] = recent_progress

        prepared["long_running_execution_tools"] = {
            "background_job": {
                "purpose": "Start a long-running command in the live /app container without blocking the model loop.",
                "args": {
                    "cmd": "shell command to run in background",
                    "job_id": "optional stable id",
                    "cwd": "optional cwd, defaults to /app",
                    "timeout_seconds": "startup timeout only, not total job duration"
                },
                "use_when": [
                    "downloads",
                    "package installs",
                    "OCR/frame extraction",
                    "QEMU/service startup",
                    "any command expected to keep running"
                ]
            },
            "monitor_job": {
                "purpose": "Inspect a background job pid/log and recent outputs.",
                "args": {
                    "job_id": "id used by background_job",
                    "log_path": "optional explicit log path",
                    "pid_path": "optional explicit pid path"
                }
            },
            "service_probe_loop": {
                "purpose": "Repeatedly probe service readiness over time instead of one-shot checking.",
                "args": {
                    "cmd": "probe command, for example nc/telnet/vncsnapshot/curl",
                    "attempts": "number of probes",
                    "interval_seconds": "sleep between probes",
                    "success_pattern": "optional stdout/stderr substring proving readiness",
                    "cwd": "optional cwd"
                }
            }
        }
        prepared["dependency_repair_policy"] = {
            "rule": "If a required task tool is missing but package managers or bootstrap tools are available, install/bootstrap the dependency instead of repeating missing-tool probes.",
            "examples": [
                "If qemu-system-i386 is required and missing, try apt-get update/install qemu-system-x86 or the package that provides it.",
                "If video/OCR tooling is missing, try installing or bootstrapping curl/ffmpeg/python/tesseract/yt-dlp as permitted by the environment.",
                "After dependency repair, run a receipt-backed self-check before proceeding."
            ],
            "anti_loop": "Do not spend many steps repeating the same missing-tool observation. Repair, install, or choose an alternate feasible route."
        }
        prepared["model_owned_working_plan"] = self._load_model_owned_plan()
        prepared["model_owned_success_contract"] = self._load_model_owned_success_contract()
        prepared["model_success_contract_schema"] = self._model_success_contract_schema()
        prepared["deduplication_mirror"] = self._dedup_mirror_for_cockpit()
        prepared["evidence_work_ledger"] = self._evidence_work_ledger_for_cockpit()

        obligations = list(prepared.get("open_obligations") or [])
        finalization = prepared.get("finalization") or {}
        current_blocker = dict(prepared.get("current_blocker") or {})

        has_open_obligations = bool(obligations)
        if has_open_obligations:
            allowed = list(prepared.get("allowed_next_actions") or [])
            prepared["allowed_next_actions"] = [
                action for action in allowed
                if str(action).strip() not in {"finalize", "claim_complete"}
            ]

            blocker_summary = str(current_blocker.get("summary") or "Open obligations remain.")
            repair_summary = (
                blocker_summary
                + " Repair protocol: do not finalize. Identify the next unsatisfied functional criterion; "
                "create or run a self-check that would fail the current invalid behavior; repair or replace "
                "the artifact/service; rerun the self-check; then run required verifiers. Avoid repeating "
                "compile-only, file-existence-only, non-empty-only, deterministic-only, or smoke-only checks that do not test the functional criterion."
            )
            current_blocker.update({
                "summary": repair_summary,
                "required_next_mode": "repair_not_finalize",
                "must_not_actions": ["finalize", "cannot_complete", "repeat_same_invalid_artifact"],
            })
            prepared["current_blocker"] = current_blocker

            prepared["repair_packet"] = {
                "mode": "repair_not_finalize",
                "open_obligation_count": len(obligations),
                "next_required_actions": [
                    "Pick one unsatisfied functional correctness criterion.",
                    "Write or run a self-check that fails the current invalid behavior.",
                    "Repair or replace the artifact/service so that the self-check can pass.",
                    "Run the self-check and inspect output.",
                    "Run required verifier/probe actions after the self-check passes.",
                ],
                "bad_repair_patterns": [
                    "rewriting the same placeholder/stub",
                    "only checking file existence",
                    "only checking compilation",
                    "only running a smoke command without validating output",
                    "accepting deterministic/non-empty output as enough",
                    "accepting numeric-only, hash-like, RNG, fixed-string, lookup-table, or common-word output for semantic generation work",
                    "testing only an easy input when the visible requirement implies harder edge cases",
                    "treating a required input argument as a filename or optional data source unless the request says it is one",
                    "finalizing while verifier/artifact/service obligations remain",
                ],
            }

        return prepared



    def _recent_receipts_for_adversarial_review(self, *, limit: int = 18) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        receipt_dir = self.receipt_root / "receipts"
        for rp in sorted(receipt_dir.glob("*.json"))[-limit:]:
            try:
                obj = json.loads(rp.read_text(encoding="utf-8"))
            except Exception as exc:
                out.append({"receipt": rp.name, "error": str(exc)})
                continue
            compact = {
                "receipt": rp.name,
                "action_type": obj.get("action_type"),
                "status": obj.get("status"),
                "summary": obj.get("summary"),
            }
            result = obj.get("result")
            if isinstance(result, dict):
                for k in ("exit_code", "stdout_excerpt", "stderr_excerpt", "path", "bytes_written"):
                    if k in result:
                        compact[k] = str(result.get(k))[:1800]
            out.append(compact)
        return out

    def _artifact_snippets_for_adversarial_review(self, *, limit: int = 10, max_chars: int = 2200) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            files = sorted(
                [x for x in self.workspace_root.rglob("*") if x.is_file()],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            files = []
        for fp in files:
            if len(out) >= limit:
                break
            try:
                rel = str(fp.relative_to(self.workspace_root))
                size = fp.stat().st_size
            except Exception:
                continue
            if size > 300000:
                continue
            if fp.suffix.lower() not in {".c", ".h", ".py", ".sh", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".log"}:
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            out.append({"path": rel, "size": size, "snippet": text[:max_chars]})
        return out


    def _receipt_index_for_claim_gate(self) -> dict[str, dict[str, Any]]:
        """Index visible receipt JSON files by several convenient reference forms."""
        index: dict[str, dict[str, Any]] = {}
        roots = [self.receipt_root, self.receipt_root / "receipts"]
        for root in roots:
            if not root.exists():
                continue
            for rp in root.rglob("*.json"):
                try:
                    obj = json.loads(rp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                # Model call logs are not action evidence for solver work.
                if rp.name.startswith("model_") or rp.name in {"remote_context.json"}:
                    continue
                try:
                    rel = str(rp.relative_to(self.receipt_root))
                except Exception:
                    rel = rp.name
                keys = {
                    rp.name,
                    rp.stem,
                    rel,
                    str(rp),
                    "receipt:" + rp.name,
                    "receipt:" + rp.stem,
                    "receipt:" + rel,
                }
                if isinstance(obj, dict):
                    for ref in (obj.get("receipt_id"), obj.get("receipt_ref"), obj.get("id"), obj.get("receipt")):
                        if isinstance(ref, str) and ref:
                            keys.add(ref)
                            keys.add("receipt:" + ref)
                wrapped = {"path": str(rp), "rel": rel, "object": obj}
                for k in keys:
                    index[k] = wrapped
        return index


    def _final_verifier_authority_enabled(self) -> bool:
        raw = __import__("os").environ.get("MLPCP_FINAL_VERIFIER_AUTHORITY", "0")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}


    def _final_verifier_task_prompt(self, *, fallback_instruction: str = "") -> str:
        candidates = []
        try:
            candidates.append(self.workspace_root / "instruction.md")
        except Exception:
            pass
        try:
            candidates.append(self.receipt_root.parent / "host_workspace" / "instruction.md")
        except Exception:
            pass

        for path in candidates:
            try:
                if path.exists():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if text.strip():
                        return text[:16000]
            except Exception:
                continue
        return str(fallback_instruction or "")[:16000]


    def _final_verifier_conditions_met(self) -> dict[str, str]:
        default = {
            "artifact_gate": "not_required",
            "service_gate": "not_required",
            "visible_verifier_gate": "not_required",
            "verifier_model_approval": "not_required",
        }

        candidates = [
            ("session.capability_graph.conditions_met", lambda: self.session.capability_graph.conditions_met()),
            ("capability_graph.conditions_met", lambda: self.capability_graph.conditions_met()),
            ("_conditions_met", lambda: self._conditions_met()),
        ]
        for _name, fn in candidates:
            try:
                value = fn()
                if isinstance(value, dict):
                    out = dict(default)
                    out.update({k: v for k, v in value.items() if k in out})
                    return out
            except Exception:
                continue
        return default


    def _final_verifier_open_obligations(self, *, finalization=None) -> list[dict]:
        candidates = [
            ("session.capability_graph.obligations", lambda: self.session.capability_graph.obligations()),
            ("capability_graph.obligations", lambda: self.capability_graph.obligations()),
            ("_open_obligations", lambda: self._open_obligations()),
        ]
        for _name, fn in candidates:
            try:
                value = fn()
                if isinstance(value, list):
                    return value
            except Exception:
                continue
        try:
            return list(getattr(finalization, "unresolved_obligations", []) or [])
        except Exception:
            return []


    def _final_verifier_relevant_receipts(self, *, step_index: int) -> list:
        refs = []

        # Prefer explicit finalize evidence_refs from the main agent.
        try:
            finalize_action = self._latest_finalize_action_for_claim_gate(step_index=step_index)
            args = finalize_action.get("args") if isinstance(finalize_action, dict) else {}
            explicit = args.get("evidence_refs") if isinstance(args, dict) else []
            if isinstance(explicit, list):
                refs.extend(explicit[:12])
        except Exception:
            pass

        # Add a small tail of recent receipts as admissible context.
        try:
            receipt_store = self.session.receipt_store
            all_receipts = list(receipt_store.all_receipts())
            for receipt in all_receipts[-8:]:
                try:
                    refs.append(receipt_store.receipt_ref(receipt))
                except Exception:
                    continue
        except Exception:
            pass

        return refs[:16]


    def _final_verifier_current_blocker(self, *, finalization=None) -> dict | None:
        try:
            obligations = self._final_verifier_open_obligations(finalization=finalization)
            if obligations:
                return obligations[0]
        except Exception:
            pass
        try:
            if finalization is not None and not finalization.allowed:
                return {
                    "failure_class": finalization.failure_class.value if hasattr(finalization.failure_class, "value") else str(finalization.failure_class),
                    "summary": finalization.summary,
                    "evidence_refs": [],
                }
        except Exception:
            pass
        return None


    def _review_final_completion_authority(
        self,
        *,
        step_index: int,
        instruction: str,
        finalization,
        critic_result,
    ) -> FinalCompletionDecision:
        """Final internal verifier authority before Harbor submission.

        Under MLPCP_FINAL_VERIFIER_AUTHORITY=1, a main-agent finalize action is
        treated as finalize_candidate. The verifier authority decides internal
        submit/no-submit from a task-prompt + receipt-backed evidence pack.

        Current implementation uses the live host's existing adversarial critic
        as the verifier decision source, then validates that decision through the
        final_completion protocol. This is a safe bridge: it gives us the final
        authority protocol and logs now, while leaving room to swap in a separate
        verifier model client later.
        """
        conditions = self._final_verifier_conditions_met()
        obligations = self._final_verifier_open_obligations(finalization=finalization)
        blocker = self._final_verifier_current_blocker(finalization=finalization)
        receipts = self._final_verifier_relevant_receipts(step_index=step_index)

        try:
            contract = self._load_model_owned_success_contract()
        except Exception:
            contract = {}

        pack = build_final_verification_pack(
            pack_id=f"final_verification_pack_{self.row_id}_{step_index}",
            run_id=self.run_id,
            row_id=self.row_id,
            step=step_index,
            task_prompt=self._final_verifier_task_prompt(fallback_instruction=instruction),
            success_contract=contract if isinstance(contract, dict) else {},
            candidate_summary="Main agent requested final verification before external submission.",
            conditions_met=conditions,
            open_obligations=obligations,
            relevant_receipts=receipts,
            current_blocker=blocker,
        )

        may_claim_complete = bool(getattr(critic_result, "may_claim_complete", False))
        critic_summary = str(getattr(critic_result, "summary", "") or "")

        if finalization is not None and getattr(finalization, "allowed", False) and may_claim_complete:
            decision = FinalCompletionDecision(
                verdict=COMPLETE_INTERNAL,
                summary=critic_summary or "Final verifier authority approves internal completion from admissible evidence.",
                evidence_refs=pack.relevant_receipts[:8],
                confidence="medium",
            )
        else:
            repair_failure = "unknown"
            repair_summary = critic_summary or "Final verifier authority requires more admissible evidence before submission."

            if obligations:
                first = obligations[0]
                repair_failure = first.get("failure_class", "unknown")
                repair_summary = first.get("summary", repair_summary)

            decision = FinalCompletionDecision(
                verdict=REPAIR_REQUIRED if obligations else EVIDENCE_INSUFFICIENT,
                summary=repair_summary,
                evidence_refs=pack.relevant_receipts[:8],
                required_repairs=[
                    RequiredRepair(
                        summary=repair_summary,
                        requirement_id=obligations[0].get("requirement_id") if obligations else None,
                        check_id=obligations[0].get("check_id") if obligations else None,
                        failure_class=repair_failure,
                        evidence_refs=pack.relevant_receipts[:3],
                    )
                ] if (obligations or repair_summary) else [],
                confidence="medium",
            )

        validated = validate_final_completion_decision(decision=decision, pack=pack)

        try:
            (self.receipt_root / f"final_verification_pack_{step_index}.json").write_text(
                __import__("json").dumps(pack.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
            (self.receipt_root / f"final_completion_decision_{step_index}.json").write_text(
                __import__("json").dumps(validated.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
            if not validated.submit_allowed:
                packet = repair_packet_from_final_completion(decision=validated, pack=pack)
                (self.receipt_root / f"final_completion_repair_packet_{step_index}.json").write_text(
                    __import__("json").dumps(packet, indent=2, default=str),
                    encoding="utf-8",
                )
        except Exception as exc:
            try:
                (self.receipt_root / f"final_completion_logging_error_{step_index}.txt").write_text(str(exc), encoding="utf-8")
            except Exception:
                pass

        return validated




    def _lean_cockpit_enabled(self) -> bool:
        import os
        raw = os.environ.get("MLPCP_LEAN_COCKPIT", "1")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}


    def _lean_cockpit_task_prompt(self, *, fallback_instruction: str = "") -> str:
        candidates = []
        try:
            candidates.append(self.workspace_root / "instruction.md")
        except Exception:
            pass
        try:
            candidates.append(self.receipt_root.parent / "host_workspace" / "instruction.md")
        except Exception:
            pass

        for path in candidates:
            try:
                if path.exists():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if text.strip():
                        return text[:16000]
            except Exception:
                continue

        return str(fallback_instruction or "")[:16000]


    def _apply_lean_cockpit_formatter(self, prepared, *, step_index: int = 0, instruction: str = ""):
        """Apply Lean Cockpit v1 to the model-visible payload only.

        Full audit/control state remains inside the harness. This formatter is
        non-coercive: it orients the model with known state, unresolved
        requirements, existing evidence refs, useful tools, and finalization
        boundaries without forcing a specific next action.
        """
        if not self._lean_cockpit_enabled():
            return prepared

        try:
            lean = build_lean_cockpit(
                prepared,
                step=step_index,
                task_prompt=self._lean_cockpit_task_prompt(fallback_instruction=instruction),
            )

            try:
                (self.receipt_root / f"lean_cockpit_{step_index}.json").write_text(
                    __import__("json").dumps(lean, indent=2, sort_keys=True, default=str),
                    encoding="utf-8",
                )
            except Exception:
                pass

            return lean
        except Exception as exc:
            try:
                (self.receipt_root / f"lean_cockpit_error_{step_index}.txt").write_text(
                    str(exc),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return prepared



    def _latest_finalize_action_for_claim_gate(self, *, step_index: int) -> dict[str, Any] | None:
        """Read the latest model_execute JSON and return the model's finalize action, if any."""
        candidates = [
            self.receipt_root / f"model_execute_{step_index}.json",
            self.receipt_root / f"model_execute_{step_index:03d}.json",
        ]
        candidates.extend(sorted(self.receipt_root.glob("model_execute_*.json"))[-3:])
        for mp in reversed(candidates):
            if not mp.exists():
                continue
            try:
                obj = json.loads(mp.read_text(encoding="utf-8"))
            except Exception:
                continue
            parsed = obj.get("parsed")
            if not isinstance(parsed, dict):
                content = obj.get("content")
                if isinstance(content, str) and content.strip():
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        parsed = None
            if not isinstance(parsed, dict):
                continue
            actions = parsed.get("actions")
            if not isinstance(actions, list):
                continue
            for action in reversed(actions):
                if isinstance(action, dict) and str(action.get("type") or "").strip() == "finalize":
                    return action
        return None

    def _evidence_work_ledger_for_cockpit(self, *, limit: int = 12) -> dict[str, Any]:
        """Compact receipt ledger shown to the next model turn."""
        receipts = []
        for item in self._receipt_index_for_claim_gate().values():
            obj = item.get("object") if isinstance(item, dict) else None
            if not isinstance(obj, dict):
                continue
            action_type = obj.get("action_type") or obj.get("type")
            status = obj.get("status")
            summary = obj.get("summary")
            if not action_type:
                continue
            receipts.append({
                "ref": item.get("rel"),
                "action_type": action_type,
                "status": status,
                "summary": str(summary or "")[:300],
            })
        # Deduplicate by ref while preserving recent-ish order.
        seen = set()
        deduped = []
        for r in reversed(receipts):
            ref = r.get("ref")
            if ref in seen:
                continue
            seen.add(ref)
            deduped.append(r)
            if len(deduped) >= limit:
                break
        deduped.reverse()
        return {
            "measured_work_receipts": deduped,
            "rule": "No receipt-linked evidence means the work claim is unsupported. Finalize requires args.evidence_refs. Create or revise success_contract before finalization.",
        }

    def _evidence_claim_gate(
        self,
        *,
        step_index: int,
        finalization: FinalizationDecision,
        critic_result: VerifierCriticResult,
    ) -> VerifierCriticResult:
        """Block false completion claims unless finalize cites real receipts."""
        if not finalization.allowed or not critic_result.may_claim_complete:
            return critic_result

        finalize_action = self._latest_finalize_action_for_claim_gate(step_index=step_index)
        if not isinstance(finalize_action, dict):
            return VerifierCriticResult(
                verdict="REPAIR_NEEDED",
                may_claim_complete=False,
                summary="Evidence Claim Gate blocked completion: no finalize action with receipt-backed evidence_refs was found.",
                failure_class=getattr(FailureClass, "UNSUPPORTED_WORK_CLAIM", FailureClass.ARTIFACT_INVALID),
                evidence_refs=[],
                repair_packet={
                    "failure_class": "unsupported_work_claim",
                    "summary": "Completion was blocked because the model did not provide a finalize action with evidence_refs.",
                    "missing_evidence": ["finalize.args.evidence_refs"],
                    "suggested_next_actions": [
                        "Inspect the work ledger and receipts.",
                        "Run missing request-relevant checks.",
                        "Finalize only with args.evidence_refs pointing to successful receipts that prove the claimed work.",
                    ],
                    "unsupported_claims": ["completion claim without finalize evidence_refs"],
                    "work_ledger": self._evidence_work_ledger_for_cockpit(),
                },
            )

        args = finalize_action.get("args")
        if not isinstance(args, dict):
            args = {}
        refs = args.get("evidence_refs") or args.get("evidence") or []
        if isinstance(refs, str):
            refs = [refs]
        refs = [str(r) for r in refs if isinstance(r, (str, int)) and str(r).strip()]

        reason = str(finalize_action.get("reason") or "")
        summary_bits = []
        for k in ("summary", "evidence_summary", "verification_summary"):
            v = args.get(k)
            if isinstance(v, str):
                summary_bits.append(v)
        claim_text = " ".join([reason] + summary_bits).lower()

        blockers: list[str] = []
        unsupported: list[str] = []

        if not refs:
            blockers.append("finalize.args.evidence_refs is missing or empty")
            unsupported.append("finalize claim has no receipt-backed evidence_refs")

        receipt_index = self._receipt_index_for_claim_gate()
        resolved = []
        for ref in refs:
            hit = receipt_index.get(ref) or receipt_index.get(ref.removeprefix("receipt:"))
            if not hit:
                blockers.append(f"evidence_ref does not resolve to a visible receipt: {ref}")
                continue
            obj = hit.get("object") or {}
            status = str(obj.get("status") or "").lower()
            if status and status not in {"success", "passed", "ok"}:
                blockers.append(f"evidence_ref is not successful: {ref} status={status}")
                continue
            resolved.append((ref, obj))

        def has_action(types: set[str]) -> bool:
            for _, obj in resolved:
                action_type = str(obj.get("action_type") or obj.get("type") or "")
                if action_type in types:
                    return True
            return False

        test_words = {"ran", "test", "tested", "verify", "verified", "validated", "validation", "checked", "passed"}
        write_words = {"created", "updated", "edited", "wrote", "written", "generated", "implemented", "fixed"}
        service_words = {"service", "server", "daemon", "ready", "healthy", "started"}

        if any(w in claim_text for w in test_words) and not has_action({"run_verifier", "raw_bash", "probe_service"}):
            blockers.append("claim mentions testing/verification but evidence_refs do not include run_verifier/raw_bash/probe_service evidence")
            unsupported.append("testing/verification claim without matching receipt")

        if any(w in claim_text for w in write_words) and not has_action({"write_file", "raw_bash"}):
            blockers.append("claim mentions writing/editing/generating but evidence_refs do not include write_file/raw_bash evidence")
            unsupported.append("write/edit/generate claim without matching receipt")

        if any(w in claim_text for w in service_words) and not has_action({"probe_service", "raw_bash"}):
            blockers.append("claim mentions service readiness but evidence_refs do not include probe_service/raw_bash evidence")
            unsupported.append("service readiness claim without matching receipt")

        if blockers:
            return VerifierCriticResult(
                verdict="REPAIR_NEEDED",
                may_claim_complete=False,
                summary="Evidence Claim Gate blocked completion: " + "; ".join(blockers[:4]),
                failure_class=getattr(FailureClass, "UNSUPPORTED_WORK_CLAIM", FailureClass.ARTIFACT_INVALID),
                evidence_refs=refs,
                repair_packet={
                    "failure_class": "unsupported_work_claim",
                    "summary": "Finalize was rejected because claimed work was not backed by receipt-linked evidence.",
                    "missing_evidence": blockers,
                    "unsupported_claims": unsupported,
                    "provided_evidence_refs": refs,
                    "suggested_next_actions": [
                        "Use the work ledger to identify existing receipts.",
                        "Run missing self-checks/verifiers/probes as actual actions.",
                        "Return finalize only with evidence_refs that resolve to successful receipts supporting each claim.",
                    ],
                    "work_ledger": self._evidence_work_ledger_for_cockpit(),
                },
            )

        return critic_result



    def _execution_requested_finalization(self, exec_result) -> bool:
        """Return True only when the main model explicitly requested finalization.

        Do not use exec_result.finalization as the signal. In this host loop that
        field can represent ambient gate state, not model intent. Verification is
        triggered only by an explicit action emitted by the model.
        """
        try:
            payload = exec_result.to_dict() if hasattr(exec_result, "to_dict") else exec_result
        except Exception:
            payload = exec_result

        finalize_action_types = {
            "finalize",
            "finish",
            "complete",
            "submit",
            "claim_complete",
        }

        ignored_metadata_keys = {
            "finalization",
            "finalization_type",
            "finalization_decision",
            "mlpcp_finalization",
            "finalization_boundary",
        }

        action_keys = {
            "type",
            "action",
            "name",
            "action_type",
        }

        def walk(value):
            if isinstance(value, dict):
                for key in action_keys:
                    if key in value:
                        action_name = str(value.get(key) or "").strip().lower()
                        if action_name in finalize_action_types:
                            return True

                for key, nested in value.items():
                    if str(key) in ignored_metadata_keys:
                        continue
                    if walk(nested):
                        return True
                return False

            if isinstance(value, list):
                return any(walk(item) for item in value)

            return False

        return walk(payload)


    def _verification_skipped_result(self, *, step_index: int, exec_result=None) -> VerifierCriticResult:
        """Cheap placeholder result when no completion claim was made.

        This is not a semantic approval or rejection. It exists so the loop keeps
        a uniform step record without invoking the model verifier.
        """
        payload = {
            "verification_skipped": True,
            "reason": "No finalize/completion claim was made by the main model in this step.",
            "step_index": step_index,
        }
        try:
            (self.receipt_root / f"verification_skipped_{step_index}.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            pass

        return VerifierCriticResult(
            verdict="INSUFFICIENT_EVIDENCE",
            may_claim_complete=False,
            failure_class=FailureClass.NONE,
            summary="Verification skipped: no finalize/completion claim was made this step.",
            evidence_refs=[],
            repair_packet={
                "schema": "verification_skipped.v1",
                "verification_skipped": True,
                "missing_evidence": [],
                "suggested_next_actions": [],
                "unresolved_obligations": [],
                **payload,
            },
        )



    def _review_finalization_adversarial(
        self,
        *,
        step_index: int,
        contract: Any,
        finalization: FinalizationDecision,
        exec_result: ExecutePlanResult,
        cockpit: dict[str, Any],
    ) -> VerifierCriticResult:
        deterministic = self.critic.review(
            VerifierCriticRequest(
                run_id=self.run_id,
                row_id=self.row_id,
                capability_graph=self.session.capability_graph,
                finalization_decision=finalization,
            )
        )
        if not finalization.allowed:
            return deterministic

        try:
            instruction_text = (self.workspace_root / "instruction.md").read_text(encoding="utf-8", errors="replace")[:12000]
        except Exception:
            instruction_text = ""

        payload = {
            "review_mode": "adversarial_completion_review",
            "instruction": instruction_text,
            "model_owned_success_contract": self._load_model_owned_success_contract(),
            "success_contract_schema": self._model_success_contract_schema(),
            "deterministic_finalization": finalization.to_dict() if hasattr(finalization, "to_dict") else str(finalization),
            "latest_execute_result": exec_result.to_dict() if hasattr(exec_result, "to_dict") else str(exec_result),
            "cockpit": cockpit,
            "model_owned_working_plan": self._load_model_owned_plan(),
            "plan_review_policy": {
                "plan_is_optional": "A missing model-owned plan is not a completion blocker by itself.",
                "plan_is_context_not_truth": "The plan is useful continuity state when present, but it does not override the original request, success contract, receipts, artifacts, or measured behavior.",
                "reviewer_should_check_only_if_plan_present": [
                    "Does the plan include a credible verification/test strategy?",
                    "Did the solver gather the evidence the plan itself says is needed?",
                    "If the solver deviated from the plan, is the deviation justified by measured evidence?",
                    "Does the plan accidentally optimize for surrogate gates such as compilation, file readability, non-empty output, or smoke tests?"
                ],
                "reviewer_must_not": [
                    "Do not reject completion merely because no plan_update was created.",
                    "Do not treat the plan as proof of completed work."
                ]
            },
            "recent_receipts": self._recent_receipts_for_adversarial_review(),
            "artifact_snippets": self._artifact_snippets_for_adversarial_review(),
            "review_instruction": (
                "Act as an adversarial completion reviewer. Do not trust the solver. "
                "Approve only if visible evidence proves the implementation satisfies the user request and success contract. "
                "Artifact existence, compilation, non-empty output, deterministic output, model claims, or weak smoke checks are insufficient unless that is exactly the requirement. "
                "Look for fake work: placeholders, stubs, echoing input, padding, canned output, hashes/RNG, ignoring required inputs/assets, treating data arguments as paths, or checks that do not validate semantics. "
                "If evidence is missing, weak, inconsistent, or merely shows that some arbitrary command exited 0, require repair. "
                "Use the model-owned working plan as continuity context when present, but do not trust it as proof. Do not require a plan as a completion gate. If a plan is present, check whether the solver's evidence satisfies the plan's own verification strategy and the original request."
            ),
            "required_json_schema": {
                "verdict": "APPROVE or REPAIR",
                "summary": "short evidence-based summary",
                "missing_evidence": ["specific missing proof or weak evidence"],
                "required_next_actions": ["specific next repair/check actions"],
            },
        }

        request = ModelCallRequest(
            call_id=f"{self.run_id}_verify_{step_index}",
            run_id=self.run_id,
            row_id=self.row_id,
            phase="VERIFY",
            messages=[
                ModelMessage(
                    "system",
                    (
                        "You are an adversarial software verification reviewer. "
                        "Your job is to prevent false completion. "
                        "Prove success from visible evidence; do not trust solver claims or weak checks. "
                        "Return strict JSON only with verdict, summary, missing_evidence, and required_next_actions. "
                        "Use APPROVE only when all visible requirements are satisfied by strong measured evidence. "
                        "Use REPAIR for any uncertainty, missing proof, fake-looking artifact, weak verifier command, or semantic mismatch."
                    ),
                ),
                ModelMessage("user", json.dumps(payload, sort_keys=True)),
            ],
        )

        try:
            model_result = self.model_client.call(request)
            (self.receipt_root / f"model_verify_{step_index}.json").write_text(
                json.dumps(model_result.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            return VerifierCriticResult(
                verdict="REPAIR_NEEDED",
                may_claim_complete=False,
                summary=f"Adversarial verifier model failed closed: {exc}",
                failure_class=FailureClass.ARTIFACT_INVALID,
                evidence_refs=[],
                repair_packet={
                    "summary": "Internal adversarial review could not prove success.",
                    "suggested_next_actions": ["Continue repair from measured evidence."],
                    "unresolved_obligations": [],
                },
            )

        parsed = model_result.parsed if isinstance(getattr(model_result, "parsed", None), dict) else {}
        verdict = str(parsed.get("verdict") or "").strip().upper()
        summary = str(parsed.get("summary") or "Adversarial reviewer did not provide a sufficient approval summary.")[:1000]
        missing = parsed.get("missing_evidence")
        if not isinstance(missing, list):
            missing = []
        next_actions = parsed.get("required_next_actions")
        if not isinstance(next_actions, list):
            next_actions = []

        if getattr(model_result, "status", None) == "success" and verdict == "APPROVE" and not missing:
            return VerifierCriticResult(
                verdict="APPROVED",
                may_claim_complete=True,
                summary="Adversarial model reviewer approved completion from visible evidence. " + summary,
                failure_class=FailureClass.NONE,
                evidence_refs=[],
                repair_packet={"summary": summary, "suggested_next_actions": [], "unresolved_obligations": []},
            )

        return VerifierCriticResult(
            verdict="REPAIR_NEEDED",
            may_claim_complete=False,
            summary="Adversarial model reviewer blocked completion. " + summary,
            failure_class=FailureClass.ARTIFACT_INVALID,
            evidence_refs=[],
            repair_packet={
                "summary": summary,
                "missing_evidence": missing,
                "suggested_next_actions": next_actions or ["Repair artifact and run stronger request-relevant validation."],
                "unresolved_obligations": missing,
            },
        )



    def _visible_required_artifact_paths(self, instruction: str) -> list[str]:
        paths: list[str] = []
        for token in ["/app/gpt2.c", "gpt2.c"]:
            if token in instruction and token not in paths:
                paths.append(token)
        return paths

    def _recent_action_receipts_compact(self, *, limit: int = 30) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        receipt_dir = self.receipt_root / "receipts"
        try:
            paths = sorted(receipt_dir.glob("*.json"))[-limit:]
        except Exception:
            paths = []
        for rp in paths:
            try:
                obj = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                continue
            stdout = obj.get("stdout")
            stderr = obj.get("stderr")
            out.append({
                "receipt_id": obj.get("receipt_id") or rp.stem,
                "step": obj.get("step"),
                "tool": obj.get("tool_name") or obj.get("action_type"),
                "status": obj.get("status"),
                "summary": obj.get("summary") or obj.get("model_visible_summary"),
                "files_written": obj.get("files_written") or [],
                "artifact_refs": obj.get("artifact_refs") or [],
                "verifier_refs": obj.get("verifier_refs") or [],
                "service_refs": obj.get("service_refs") or [],
                "stdout": (stdout or {}).get("excerpt", "")[:500] if isinstance(stdout, dict) else "",
                "stderr": (stderr or {}).get("excerpt", "")[:500] if isinstance(stderr, dict) else "",
                "tool_args_hash": obj.get("tool_args_hash"),
            })
        return out


    def _workspace_file_hash(self, model_path: str) -> str | None:
        """Hash a visible workspace file by model path such as /app/gpt2.c."""
        try:
            rel = model_path.removeprefix("/app/") if model_path.startswith("/app/") else model_path
            path = self.workspace_root / rel
            if not path.exists() or not path.is_file():
                return None
            h = __import__("hashlib").sha256()
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def _read_workspace_text(self, model_path: str, *, limit: int = 60000) -> str:
        try:
            rel = model_path.removeprefix("/app/") if model_path.startswith("/app/") else model_path
            path = self.workspace_root / rel
            if not path.exists() or not path.is_file():
                return ""
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        except Exception:
            return ""

    def _parse_model_jsonish_actions(self, content: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Parse model action JSON from stored model_execute content.

        Some model outputs contain duplicate JSON objects on separate lines. Prefer
        the last parseable object because that is usually the final corrected one.
        """
        candidates: list[dict[str, Any]] = []
        for line in str(content or "").splitlines():
            t = line.strip()
            if not (t.startswith("{") and t.endswith("}")):
                continue
            try:
                obj = json.loads(t)
            except Exception:
                continue
            if isinstance(obj, dict):
                candidates.append(obj)

        if not candidates:
            try:
                obj = json.loads(str(content or ""))
                if isinstance(obj, dict):
                    candidates.append(obj)
            except Exception:
                pass

        if not candidates:
            return [], None

        parsed = candidates[-1]
        actions = parsed.get("actions") or parsed.get("execute_plan") or []
        if not isinstance(actions, list):
            actions = []

        plan_update = parsed.get("plan_update") or parsed.get("working_plan") or parsed.get("model_plan")
        if not isinstance(plan_update, dict):
            plan_update = None

        return [a for a in actions if isinstance(a, dict)], plan_update

    def _recent_model_actions_compact(self, *, limit: int = 40) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            paths = sorted(
                self.receipt_root.glob("model_execute_*.json"),
                key=lambda p: int(__import__("re").search(r"(\d+)", p.name).group(1)),
            )[-limit:]
        except Exception:
            paths = []

        for mp in paths:
            try:
                obj = json.loads(mp.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            content = obj.get("content") or json.dumps(obj.get("parsed") or obj, default=str)
            actions, plan_update = self._parse_model_jsonish_actions(content)
            step_match = __import__("re").search(r"(\d+)", mp.name)
            step = int(step_match.group(1)) if step_match else None

            for i, a in enumerate(actions):
                args = a.get("args") or {}
                payload = a.get("payload") if isinstance(a.get("payload"), dict) else {}
                cmd = None
                path = None
                if isinstance(args, dict):
                    cmd = args.get("cmd") or args.get("command")
                    path = args.get("path")
                cmd = cmd or payload.get("cmd") or payload.get("command") or a.get("cmd") or a.get("command")
                path = path or payload.get("path") or a.get("path")
                action_type = str(a.get("type") or a.get("action") or a.get("action_type") or "")
                reason = str(a.get("reason") or "")
                text = "\n".join([action_type, reason, str(cmd or ""), str(path or "")]).lower()

                is_write = (
                    action_type == "write_file"
                    or ("cat >" in text and "gpt2.c" in text)
                    or ("write_text" in text and "gpt2.c" in text)
                )
                is_read = (
                    action_type == "read_file"
                    or "sed -n" in text
                    or "wc -c" in text
                    or "head -c" in text
                    or "od -an" in text
                )
                is_compile = "gcc" in text or "compile" in text or "-lm" in text or "libm" in text
                is_run = "./a.out" in text or "/tmp/gpt2_test" in text or "prompt" in text or "hello" in text or "world" in text or "diff" in text or "cmp -s" in text
                is_measurement = (is_read or is_compile or is_run) and not is_write
                is_plan_action = action_type == "plan_update"

                out.append({
                    "step": step,
                    "index": i,
                    "type": action_type,
                    "reason": reason[:600],
                    "cmd": str(cmd or "")[:1000],
                    "path": str(path or "")[:300],
                    "has_top_level_plan_update": bool(plan_update),
                    "is_write": is_write,
                    "is_read": is_read,
                    "is_compile": is_compile,
                    "is_run": is_run,
                    "is_measurement": is_measurement,
                    "is_plan_action": is_plan_action,
                })

        return out

    def _fake_artifact_findings(self, *, instruction: str = "") -> dict[str, Any] | None:
        """Detect obviously fake generated artifacts for the current task.

        Generic enough to avoid benchmark-specific answers, but strong enough to
        catch checksum/hash/random/echo programs masquerading as semantic work.
        """
        text = self._read_workspace_text("/app/gpt2.c", limit=80000)
        if not text:
            return None

        low = text.lower()
        findings: list[str] = []

        fake_markers = [
            "2166136261", "16777619", "2654435761", "%50000",
            "% 50000", "%1000000007", "% 1000000007",
            "checksum", "fnv", "hash", "rand(", "srand(",
            "puts(v[3])", "printf(\"%s", "fopen(v[1]", "fopen(argv[1]"
        ]
        for marker in fake_markers:
            if marker in low:
                findings.append(f"source contains hash/checksum/pseudo-random marker: {marker}")

        if "__import__" in low:
            findings.append("source contains suspicious dynamic import marker")

        compact = "".join(low.split())
        if "puts(v[3])" in compact or "puts(argv[3])" in compact:
            findings.append("source directly echoes the prompt argument instead of generating a continuation")
        if ("fopen(v[1]" in compact or "fopen(argv[1]" in compact) and ("vocab" not in low and "v[2]" not in low and "argv[2]" not in low):
            findings.append("source opens checkpoint but appears to ignore vocab/BPE input")
        if len(text.encode("utf-8", errors="replace")) < 800 and ("gpt" in str(instruction).lower() or "gpt2" in low):
            findings.append("source is implausibly tiny for the requested GPT-style checkpoint/tokenizer/inference behavior")

        # Task-specific semantic red flags only when the visible task is GPT-style generation.
        task_text = str(instruction or "").lower()
        if "gpt" in task_text or "gpt2" in low or "gpt2.c" in task_text:
            required_footprints = [
                "matmul", "layer", "att", "softmax", "logit", "embed",
                "norm", "gelu", "pos", "token", "vocab"
            ]
            present = [x for x in required_footprints if x in low]
            if len(present) < 4:
                findings.append("source lacks plausible transformer/GPT inference footprints")
            if "printf(\"%u" in low or "printf(\"%d" in low:
                findings.append("source appears to print numeric token IDs rather than continuation text")

        if not findings:
            return None

        return {
            "artifact": "/app/gpt2.c",
            "hash": self._workspace_file_hash("/app/gpt2.c"),
            "size_bytes": len(text.encode("utf-8", errors="replace")),
            "findings": findings[:12],
            "ruling": "artifact_suspicious_or_semantically_invalid_until_repaired_or_stronger_verified",
        }


    def _progress_ledger_path(self, step_index: int) -> Path:
        return self.receipt_root / f"progress_ledger_{step_index}.json"

    def _progress_required_artifact_paths(self, instruction: str) -> list[str]:
        paths: list[str] = []

        try:
            for item in self._visible_required_artifact_paths(instruction):
                if item:
                    paths.append(str(item))
        except Exception:
            pass

        try:
            stored = self._load_model_owned_success_contract()
        except Exception:
            stored = {}

        candidates = []
        if isinstance(stored, dict):
            candidates.append(stored)
            if isinstance(stored.get("contract"), dict):
                candidates.append(stored.get("contract"))

        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            for key in ("required_artifacts", "required_outputs", "artifacts", "outputs"):
                value = obj.get(key)
                if not isinstance(value, list):
                    continue
                for item in value:
                    if isinstance(item, str):
                        paths.append(item)
                    elif isinstance(item, dict):
                        for path_key in ("path", "file", "output_path", "artifact"):
                            v = item.get(path_key)
                            if v:
                                paths.append(str(v))
                                break

        out = []
        seen = set()
        for raw in paths:
            text = str(raw).strip()
            if not text:
                continue
            if text.startswith("/app/") or text.startswith("./") or "/" in text or "." in Path(text).name:
                if text not in seen:
                    out.append(text)
                    seen.add(text)
        return out[:12]

    def _progress_local_path(self, path: str) -> Path:
        text = str(path or "")
        if text.startswith("/app/"):
            text = text.removeprefix("/app/")
        elif text.startswith("./"):
            text = text[2:]
        return self.workspace_root / text

    def _progress_actions_for_step(self, step_index: int) -> list[dict[str, Any]]:
        path = self.receipt_root / f"model_execute_{step_index}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return []

        parsed = data.get("parsed") if isinstance(data, dict) else None
        if not isinstance(parsed, dict):
            content = data.get("content") if isinstance(data, dict) else ""
            actions, plan_update = self._parse_model_jsonish_actions(str(content or ""))
            parsed = {"actions": actions}
            if isinstance(plan_update, dict):
                parsed["plan_update"] = plan_update

        actions = parsed.get("actions") or parsed.get("execute_plan") or []
        if not isinstance(actions, list):
            actions = []

        out = [a for a in actions if isinstance(a, dict)]
        if isinstance(parsed.get("plan_update"), dict):
            out.append({"type": "plan_update", "args": parsed.get("plan_update"), "_synthetic_top_level_plan_update": True})
        return out

    def _progress_action_fields(self, action: dict[str, Any]) -> dict[str, Any]:
        raw_args = action.get("args")
        args = raw_args if isinstance(raw_args, dict) else {}
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        action_type = str(
            action.get("type")
            or action.get("action")
            or action.get("action_type")
            or action.get("name")
            or ""
        ).strip()

        command = (
            action.get("command")
            or action.get("cmd")
            or payload.get("command")
            or payload.get("cmd")
            or args.get("command")
            or args.get("cmd")
            or (raw_args if isinstance(raw_args, str) else "")
            or ""
        )
        path = (
            action.get("path")
            or payload.get("path")
            or payload.get("file")
            or payload.get("output_path")
            or args.get("path")
            or args.get("file")
            or args.get("output_path")
            or ""
        )
        content = action.get("content") or payload.get("content") or args.get("content") or ""

        return {
            "type": action_type,
            "path": str(path or ""),
            "command": str(command or ""),
            "content_chars": len(str(content)) if content else 0,
        }

    def _progress_artifact_states(self, required_paths: list[str]) -> list[dict[str, Any]]:
        states = []
        for path in required_paths:
            local = self._progress_local_path(path)
            exists = False
            size = None
            signals = []
            sha256 = None

            try:
                exists = local.exists()
                if exists and local.is_file():
                    data = local.read_bytes()
                    size = len(data)
                    sha256 = text_hash(data.decode("utf-8", errors="replace"))
                    text = data[:4000].decode("utf-8", errors="replace").lower()

                    if size == 0:
                        signals.append("empty_file")
                    if size is not None and size < 120:
                        signals.append("tiny_file")
                    if "todo" in text or "placeholder" in text or "stub" in text:
                        signals.append("placeholder_marker")
                    if "return 0" in text and "main" in text and size < 300:
                        signals.append("returns_zero_stub")
                    if "printf" in text and size < 300:
                        signals.append("tiny_print_program")
                    if "<tok" in text or "tok%d" in text or "tok%u" in text:
                        signals.append("canned_token_output")
                    if (
                        ("v[3]" in text or "argv[3]" in text)
                        and (
                            'printf("%.*s' in text
                            or 'printf("%s' in text
                            or "puts(v[3])" in text
                            or "puts(argv[3])" in text
                        )
                    ):
                        signals.append("echoes_prompt_argument")
                    if (
                        ("fopen(v[1]" in text or "fopen(argv[1]" in text)
                        and ("fopen(v[2]" in text or "fopen(argv[2]" in text)
                        and ("<tok" in text or 'printf("%.*s' in text or "tok%d" in text)
                    ):
                        signals.append("surface_reads_required_inputs_but_outputs_canned_or_echo")
                    if (
                        ("gpt" in str(getattr(self, "_current_instruction", "")).lower()
                         or "gpt2" in str(getattr(self, "_current_instruction", "")).lower()
                         or "gpt2.c" in str(path).lower())
                        and sum(1 for marker in ("matmul", "softmax", "layer", "att", "gelu", "logit", "embed", "norm") if marker in text) < 3
                        and ("<tok" in text or 'printf("%.*s' in text)
                    ):
                        signals.append("lacks_plausible_model_inference_footprints")
            except Exception:
                pass

            states.append({
                "path": path,
                "exists": exists,
                "size_bytes": size,
                "sha256": sha256,
                "signals": signals,
                "likely_stub": bool({"empty_file", "tiny_file", "placeholder_marker", "returns_zero_stub"} & set(signals)),
                "likely_invalid": bool({
                    "empty_file",
                    "tiny_file",
                    "placeholder_marker",
                    "returns_zero_stub",
                    "canned_token_output",
                    "echoes_prompt_argument",
                    "surface_reads_required_inputs_but_outputs_canned_or_echo",
                    "lacks_plausible_model_inference_footprints",
                } & set(signals)),
            })

        return states

    def _recent_progress_entries(self, *, limit: int = 8) -> list[dict[str, Any]]:
        out = []
        try:
            paths = sorted(
                self.receipt_root.glob("progress_ledger_*.json"),
                key=lambda p: int(__import__("re").search(r"(\d+)", p.name).group(1)),
            )[-limit:]
        except Exception:
            paths = []
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, dict):
                    out.append(data)
            except Exception:
                continue
        return out

    def _record_progress_ledger(self, *, step_index: int, instruction: str, exec_result) -> dict[str, Any]:
        actions = self._progress_actions_for_step(step_index)
        fields = [self._progress_action_fields(a) for a in actions]
        action_types = [f["type"] for f in fields if f.get("type")]

        plan_types = {"plan_update", "update_plan", "success_contract", "working_plan", "model_plan"}
        concrete_types = {
            "read_file", "write_file", "search_files", "raw_bash", "run_verifier",
            "probe_service", "view_receipt", "search_receipts", "view_file_cache"
        }

        plan_only = bool(action_types) and all(t in plan_types for t in action_types)
        concrete_action_count = sum(1 for t in action_types if t in concrete_types)

        commands = [f["command"] for f in fields if f.get("command")]
        paths = [f["path"] for f in fields if f.get("path")]
        required_paths = self._progress_required_artifact_paths(instruction)
        artifact_states = self._progress_artifact_states(required_paths)
        missing_required = [s["path"] for s in artifact_states if not s.get("exists")]

        try:
            payload = exec_result.to_dict() if hasattr(exec_result, "to_dict") else exec_result
        except Exception:
            payload = exec_result
        payload_text = json.dumps(payload, sort_keys=True, default=str).lower()

        no_such_file = "no such file or directory" in payload_text
        failed_missing_artifact_probe = False
        for path in missing_required:
            tokens = {str(path).lower(), Path(str(path)).name.lower()}
            if no_such_file and any(t and t in payload_text for t in tokens):
                failed_missing_artifact_probe = True
                break

        compile_attempted = any(
            any(marker in c.lower() for marker in ("gcc", "g++", "make ", "cmake", "cargo build", "javac", "go build"))
            for c in commands
        )
        runtime_attempted = any(
            any(marker in c.lower() for marker in ("./", "/app/a.out", "python ", "node ", "java ", "cargo run", "go run"))
            for c in commands
        )

        previous = self._recent_progress_entries(limit=5)
        prior_plan_only_count = 0
        for item in reversed(previous):
            if item.get("plan_only"):
                prior_plan_only_count += 1
            else:
                break

        repeated_command_count = 0
        prior_commands = []
        for item in previous:
            prior_commands.extend(item.get("commands") or [])
        for command in commands:
            if command and command in prior_commands:
                repeated_command_count += 1

        failure_hint = "none"
        progress_stage = "execution"
        productive_step = concrete_action_count > 0 and not failed_missing_artifact_probe

        if missing_required and failed_missing_artifact_probe:
            failure_hint = "artifact_missing"
            progress_stage = "missing_artifact_probe"
            productive_step = False
        elif missing_required and plan_only and prior_plan_only_count >= 1:
            failure_hint = "artifact_missing"
            progress_stage = "plan_only_stall_with_required_artifact_missing"
            productive_step = False
        elif plan_only:
            failure_hint = "plan_only"
            progress_stage = "plan_only"
            productive_step = False
        elif repeated_command_count and not productive_step:
            failure_hint = "repeated_no_progress"
            progress_stage = "repeated_command"
        elif any(s.get("likely_invalid") or s.get("likely_stub") for s in artifact_states):
            failure_hint = "artifact_invalid"
            progress_stage = "fake_or_placeholder_artifact"
            productive_step = False
        elif required_paths and any(s.get("exists") for s in artifact_states) and not compile_attempted and not runtime_attempted:
            failure_hint = "verifier_not_run"
            progress_stage = "artifact_written_without_behavior_evidence"
            productive_step = True

        facts = []
        if missing_required:
            facts.append("Required artifact(s) missing: " + ", ".join(missing_required[:4]))
        if failed_missing_artifact_probe:
            facts.append("A concrete command failed because a required artifact was missing.")
        if plan_only:
            facts.append("This step only updated planning/contract state and produced no concrete workspace action.")
        if prior_plan_only_count and plan_only:
            facts.append(f"Consecutive prior plan-only steps: {prior_plan_only_count}.")
        if repeated_command_count:
            facts.append(f"Repeated command count: {repeated_command_count}.")
        if compile_attempted:
            facts.append("Compile/build command attempted.")
        if runtime_attempted:
            facts.append("Runtime command attempted.")

        entry = {
            "schema": "progress_ledger.v1",
            "step_index": step_index,
            "action_types": action_types,
            "concrete_action_count": concrete_action_count,
            "plan_only": plan_only,
            "commands": commands[:8],
            "paths": paths[:8],
            "required_artifacts": required_paths,
            "artifact_states": artifact_states,
            "missing_required_artifacts": missing_required,
            "compile_attempted": compile_attempted,
            "runtime_attempted": runtime_attempted,
            "failed_missing_artifact_probe": failed_missing_artifact_probe,
            "repeated_command_count": repeated_command_count,
            "productive_step": productive_step,
            "progress_stage": progress_stage,
            "failure_hint": failure_hint,
            "facts": facts[:8],
        }

        try:
            self._progress_ledger_path(step_index).write_text(
                json.dumps(entry, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

        return entry

    def _progress_state_from_ledger(self, entry: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None

        failure_hint = str(entry.get("failure_hint") or "none")
        if failure_hint in {"", "none"}:
            return {
                "type": "progress_state",
                "failure_class": "none",
                "summary": "Recent step made measurable progress or no actionable progress issue was detected.",
                "progress_stage": entry.get("progress_stage"),
                "facts": entry.get("facts") or [],
            }

        failure_class = {
            "artifact_missing": "artifact_missing",
            "artifact_invalid": "artifact_invalid",
            "verifier_not_run": "verifier_not_run",
            "plan_only": "repeated_no_progress",
            "repeated_no_progress": "repeated_no_progress",
        }.get(failure_hint, "unknown")

        missing = entry.get("missing_required_artifacts") or []
        if failure_hint == "artifact_missing":
            summary = "Required artifact is missing after recent concrete/plan steps."
        elif failure_hint == "plan_only":
            summary = "Recent step only updated plan state and produced no concrete workspace progress."
        elif failure_hint == "artifact_invalid":
            summary = "Required artifact exists but looks fake, canned, stub-like, or placeholder-like."
        elif failure_hint == "verifier_not_run":
            summary = "Required artifact exists, but no receipt-backed compile/runtime/finalization evidence has been produced yet."
        else:
            summary = "Recent steps show no measurable concrete progress."

        return {
            "type": "progress_state",
            "failure_class": failure_class,
            "summary": summary,
            "progress_stage": entry.get("progress_stage"),
            "missing_required_artifacts": missing,
            "facts": entry.get("facts") or [],
            "productive_step": entry.get("productive_step"),
            "step_index": entry.get("step_index"),
        }

    def _latest_progress_ledger_entry(self) -> dict[str, Any]:
        entries = self._recent_progress_entries(limit=1)
        return entries[-1] if entries else {}


    def _evidence_saturation_packet(self, *, step_index: int, instruction: str) -> dict[str, Any] | None:
        """Convert repeated history into stateful non-progress rulings.

        This does not require a plan. It detects repeated reads/measurements of an
        unchanged state. If a plan exists, the packet also enforces plan-action
        accountability.
        """
        actions = self._recent_model_actions_compact(limit=50)
        if not actions:
            return None

        recent = actions[-24:]
        writes_recent = [a for a in recent if a.get("is_write")]
        measurements_recent = [a for a in recent if a.get("is_measurement")]
        compile_recent = [a for a in recent if a.get("is_compile")]
        read_recent = [a for a in recent if a.get("is_read")]
        run_recent = [a for a in recent if a.get("is_run")]

        gpt2_hash = self._workspace_file_hash("/app/gpt2.c")
        gpt2_exists = gpt2_hash is not None

        plan_obj = self._load_model_owned_plan()
        has_plan = isinstance(plan_obj, dict) and plan_obj.get("status") not in {"no_plan_yet", "plan_read_error", "plan_invalid"}
        plan_text = json.dumps(plan_obj, sort_keys=True, default=str).lower() if has_plan else ""

        plan_says_unresolved = any(x in plan_text for x in [
            "evidence_gaps", "known_bad_behavior", "no verified semantic implementation",
            "invalid", "unverified", "repair", "needs repair", "semantic",
        ])

        fake_findings = self._fake_artifact_findings(instruction=instruction)

        # Stop early repeated gcc/libm readiness probes when no artifact progress exists.
        if step_index >= 8 and not gpt2_exists and len(compile_recent) >= 6 and not writes_recent:
            return {
                "type": "evidence_saturation",
                "severity": "repair_required",
                "summary": "Compiler/library readiness and file inspection have already been measured repeatedly, but the required artifact is still missing.",
                "saturated_evidence_classes": ["gcc/libm readiness", "workspace/file inspection"],
                "ruling": [
                    "Do not run another gcc/libm/readiness probe.",
                    "Known state already covers generic workspace inspection. Useful new evidence would come from artifact work, implementation design, or a genuinely new implementation-critical detail.",
                    "A successful raw_bash exit is not progress when it repeats an already-known fact."
                ],
                "required_next_action": "Write /app/gpt2.c or perform one specific new implementation-critical analysis. No more readiness-only commands.",
                "recent_actions": recent[-12:],
            }

        # If artifact exists and recent turns repeatedly measure unchanged state, block.
        if step_index >= 14 and gpt2_exists and len(measurements_recent) >= 5 and not writes_recent and not fake_findings:
            return {
                "type": "evidence_saturation",
                "severity": "repair_required",
                "summary": "Recent actions repeatedly inspect/compile/run the same unchanged artifact without modifying it.",
                "artifact_state": {
                    "path": "/app/gpt2.c",
                    "sha256": gpt2_hash,
                    "fake_artifact_findings": fake_findings,
                },
                "plan_context": {
                    "plan_present": has_plan,
                    "plan_says_unresolved": plan_says_unresolved,
                },
                "saturated_evidence_classes": [
                    "read unchanged source",
                    "compile unchanged source",
                    "run prompt-difference check on unchanged source",
                ],
                "ruling": [
                    "Do not repeat another read/compile/run-only measurement of unchanged /app/gpt2.c.",
                    "If the artifact is invalid, unverified, echo-only, stub-like, or input-ignoring, measurement has saturated.",
                    "The next action must modify/replace /app/gpt2.c, run a materially stronger semantic verifier, or explicitly revise the implementation strategy.",
                    "Prompt-dependent output is not sufficient when the task requires semantic model behavior."
                ],
                "required_next_action": "Mutate /app/gpt2.c or change implementation strategy. Measurement-only actions are invalid until state changes.",
                "recent_actions": recent[-14:],
            }

        # If fake markers are found, be even stricter.
        if step_index >= 10 and gpt2_exists and fake_findings and len(measurements_recent) >= 2 and not writes_recent:
            return {
                "type": "fake_artifact_guard",
                "severity": "repair_required",
                "summary": "The required artifact appears to be a hash/checksum/pseudo-output implementation rather than the semantic implementation requested.",
                "artifact_state": {
                    "path": "/app/gpt2.c",
                    "sha256": gpt2_hash,
                    "fake_artifact_findings": fake_findings,
                },
                "ruling": [
                    "Compile success and prompt-dependent output do not validate this artifact.",
                    "Numeric/hash/checksum/pseudo-random/echo/stub output is not acceptable when the request requires semantic continuation.",
                    "Do not finalize from this artifact.",
                    "Do not rerun the same weak prompt-difference check.",
                    "Repair or replace the implementation, or revise the implementation strategy honestly from visible constraints."
                ],
                "required_next_action": "Repair/replace /app/gpt2.c or revise strategy. Do not run another weak measurement on this unchanged artifact.",
                "recent_actions": recent[-14:],
            }

        return None

    def _strip_action_level_plan_updates(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Capture plan/checklist/notes actions as model state, not executable tools."""
        if not isinstance(parsed, dict):
            return parsed

        out = dict(parsed)
        state_only_types = {
            "plan_update",
            "update_plan",
            "working_checklist",
            "checklist_update",
            "model_notes",
            "action_rationale",
            "working_memory",
            "scratchpad",
            "notes",
            "scratchpad_update",
            "success_contract",
            "contract",
            "message",
            "error",
            "observation",
            "analysis",
            "thought",
            "comment",
        }

        for key in ("actions", "execute_plan"):
            actions = out.get(key)
            if not isinstance(actions, list):
                continue

            kept = []
            action_plan = None
            action_notes = None

            for a in actions:
                if not isinstance(a, dict):
                    kept.append(a)
                    continue

                action_type = str(a.get("type") or a.get("action_type") or "").strip()

                if action_type not in state_only_types:
                    kept.append(a)
                    continue

                if action_type in {"plan_update", "update_plan", "working_checklist", "checklist_update"}:
                    for source_key in ("args", "plan", "working_plan", "model_plan", "working_checklist", "checklist_update"):
                        value = a.get(source_key)
                        if isinstance(value, dict):
                            action_plan = value
                            break
                        if isinstance(value, list):
                            action_plan = {source_key: value}
                            break

                note_payload = {}
                for notes_key in ("model_notes", "action_rationale", "working_memory", "scratchpad", "notes", "args"):
                    value = a.get(notes_key)
                    if isinstance(value, dict):
                        note_payload[notes_key] = value
                    elif isinstance(value, str) and value.strip():
                        note_payload[notes_key] = value.strip()[:4000]

                if note_payload:
                    if isinstance(action_notes, dict):
                        action_notes.update(note_payload)
                    else:
                        action_notes = note_payload

            if action_plan is not None and not isinstance(out.get("plan_update"), dict):
                out["plan_update"] = action_plan
            if action_notes is not None and not isinstance(out.get("model_notes"), dict):
                out["model_notes"] = action_notes
            out[key] = kept

        return out


    def _progress_guard_packet(self, *, step_index: int, instruction: str) -> dict[str, Any] | None:
        """Detect non-progress loops and return a model-visible repair packet.

        This is intentionally generic, but it has a strong rule: when the user
        requires a concrete artifact, repeated environment/tool readiness checks
        without writing or testing that artifact are non-progress.
        """
        receipts = self._recent_action_receipts_compact(limit=40)
        required_paths = self._visible_required_artifact_paths(instruction)

        if not receipts:
            return None

        recent = receipts[-20:]
        raw_count = sum(1 for r in recent if r.get("tool") == "raw_bash")
        writes = [r for r in receipts if r.get("files_written")]
        artifact_refs = [r for r in receipts if r.get("artifact_refs")]
        verifier_refs = [r for r in receipts if r.get("verifier_refs")]

        text = "\n".join(
            " ".join(str(r.get(k) or "") for k in ("summary", "stdout", "stderr"))
            for r in recent
        ).lower()

        readiness_words = [
            "gcc", "libm", "link", "linked", "compile_link", "probe",
            "readiness", "ready", "service gate", "service obligation",
            "gcc_ok", "libm_ok"
        ]
        repeated_readiness = sum(1 for w in readiness_words if w in text) >= 3

        required_missing = []
        for path in required_paths:
            check = path
            if path.startswith("/app/"):
                check = path.removeprefix("/app/")
            if not (self.workspace_root / check).exists():
                required_missing.append(path)

        # Soft-block early enough to avoid 300-step loops, but after initial orientation.
        if step_index >= 8 and required_missing and raw_count >= 8 and not writes and repeated_readiness:
            return {
                "type": "progress_guard",
                "severity": "repair_required",
                "summary": "The loop is stuck on environment/tool readiness checks without creating the required artifact.",
                "required_missing_artifacts": required_missing,
                "non_progress_pattern": {
                    "recent_raw_bash_count": raw_count,
                    "writes_seen": len(writes),
                    "artifact_refs_seen": len(artifact_refs),
                    "verifier_refs_seen": len(verifier_refs),
                    "repeated_readiness_checks": True,
                },
                "ruling": [
                    "Stop running gcc/libm/tool-readiness probes. They are prerequisites, not the user request.",
                    "Do not claim service gates are the only open obligations.",
                    "The next action must either create/modify the required source artifact, or inspect a specific required data/file format needed to implement it.",
                    "Workspace listing and tool readiness checks are already sufficient and must not be repeated unless a new failure demands it.",
                    "Finalize is forbidden until the required artifact exists and has behavior evidence.",
                ],
                "required_next_action": (
                    "Create or modify the missing artifact now, or inspect checkpoint/tokenizer format specifically for implementation. "
                    "Do not run another gcc/libm readiness probe."
                ),
                "recent_receipts": recent[-8:],
            }

        # Harder block if the loop ignores the guard for a long time.
        if step_index >= 24 and required_missing and not writes and repeated_readiness:
            return {
                "type": "progress_guard",
                "severity": "hard_block_imminent",
                "summary": "No artifact progress after many steps. Required source artifact is still missing.",
                "required_missing_artifacts": required_missing,
                "ruling": [
                    "The run is not making implementation progress.",
                    "Any further readiness-only command is invalid.",
                    "Known state already covers generic inspection. Useful next work is artifact work, implementation design, or a specific implementation-critical check."
                ],
                "required_next_action": "Write the required artifact or perform specific implementation analysis immediately.",
                "recent_receipts": recent[-10:],
            }

        return None


    async def _run_execute_step(self, *, step_index: int, cockpit: dict[str, Any]) -> ExecutePlanResult:
        cockpit_for_model = self._prepare_cockpit_for_model(cockpit)
        cockpit_for_model = self._apply_lean_cockpit_formatter(
            cockpit_for_model,
            step_index=step_index,
            instruction=getattr(self, "_current_instruction", ""),
        )
        try:
            self._remote_context_cache = await self._remote_context()
        except Exception as exc:
            self._remote_context_cache = {"context_error": str(exc)}

        request = ModelCallRequest(
            call_id=f"{self.run_id}_execute_{step_index}",
            run_id=self.run_id,
            row_id=self.row_id,
            phase="EXECUTE",
            messages=[
                ModelMessage(
                    "system",
                    (
                        (
                            'You are an interactive software engineering agent. '
                        "Your job is to solve the user's visible request using only visible files, local commands, recorded history, tool results, and observed runtime behavior. "
                        'Do not rely on prior attempts, outside information, hidden files, solution files, non-visible evaluation internals, non-visible expected answers, or memorized answers. '
                        'You are not here to guess the answer. Inspect, act, measure, repair, and finish only when the visible requirements are satisfied by evidence. '
                        ' '
                        'Response format: '
                        'Return strict JSON only. '
                        'The top-level object must contain an actions list. The top-level object may also contain success_contract, a model-authored contract following the provided schema. The harness provides the schema only; you own the task interpretation from the original request and visible environment. Create or revise success_contract when useful, and before finalization. The top-level object may also contain plan_update, working_checklist, and model_notes. These are model-owned working memory fields that the host stores and feeds back on later turns. Use them to keep a concise checklist of task understanding, implementation choices, evidence, risks, and next checks. Do not use a placeholder artifact just to satisfy existence. model_notes must be concise auditable rationale, not hidden chain-of-thought. Prefer structured tools for structured operations: use read_file for file reads, write_file for source edits, search_files for search, and raw_bash for shell-native compile/run/system commands. Do not bundle inspect+compile+run+diff into one repeated raw_bash loop when structured tools can provide cleaner evidence. '
                        'Each action should have this shape: {"type":"action_type","reason":"short evidence-based reason","args":{}}. '
                        'Do not include prose outside JSON. '
                        'Do not include markdown. '
                        'Do not include comments. '
                        'Do not invent action types. '
                        'Use only the allowed actions provided by the harness. '
                        'When done, return a finalize action with a concise evidence summary and args.evidence_refs listing receipt-backed evidence. Finalize without evidence_refs is invalid. '
                        ' '
                        'Core operating loop: '
                        '1. Orient from visible evidence. Inspect the working directory, relevant files, configs, tests, scripts, logs, services, existing artifacts, and recorded receipts before making important changes. '
                        '2. Define success from evidence. Identify required outputs, required inputs or assets, functional criteria, services, verifiers, risks, unknowns, and the smallest useful next action. '
                        '3. Plan briefly and update as evidence changes. Revise the plan when file contents, logs, verifier output, service probes, or command results contradict earlier assumptions. '
                        '4. Execute focused actions. Prefer minimal targeted changes. Edit existing files when appropriate. Do not add unrelated features, broad refactors, placeholder files, canned answers, or speculative work. '
                        '5. Verify behavior, not appearances. A valid check must test the visible requirement. File existence, compilation, formatting, deterministic output, non-empty output, or a passing smoke check is not enough unless that is the actual requirement. '
                        '6. Repair from measured failures. Treat stdout, stderr, logs, service probes, file diffs, verifier output, and receipts as evidence. Use them to choose the next repair. '
                        '7. Finalize only with evidence. Finalize only when required outputs exist, required behavior is proven, required services are ready, required verifiers or probes pass, and no open blocker remains. '
                        ' '
                        'Action discipline: '
                        'Use actions intentionally. '
                        'Prefer this order: inspect visible evidence; identify or refine the success contract; make the smallest useful change; run a relevant self-check; run verifier or probe when appropriate; inspect failures; repair; finalize. '
                        'Do not call tools randomly. '
                        'Do not repeat work if a receipt already contains the needed evidence. If compiler/linker/library readiness has been proven once, move to implementation; repeated readiness probes are non-progress. '
                        'Use recorded history, receipts, file cache, logs, and current blocker summaries before repeating expensive commands. '
                        'If recorded history conflicts with current observations, trust current measured behavior. '
                        ' '
                        'Tool use rules: '
                        'Use read_file when available to inspect a known specific file. Use raw_bash with bounded find, grep, ls, sed, awk, or similar commands to search the visible workspace. '
                        'Use raw_bash for shell exploration, diagnostics, builds, tests, service inspection, local scripts, and implementation commands. Keep commands focused, bounded, and evidence-producing. '
                        'Use write_file only for real required artifacts or necessary support files. Do not use it for placeholders, stubs, guesses, or fake completion. '
                        'Use run_verifier for concrete visible verifier or test commands after you have done your own request-relevant self-checks. '
                        'Use probe_service for readiness checks of HTTP servers, APIs, daemons, background processes, sockets, protocol endpoints, or long-running services. '
                        'Use receipt and file-cache inspection actions when available to inspect prior commands, stdout, stderr, verifier results, service probes, and created artifacts. '
                        'Use finalize only when the completion checklist is satisfied. A finalize action must include args.evidence_refs, and each referenced receipt must support the claimed work. '
                        ' '
                        'Path and boundary rules: '
                        'Work only inside the visible workspace and explicitly allowed output paths. '
                        'Do not read, write, search, or reference hidden, oracle, reviewer, solution, or verifier-internal paths unless the harness explicitly exposes them as visible. '
                        'Visible tests, scripts, and examples may be inspected and run when they are part of the workspace. Do not modify tests or verifier files unless the user request explicitly requires it. '
                        'Do not use hidden or oracle information as solver evidence. '
                        'Do not treat a user-provided data argument as a file path unless the request says it is a path. '
                        'Quote paths and arguments safely. '
                        'Inspect a file before modifying it unless it is a newly required output. '
                        ' '
                        'Environment map and recorded history: '
                        'The remote environment map is an initial snapshot. It may be incomplete or stale after commands run, packages install, files change, services start, or containers restart. '
                        'Use the map as a starting point, then verify important facts with commands. '
                        'Use success contract snapshot, required outputs, required services, required verifiers, done condition, cockpit state, last result, receipts, logs, service probes, file cache, current blockers, and capability graph status as recorded history when available. '
                        'Before repeating work, inspect recorded evidence when available. '
                        ' '
                        'Success contract and requirement gates: '
                        'The success contract defines what must be true before completion. '
                        'If the contract is incomplete or wrong, infer the corrected requirement from visible evidence and act accordingly. '
                        'Required outputs must be real artifacts, not placeholders. '
                        'Required services must be ready by measured checks, not by claims. Compilers, linkers, libraries, interpreters, package managers, files, and local CLI tools are build/runtime prerequisites, not services. Do not create persistent service gates for gcc, libm, Python, shell tools, checkpoints, tokenizer files, or ordinary local files. '
                        'Required verifiers must pass with relevant evidence. '
                        'Capability or requirement gates are satisfied only by measured evidence with receipt references. '
                        'A model claim is not readiness. '
                        'A process starting is not readiness. Tool availability checks may support implementation, but they never satisfy the user request by themselves. '
                        'A low-level signal is not full readiness unless the visible requirement only asks for that exact signal. Repeating tool-readiness probes after success is not progress. '
                        'A broad check may satisfy multiple requirements only when those links are explicit. '
                        ' '
                        'Self-check quality: '
                        'A self-check should be derived from visible requirements, local files, and observed behavior. '
                        'A self-check should fail the known-bad behavior before it is accepted as validating the repair. '
                        'A self-check should prove required inputs affect behavior when the request requires using them. '
                        'For data, parser, compiler, model, service, or generator work, compare behavior across changed inputs where possible. '
                        'Reject checks that only prove compilation, formatting, file existence, non-empty output, deterministic output, fixed strings, hashes without behavioral meaning, random seed control, lookup tables, echoes, padding, or smoke-only success. '
                        'For difficult implementation work, derive actual data and file formats from the workspace, build a small diagnostic oracle when possible, compare against it, then simplify or optimize after correctness is demonstrated. '
                        ' '
                        'Service monitoring: '
                        'If the request involves a service, daemon, server, API, socket, VM, or background process, identify required behavior from visible evidence, start only when needed, capture logs, confirm the expected process or listener exists, probe the expected endpoint/protocol/command/behavior, inspect failures before repairing, and refresh service state after config, file, package, or process changes. '
                        'Do not assume a service is ready because the process started. '
                        'Use protocol, content, command, log, RPC, HTTP, SSH, socket, or domain-specific probes when the visible requirement demands them. '
                        ' '
                        'Verifier use: '
                        'Use visible verifiers as evidence, not as a substitute for understanding. '
                        'Run relevant self-checks before the final verifier when possible. '
                        'When verifier output fails, inspect it carefully and repair from the failure evidence. '
                        'Do not expose non-visible verifier internals in reasoning or final answers. '
                        'Do not turn hidden or oracle verifier results into solver hints. '
                        'If a verifier is unavailable or the environment is missing dependencies, classify that from evidence and continue with the strongest visible request-relevant checks available. '
                        ' '
                        'Raw bash rules: '
                        'raw_bash is allowed, but every command should be evidence-producing. '
                        'Use bounded commands. '
                        'Avoid unnecessary long-running processes. '
                        'Do not start silent background services unless the action explicitly declares background intent and you will probe or log them afterward. '
                        'Avoid destructive commands unless they are required and safe for the visible workspace. '
                        ' '
                        'Completion checklist: '
                        'Before finalizing, confirm required outputs exist, artifacts are real and complete, required inputs or assets were used when required, functional criteria have behavioral evidence, required verifiers or self-checks passed, required services are healthy by measured probes, current blockers are resolved, no output is a placeholder/stub/mock/canned answer/incomplete shortcut, and no hidden/oracle/solution material was used as solver evidence. '
                        'When you believe the work is done, treat verification as a high-stakes final gate. Never claim that you inspected, edited, ran, tested, verified, started, installed, generated, or confirmed anything unless that action appears in recorded receipts or the current action result. '
                        'Run the strongest visible verifier or request-relevant check available, inspect the result, repair failures, then finalize only when the checklist is satisfied. '
                        'Do not use cannot_complete unless the visible requirements are impossible from the available environment. '
                            'If current work is invalid, continue repairing from evidence instead of giving up. '
                        )
                        if step_index <= 1 or __import__("os").environ.get("MLPCP_FULL_PROMPT_EVERY_STEP") == "1"
                        else (
                            "You are an interactive software engineering agent. Return strict JSON only with a top-level actions list. "
                            "Use only allowed actions. Use receipts, file cache, and measured evidence before repeating equivalent work. "
                            "You may include success_contract, plan_update, working_checklist, or model_notes when useful. "
                            "Finalize only when completion is supported by receipt-backed evidence_refs. "
                            "If cockpit or derived state conflicts with the original request or measured evidence, preserve the original request and repair the derived state."
                        )
                    ),
                ),
                ModelMessage(
                    "user",
                    "ORIGINAL USER REQUEST / AUTHORITATIVE TASK OBJECTIVE:\n"
                    + self._original_instruction_for_model()
                    + "\n\nInstruction priority note: the success contract, cockpit, receipts, and repair packets are derived aids. If they conflict with the original request, preserve the original request and repair the derived state. Do not satisfy surrogate gates such as compile/read/non-empty-output when the original request demands semantic behavior.",
                ),
                ModelMessage(
                    "user",
                    "REMOTE ENVIRONMENT MAP:\n"
                    + json.dumps(
                        compact_remote_context_for_model(getattr(self, "_remote_context_cache", {})),
                        sort_keys=True,
                    ),
                ),
                ModelMessage(
                    "user",
                    "SUCCESS CONTRACT CHECKLIST:\n"
                    + json.dumps(self._success_checklist_for_model(), sort_keys=True),
                ),
                ModelMessage(
                    "user",
                    "MODEL-OWNED WORKING PLAN:\n"
                    + json.dumps(self._load_model_owned_plan(), sort_keys=True),
                ),
                ModelMessage("user", json.dumps(cockpit_for_model, sort_keys=True)),
            ],
        )
        try:
            (self.receipt_root / f"model_execute_request_{step_index}.json").write_text(
                json.dumps(
                    {
                        "call_id": getattr(request, "call_id", None),
                        "run_id": getattr(request, "run_id", None),
                        "row_id": getattr(request, "row_id", None),
                        "phase": getattr(request, "phase", None),
                        "messages": [
                            {
                                "role": getattr(m, "role", None),
                                "content": getattr(m, "content", None),
                            }
                            for m in getattr(request, "messages", [])
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                    default=str,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            try:
                (self.receipt_root / f"model_execute_request_log_error_{step_index}.txt").write_text(
                    str(exc),
                    encoding="utf-8",
                )
            except Exception:
                pass

        model_result = self.model_client.call(request)
        try:
            (self.receipt_root / f"model_execute_{step_index}.json").write_text(
                json.dumps(model_result.to_dict(), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as log_exc:
            (self.receipt_root / f"model_execute_{step_index}_logging_error.txt").write_text(str(log_exc), encoding="utf-8")
        if model_result.status != "success" or model_result.parsed is None:
            raise ModelIOError(model_result.error or "Model did not return valid execute actions.")
        self._capture_model_success_contract(model_result.parsed, step_index=step_index)
        self._capture_model_plan_update(model_result.parsed, step_index=step_index)
        parsed_for_execution = self._strip_action_level_plan_updates(model_result.parsed)
        self._capture_model_success_contract(parsed_for_execution, step_index=step_index)
        self._capture_model_plan_update(parsed_for_execution, step_index=step_index)
        plan_request = parse_execute_plan_request(
            parsed=parsed_for_execution,
            run_id=self.run_id,
            row_id=self.row_id,
            request_id=f"execute_{step_index}",
            step_start=step_index,
        )
        return await self._execute_request(plan_request)

    async def _execute_request(self, request: ExecutePlanRequest) -> ExecutePlanResult:
        action_results: list[ActionResult] = []
        status = "success"
        stopped_at: str | None = None
        finalization: FinalizationDecision | None = None
        for offset, action in enumerate(request.actions, start=1):
            step = request.step_start + offset
            try:
                action_plain_for_dedup = self._action_plain_dict_for_dedup(action)
                duplicate_execution = self._find_duplicate_execution(action_plain_for_dedup)

                if duplicate_execution is not None:
                    mirror = self._duplicate_execution_mirror_result(
                        action_plain_for_dedup,
                        step_index=step,
                        duplicate=duplicate_execution,
                    )
                    result = ActionResult(
                        action.action_id,
                        action.action_type,
                        "success",
                        mirror.get("message") or "Duplicate action skipped as already-known evidence. Continue with a more specific follow-up or proceed from the known state.",
                        failure_class=FailureClass.NONE,
                        result=mirror,
                    )
                else:
                    result = await self._execute_action(action, step=step)
                    self._record_action_execution_signature(
                        action_plain_for_dedup,
                        step_index=step,
                        result=result,
                        receipt_ref=getattr(result, "receipt_ref", None),
                    )
            except Exception as exc:
                result = ActionResult(
                    action.action_id,
                    action.action_type,
                    "error",
                    f"{action.action_type} errored: {exc}",
                    failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                    error=str(exc),
                )
            action_results.append(result)
            if action.action_type == "finalize" and isinstance(result.result, FinalizationDecision):
                finalization = result.result
            if result.status in {"blocked", "error"}:
                status = "blocked"
                stopped_at = action.action_id
                break
        if finalization is None:
            finalization = self._evaluate_finalization()
        return ExecutePlanResult(
            request_id=request.request_id,
            run_id=request.run_id,
            row_id=request.row_id,
            status=status,
            action_results=action_results,
            finalization=finalization,
            stopped_at_action_id=stopped_at,
        )

    async def _execute_action(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        action_type = action.action_type
        if action_type == "read_file":
            return await self._action_read_file(action, step=step)
        if action_type == "write_file":
            return await self._action_write_file(action, step=step)
        if action_type == "search_files":
            return await self._action_search_files(action, step=step)
        if action_type == "raw_bash":
            return await self._action_raw_bash(action, step=step)
        if action_type == "run_verifier":
            return await self._action_run_verifier(action, step=step)
        if action_type == "probe_service":
            return await self._action_probe_service(action, step=step)
        if action_type == "view_receipt":
            return self._action_view_receipt(action)
        if action_type == "search_receipts":
            return self._action_search_receipts(action)
        if action_type == "view_file_cache":
            return self._action_view_file_cache(action)
        if action_type in {"background_job", "start_background_job"}:
            return await self._action_background_job(action, step=step)
        if action_type in {"monitor_job", "check_background_job"}:
            return await self._action_monitor_job(action, step=step)
        if action_type in {"service_probe_loop", "wait_for_service"}:
            return await self._action_service_probe_loop(action, step=step)
        if action_type == "finalize":
            return self._action_finalize(action)
        if action_type in {
            "model_notes",
            "action_rationale",
            "working_memory",
            "scratchpad",
            "notes",
            "scratchpad_update",
            "plan_update",
            "update_plan",
            "working_checklist",
            "checklist_update",
            "success_contract",
            "contract",
            "message",
            "error",
            "observation",
            "analysis",
            "thought",
            "comment",
        }:
            return ActionResult(
                action.action_id,
                action.action_type,
                "success",
                f"Captured non-executable model state action: {action_type}.",
                result={"captured_state_action": action_type},
            )
        raise ValueError(f"Unsupported action type: {action_type}")


    def _remote_search_target(self, raw_path: str) -> tuple[str, str]:
        """Map model-visible search paths onto the live Harbor /app filesystem."""
        raw = str(raw_path or ".").strip().replace("\\", "/")
        raw = raw.strip("'\"`")

        if raw in {"", ".", "./", "app", "./app", REMOTE_WORKSPACE_ROOT}:
            return REMOTE_WORKSPACE_ROOT, "."

        if raw == "/app":
            return REMOTE_WORKSPACE_ROOT, "."

        if raw.startswith(f"{REMOTE_WORKSPACE_ROOT}/"):
            rel = raw[len(f"{REMOTE_WORKSPACE_ROOT}/"):].strip("/")
            return f"{REMOTE_WORKSPACE_ROOT}/{rel}" if rel else REMOTE_WORKSPACE_ROOT, rel or "."

        if raw.startswith("/"):
            raise ValueError("search path must stay inside live /app workspace")

        rel = raw.strip("/")
        return f"{REMOTE_WORKSPACE_ROOT}/{rel}" if rel else REMOTE_WORKSPACE_ROOT, rel or "."

    @staticmethod
    def _matches_search_pattern(rel: str, pattern: str) -> bool:
        rel = str(rel or "").replace("\\", "/").lstrip("/")
        name = rel.rsplit("/", 1)[-1]
        pattern = str(pattern or "*").strip() or "*"

        if pattern in {"*", "**", "**/*", "./**/*"}:
            return True

        return (
            fnmatch(name, pattern)
            or fnmatch(rel, pattern)
            or fnmatch(f"/{rel}", pattern)
            or fnmatch(f"{REMOTE_WORKSPACE_ROOT}/{rel}", pattern)
        )

    async def _action_search_files(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        args = action.args or {}
        raw_base = str(args.get("path") or ".")
        pattern = str(args.get("pattern") or "*")
        max_results = int(args.get("max_results") or 80)
        max_results = max(1, min(max_results, 200))

        try:
            remote_base, rel_base = self._remote_search_target(raw_base)
        except Exception as exc:
            return ActionResult(
                action.action_id,
                action.action_type,
                "error",
                f"search_files invalid path: {exc}",
                failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                error=str(exc),
            )

        matches: list[str] = []
        seen: set[str] = set()

        # Primary truth: live Harbor task container /app.
        find_cmd = (
            "if [ -d {base} ]; then find {base} -type f -print 2>/dev/null; "
            "elif [ -f {base} ]; then printf '%s\\n' {base}; "
            "else true; fi"
        ).format(base=shlex.quote(remote_base))

        try:
            cp = await self.environment.exec(
                command=find_cmd,
                cwd=REMOTE_WORKSPACE_ROOT,
                timeout_sec=20,
            )
            for line in (cp.stdout or "").splitlines():
                remote_path = line.strip()
                if not remote_path:
                    continue

                if remote_path == REMOTE_WORKSPACE_ROOT:
                    rel = "."
                elif remote_path.startswith(f"{REMOTE_WORKSPACE_ROOT}/"):
                    rel = remote_path[len(f"{REMOTE_WORKSPACE_ROOT}/"):]
                else:
                    continue

                rel = rel.strip("/")
                if not rel:
                    continue

                if self._matches_search_pattern(rel, pattern) and rel not in seen:
                    seen.add(rel)
                    matches.append(rel)

                if len(matches) >= max_results:
                    break
        except Exception as exc:
            return ActionResult(
                action.action_id,
                action.action_type,
                "error",
                f"search_files failed against live /app: {exc}",
                failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                error=str(exc),
            )

        # Secondary convenience: host-side task prompt files such as instruction.md.
        # This avoids losing the visible instruction file while still treating /app as the task truth.
        if len(matches) < max_results:
            try:
                local_base = self.workspace_root if rel_base == "." else self.workspace_root / rel_base
                if local_base.exists():
                    for fp in local_base.rglob("*") if local_base.is_dir() else [local_base]:
                        if not fp.is_file():
                            continue
                        rel = str(fp.relative_to(self.workspace_root)).replace("\\", "/")
                        if self._matches_search_pattern(rel, pattern) and rel not in seen:
                            seen.add(rel)
                            matches.append(rel)
                        if len(matches) >= max_results:
                            break
            except Exception:
                pass

        summary = f"search_files found {len(matches)} matches."
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="search_files",
            tool_args={
                "path": rel_base,
                "raw_path": raw_base,
                "pattern": pattern,
                "max_results": max_results,
                "remote_base": remote_base,
            },
            cwd=REMOTE_WORKSPACE_ROOT,
            status="success",
            exit_code=0,
            stdout="\n".join(matches),
            stderr="",
            summary=summary,
            files_read=[Reference(ref_type="file", ref_id=rel_base, summary=f"Searched live {remote_base}")],
            failure_class=FailureClass.NONE,
            model_visible_summary=summary,
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        self.session.memory_store.record_directory_listing(
            path=rel_base,
            entries=matches,
            receipt_ref=receipt_ref,
            step=step,
        )
        return ActionResult(
            action.action_id,
            action.action_type,
            "success",
            summary,
            result={"matches": matches, "pattern": pattern, "path": rel_base, "remote_base": remote_base},
            receipt_ref=receipt_ref,
        )


    async def _action_read_file(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        path = self.guard.validate_read_path(self._normalize_model_path(str(action.args.get("path") or "")))
        rel = self._rel(path)
        target = path
        target.parent.mkdir(parents=True, exist_ok=True)
        await self.environment.download_file(self._remote_path(rel), target)
        content = target.read_text(encoding="utf-8", errors="replace")
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="read_file",
            tool_args={"path": rel},
            cwd=REMOTE_WORKSPACE_ROOT,
            status="success",
            exit_code=0,
            stdout=content,
            stderr="",
            summary=f"Read file {rel}.",
            files_read=[Reference(ref_type="file", ref_id=rel, summary=f"Read {rel}")],
            failure_class=FailureClass.NONE,
            model_visible_summary=f"Read file {rel}.",
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        self.session.memory_store.record_file_read(path=rel, content=content, receipt_ref=receipt_ref, step=step)
        return ActionResult(action.action_id, action.action_type, "success", f"Read file {rel}.", receipt_ref=receipt_ref, result={"path": rel, "content": content})

    async def _action_write_file(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        path = self.guard.validate_write_path(self._normalize_model_path(str(action.args.get("path") or "")))
        content = str(action.args.get("content") or "")
        rel = self._rel(path)
        before_hash = text_hash(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        remote_parent = self._remote_parent(rel)
        await self.environment.exec(command=f"mkdir -p {shlex.quote(remote_parent)}", cwd=REMOTE_WORKSPACE_ROOT, timeout_sec=30)
        await self.environment.upload_file(path, self._remote_path(rel))
        after_hash = text_hash(content)
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="write_file",
            tool_args={"path": rel, "content_sha256": after_hash},
            cwd=REMOTE_WORKSPACE_ROOT,
            status="success",
            exit_code=0,
            stdout=f"wrote {rel}\n",
            stderr="",
            summary=f"Wrote file {rel}.",
            files_written=[Reference(ref_type="file", ref_id=rel, summary=f"Wrote {rel}")],
            file_hashes={rel: {"before": before_hash, "after": after_hash}},
            failure_class=FailureClass.NONE,
            model_visible_summary=f"Wrote file {rel}.",
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        self.session.memory_store.record_file_read(path=rel, content=content, receipt_ref=receipt_ref, step=step)
        self._apply_capability_if_requested(action, passed=True, receipt_ref=receipt_ref, summary=f"Measured write_file success for {rel}.")
        self._apply_artifact_write_evidence(rel=rel, receipt_ref=receipt_ref)
        return ActionResult(action.action_id, action.action_type, "success", f"Wrote file {rel}.", receipt_ref=receipt_ref, result={"path": rel, "before_sha256": before_hash, "after_sha256": after_hash})

    def _artifact_path_variants(self, value: str) -> set[str]:
        text = str(value or "").strip().strip("`'\"")
        text = text.replace("\\", "/")
        stripped = text.strip("/")
        leaf = stripped.rsplit("/", 1)[-1] if stripped else stripped
        sanitized = stripped.replace("/", "_").replace(".", "_").replace("-", "_").strip("_")
        leaf_sanitized = leaf.replace(".", "_").replace("-", "_").strip("_")
        variants = {text, stripped, "/" + stripped if stripped else "", leaf, sanitized, leaf_sanitized}
        return {v for v in variants if v}


    def _artifact_candidate_check_ids(self, *, output: dict, idx: int, graph) -> list[str]:
        path = str(output.get("path") or output.get("name") or f"output_{idx}").strip()
        variants = self._artifact_path_variants(path)

        candidates: list[str] = []

        for key in ("check_id", "exists_check_id"):
            value = output.get(key)
            if value:
                candidates.append(str(value))

        req = output.get("requirement_id")
        if req:
            candidates.append(f"{req}:exists")

        for v in variants:
            candidates.append(f"artifact:{v}:exists")

        # Important: CapabilityGraph usually sanitizes /app/gpt2.c to app_gpt2_c.
        sanitized = path.strip("/").replace("/", "_").replace(".", "_").replace("-", "_").strip("_")
        if sanitized:
            candidates.append(f"artifact:{sanitized}:exists")

        try:
            obligations = graph.obligations()
        except Exception:
            obligations = []

        for obligation in obligations:
            if hasattr(obligation, "to_dict"):
                try:
                    data = obligation.to_dict()
                except Exception:
                    data = {}
            elif isinstance(obligation, dict):
                data = obligation
            else:
                data = {}

            check_id = str(data.get("check_id") or "")
            requirement_id = str(data.get("requirement_id") or "")
            haystack = f"{check_id} {requirement_id}"
            if check_id.startswith("artifact:") and any(v and v in haystack for v in variants):
                candidates.append(check_id)

        out: list[str] = []
        seen = set()
        for c in candidates:
            c = str(c).strip()
            if c and c not in seen:
                out.append(c)
                seen.add(c)
        return out


    def _credit_artifact_output(
        self,
        *,
        output: dict,
        idx: int,
        receipt_ref,
        summary: str,
    ) -> bool:
        graph = getattr(self.session, "capability_graph", None)
        if graph is None or receipt_ref is None:
            return False

        applied = False
        for check_id in self._artifact_candidate_check_ids(output=output, idx=idx, graph=graph):
            try:
                graph.apply_measured_check(
                    check_id=check_id,
                    passed=True,
                    receipt_ref=receipt_ref,
                    summary=summary,
                    failure_class=FailureClass.NONE,
                )
                applied = True
            except Exception:
                pass
        return applied


    def _apply_artifact_write_evidence(self, *, rel: str, receipt_ref) -> None:
        contract = getattr(self.session, "success_contract", None)
        if contract is None or receipt_ref is None:
            return

        rel_variants = self._artifact_path_variants(rel)

        for idx, output in enumerate(getattr(contract, "required_outputs", []) or []):
            if output.get("required", True) is False:
                continue

            path = str(output.get("path") or output.get("name") or f"output_{idx}").strip()
            path_variants = self._artifact_path_variants(path)

            if rel_variants & path_variants:
                self._credit_artifact_output(
                    output=output,
                    idx=idx,
                    receipt_ref=receipt_ref,
                    summary=f"Required artifact observed in Harbor workspace: {path}",
                )


    async def _action_raw_bash(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        command = str(action.args.get("cmd") or action.args.get("command") or "")
        if not command:
            raise ValueError("raw_bash requires cmd")
        original_command = command
        command = re.sub(r"(?<![\w./-])python(?![\w.-])", "python3", command)
        self.guard.validate_command_text(command)
        cwd = self.guard.validate_cwd(self._normalize_model_path(str(action.args.get("cwd") or "")) if action.args.get("cwd") else None)
        timeout = int(action.args.get("timeout_seconds") or (self.execute_policy or ExecutePlanPolicy()).raw_bash_timeout_seconds)
        remote_cwd = self._remote_path(self._rel(cwd))
        cp = await self.environment.exec(command=command, cwd=remote_cwd, timeout_sec=timeout)
        status = "success" if cp.return_code == 0 else "fail"
        failure_class = FailureClass.NONE if cp.return_code == 0 else FailureClass.TOOL_EXECUTION_ERROR
        summary = f"raw_bash exited {cp.return_code}."
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="raw_bash",
            tool_args={"cmd": command, "original_cmd": original_command if original_command != command else None, "cwd": self._rel(cwd), "timeout_seconds": timeout},
            cwd=remote_cwd,
            status=status,
            exit_code=cp.return_code,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            summary=summary,
            failure_class=failure_class,
            model_visible_summary=summary,
            excerpt_chars=(self.execute_policy or ExecutePlanPolicy()).raw_bash_max_output_chars,
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        if action.args.get("capability_check_id"):
            self._apply_capability_if_requested(action, passed=status == "success", receipt_ref=receipt_ref, summary=summary, failure_class=failure_class)

        if status == "success":
            await self._scan_artifact_outputs(receipt_ref=receipt_ref)

        action_status = "success" if status == "success" else "error"
        return ActionResult(action.action_id, action.action_type, action_status, summary, failure_class=failure_class, receipt_ref=receipt_ref, result={"exit_code": cp.return_code, "stdout_excerpt": receipt.stdout["excerpt"], "stderr_excerpt": receipt.stderr["excerpt"]})


    async def _scan_artifact_outputs(self, *, receipt_ref) -> None:
        contract = getattr(self.session, "success_contract", None)
        if contract is None:
            return

        for idx, output in enumerate(getattr(contract, "required_outputs", []) or []):
            path_raw = str(output.get("path") or output.get("name") or "").strip()
            if not path_raw:
                continue

            # Contract paths may be absolute task-container paths like /app/gpt2.c
            # or workspace-relative paths like gpt2.c. Test the actual remote path.
            if path_raw.startswith("/"):
                remote_target = path_raw
                evidence_rel = path_raw
            else:
                rel = path_raw.strip("/")
                remote_target = self._remote_path(rel)
                evidence_rel = rel

            try:
                exists = await self.environment.exec(
                    command=f"test -e {shlex.quote(remote_target)}",
                    cwd=REMOTE_WORKSPACE_ROOT,
                    timeout_sec=10,
                )
            except Exception:
                continue

            if exists.return_code == 0:
                self._apply_artifact_write_evidence(
                    rel=evidence_rel,
                    receipt_ref=receipt_ref,
                )


    def _safe_job_id(self, raw: object, *, fallback: str) -> str:
        text = str(raw or fallback).strip()
        text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
        return text[:80] or fallback

    async def _action_background_job(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        args = action.args or {}
        command = str(args.get("cmd") or args.get("command") or "").strip()
        if not command:
            return ActionResult(
                action.action_id,
                action.action_type,
                "error",
                "background_job requires cmd/command.",
                failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                error="background_job requires cmd/command",
            )

        original_command = command
        command = re.sub(r"(?<![\w./-])python(?![\w.-])", "python3", command)
        self.guard.validate_command_text(command)

        job_id = self._safe_job_id(args.get("job_id") or args.get("id"), fallback=f"job_{step}_{action.action_id}")
        cwd_arg = str(args.get("cwd") or "").strip()
        cwd = self.guard.validate_cwd(self._normalize_model_path(cwd_arg) if cwd_arg else None)
        remote_cwd = self._remote_path(self._rel(cwd))
        timeout = int(args.get("timeout_seconds") or 20)

        job_dir = f"{REMOTE_WORKSPACE_ROOT}/.mlpcp_jobs/{job_id}"
        script_path = f"{job_dir}/run.sh"
        log_path = f"{job_dir}/job.log"
        pid_path = f"{job_dir}/job.pid"
        status_path = f"{job_dir}/status.txt"

        launcher = f"""
set -eu
mkdir -p {shlex.quote(job_dir)}
cat > {shlex.quote(script_path)} <<'MLPCP_JOB_SCRIPT'
#!/usr/bin/env bash
set -eo pipefail
cd {shlex.quote(remote_cwd)}
{command}
MLPCP_JOB_SCRIPT
chmod +x {shlex.quote(script_path)}
(
  {shlex.quote(script_path)}
  code=$?
  echo "$code" > {shlex.quote(status_path)}
  exit "$code"
) > {shlex.quote(log_path)} 2>&1 &
pid=$!
echo "$pid" > {shlex.quote(pid_path)}
sleep 0.5
echo "JOB_ID={job_id}"
echo "PID=$pid"
echo "PID_PATH={pid_path}"
echo "LOG_PATH={log_path}"
echo "STATUS_PATH={status_path}"
if kill -0 "$pid" 2>/dev/null; then
  echo "STATE=running"
else
  echo "STATE=exited"
fi
tail -80 {shlex.quote(log_path)} 2>/dev/null || true
"""

        cp = await self.environment.exec(command=launcher, cwd=REMOTE_WORKSPACE_ROOT, timeout_sec=timeout)
        ok = cp.return_code == 0
        summary = "background_job started." if ok else "background_job launch failed."
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="background_job",
            tool_args={
                "cmd": command,
                "original_cmd": original_command if original_command != command else None,
                "job_id": job_id,
                "cwd": remote_cwd,
                "log_path": log_path,
                "pid_path": pid_path,
                "status_path": status_path,
                "timeout_seconds": timeout,
            },
            cwd=remote_cwd,
            status="success" if ok else "fail",
            exit_code=cp.return_code,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            summary=summary,
            failure_class=FailureClass.NONE if ok else FailureClass.TOOL_EXECUTION_ERROR,
            model_visible_summary=summary,
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        return ActionResult(
            action.action_id,
            action.action_type,
            "success" if ok else "error",
            summary,
            failure_class=FailureClass.NONE if ok else FailureClass.TOOL_EXECUTION_ERROR,
            receipt_ref=receipt_ref,
            result={
                "job_id": job_id,
                "pid_path": pid_path,
                "log_path": log_path,
                "status_path": status_path,
                "stdout_excerpt": (cp.stdout or "")[-1500:],
                "stderr_excerpt": (cp.stderr or "")[-800:],
                "exit_code": cp.return_code,
            },
        )

    async def _action_monitor_job(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        args = action.args or {}
        job_id = self._safe_job_id(args.get("job_id") or args.get("id"), fallback="")
        if not job_id:
            return ActionResult(
                action.action_id,
                action.action_type,
                "error",
                "monitor_job requires job_id.",
                failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                error="monitor_job requires job_id",
            )

        job_dir = f"{REMOTE_WORKSPACE_ROOT}/.mlpcp_jobs/{job_id}"
        log_path = str(args.get("log_path") or f"{job_dir}/job.log")
        pid_path = str(args.get("pid_path") or f"{job_dir}/job.pid")
        status_path = str(args.get("status_path") or f"{job_dir}/status.txt")

        probe = f"""
set +e
echo "JOB_ID={job_id}"
echo "PID_PATH={pid_path}"
echo "LOG_PATH={log_path}"
echo "STATUS_PATH={status_path}"
pid=""
if [ -f {shlex.quote(pid_path)} ]; then
  pid="$(cat {shlex.quote(pid_path)} 2>/dev/null)"
fi
echo "PID=$pid"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "STATE=running"
else
  echo "STATE=not_running"
fi
if [ -f {shlex.quote(status_path)} ]; then
  echo "EXIT_CODE=$(cat {shlex.quote(status_path)} 2>/dev/null)"
else
  echo "EXIT_CODE=unknown"
fi
echo "--- log tail ---"
tail -120 {shlex.quote(log_path)} 2>/dev/null || true
echo "--- job files ---"
find {shlex.quote(job_dir)} -maxdepth 2 -type f -printf "%p %s bytes\\n" 2>/dev/null | sort || true
"""

        cp = await self.environment.exec(command=probe, cwd=REMOTE_WORKSPACE_ROOT, timeout_sec=20)
        summary = "monitor_job inspected background job."
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="monitor_job",
            tool_args={"job_id": job_id, "log_path": log_path, "pid_path": pid_path, "status_path": status_path},
            cwd=REMOTE_WORKSPACE_ROOT,
            status="success",
            exit_code=cp.return_code,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            summary=summary,
            failure_class=FailureClass.NONE,
            model_visible_summary=summary,
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        return ActionResult(
            action.action_id,
            action.action_type,
            "success",
            summary,
            failure_class=FailureClass.NONE,
            receipt_ref=receipt_ref,
            result={
                "job_id": job_id,
                "stdout_excerpt": (cp.stdout or "")[-2500:],
                "stderr_excerpt": (cp.stderr or "")[-800:],
                "exit_code": cp.return_code,
            },
        )

    async def _action_service_probe_loop(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        args = action.args or {}
        command = str(args.get("cmd") or args.get("command") or "").strip()
        if not command:
            return ActionResult(
                action.action_id,
                action.action_type,
                "error",
                "service_probe_loop requires cmd/command.",
                failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                error="service_probe_loop requires cmd/command",
            )

        self.guard.validate_command_text(command)
        attempts = max(1, min(int(args.get("attempts") or 8), 60))
        interval = max(0, min(int(args.get("interval_seconds") or 2), 30))
        success_pattern = str(args.get("success_pattern") or "").strip()
        cwd_arg = str(args.get("cwd") or "").strip()
        cwd = self.guard.validate_cwd(self._normalize_model_path(cwd_arg) if cwd_arg else None)
        remote_cwd = self._remote_path(self._rel(cwd))
        timeout = max(10, attempts * (interval + 8))

        loop_cmd = f"""
set +e
for i in $(seq 1 {attempts}); do
  echo "=== probe_attempt:$i ==="
  out="$( ( {command} ) 2>&1 )"
  code=$?
  printf '%s\\n' "$out"
  echo "exit_code=$code"
  if [ -n {shlex.quote(success_pattern)} ]; then
    printf '%s\\n' "$out" | grep -F {shlex.quote(success_pattern)} >/dev/null 2>&1 && exit 0
  else
    [ "$code" -eq 0 ] && exit 0
  fi
  sleep {interval}
done
exit 1
"""

        cp = await self.environment.exec(command=loop_cmd, cwd=remote_cwd, timeout_sec=timeout)
        passed = cp.return_code == 0
        summary = "service_probe_loop passed." if passed else "service_probe_loop failed."
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="service_probe_loop",
            tool_args={
                "cmd": command,
                "attempts": attempts,
                "interval_seconds": interval,
                "success_pattern": success_pattern,
                "cwd": remote_cwd,
            },
            cwd=remote_cwd,
            status="success" if passed else "fail",
            exit_code=cp.return_code,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            summary=summary,
            failure_class=FailureClass.NONE if passed else FailureClass.SERVICE_NOT_READY,
            model_visible_summary=summary,
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        return ActionResult(
            action.action_id,
            action.action_type,
            "success" if passed else "blocked",
            summary,
            failure_class=FailureClass.NONE if passed else FailureClass.SERVICE_NOT_READY,
            receipt_ref=receipt_ref,
            result={
                "passed": passed,
                "stdout_excerpt": (cp.stdout or "")[-3000:],
                "stderr_excerpt": (cp.stderr or "")[-1000:],
                "exit_code": cp.return_code,
            },
        )

    async def _action_run_verifier(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        command = str(action.args.get("cmd") or action.args.get("command") or "")
        if not command:
            return ActionResult(
                action.action_id,
                action.action_type,
                "blocked",
                "Verifier command missing; request a concrete verifier command before retrying.",
                failure_class=FailureClass.TOOL_EXECUTION_ERROR,
                result={"passed": False, "safe_summary": "Verifier command missing."},
            )
        self.guard.validate_command_text(command)
        cwd = self.guard.validate_cwd(self._normalize_model_path(str(action.args.get("cwd") or "")) if action.args.get("cwd") else None)
        timeout = int(action.args.get("timeout_seconds") or (self.execute_policy or ExecutePlanPolicy()).raw_bash_timeout_seconds)
        remote_cwd = self._remote_path(self._rel(cwd))
        cp = await self.environment.exec(command=command, cwd=remote_cwd, timeout_sec=timeout)
        passed = cp.return_code == 0
        failure_class = FailureClass.NONE if passed else FailureClass.VERIFIER_FAILED
        summary = "Verifier passed." if passed else "Verifier failed."
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="run_verifier",
            tool_args={"command": command, "timeout_seconds": timeout},
            cwd=remote_cwd,
            status="success" if passed else "fail",
            exit_code=cp.return_code,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
            summary=summary,
            failure_class=failure_class,
            model_visible_summary=summary,
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        self._apply_capability_if_requested(action, passed=passed, receipt_ref=receipt_ref, summary=summary, failure_class=failure_class)
        self._apply_required_verifier_evidence(
            command=command,
            passed=passed,
            receipt_ref=receipt_ref,
            summary=summary,
            failure_class=failure_class,
        )
        safe_summary = "Verifier passed." if passed else "Verifier failed. See receipt ref for safe output retrieval."
        return ActionResult(action.action_id, action.action_type, "success" if passed else "blocked", safe_summary, failure_class=failure_class, receipt_ref=receipt_ref, result={"passed": passed, "safe_summary": safe_summary})

    def _normalize_verifier_command_for_match(self, command: str) -> str:
        text = str(command or "").strip().strip("`").strip()
        # Collapse shell whitespace and remove harmless wrapping quotes/backticks.
        text = " ".join(text.replace("\\\n", " ").split())
        return text


    def _verifier_commands_match(self, observed: str, expected: str) -> bool:
        obs = self._normalize_verifier_command_for_match(observed)
        exp = self._normalize_verifier_command_for_match(expected)
        if not obs or not exp:
            return False
        if obs == exp:
            return True
        # A model may run the required verifier plus extra smoke-test commands.
        if exp in obs:
            return True
        return False


    def _apply_required_verifier_evidence(
        self,
        *,
        command: str,
        passed: bool,
        receipt_ref,
        summary: str,
        failure_class: FailureClass,
    ) -> None:
        graph = getattr(self.session, "capability_graph", None)
        contract = getattr(self.session, "success_contract", None)
        if graph is None or contract is None or receipt_ref is None:
            return

        verifiers = list(getattr(contract, "required_verifiers", []) or [])
        if not verifiers:
            return

        matches: list[dict] = []
        for verifier in verifiers:
            expected = str(verifier.get("command") or verifier.get("cmd") or "").strip()
            if self._verifier_commands_match(command, expected):
                matches.append(verifier)

        # If there is exactly one required verifier, a run_verifier action is
        # almost certainly intended to satisfy it even if the model omitted the
        # check id or used equivalent command formatting.
        if not matches and len(verifiers) == 1:
            matches = verifiers

        for verifier in matches:
            name = str(verifier.get("name") or verifier.get("id") or "model_visible_verifier").strip()
            check_id = str(verifier.get("check_id") or f"verifier:{name}:run")
            try:
                graph.apply_measured_check(
                    check_id=check_id,
                    passed=passed,
                    receipt_ref=receipt_ref,
                    summary=summary,
                    failure_class=FailureClass.NONE if passed else failure_class,
                )
            except Exception:
                pass


    async def _action_probe_service(self, action: ExecutePlanAction, *, step: int) -> ActionResult:
        request_data = dict(action.args.get("request") or action.args)
        check_id = request_data.get("capability_check_id") or action.args.get("capability_check_id")
        service_name = str(request_data.get("service_name") or "service")
        checks = list(request_data.get("checks") or [])
        if not checks:
            raise ValueError("probe_service requires checks")
        outcomes: list[dict[str, Any]] = []
        blocker_summary = ""
        blocker_failure = FailureClass.NONE
        all_passed = True
        remote_cwd = self._remote_path(self._rel(self.guard.validate_cwd(self._normalize_model_path(str(action.args.get("cwd") or "")) if action.args.get("cwd") else None)))
        for check in checks:
            outcome = await self._run_probe_check(check, remote_cwd=remote_cwd)
            outcomes.append(outcome)
            if outcome["status"] != "pass" and not blocker_summary:
                blocker_summary = outcome["evidence"]
                blocker_failure = outcome["failure_class"]
            all_passed = all_passed and outcome["status"] == "pass"
        receipt = self.session.receipt_store.create_receipt(
            receipt_id=self._receipt_id(action, step),
            run_id=self.run_id,
            row_id=self.row_id,
            step=step,
            tool_name="probe_service",
            tool_args={"service_name": service_name, "checks": checks},
            cwd=remote_cwd,
            status="success" if all_passed else "fail",
            exit_code=0 if all_passed else 1,
            stdout=json.dumps(outcomes, indent=2, sort_keys=True),
            stderr="",
            summary=f"{service_name} probe {'passed' if all_passed else 'failed'}.",
            service_refs=[Reference(ref_type="service", ref_id=service_name, summary=f"Service {service_name}")],
            failure_class=FailureClass.NONE if all_passed else blocker_failure,
            model_visible_summary=f"{service_name} probe {'passed' if all_passed else 'failed'}.",
        )
        receipt_ref = self.session.receipt_store.receipt_ref(receipt)
        if check_id and self.session.capability_graph is not None:
            self.session.capability_graph.apply_measured_check(
                check_id=str(check_id),
                passed=all_passed,
                receipt_ref=receipt_ref,
                summary="All required service checks passed." if all_passed else blocker_summary,
                failure_class=FailureClass.NONE if all_passed else blocker_failure,
            )
        status = "success" if all_passed else "blocked"
        return ActionResult(action.action_id, action.action_type, status, f"Probe {service_name}: {'READY' if all_passed else 'NOT_READY'}.", failure_class=FailureClass.NONE if all_passed else blocker_failure, receipt_ref=receipt_ref, result={"checks": outcomes})

    def _action_receipt_records_for_search(self) -> list[dict[str, Any]]:
        receipts_dir = self.receipt_root / "receipts"
        records: list[dict[str, Any]] = []

        def _short(value: object, n: int = 1000) -> str:
            text = "" if value is None else str(value)
            return text if len(text) <= n else text[: n // 2] + "\n...[truncated]...\n" + text[-n // 2 :]

        if not receipts_dir.exists():
            return records

        for rp in sorted(receipts_dir.glob("*.json")):
            try:
                obj = json.loads(rp.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue

            tool = str(obj.get("tool_name") or obj.get("tool") or "").strip()
            if not tool:
                continue

            rid = str(obj.get("receipt_id") or obj.get("id") or rp.stem)
            summary = str(obj.get("summary") or obj.get("model_visible_summary") or "")
            args = obj.get("tool_args") or obj.get("args") or {}
            stdout = str(obj.get("stdout") or "")
            stderr = str(obj.get("stderr") or "")

            raw_dir = self.receipt_root / "raw" / rp.stem
            if raw_dir.exists():
                try:
                    raw_stdout = (raw_dir / "stdout").read_text(encoding="utf-8", errors="replace")
                    if raw_stdout:
                        stdout = raw_stdout
                except Exception:
                    pass
                try:
                    raw_stderr = (raw_dir / "stderr").read_text(encoding="utf-8", errors="replace")
                    if raw_stderr:
                        stderr = raw_stderr
                except Exception:
                    pass

            search_text = json.dumps(
                {
                    "receipt_id": rid,
                    "tool": tool,
                    "summary": summary,
                    "args": args,
                    "stdout": stdout[:4000],
                    "stderr": stderr[:2000],
                },
                sort_keys=True,
                default=str,
            ).lower()

            records.append({
                "receipt_id": rid,
                "path": str(rp),
                "rel": str(rp.relative_to(self.receipt_root)),
                "tool": tool,
                "summary": _short(summary, 400),
                "args": args,
                "stdout_excerpt": _short(stdout, 900),
                "stderr_excerpt": _short(stderr, 500),
                "search_text": search_text,
                "object": obj,
            })

        return records

    def _action_view_receipt(self, action: ExecutePlanAction) -> ActionResult:
        rid = str(
            action.args.get("receipt_id")
            or action.args.get("ref_id")
            or action.args.get("id")
            or action.args.get("receipt")
            or ""
        ).strip()
        if not rid:
            raise ValueError("view_receipt requires receipt_id/ref_id")

        key = rid.removeprefix("receipt:")
        records = self._action_receipt_records_for_search()
        for rec in records:
            candidates = {
                rec["receipt_id"],
                "receipt:" + rec["receipt_id"],
                Path(rec["path"]).name,
                Path(rec["path"]).stem,
                rec["rel"],
                "receipt:" + rec["rel"],
            }
            if rid in candidates or key in candidates:
                payload = {
                    "receipt_id": rec["receipt_id"],
                    "tool": rec["tool"],
                    "summary": rec["summary"],
                    "args": rec["args"],
                    "stdout_excerpt": rec["stdout_excerpt"],
                    "stderr_excerpt": rec["stderr_excerpt"],
                    "path": rec["rel"],
                }
                return ActionResult(
                    action.action_id,
                    action.action_type,
                    "success",
                    f"Viewed receipt {rec['receipt_id']}.",
                    result=payload,
                )

        return ActionResult(
            action.action_id,
            action.action_type,
            "blocked",
            f"Receipt not found: {rid}",
            failure_class=FailureClass.MEMORY_RETRIEVAL_FAILED,
            result={"receipt_id": rid, "available": [r["receipt_id"] for r in records[-12:]]},
        )

    def _action_search_receipts(self, action: ExecutePlanAction) -> ActionResult:
        query = str(action.args.get("query") or action.args.get("q") or "").strip().lower()
        limit = int(action.args.get("limit") or action.args.get("max_results") or 8)
        limit = max(1, min(limit, 20))

        records = self._action_receipt_records_for_search()
        terms = [t for t in re.findall(r"[a-zA-Z0-9_.:/-]+", query) if len(t) >= 2]

        scored: list[tuple[int, dict[str, Any]]] = []
        for rec in records:
            text = rec.get("search_text") or ""
            if not terms:
                score = 1
            else:
                score = sum(1 for t in terms if t in text)
            if score > 0:
                scored.append((score, rec))

        scored.sort(key=lambda x: (x[0], x[1].get("receipt_id", "")), reverse=True)
        selected = [rec for _score, rec in scored[:limit]]

        refs = [
            Reference(
                ref_type="receipt",
                ref_id=str(rec["receipt_id"]),
                summary=f"{rec.get('tool')}: {rec.get('summary')}",
            ).to_dict()
            for rec in selected
        ]

        safe_matches = [
            {
                "receipt_id": rec["receipt_id"],
                "tool": rec["tool"],
                "summary": rec["summary"],
                "args": rec["args"],
                "stdout_excerpt": rec["stdout_excerpt"],
                "stderr_excerpt": rec["stderr_excerpt"],
            }
            for rec in selected
        ]

        return ActionResult(
            action.action_id,
            action.action_type,
            "success",
            f"Found {len(refs)} receipt refs.",
            result={"refs": refs, "matches": safe_matches, "query": query},
        )


    def _action_view_file_cache(self, action: ExecutePlanAction) -> ActionResult:
        path = str(action.args.get("path") or "")
        if not path:
            raise ValueError("view_file_cache requires path")
        normalized = self._normalize_model_path(path)
        self.guard.validate_read_path(normalized)
        cache = self.session.memory_store.view_file_cache(normalized, start_line=action.args.get("start_line"), end_line=action.args.get("end_line"))
        return ActionResult(action.action_id, action.action_type, "success", f"Viewed file cache {path}.", result=cache)

    def _action_finalize(self, action: ExecutePlanAction) -> ActionResult:
        status = str(action.args.get("status") or action.args.get("result") or "").strip().lower()
        if status in {"cannot_complete", "can't_complete", "incomplete", "give_up", "giveup", "blocked"}:
            summary = (
                "finalize with cannot_complete/incomplete is not allowed while visible requirements remain satisfiable from the available environment. "
                "Continue repairing: create or strengthen self-checks, replace invalid artifacts, run tests, "
                "and only finalize when the success contract is satisfied."
            )
            return ActionResult(
                action.action_id,
                action.action_type,
                "blocked",
                summary,
                failure_class=FailureClass.ARTIFACT_INVALID,
                result={
                    "unsupported_finalize_status": status,
                    "required_next_step": "continue_repair",
                },
            )

        self._measure_required_outputs_from_receipts()
        decision = self._evaluate_finalization(force_finalize=bool(action.args.get("force", False)))
        return ActionResult(action.action_id, action.action_type, "success" if decision.allowed else "blocked", decision.summary, failure_class=decision.failure_class, result=decision)

    def _measure_required_outputs_from_receipts(self) -> None:
        graph = getattr(self.session, "capability_graph", None)
        contract = getattr(self.session, "success_contract", None)
        if graph is None or contract is None:
            return

        try:
            refs = self.session.memory_store.search_receipts(query=None, limit=50)
        except Exception:
            refs = []

        for idx, output in enumerate(getattr(contract, "required_outputs", []) or []):
            if output.get("required", True) is False:
                continue
            path = str(output.get("path") or output.get("name") or f"output_{idx}").strip()
            if not path:
                continue

            requirement_id = output.get("requirement_id") or f"artifact:{path.rstrip('/')}"
            check_id = output.get("check_id") or f"{requirement_id}:exists"

            matched_ref = None
            for ref in refs[:50]:
                try:
                    ref_id = getattr(ref, "ref_id", None) or ref.get("ref_id")
                    view = self.session.memory_store.view_receipt(ref_id, summary_only=False)
                    text = json.dumps(view.to_dict() if hasattr(view, "to_dict") else view)
                except Exception:
                    continue
                path_variants = {
                    path,
                    path.rstrip("/"),
                    path.lstrip("/"),
                    path.rstrip("/").lstrip("/"),
                    path.replace("/", "_").replace(".", "_").replace("-", "_").strip("_"),
                    path.rstrip("/").replace("/", "_").replace(".", "_").replace("-", "_").strip("_"),
                }
                if any(v and v in text for v in path_variants):
                    matched_ref = ref
                    break

            if matched_ref is not None:
                try:
                    graph.apply_measured_check(
                        check_id=check_id,
                        passed=True,
                        receipt_ref=matched_ref,
                        summary=f"Required artifact observed in Harbor receipt: {path}",
                        failure_class=FailureClass.NONE,
                    )
                except Exception:
                    pass

    def _evaluate_finalization(self, *, force_finalize: bool = False) -> FinalizationDecision:
        conditions = capability_conditions(self.session.capability_graph) if self.session.capability_graph is not None else None
        obligations = self.session.capability_graph.obligations() if self.session.capability_graph is not None else []
        return self.finalization_gate.evaluate(open_obligations=obligations, conditions_met=conditions, force_finalize=force_finalize)

    async def _run_probe_check(self, check: dict[str, Any], *, remote_cwd: str) -> dict[str, Any]:
        check_type = str(check.get("type") or check.get("check_type") or "custom_command")
        timeout = int(check.get("timeout_seconds") or 15)
        if check_type == "custom_command":
            command = str(check.get("command") or check.get("cmd") or "")
        elif check_type == "process_pattern":
            pattern = str(check.get("pattern") or check.get("expected_text") or "")
            command = f"ps -eo pid=,comm=,args= | grep -F -- {shlex.quote(pattern)} | grep -v grep"
        elif check_type == "tcp_port":
            host = str(check.get("host") or "127.0.0.1")
            port = str(check.get("port") or "")
            command = f"sh -lc 'command -v nc >/dev/null 2>&1 && nc -z {shlex.quote(host)} {shlex.quote(port)}'"
        elif check_type == "http":
            url = str(check.get("url") or f"http://{check.get('host') or '127.0.0.1'}:{check.get('port')}{check.get('path') or '/'}")
            command = f"sh -lc 'command -v curl >/dev/null 2>&1 && curl -fsS {shlex.quote(url)}'"
        elif check_type == "log_tail":
            path = str(check.get("path") or "")
            lines = int(check.get("lines") or 40)
            command = f"tail -n {lines} {shlex.quote(path)}"
        else:
            command = str(check.get("command") or check.get("cmd") or "")
        cp = await self.environment.exec(command=command, cwd=remote_cwd, timeout_sec=timeout)
        passed = cp.return_code == 0
        failure_class = FailureClass.NONE if passed else (
            FailureClass.SERVICE_PORT_CLOSED if check_type == "tcp_port" else
            FailureClass.SERVICE_PROTOCOL_FAILED if check_type == "http" else
            FailureClass.SERVICE_PROCESS_MISSING if check_type == "process_pattern" else
            FailureClass.SERVICE_LOG_ERROR if check_type == "log_tail" else
            FailureClass.SERVICE_PROBE_FAILED
        )
        evidence = f"{check_type} passed" if passed else (cp.stderr or cp.stdout or f"{check_type} failed")
        return {
            "type": check_type,
            "status": "pass" if passed else "fail",
            "evidence": evidence[:500],
            "failure_class": failure_class,
            "stdout": cp.stdout or "",
            "stderr": cp.stderr or "",
        }

    async def _remote_context(self) -> dict[str, Any]:
        return await build_remote_context(self.environment, REMOTE_WORKSPACE_ROOT)

    def _apply_capability_if_requested(
        self,
        action: ExecutePlanAction,
        *,
        passed: bool,
        receipt_ref: Reference,
        summary: str,
        failure_class: FailureClass | str = FailureClass.NONE,
    ) -> None:
        check_id = action.args.get("capability_check_id") or action.args.get("check_id")
        if check_id and self.session.capability_graph is not None:
            self.session.capability_graph.apply_measured_check(
                check_id=str(check_id),
                passed=passed,
                receipt_ref=receipt_ref,
                summary=summary,
                failure_class=failure_class,
            )

    def _receipt_id(self, action: ExecutePlanAction, step: int) -> str:
        safe_action = re.sub(r"[^a-zA-Z0-9_.-]+", "_", action.action_id)[:80] or "action"
        return f"{step:04d}_{safe_action}_{action.action_type}"

    def _rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.workspace_root)).replace("\\", "/") or "."
        except ValueError:
            return str(path)

    def _remote_path(self, rel: str) -> str:
        rel_value = rel.strip().lstrip("/")
        if not rel_value or rel_value == ".":
            return REMOTE_WORKSPACE_ROOT
        return f"{REMOTE_WORKSPACE_ROOT}/{rel_value}"

    def _remote_parent(self, rel: str) -> str:
        if "/" not in rel:
            return REMOTE_WORKSPACE_ROOT
        return self._remote_path(rel.rsplit("/", 1)[0])

    def _normalize_model_path(self, value: str) -> str:
        text = value.strip()
        if text == REMOTE_WORKSPACE_ROOT:
            return "."
        if text.startswith(f"{REMOTE_WORKSPACE_ROOT}/"):
            return text[len(f"{REMOTE_WORKSPACE_ROOT}/") :]
        return text


__all__ = ["HarborHostRunner"]
