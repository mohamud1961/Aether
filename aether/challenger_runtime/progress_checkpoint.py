"""Build and ask the bounded typed JUDGE question set for timed progress checkpoints."""
from __future__ import annotations

import math
import time
from typing import Any, Mapping, Sequence

from ..challenger_claim_types import QUESTIONNAIRE_SCHEMA
from ..ledger import ExecutionLedger
from ..progress_checkpoints import MAX_REQUEST_BYTES
from .artifact_evidence import (
    ArtifactFile, ArtifactTest, build_artifact_request, looks_like_test, request_size,
)
from .artifact_review import collect_files
from .evidence import is_scratch_path
from .judge_client import _wire_question
from .progress_question import compact, split_criteria
from .state import FlowContext
from ..run_cancellation import RunCancellationRequested
from ..run_deadline import KernelRunTimeout

STAGE_CHOICES = (
    "not_started", "exploring_only", "partial_not_runnable", "runnable_with_failures",
    "mostly_working", "appears_complete",
)
E2E_CHOICES = ("yes", "no", "unclear")
TRACK_CHOICES = ("likely", "uncertain", "unlikely")
FOCUS_CHOICES = (
    "get_minimal_end_to_end_run", "fix_current_failures", "verify_outputs",
    "reduce_scope_to_required", "continue",
)
QUESTION_PREFIX = "progress_checkpoint:"


def checkpoint_questions(criteria: Sequence[Mapping[str, str]], refs: list[str]) -> dict[str, Any]:
    ids = [str(c["criterion_id"]) for c in criteria]
    return {
        QUESTION_PREFIX + "stage": {
            "relation": "Classify the current stage of the work from the cited task state and evidence.",
            "choices": list(STAGE_CHOICES), "evidence_refs": refs,
        },
        QUESTION_PREFIX + "end_to_end_run_exists": {
            "relation": "Classify whether a complete end-to-end run of the current work has happened.",
            "choices": list(E2E_CHOICES), "evidence_refs": refs,
        },
        QUESTION_PREFIX + "on_track_for_remaining_time": {
            "relation": "Estimate whether the current work is on track for the remaining time.",
            "choices": list(TRACK_CHOICES), "evidence_refs": refs,
        },
        QUESTION_PREFIX + "biggest_gap": {
            "relation": "Choose the criterion that appears to be the biggest remaining gap, or none if no gap is evident.",
            "choices": ids + ["none"], "evidence_refs": refs,
            "choice_details": {cid: next(str(c["text"]) for c in criteria if str(c["criterion_id"]) == cid)
                               for cid in ids},
        },
        QUESTION_PREFIX + "recommended_focus": {
            "relation": "Choose the most useful next focus based on the cited evidence and remaining time.",
            "choices": list(FOCUS_CHOICES), "evidence_refs": refs,
        },
    }


def _action_summary(ledger: ExecutionLedger) -> dict[str, Any]:
    explore = edit = run = 0
    first_run: int | None = None
    first_test: int | None = None
    for receipt in ledger.all_receipts():
        if receipt.kind in {"read_file", "list_files", "search_files"}:
            explore += 1
        elif receipt.kind in {"write_file", "edit_file"}:
            edit += 1
        elif receipt.kind == "run_command":
            run += 1
            payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
            command = str(payload.get("command", ""))
            output = f"{payload.get('stdout') or ''}\n{payload.get('stderr') or ''}"
            if first_run is None:
                first_run = int(receipt.step)
            if first_test is None and looks_like_test(command, output):
                first_test = int(receipt.step)
    return {"explore_actions": explore, "edit_actions": edit, "run_actions": run,
            "first_run_command_step": first_run, "first_test_command_step": first_test,
            "first_end_to_end_run_step": None,
            "first_end_to_end_run_step_status": "unknown_not_inferred"}


def _run_outputs(ledger: ExecutionLedger) -> list[ArtifactTest]:
    """Return recent command observations, including failures and non-test commands."""
    outputs: list[ArtifactTest] = []
    for receipt in reversed(ledger.all_receipts()):
        if receipt.kind != "run_command":
            continue
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        command = str(payload.get("command", ""))
        output = (
            f"exit_code={payload.get('exit_code')}\n"
            f"{payload.get('stdout') or ''}"
            + (f"\nstderr: {payload['stderr']}" if payload.get("stderr") else "")
        )
        text = f"[run_command] {command}\n-> {output}"
        outputs.append(ArtifactTest(f"a{receipt.step}", lambda limit, text=text: compact(text, limit), receipt.receipt_id))
    return outputs


def build_checkpoint_request(
    *, fc: FlowContext, fraction: int, elapsed_sec: float, remaining_sec: float,
) -> tuple[dict[str, Any], dict[str, Any], int]:
    binding = fc.binding
    if binding is None:
        raise ValueError("CHALLENGER controller is not bound to a run")
    raw_task = str(fc.task_text)
    criteria = [{"criterion_id": f"C{i + 1}", "text": str(row["text"])}
                for i, row in enumerate(split_criteria(fc.task_text, fallback=False))]
    files, _ = collect_files(binding.exec_ledger, binding.executor, fc.workspace_root)
    run_outputs = _run_outputs(binding.exec_ledger)
    # edit_file receipts are checkpoint-only here: read the current file at this
    # boundary, never a later snapshot. Existing completion-request collection is
    # deliberately unchanged when progress checkpoints are off.
    seen_paths = {f.path for f in files}
    # ArtifactFile refs are derived from call_index. collect_files allocates
    # synthetic unique indexes for same-step shell writes, so edit receipts must
    # use a separate unique ordering range as well. Keep the real ledger step as
    # provenance instead of presenting that synthetic index as an execution step.
    next_index = max((f.call_index for f in files), default=0) + 1
    for receipt in reversed(binding.exec_ledger.all_receipts()):
        if receipt.kind != "edit_file" or not receipt.success:
            continue
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        path = str(payload.get("path") or "").strip()
        if not path or path in seen_paths or is_scratch_path(path, fc.workspace_root):
            continue
        try:
            content = binding.executor.read_file(path)
        except (RunCancellationRequested, KernelRunTimeout):
            raise
        except Exception:
            continue
        if content is not None:
            files.append(ArtifactFile(
                path, str(content), "current_after_edit", next_index,
                provenance_step=int(receipt.step),
            ))
            next_index += 1
            seen_paths.add(path)
    summary = _action_summary(binding.exec_ledger)

    def wire(card: dict[str, Any], crit: Sequence[Mapping[str, str]], views: Mapping[str, str],
             questions: Mapping[str, Any]) -> dict[str, Any]:
        criterion_text = {str(row["criterion_id"]): str(row["text"]) for row in crit}
        return {
            "model": str(getattr(fc.evaluator, "model", "")),
            "state": {
                "schema": QUESTIONNAIRE_SCHEMA, "raw_task": raw_task, "criteria": list(crit),
                "claim_card": card, "visible_evidence": dict(views),
            },
            "questions": {
                qid: _wire_question(spec, criterion_text) for qid, spec in questions.items()
            },
        }

    built = build_artifact_request(
        wire=wire, criteria_all=criteria, files=files, tests=run_outputs,
        budget=MAX_REQUEST_BYTES, allow_empty=True, question_factory=checkpoint_questions,
        base_card=lambda refs: {
            "checkpoint_fraction_percent": fraction,
            "elapsed_sec": round(elapsed_sec, 3), "remaining_sec": round(remaining_sec, 3),
            "action_summary": summary, "evidence_refs": refs,
        },
    )
    size = request_size(built.request)
    if size > MAX_REQUEST_BYTES:
        raise ValueError(f"checkpoint request is {size} bytes; cap is {MAX_REQUEST_BYTES}")
    questions = checkpoint_questions(built.criteria, list(built.views))
    return built.request, questions, size


def ask_checkpoint(
    fc: FlowContext, *, fraction: int, elapsed_sec: float, remaining_sec: float, step: int,
) -> dict[str, Any] | None:
    request_bytes = 0
    questions: dict[str, Any] = {}
    started = time.monotonic()
    try:
        request, questions, request_bytes = build_checkpoint_request(
            fc=fc, fraction=fraction, elapsed_sec=elapsed_sec, remaining_sec=remaining_sec,
        )
    except (RunCancellationRequested, KernelRunTimeout):
        raise
    except Exception as exc:
        fc.log.append(
            "progress_checkpoint_error", card_id=f"progress_checkpoint:{fraction}", step=step,
            fraction_percent=fraction, request_bytes=request_bytes,
            error_type=type(exc).__name__, error=str(exc)[:300], judge_latency_sec=0.0,
        )
        return None
    fc.log.append(
        "judge_question", card_id=f"progress_checkpoint:{fraction}", step=step,
        fraction_percent=fraction, request_bytes=request_bytes,
        questions=questions, wire_questions=request["questions"],
    )
    try:
        send = getattr(fc.evaluator, "send_progress_prepared", None)
        if not callable(send):
            raise ValueError("dedicated progress-checkpoint JUDGE transport is unavailable")
        answers = send(request, max_bytes=MAX_REQUEST_BYTES)
        parsed: dict[str, dict[str, Any]] = {}
        for qid, spec in questions.items():
            row = answers.get(qid) if isinstance(answers, Mapping) else None
            if not isinstance(row, Mapping):
                raise ValueError(f"missing typed answer for {qid}")
            choice = row.get("choice")
            if choice not in spec["choices"]:
                raise ValueError(f"undeclared choice for {qid}")
            confidence = row.get("confidence")
            probs = row.get("probabilities")
            if isinstance(probs, Mapping) and choice in probs:
                confidence = probs[choice]
            if isinstance(confidence, bool):
                raise ValueError(f"invalid confidence for {qid}")
            confidence = float(confidence)
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise ValueError(f"invalid confidence for {qid}")
            parsed[qid] = {"choice": str(choice), "confidence": confidence}
        elapsed = max(0.0, time.monotonic() - started)
        feedback = render_feedback(fraction, remaining_sec, parsed, questions)
        fc.log.append(
            "judge_answer", card_id=f"progress_checkpoint:{fraction}", step=step,
            fraction_percent=fraction, request_bytes=request_bytes,
            answers=parsed, feedback_text=feedback["text"], judge_latency_sec=round(elapsed, 6),
        )
        fc.log.append(
            "progress_checkpoint", card_id=f"progress_checkpoint:{fraction}", step=step,
            fraction_percent=fraction, request_bytes=request_bytes,
            answers=parsed, feedback_text=feedback["text"], judge_latency_sec=round(elapsed, 6),
        )
        return feedback
    except (RunCancellationRequested, KernelRunTimeout):
        raise
    except Exception as exc:
        elapsed = max(0.0, time.monotonic() - started)
        fc.log.append(
            "progress_checkpoint_error", card_id=f"progress_checkpoint:{fraction}", step=step,
            fraction_percent=fraction, request_bytes=request_bytes,
            error_type=type(exc).__name__, error=str(exc)[:300], judge_latency_sec=round(elapsed, 6),
        )
        return None


def render_feedback(
    fraction: int, remaining_sec: float, answers: Mapping[str, Mapping[str, Any]],
    questions: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    prefix = QUESTION_PREFIX
    def choice(suffix: str) -> str:
        return str(answers[prefix + suffix]["choice"])
    gap = choice("biggest_gap")
    gap_text = str(questions[prefix + "biggest_gap"].get("choice_details", {}).get(gap, gap))
    text = (
        f"Progress check at {fraction}% of time ({round(remaining_sec)} s left): "
        f"stage={choice('stage')}, end-to-end run: {choice('end_to_end_run_exists')}, "
        f"on track: {choice('on_track_for_remaining_time')}, biggest gap: {gap_text}"
    )
    return {"schema": "aether.challenger.feedback.v1", "kind": "progress_checkpoint", "text": text}
