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
from .model_parse import (
    _extract_json_object,
    parse_runtime_config_ir,
    parse_solver_turn,
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


_PATH_IN_REQUEST_RE = re.compile(r"(?:/app/|\b)([A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)*\.[A-Za-z0-9]{1,8})")

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
_TRANSCRIPT_REQUEST_RE = re.compile(
    r"\b(stdout|stderr|transcript|frame-evidence|frame evidence|receipt text|command output|printed by)\b",
    re.IGNORECASE,
)


def _inspections_from_missing_evidence(
    result: Any,
    *,
    packet: Mapping[str, Any] | None = None,
) -> tuple[VerifierInspectionRequest, ...]:
    """Realize prose missing-evidence requests that name concrete files.

    Observed live: verifiers returned uncertain_missing_evidence asking the
    SOLVER to "provide the contents of /app/output.txt" -- evidence only
    verifier-side inspection can produce (solver claims never enter the
    state-only packet).  When a request names a workspace file, inspect it
    directly instead of stalling the run on an unsatisfiable ask.
    """
    seen: list[str] = []
    wants_transcript = False
    for request in getattr(result, "missing_evidence_requests", ()) or ():
        text = str(request)
        if _TRANSCRIPT_REQUEST_RE.search(text):
            wants_transcript = True
        for match in _PATH_IN_REQUEST_RE.finditer(str(request)):
            path = match.group(1)
            if path not in seen:
                seen.append(path)
    requests: list[VerifierInspectionRequest] = []
    for idx, path in enumerate(seen[:4]):
        kind = "perceive_artifact" if path.lower().endswith(_IMAGE_EXTENSIONS) else "read_file"
        requests.append(VerifierInspectionRequest(
            request_id=f"auto-missing-evidence-{idx}",
            kind=kind,
            path=path,
        ))
    if wants_transcript:
        requests.extend(_read_output_requests_from_packet(packet, start_idx=len(requests)))
    return tuple(requests)


def _read_output_requests_from_packet(
    packet: Mapping[str, Any] | None,
    *,
    start_idx: int = 0,
) -> tuple[VerifierInspectionRequest, ...]:
    if not isinstance(packet, Mapping):
        return ()
    handles = packet.get("state_inspection_handles")
    if not isinstance(handles, (list, tuple)):
        return ()
    output_handles: list[dict[str, Any]] = []
    for item in handles:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("kind", "")).strip() != "output":
            continue
        handle = str(item.get("handle", "")).strip()
        stream = str(item.get("stream", "")).strip()
        if not handle or stream not in {"stdout", "stderr"}:
            continue
        output_handles.append({
            "handle": handle,
            "stream": stream,
            "bytes": int(item.get("bytes", 0) or 0),
        })
    if not output_handles:
        return ()
    def _handle_key(item: Mapping[str, Any]) -> tuple[int, str]:
        handle = str(item.get("handle", ""))
        try:
            step_part = handle.split(":", 1)[0]
            return (int(step_part), handle)
        except Exception:
            return (-1, handle)

    def _handle_base(handle: str) -> str:
        parts = handle.split(":")
        return ":".join(parts[:-1]) if len(parts) >= 2 else handle

    output_handles.sort(key=_handle_key)
    latest_stdout = next((item for item in reversed(output_handles) if item["stream"] == "stdout"), None)
    chosen: list[dict[str, Any]] = []
    if latest_stdout is not None:
        chosen.append(latest_stdout)
        sibling_base = _handle_base(latest_stdout["handle"])
        sibling_stderr = next(
            (
                item
                for item in reversed(output_handles)
                if item["stream"] == "stderr" and _handle_base(item["handle"]) == sibling_base
            ),
            None,
        )
        if sibling_stderr is not None:
            chosen.append(sibling_stderr)
    if not chosen:
        chosen = output_handles[-2:]
    requests: list[VerifierInspectionRequest] = []
    for idx, item in enumerate(chosen, start=start_idx):
        requests.append(VerifierInspectionRequest(
            request_id=f"auto-missing-output-{idx}",
            kind="read_output",
            handle=item["handle"],
            span=4000,
        ))
    return tuple(requests)


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
    command_receipts = packet.get("recent_command_receipts", ())
    if len(requests) < 3 and isinstance(command_receipts, (list, tuple)):
        latest_stdout = ""
        latest_stderr = ""
        for item in reversed(command_receipts):
            if not isinstance(item, Mapping):
                continue
            if not latest_stdout:
                latest_stdout = str(item.get("stdout_handle", "")).strip()
            if not latest_stderr:
                latest_stderr = str(item.get("stderr_handle", "")).strip()
            if latest_stdout and latest_stderr:
                break
        if latest_stdout:
            requests.append(VerifierInspectionRequest(
                request_id="auto-latest-command-stdout",
                kind="read_output",
                handle=latest_stdout,
                span=4000,
            ))
        if len(requests) < 3 and latest_stderr:
            requests.append(VerifierInspectionRequest(
                request_id="auto-latest-command-stderr",
                kind="read_output",
                handle=latest_stderr,
                span=4000,
            ))
    return tuple(requests[:3])


def _completed_inspection_is_semantically_grounded(
    packet: Mapping[str, Any],
    inspection_results: list[Mapping[str, Any]],
) -> bool:
    if not inspection_results:
        return False
    if not packet.get("local_verification_limits") and not packet.get("false_positive_risks"):
        return True
    saw_output = False
    saw_substantive_file = False
    for row in inspection_results:
        if not isinstance(row, Mapping):
            continue
        kind = str(row.get("kind", "")).strip()
        if kind == "read_output" and str(row.get("excerpt", "")).strip():
            saw_output = True
            continue
        if kind == "read_file":
            excerpt = str(row.get("excerpt", "")).strip()
            path = str(row.get("path", "")).strip()
            if excerpt and path and not path.endswith((".py", ".sh", ".js", ".ts", ".java", ".c", ".cpp", ".rs", ".go")):
                saw_substantive_file = True
    return saw_output or saw_substantive_file


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
        missing_evidence_realized = False
        last_inspection_results: list[dict[str, Any]] = []
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
                last_inspection_results = list(results)
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
            if (
                result.verdict == "uncertain_missing_evidence"
                and round_idx < max_rounds
                and not missing_evidence_realized
            ):
                # Realize once per verification round: inspect, re-judge, and
                # if the verdict is still uncertain let durable findings and
                # unchanged-state memoization take over instead of looping.
                missing_evidence_realized = True
                auto_requests = _inspections_from_missing_evidence(result, packet=packet)
                if auto_requests:
                    results = inspector(auto_requests)
                    inspected = True
                    last_inspection_results = list(results)
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": json.dumps(
                            {
                                "verifier_inspection_results": results,
                                "instruction": (
                                    "The runtime executed read-only inspections for the files "
                                    "your missing-evidence requests named: the solver cannot "
                                    "supply packet evidence, only your own inspection can. "
                                    "Judge the current state now and return a final verdict; "
                                    "request further bounded inspections only if these "
                                    "observations are genuinely insufficient."
                                ),
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
                    last_inspection_results = list(results)
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
            if (
                result.verdict == "completed"
                and inspected
                and not _completed_inspection_is_semantically_grounded(packet, last_inspection_results)
                and round_idx < max_rounds
            ):
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": json.dumps(
                        {
                            "instruction": (
                                "Do not return completed yet. The inspections so far only prove shape or artifact presence, "
                                "not semantically grounded current-state support for the produced result. Inspect concrete "
                                "result-bearing evidence next, such as the latest command output, produced output artifact, "
                                "or an independent overlay check against the deliverable, then judge again."
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
                    last_inspection_results = list(results)
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
