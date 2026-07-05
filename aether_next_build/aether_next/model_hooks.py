"""Model-reasoning layer: provider-agnostic LLM hooks for Aether-Next."""
from __future__ import annotations

import json
import os
import re
from dataclasses import fields as dc_fields
from typing import Any, Mapping, Protocol, runtime_checkable

from .ledger import ExecutionLedger
from .runtime_ir import (
    ACTION_SCHEMA,
    MODEL_TIERS,
    WORKFLOW_MODES,
    ActionRequest,
    BootstrapPolicy,
    CompletionPolicy,
    CompiledRuntime,
    ContextPolicy,
    HelperToolPolicy,
    ProcessPolicy,
    ReconfigurePolicy,
    RefusalPolicy,
    RuntimeConfigIR,
    SolverTurn,
    WorkflowPolicy,
)
from .model_prompts import (
    ARCHITECT_SYSTEM_PROMPT,
    DEFAULT_VERIFIER_IDENTITY_PROMPT,
    VERIFIER_RUNTIME_CONTRACT,
)
from .verifier import parse_model_verifier_result
from .verifier_inspector import VerifierInspectionRequest, parse_verifier_inspection_requests



@runtime_checkable
class ModelCallable(Protocol):
    def __call__(self, messages: list[dict[str, str]], *, max_output_tokens: int = 8000) -> str: ...


class ModelOutputError(Exception):
    """Raised when model output cannot be parsed into the expected IR."""

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?", re.IGNORECASE)


def _extract_json_object(text: str) -> str:
    """First balanced ``{...}`` from *text*; tolerates fences and prose."""
    cleaned = _FENCE_RE.sub("", text)
    start = cleaned.find("{")
    if start == -1:
        raise ModelOutputError("no JSON object found in model output")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : i + 1]
    raise ModelOutputError("unbalanced braces in model output")



def _accepted_fields(cls: type) -> set[str]:
    return {f.name for f in dc_fields(cls)}


def _coerce_tuple(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    return ()


def _build_frozen(cls: type, raw: Mapping[str, Any]) -> Any:
    accepted = _accepted_fields(cls)
    kwargs: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in accepted:
            continue
        field_obj = next(f for f in dc_fields(cls) if f.name == key)
        if field_obj.type in ("tuple[str, ...]", "tuple[str, ...] | None"):
            value = _coerce_tuple(value)
        kwargs[key] = value
    return cls(**kwargs)

_POLICY_MAP: dict[str, type] = {
    "context_policy": ContextPolicy,
    "process_policy": ProcessPolicy,
    "helper_tool_policy": HelperToolPolicy,
    "bootstrap_policy": BootstrapPolicy,
    "completion_policy": CompletionPolicy,
    "refusal_policy": RefusalPolicy,
    "reconfigure_policy": ReconfigurePolicy,
    "workflow_policy": WorkflowPolicy,
}


def parse_runtime_config_ir(text: str, *, capability_index: Any = None) -> RuntimeConfigIR:
    """Parse raw model text into a ``RuntimeConfigIR``."""
    raw_json = _extract_json_object(text)
    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ModelOutputError("expected a JSON object at top level")

    # Required scalars
    if "architect_summary" not in data:
        raise ModelOutputError("missing required field: architect_summary")
    if "solver_identity_prompt" not in data:
        raise ModelOutputError("missing required field: solver_identity_prompt")

    accepted = _accepted_fields(RuntimeConfigIR)
    kwargs: dict[str, Any] = {}

    for key, value in data.items():
        if key not in accepted:
            continue
        # Policy sub-objects
        if key in _POLICY_MAP and isinstance(value, dict):
            kwargs[key] = _build_frozen(_POLICY_MAP[key], value)
            continue
        # Tuple fields
        field_obj = next((f for f in dc_fields(RuntimeConfigIR) if f.name == key), None)
        if field_obj is not None and "tuple" in str(field_obj.type):
            kwargs[key] = _coerce_tuple(value)
            continue
        kwargs[key] = value

    # selected_capabilities must be a tuple of strings
    if "selected_capabilities" in kwargs:
        kwargs["selected_capabilities"] = tuple(
            str(cap_id) for cap_id in kwargs["selected_capabilities"]
        )
    else:
        kwargs["selected_capabilities"] = ()

    return RuntimeConfigIR(**kwargs)


def parse_solver_turn(text: str) -> SolverTurn:
    """Parse raw model text into a ``SolverTurn``."""
    raw_json = _extract_json_object(text)
    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ModelOutputError("expected a JSON object at top level")

    kind = str(data.get("kind", "")).strip()
    raw_actions = data.get("actions", ()) or ()
    if not kind:
        # A turn that carries actions IS an act turn; do not burn a retry on
        # a missing label the payload already implies.  A turn with neither
        # kind nor actions stays a hard error -- submission is never inferred.
        if isinstance(raw_actions, (list, tuple)) and len(raw_actions) > 0:
            kind = "act"
        else:
            raise ModelOutputError("missing required field: kind")

    summary = str(data.get("summary", "")).strip() or f"({kind} turn without summary)"

    actions: list[ActionRequest] = []
    action_accepted = _accepted_fields(ActionRequest)
    for action_index, raw_action in enumerate(raw_actions):
        if not isinstance(raw_action, dict):
            continue
        action_kwargs: dict[str, Any] = {}
        for akey, aval in raw_action.items():
            if akey not in action_accepted:
                continue
            if akey == "arguments" and isinstance(aval, dict):
                action_kwargs[akey] = dict(aval)
            else:
                action_kwargs[akey] = aval
        # Ensure required fields have defaults so construction does not crash
        action_kwargs.setdefault("action_id", f"a-{action_index}")
        if not str(action_kwargs.get("action_id", "")).strip():
            action_kwargs["action_id"] = f"a-{action_index}"
        action_kwargs.setdefault("kind", "")
        action_kwargs.setdefault("capability_id", "")
        action_kwargs.setdefault("arguments", {})
        action_kwargs.setdefault("intent", "")
        action_kwargs.setdefault("expected_observation", "")
        action_kwargs.setdefault("if_fail_next", "")
        actions.append(ActionRequest(**action_kwargs))

    turn_kwargs: dict[str, Any] = {
        "kind": kind,
        "summary": summary,
        "actions": tuple(actions),
    }
    for optional_key in ("requested_check_ids", "claimed_artifacts"):
        if optional_key in data:
            turn_kwargs[optional_key] = _coerce_tuple(data[optional_key])

    return SolverTurn(**turn_kwargs)

def _verifier_identity_prompt_for(compiled: CompiledRuntime) -> str:
    prompt = str(getattr(compiled, "verifier_identity_prompt", "") or "").strip()
    if prompt:
        return prompt
    raise ModelOutputError("architect-authored verifier prompt is required")


def _verifier_max_output_tokens() -> int:
    return int(os.environ.get("AETHER_VERIFIER_MAX_OUTPUT_TOKENS", "6000"))


def _structured_missing_evidence_requests(raw: str) -> tuple[VerifierInspectionRequest, ...]:
    text = str(raw or "").strip()
    decoder = json.JSONDecoder()
    data: Any = None
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            data, _end = decoder.raw_decode(text[idx:])
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(data, Mapping):
        return ()
    raw_requests = data.get("missing_evidence_requests")
    if not isinstance(raw_requests, list) or not any(isinstance(item, Mapping) for item in raw_requests):
        return ()
    request_items = [dict(item) for item in raw_requests if isinstance(item, Mapping)]
    return parse_verifier_inspection_requests({"kind": "inspect", "requests": request_items})


def _default_completion_inspection_requests(packet: Mapping[str, Any]) -> tuple[VerifierInspectionRequest, ...]:
    """Minimal generic read-only evidence when a verifier completes uninspected.

    This does not decide task state. It gives the verifier current-state
    observations it failed to ask for itself, then asks the verifier to judge.
    """
    requests: list[VerifierInspectionRequest] = []
    artifact_paths: list[str] = []
    raw_state_paths: list[str] = []
    for key in ("artifacts_present",):
        raw = packet.get(key, ())
        if isinstance(raw, (list, tuple)):
            artifact_paths.extend(str(item).strip() for item in raw if str(item).strip())
    artifact_evidence = packet.get("artifact_evidence", ())
    if isinstance(artifact_evidence, (list, tuple)):
        for item in artifact_evidence:
            if isinstance(item, Mapping):
                path = str(item.get("path", "") or item.get("artifact_path", "")).strip()
                if path:
                    artifact_paths.append(path)

    latest_file_reads = packet.get("latest_file_reads", ())
    if isinstance(latest_file_reads, (list, tuple)):
        for item in latest_file_reads:
            if isinstance(item, Mapping):
                path = str(item.get("path", "")).strip()
                if path:
                    raw_state_paths.append(path)
    raw_state_candidates = packet.get("raw_state_candidates", ())
    if isinstance(raw_state_candidates, (list, tuple)):
        for item in raw_state_candidates:
            if isinstance(item, Mapping):
                path = str(item.get("path", "")).strip()
                if path:
                    raw_state_paths.append(path)

    def _dedupe(paths: list[str], *, seen: set[str] | None = None) -> list[str]:
        local_seen = seen if seen is not None else set()
        deduped: list[str] = []
        for path in paths:
            if path in local_seen:
                continue
            local_seen.add(path)
            deduped.append(path)
        return deduped

    seen_paths: set[str] = set()
    deduped_artifacts = _dedupe(artifact_paths, seen=seen_paths)
    deduped_raw_state = _dedupe(raw_state_paths, seen=seen_paths)

    for idx, path in enumerate(deduped_artifacts[:1]):
        requests.append(VerifierInspectionRequest(
            request_id=f"auto-read-artifact-{idx}",
            kind="read_file",
            path=path,
            limit=1,
        ))
    for idx, path in enumerate(deduped_raw_state[:1]):
        requests.append(VerifierInspectionRequest(
            request_id=f"auto-read-raw-state-{idx}",
            kind="read_file",
            path=path,
            limit=1,
        ))
    if len(requests) < 3:
        requests.append(VerifierInspectionRequest(
            request_id="auto-recent-receipts",
            kind="inspect_recent_receipts",
            limit=8,
        ))
    if len(requests) < 3 and deduped_artifacts:
        requests.append(VerifierInspectionRequest(
            request_id="auto-artifact-history",
            kind="inspect_artifact_history",
            path=deduped_artifacts[0],
            limit=8,
        ))
    return tuple(requests[:3])


class ModelHooks:
    """``KernelHooks`` backed by ``ModelCallable`` functions."""

    def __init__(
        self,
        architect_model: ModelCallable,
        solver_model: ModelCallable,
        verifier_model: ModelCallable | None = None,
        vision_model: Any | None = None,
    ) -> None:
        self._architect = architect_model
        self._solver = solver_model
        self._verifier = verifier_model or architect_model
        self.last_parse_errors: list[str] = []
        if vision_model is not None:
            # Exposed only when a vision route exists so the perception lane
            # can detect availability with a plain getattr -- absence stays an
            # honest capability gap, never a fake success.
            self._vision = vision_model

            def perceive_image(prompt: str, image_b64: str, media_type: str) -> str:
                return str(self._vision(prompt, image_b64, media_type))

            self.perceive_image = perceive_image

    def architect(self, request: Mapping[str, Any]) -> RuntimeConfigIR:
        self.last_parse_errors = []
        messages = [
            {"role": "system", "content": ARCHITECT_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, default=str)},
        ]
        try:
            raw = self._architect(messages, max_output_tokens=8000)
            cap_index = request.get("capability_index", [])
            return parse_runtime_config_ir(raw, capability_index=cap_index)
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            raise ModelOutputError(f"architect output could not be parsed: {exc}") from exc

    def solve(
        self,
        messages: list[dict[str, str]],
        compiled: CompiledRuntime,
    ) -> SolverTurn:
        """Return a parsed solver turn, or fail loudly.

        Solver parse/validation errors must never be converted into a
        fabricated turn.  The kernel owns parse-error receipts and same-step
        retry so the solver sees the exact failure and raw malformed output is
        preserved for audit.
        """
        self.last_parse_errors = []
        raw = ""
        try:
            raw = self._solver(list(messages), max_output_tokens=16000)
            turn = parse_solver_turn(raw)
            errors = turn.validate(compiled.action_schema)
            if not errors:
                return turn
            message = f"parsed turn failed validation: {errors}"
            self.last_parse_errors.append(message)
            raise ModelOutputError(message)
        except ModelOutputError as exc:
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver output could not be parsed: {exc}") from exc
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            setattr(self, "last_raw_solver_output", raw)
            raise ModelOutputError(f"solver call failed: {exc}") from exc

    def verify(
        self,
        packet: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
    ) -> str:
        self.last_parse_errors = []
        user_payload = {
            "verifier_runtime_contract": VERIFIER_RUNTIME_CONTRACT,
            "verifier_packet": dict(packet),
            "compiled_summary": compiled.task_prompt[:500],
            "ledger_receipt_count": len(ledger.all_receipts()),
        }
        messages = [
            {
                "role": "system",
                "content": _verifier_identity_prompt_for(compiled),
            },
            {"role": "user", "content": json.dumps(user_payload, default=str, sort_keys=True)},
        ]
        try:
            return self._verifier(messages, max_output_tokens=_verifier_max_output_tokens())
        except Exception as exc:
            self.last_parse_errors.append(str(exc))
            raise

    def verify_with_inspector(
        self,
        packet: Mapping[str, Any],
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        inspector,
    ) -> str:
        self.last_parse_errors = []
        user_payload = {
            "verifier_runtime_contract": VERIFIER_RUNTIME_CONTRACT,
            "verifier_packet": dict(packet),
            "compiled_summary": compiled.task_prompt[:500],
            "ledger_receipt_count": len(ledger.all_receipts()),
        }
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": _verifier_identity_prompt_for(compiled),
            },
            {"role": "user", "content": json.dumps(user_payload, default=str, sort_keys=True)},
        ]
        max_rounds = int(VERIFIER_RUNTIME_CONTRACT["read_only_inspector"]["max_rounds"])
        inspected = False
        for round_idx in range(max_rounds + 1):
            try:
                raw = self._verifier(messages, max_output_tokens=_verifier_max_output_tokens())
                setattr(self, "last_raw_verifier_output", raw)
            except Exception as exc:
                self.last_parse_errors.append(str(exc))
                raise
            try:
                result = parse_model_verifier_result(raw)
            except Exception as verdict_exc:
                try:
                    requests = parse_verifier_inspection_requests(raw)
                except Exception as inspection_exc:
                    self.last_parse_errors.append(f"{verdict_exc}; {inspection_exc}")
                    if round_idx < max_rounds:
                        messages.append({"role": "assistant", "content": raw})
                        messages.append({
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "instruction": (
                                        "Your previous verifier message was not valid protocol JSON. "
                                        "Return exactly one JSON object and no prose. The object must "
                                        "be either a final verifier verdict with fields verdict, "
                                        "confidence, and summary, or an inspection request with "
                                        "kind='inspect' and a non-empty requests list."
                                    ),
                                },
                                default=str,
                                sort_keys=True,
                            ),
                        })
                        continue
                    raise
                results = inspector(requests)
                inspected = True
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "verifier_inspection_results": results,
                            "instruction": "Use these observations together with the original verifier_packet and return either a final verdict or another bounded inspection request.",
                        },
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
            # Runtime-enforced, not prompt-only: a completed verdict must be
            # backed by at least one real independent inspection when the
            # inspector is available -- a model that judges "completed"
            # straight from the packet's narrative is exactly the false-clean
            # failure mode this mechanism exists to close. Force one more
            # round requiring inspection rather than trusting the prompt alone.
            if result.verdict == "completed" and not inspected and round_idx < max_rounds:
                auto_requests = _default_completion_inspection_requests(packet)
                if auto_requests:
                    results = inspector(auto_requests)
                    inspected = True
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": json.dumps(
                            {
                                "verifier_inspection_results": results,
                                "instruction": (
                                "The runtime supplied a minimal read-only current-state "
                                "inspection because completed cannot be accepted from "
                                "packet evidence alone. Use these observations together "
                                "with the original verifier_packet and return your final "
                                "verdict. Treat solver-authored validation commands and "
                                "recomputation receipts as claims to audit, not as proof; "
                                "inspect whether their method matches the task semantics "
                                "before returning completed."
                            ),
                        },
                            default=str,
                            sort_keys=True,
                        ),
                    })
                    continue
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": (
                                "Protocol requires at least one read-only inspection before a "
                                "completed verdict can be accepted. Submit a bounded inspection "
                                "request (kind: inspect) that independently confirms the claim "
                                "your verdict depends on, then return your verdict."
                            ),
                        },
                        default=str,
                        sort_keys=True,
                    ),
                })
                continue
            if result.verdict == "uncertain_missing_evidence" and round_idx < max_rounds:
                try:
                    missing_requests = _structured_missing_evidence_requests(raw)
                except Exception as exc:
                    self.last_parse_errors.append(str(exc))
                    missing_requests = ()
                if missing_requests:
                    results = inspector(missing_requests)
                    inspected = True
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": json.dumps(
                            {
                                "verifier_inspection_results": results,
                                "instruction": (
                                    "The runtime executed the structured read-only evidence "
                                    "requests from your uncertain_missing_evidence verdict. "
                                    "Use these observations with the original verifier_packet "
                                    "and return a final verdict or another bounded inspection request."
                                ),
                            },
                            default=str,
                            sort_keys=True,
                        ),
                    })
                    continue
            if result.verdict == "completed" and not inspected:
                # Out of rounds and still uninspected: do not accept the
                # completion. Return an explicit non-completion verdict so the
                # solver sees a durable evidence gap instead of an opaque
                # verifier protocol error. This is protocol enforcement, not a
                # harness-side judgment that the task is wrong.
                return json.dumps({
                    "verdict": "uncertain_missing_evidence",
                    "confidence": "high",
                    "summary": (
                        "Completion cannot be accepted because the verifier "
                        "did not perform a read-only current-state inspection."
                    ),
                    "missing_evidence_requests": [
                        "Provide independent current-state evidence, such as a relevant file read, recent receipt, or rerun check, before accepting completed.",
                    ],
                    "findings": [
                        {
                            "finding_id": "vf-uninspected-completion",
                            "verdict": "uncertain_missing_evidence",
                            "priority": "blocking",
                            "summary": "The verifier attempted to mark the task completed without read-only inspection.",
                            "evidence": [
                                "A completed verifier verdict requires read-only inspection when inspector tools are available.",
                            ],
                            "repair_instruction": (
                                "Surface concrete current-state evidence and resubmit only after the evidence gap is closed."
                            ),
                            "applies_to": ["verifier_evidence"],
                        },
                    ],
                })
            return raw
        raise ModelOutputError("verifier exceeded bounded inspection rounds without returning a verdict")

    @staticmethod
    def _safe_fallback_turn() -> SolverTurn:
        raise ModelOutputError("safe fallback turns are forbidden in certified solver runtime")
