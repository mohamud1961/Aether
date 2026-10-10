"""Loop-facing CHALLENGER controller: two narrow hooks plus a feedback queue.

Every failure of the arm's own machinery (card, JUDGE, parsing) is recorded and
degrades to control behaviour: the action runs or the finish is admitted.
Cancellation and the run deadline always propagate.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from concurrent.futures import Future, ThreadPoolExecutor
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from ..challenger_claim_ledger_state import TaskLocalClaimLedger
from ..challenger_claim_types import ActionKind, ActionObservation, FileWrite, LedgerIdentity, TriggerKind
from ..ledger import Receipt
from ..run_cancellation import RunCancellationRequested
from ..run_deadline import KernelRunTimeout
from ..runtime_ir import SolverTurn
from .completion import hold_label, run_completion_review
from .config import (
    CERTAIN_THRESHOLD, ARTIFACT_HOLD_THRESHOLD, CHALLENGER_V1, CHALLENGER_V2, CHALLENGER_V3, CHALLENGER_V4, CHALLENGER_V5, CONFIDENCE_THRESHOLD, DEADLINE_ADMIT_REMAINING_SEC,
    FINISH_CARD_MODES, HARD_HOLD_LIMIT_NO_DEADLINE, HARD_HOLD_LIMIT_WITH_DEADLINE, HOLD_THRESHOLD, LEDGER_MAX_CYCLES,
    LEDGER_MAX_CYCLES_V2, MAX_HOLD_CYCLES, MAX_UNVERIFIED_HOLDS, UNVERIFIED_HOLD_THRESHOLD, V2_FAMILY, T1_FALLBACK_ACTIONS, T2_MAX_REFRESHES, T2_WINDOW_ACTIONS,
)
from .diagnosis import run_diagnosis
from .failure_question import UNVERIFIED_MODE
from .evidence import is_scratch_path
from .events import ChallengerEventLog
from .progress import ask_progress, is_flag, task_actions
from .progress_checkpoint import ask_checkpoint
from .progress_checkpoint_v2 import build_request as build_checkpoint_v2_request, parse_answers as parse_checkpoint_v2_answers, factual_note
from .success_contract import build_contract_prompt, parse_success_contract
from .state_snapshot import capture_state_snapshot
from ..progress_checkpoints import V2
from ..progress_checkpoints import CONTROL, STATE_FINISH_REVIEW, BLIND_FINISH_REVIEW
from .shell_writes import command_write_targets
from .state import CardModel, FlowContext, LoopBinding, tree_note

_PROPAGATE = (RunCancellationRequested, KernelRunTimeout)


class _ReceiptView:
    """Immutable receipt slice for a background checkpoint request."""
    def __init__(self, receipts: Sequence[Any]) -> None:
        self._receipts = tuple(receipts)

    def all_receipts(self) -> tuple[Any, ...]:
        return self._receipts


class ChallengerController:
    def __init__(self, *, card_model: CardModel, evaluator: Any, evidence_dir: Path,
                 run_id: str, task_text: str, threshold: float = CONFIDENCE_THRESHOLD,
                 mode: str = CHALLENGER_V1, progress_fractions: tuple[int, ...] = (),
                 progress_mode: str = "control", state_snapshot_mode: str = "control",
                 success_contract_mode: str = "control", finish_review_mode: str = CONTROL) -> None:
        if mode not in (CHALLENGER_V1, CHALLENGER_V2, CHALLENGER_V3, CHALLENGER_V4, CHALLENGER_V5):
            raise ValueError(f"unknown CHALLENGER controller mode: {mode!r}")
        v2 = mode in V2_FAMILY
        identity = LedgerIdentity(run_id, sha256(task_text.encode("utf-8")).hexdigest())
        ledger = TaskLocalClaimLedger(identity, max_cycles=LEDGER_MAX_CYCLES_V2 if v2 else LEDGER_MAX_CYCLES)
        self._fc = FlowContext(card_model, evaluator, ChallengerEventLog(Path(evidence_dir), run_id),
                               ledger, task_text, threshold,
                               hold_threshold=HOLD_THRESHOLD if v2 else None, failure_mode=v2,
                               artifact_threshold=ARTIFACT_HOLD_THRESHOLD if mode == CHALLENGER_V5 else None)
        self._v2 = v2
        self._v3 = mode == CHALLENGER_V3
        self._finish_card = mode in FINISH_CARD_MODES
        self._unverified_holds = 0
        self._diagnosed = False
        self._holds = 0
        self._refreshes = 0
        self._baseline = 0  # task-action count at T1; T2 windows are counted from here
        self._feedback: list[dict[str, Any]] = []
        if progress_fractions and mode not in (CHALLENGER_V4, CHALLENGER_V5):
            raise ValueError("progress checkpoints require challenger_v4 or challenger_v5")
        if len(progress_fractions) > 4 or tuple(sorted(set(progress_fractions))) != progress_fractions:
            raise ValueError("progress checkpoint fractions must be unique and increasing")
        self._progress_fractions = progress_fractions
        if progress_mode not in {"control", V2}:
            raise ValueError(f"unknown progress checkpoint mode: {progress_mode!r}")
        if state_snapshot_mode not in {"control", "v1"}:
            raise ValueError(f"unknown state snapshot mode: {state_snapshot_mode!r}")
        if progress_mode == V2 and state_snapshot_mode != "v1":
            raise ValueError("progress checkpoint v2 requires state snapshot v1")
        if success_contract_mode not in {"control", "v1"}:
            raise ValueError(f"unknown success contract mode: {success_contract_mode!r}")
        if success_contract_mode == "v1" and progress_mode != V2:
            raise ValueError("success contract v1 requires progress checkpoint mode v2")
        if finish_review_mode not in {CONTROL, STATE_FINISH_REVIEW, BLIND_FINISH_REVIEW}:
            raise ValueError(f"unknown finish review mode: {finish_review_mode!r}")
        if finish_review_mode != CONTROL and (mode != CHALLENGER_V5 or state_snapshot_mode != "v1"):
            raise ValueError("state-aware finish review requires challenger_v5 and state snapshot v1")
        if progress_mode == V2 and not progress_fractions:
            raise ValueError("progress checkpoint v2 requires at least one fraction")
        self._progress_mode = progress_mode
        self._state_snapshot_mode = state_snapshot_mode
        self._success_contract_mode = success_contract_mode
        self._finish_review_mode = finish_review_mode
        self._success_contract: list[dict[str, str]] = []
        self._success_contract_attempted = False
        self._progress_index = 0
        self._feedback_lock = threading.RLock()
        snapshots_enabled = progress_mode == V2 or state_snapshot_mode == "v1"
        self._snapshot_executor = (ThreadPoolExecutor(max_workers=4, thread_name_prefix="aether-state-snapshot")
                                   if snapshots_enabled else None)
        self._progress_executor = (ThreadPoolExecutor(max_workers=2, thread_name_prefix="aether-progress-judge")
                                   if progress_mode == V2 else None)
        self._snapshot_futures: list[Future[Any]] = []
        self._progress_futures: list[Future[Any]] = []
        self._checkpoint_timers: list[threading.Timer] = []
        self._checkpoint_latest_trigger = 0
        self._checkpoint_pending: dict[str, Any] | None = None
        self._checkpoint_last_envmap: Any = None
        self._checkpoint_last_step = 0
        self._run_started_monotonic: float | None = None
        self._run_deadline_sec: float | None = None
        self._snapshot_start_marker: str | None = None

    @property
    def ledger(self) -> TaskLocalClaimLedger:
        return self._fc.ledger

    def bind(self, *, kernel: Any, compiled: Any, executor: Any, exec_ledger: Any, world_state: Any,
             context_tree_adapter: Any | None = None) -> None:
        self._fc.binding = LoopBinding(kernel, compiled, executor, exec_ledger, world_state,
                                       context_tree_adapter)
        configured_root = getattr(executor, "workspace_root", None) or getattr(executor, "_root", None)
        if configured_root:
            self._fc.workspace_root = str(configured_root)

    def pop_feedback(self) -> dict[str, Any] | None:
        with self._feedback_lock:
            if self._progress_mode == V2 and self._checkpoint_pending is not None:
                pending, self._checkpoint_pending = self._checkpoint_pending, None
                elapsed = max(0.0, time.monotonic() - float(pending["run_started_monotonic"]))
                delivered = int(min(99, max(0, 100 * elapsed / pending["deadline_sec"]))) if pending["deadline_sec"] else 0
                self._fc.log.append("progress_checkpoint_v2_delivered",
                                    fraction_percent=pending["fraction"],
                                    taken_at_unix_s=pending["taken_at_unix_s"],
                                    delivered_at_unix_s=time.time(), delivery_fraction_percent=delivered)
                note = pending["note"].replace("delivered at 0%", f"delivered at {delivered}%")
                return {"schema": "aether.challenger.feedback.v1", "kind": "progress_checkpoint_v2", "text": note}
            if not self._feedback:
                return None
            rows, self._feedback = self._feedback, []
            return {"schema": "aether.challenger.feedback.v1", "kind": rows[-1]["kind"],
                    "text": "\n\n".join(r["text"] for r in rows)}

    def start_progress_schedule(self, *, run_started_monotonic: float, deadline_sec: float | None) -> None:
        """Schedule v2 snapshots against the run clock, outside the Solver path."""
        self._run_started_monotonic = float(run_started_monotonic)
        self._run_deadline_sec = float(deadline_sec) if deadline_sec is not None else None
        if self._state_snapshot_mode == "v1" and self._fc.binding is not None:
            prepare = getattr(self._fc.binding.executor, "prepare_state_snapshot_marker", None)
            if callable(prepare):
                try:
                    self._snapshot_start_marker = str(prepare())
                except Exception as exc:
                    self._fc.log.append("state_snapshot_marker_error", error_type=type(exc).__name__,
                                        error=str(exc)[:300])
        if self._progress_mode != V2 or deadline_sec is None or deadline_sec <= 0:
            return
        for fraction in self._progress_fractions:
            delay = max(0.0, float(run_started_monotonic) + float(deadline_sec) * fraction / 100 - time.monotonic())
            timer = threading.Timer(delay, self._trigger_checkpoint_v2,
                                    kwargs={"fraction": fraction, "deadline_sec": float(deadline_sec),
                                            "run_started_monotonic": float(run_started_monotonic)})
            timer.daemon = True
            self._checkpoint_timers.append(timer)
            timer.start()

    def _trigger_checkpoint_v2(self, *, fraction: int, deadline_sec: float,
                               run_started_monotonic: float) -> None:
        fc = self._fc
        if fc.binding is None:
            return
        taken_mono = time.monotonic()
        taken_wall = time.time()
        elapsed = max(0.0, taken_mono - run_started_monotonic)
        remaining = max(0.0, deadline_sec - elapsed)
        self._checkpoint_latest_trigger = max(self._checkpoint_latest_trigger, fraction)
        self._fc.log.append("progress_checkpoint_v2_trigger", fraction_percent=fraction,
                            step=self._checkpoint_last_step, taken_at_unix_s=round(taken_wall, 3),
                            elapsed_fraction=round(elapsed / deadline_sec, 6))
        trigger_step = int(self._checkpoint_last_step)
        trigger_envmap = self._checkpoint_last_envmap
        receipts = fc.binding.exec_ledger.all_receipts()
        def evaluate(snapshot: dict[str, Any]) -> None:
            try:
                request, questions, trim = build_checkpoint_v2_request(
                    task_text=fc.task_text, snapshot=snapshot, receipts=receipts,
                    envmap=trigger_envmap, fraction=fraction, elapsed_sec=elapsed, remaining_sec=remaining,
                    model=str(getattr(fc.evaluator, "model", "")),
                    success_contract=self._success_contract)
                self._fc.log.append("judge_question", card_id=f"progress_checkpoint_v2:{fraction}",
                                    fraction_percent=fraction, request_bytes=trim["request_bytes"],
                                    trim=trim, questions=questions, wire_questions=request["questions"])
                send = getattr(fc.evaluator, "send_progress_prepared", None)
                if not callable(send):
                    raise ValueError("dedicated progress-checkpoint JUDGE transport is unavailable")
                answers = parse_checkpoint_v2_answers(send(request, max_bytes=120_000), questions)
                criteria = request["state"]["criteria"]
                note = factual_note(fraction=fraction, remaining_sec=remaining,
                                    delivery_fraction=0, answers=answers, criteria=criteria,
                                    success_contract=self._success_contract,
                                    observation_start_fraction=snapshot["capture_timing"]["observed_elapsed_fraction"],
                                    observation_end_fraction=snapshot["capture_timing"]["observation_end_elapsed_fraction"])
                delivered_at = time.time()
                self._fc.log.append("progress_checkpoint_v2", fraction_percent=fraction,
                                    request_bytes=trim["request_bytes"], trim=trim,
                                    answers=answers, snapshot_id=f"progress:{fraction}",
                                    judge_latency_sec=round(max(0.0, time.monotonic() - taken_mono), 6),
                                    taken_at_unix_s=snapshot["taken_at_unix_s"],
                                    observation_completed_at_unix_s=snapshot["capture_timing"]["observed_completion_unix_s"],
                                    observation_window_s=snapshot["capture_timing"]["observation_window_s"],
                                    observed_elapsed_fraction=snapshot["elapsed_fraction"],
                                    completed_at_unix_s=round(delivered_at, 3))
                with self._feedback_lock:
                    if fraction != self._checkpoint_latest_trigger:
                        self._fc.log.append("progress_checkpoint_v2_superseded", fraction_percent=fraction,
                                            superseded_by=self._checkpoint_latest_trigger)
                        return
                    if self._checkpoint_pending is not None:
                        self._fc.log.append("progress_checkpoint_v2_superseded", fraction_percent=self._checkpoint_pending["fraction"],
                                            superseded_by=fraction)
                    self._checkpoint_pending = {"fraction": fraction, "note": note,
                                                "taken_at_unix_s": snapshot["taken_at_unix_s"],
                                                "run_started_monotonic": run_started_monotonic,
                                                "deadline_sec": deadline_sec}
                    self._fc.note_to_tree(tree_note(note))
            except Exception as exc:
                self._fc.log.append("progress_checkpoint_v2_error", fraction_percent=fraction,
                                    error_type=type(exc).__name__, error=str(exc)[:500],
                                    taken_at_unix_s=round(taken_wall, 3))
        if self._snapshot_executor is None or self._progress_executor is None:
            return
        def capture() -> dict[str, Any]:
            snapshot = capture_state_snapshot(
                executor=fc.binding.executor, workspace_root=fc.workspace_root,
                task_text=fc.task_text, ledger=_ReceiptView(receipts), taken_at_unix_s=taken_wall,
                elapsed_fraction=elapsed / deadline_sec, step=trigger_step,
                run_start_marker=self._snapshot_start_marker,
                run_started_monotonic=run_started_monotonic, deadline_sec=deadline_sec,
            )
            timing = snapshot["capture_timing"]
            self._fc.log.append("state_snapshot", snapshot_id=f"progress:{fraction}",
                                fraction_percent=fraction, taken_at_unix_s=snapshot["taken_at_unix_s"],
                                elapsed_fraction=snapshot["elapsed_fraction"], capture_timing=timing,
                                snapshot=snapshot)
            return snapshot
        future = self._snapshot_executor.submit(capture)
        self._snapshot_futures.append(future)
        def captured(done: Future[Any]) -> None:
            try:
                snapshot = done.result()
                if snapshot.get("capture_timing", {}).get("status") == "late":
                    self._fc.log.append("progress_checkpoint_v2_error", fraction_percent=fraction,
                                        error_type="LateSnapshot", error="snapshot started more than 100ms after its trigger",
                                        taken_at_unix_s=snapshot.get("taken_at_unix_s"),
                                        snapshot_id=f"progress:{fraction}")
                    return
                job = self._progress_executor.submit(evaluate, snapshot)
                self._progress_futures.append(job)
            except Exception as exc:
                self._fc.log.append("progress_checkpoint_v2_error", fraction_percent=fraction,
                                    error_type=type(exc).__name__, error=str(exc)[:500],
                                    taken_at_unix_s=round(taken_wall, 3))
        future.add_done_callback(captured)

    def on_turn_boundary(self, *, step: int, elapsed_sec: float, deadline_sec: float | None,
                         envmap: Any = None) -> None:
        """Ask due checkpoints after a Solver turn, before its action/finish is dispatched."""
        self._checkpoint_last_step = int(step)
        if envmap is not None:
            self._checkpoint_last_envmap = envmap
            self._fc.workspace_root = str(getattr(envmap, "workspace_root", self._fc.workspace_root) or self._fc.workspace_root)
        # This hook runs for every returned Solver turn before validation and
        # before owned/public action dispatch, so invalid turns do not move the
        # once-after-three-actions card to a later boundary.
        self._capture_success_contract(envmap=envmap, step=step)
        if self._progress_mode == V2:
            return
        if not self._progress_fractions or deadline_sec is None or deadline_sec <= 0:
            return
        while self._progress_index < len(self._progress_fractions):
            fraction = self._progress_fractions[self._progress_index]
            if elapsed_sec < deadline_sec * fraction / 100:
                break
            self._progress_index += 1  # one attempt per fraction, including request/callback failure
            feedback = ask_checkpoint(
                self._fc, fraction=fraction, elapsed_sec=elapsed_sec,
                remaining_sec=max(0.0, deadline_sec - elapsed_sec), step=step,
            )
            self._queue(feedback)
            self._fc.log.snapshot(self._fc.ledger)

    def on_run_end(self) -> None:
        """Capture the run-end state for evidence, then drain owned snapshot work."""
        fc = self._fc
        if (self._progress_mode == V2 or self._state_snapshot_mode == "v1") and fc.binding is not None:
            taken = time.time()
            receipts = fc.binding.exec_ledger.all_receipts()
            assert self._snapshot_executor is not None
            future = self._snapshot_executor.submit(
                capture_state_snapshot, executor=fc.binding.executor,
                workspace_root=fc.workspace_root, task_text=fc.task_text,
                ledger=_ReceiptView(receipts), taken_at_unix_s=taken, elapsed_fraction=1.0,
                step=self._checkpoint_last_step, run_start_marker=self._snapshot_start_marker,
                run_started_monotonic=self._run_started_monotonic, deadline_sec=self._run_deadline_sec,
            )
            self._snapshot_futures.append(future)
            try:
                snapshot = future.result(timeout=16)
                fc.log.append("state_snapshot", snapshot_id="run_end", taken_at_unix_s=snapshot["taken_at_unix_s"],
                              elapsed_fraction=snapshot["elapsed_fraction"],
                              capture_timing=snapshot["capture_timing"], snapshot=snapshot)
            except Exception as exc:
                fc.log.append("state_snapshot_error", snapshot_id="run_end", error_type=type(exc).__name__,
                              error=str(exc)[:500])
        for timer in self._checkpoint_timers:
            timer.cancel()
        if self._snapshot_executor is not None:
            self._snapshot_executor.shutdown(wait=False, cancel_futures=False)
        if self._progress_executor is not None:
            self._progress_executor.shutdown(wait=False, cancel_futures=False)
        if self._snapshot_start_marker and fc.binding is not None:
            cleanup = getattr(fc.binding.executor, "cleanup_state_snapshot_marker", None)
            if callable(cleanup):
                try:
                    cleanup()
                    self._snapshot_start_marker = None
                except Exception as exc:
                    fc.log.append("state_snapshot_marker_cleanup_error", error_type=type(exc).__name__,
                                  error=str(exc)[:300])

    def _capture_auxiliary_snapshot(self, snapshot_id: str, *, elapsed_fraction: float) -> None:
        fc = self._fc
        if self._snapshot_executor is None or fc.binding is None:
            return
        if (elapsed_fraction == 0.0 and self._run_started_monotonic is not None
                and self._run_deadline_sec and self._run_deadline_sec > 0):
            elapsed_fraction = max(0.0, (time.monotonic() - self._run_started_monotonic) / self._run_deadline_sec)
        taken = time.time()
        receipts = fc.binding.exec_ledger.all_receipts()
        future = self._snapshot_executor.submit(
            capture_state_snapshot, executor=fc.binding.executor,
            workspace_root=fc.workspace_root, task_text=fc.task_text,
            ledger=_ReceiptView(receipts), taken_at_unix_s=taken,
            elapsed_fraction=elapsed_fraction, step=self._checkpoint_last_step,
            run_start_marker=self._snapshot_start_marker,
            run_started_monotonic=self._run_started_monotonic, deadline_sec=self._run_deadline_sec,
        )
        self._snapshot_futures.append(future)
        def record() -> None:
            try:
                snapshot = future.result()
                fc.log.append("state_snapshot", snapshot_id=snapshot_id,
                              taken_at_unix_s=snapshot["taken_at_unix_s"],
                              elapsed_fraction=snapshot["elapsed_fraction"],
                              capture_timing=snapshot["capture_timing"], snapshot=snapshot)
            except Exception as exc:
                fc.log.append("state_snapshot_error", snapshot_id=snapshot_id,
                              error_type=type(exc).__name__, error=str(exc)[:500])
        self._snapshot_executor.submit(record)

    def _capture_finish_state_snapshot(self, snapshot_id: str, *, step: int) -> dict[str, Any]:
        """Capture the bounded finish-time observation before constructing a state review."""
        fc = self._fc
        if fc.binding is None:
            unavailable = {"status": "unavailable", "reason": "executor is not bound"}
            fc.log.append("state_snapshot_error", snapshot_id=snapshot_id, **unavailable)
            return unavailable
        taken = time.time()
        receipts = fc.binding.exec_ledger.all_receipts()
        try:
            snapshot = capture_state_snapshot(
                executor=fc.binding.executor, workspace_root=fc.workspace_root,
                task_text=fc.task_text, ledger=_ReceiptView(receipts), taken_at_unix_s=taken,
                elapsed_fraction=0.0, step=step,
                run_start_marker=self._snapshot_start_marker,
                run_started_monotonic=self._run_started_monotonic, deadline_sec=self._run_deadline_sec,
            )
        except _PROPAGATE:
            raise
        except Exception as exc:
            unavailable = {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"[:300]}
            fc.log.append("state_snapshot_error", snapshot_id=snapshot_id, error_type=type(exc).__name__,
                          error=str(exc)[:500])
            return unavailable
        fc.log.append("state_snapshot", snapshot_id=snapshot_id,
                      taken_at_unix_s=snapshot["taken_at_unix_s"],
                      elapsed_fraction=snapshot["elapsed_fraction"],
                      capture_timing=snapshot["capture_timing"], snapshot=snapshot)
        return snapshot

    def _queue(self, feedback: dict[str, Any] | None) -> None:
        if feedback:
            self._feedback.append(feedback)
            self._fc.note_to_tree(tree_note(feedback.get("note") or feedback["text"]))

    def _degrade(self, where: str, exc: BaseException) -> None:
        self._fc.log.append("degraded", where=where, error_type=type(exc).__name__, error=str(exc)[:500])

    def _capture_success_contract(self, *, envmap: Any, step: int) -> None:
        if self._success_contract_mode != "v1" or self._success_contract_attempted or self._fc.binding is None:
            return
        receipts = self._fc.binding.exec_ledger.all_receipts()
        actions = [row for row in receipts if row.kind in {
            "read_file", "read_file_page", "list_files", "search_files", "write_file", "edit_file",
            "run_command", "job_output", "job_wait", "job_stop", "m_tree_zoom", "managed_context_edit_context",
        }]
        if len(actions) < 3:
            return
        self._success_contract_attempted = True
        prompt = build_contract_prompt(self._fc.task_text, envmap, actions[:3])
        started = time.monotonic()
        response = ""
        try:
            # The contract turn receives only the task, lean environment map, and first three actions.
            response = self._fc.ask_card_model([], prompt, "Success checks", record_note=False)
            self._success_contract = parse_success_contract(response)
            status, error = "accepted", None
        except _PROPAGATE:
            raise
        except Exception as exc:
            status, error = "invalid_or_unavailable", f"{type(exc).__name__}: {exc}"[:300]
        usage = getattr(self._fc.card_model, "last_token_usage", None)
        if callable(usage):
            usage = usage()
        usage = usage if isinstance(usage, Mapping) else {}
        token_usage_status = str(usage.get("usage_status") or "not_exposed_by_card_model")
        self._fc.log.append("success_contract", step=step, status=status,
                            checks=self._success_contract if status == "accepted" else None,
                            error=error, response=response, call_count=1,
                            latency_sec=round(time.monotonic() - started, 6),
                            request_chars=len(prompt), response_chars=len(response),
                            token_usage={key: usage.get(key) for key in (
                                "input_tokens", "output_tokens", "total_tokens", "cached_input_tokens",
                                "cache_write_tokens", "reasoning_tokens")},
                            token_usage_status=token_usage_status)

    def before_act(self, turn: SolverTurn, *, messages: Sequence[Mapping[str, Any]],
                   step: int, envmap: Any) -> Any:
        """Observe the pending act turn; at the first production write run T1 first."""
        fc = self._fc
        fc.workspace_root = envmap.workspace_root
        action = turn.actions[0]
        writes: tuple[FileWrite, ...] = ()
        source = "write_file"
        if action.kind in {"write_file", "edit_file"} and str(action.arguments.get("path", "")).strip():
            paths: tuple[str, ...] = (str(action.arguments["path"]).strip(),)
        elif action.kind == "run_command":
            paths = command_write_targets(str(action.arguments.get("command", "")))
            source = "command_write"
        else:
            paths = ()
        writes = tuple(FileWrite(p, is_scratch_path(p, envmap.workspace_root)) for p in paths)
        events = fc.ledger.observe_action(ActionObservation(
            action_id=f"{action.action_id}@{step}", accepted=True,
            state_fingerprint=f"gen:{fc.binding.exec_ledger.task_state_generation()}",
            material=bool(writes), writes=writes))
        trigger = next((e for e in events if e.kind == TriggerKind.FIRST_PRODUCTION_WRITE), None)
        if self._diagnosed:
            return self._maybe_refresh(turn, messages=messages, step=step, envmap=envmap)
        if trigger is not None:
            detail = next(w.path for w in writes if not w.is_scratch)
        elif fc.ledger.accepted_action_count > T1_FALLBACK_ACTIONS:
            source = "fallback"
            detail = f"{fc.ledger.accepted_action_count - 1} accepted actions without a detected production write"
            trigger = fc.ledger.force_trigger(
                TriggerKind.FIRST_PRODUCTION_WRITE, (f"fallback_after_{T1_FALLBACK_ACTIONS}_accepted_actions",))
        else:
            return None
        self._diagnosed = True
        self._baseline = len(task_actions(fc))
        fc.log.append("trigger", kind=trigger.kind.value, trigger_id=trigger.trigger_id, step=step,
                      source=source, path=detail)
        if fc.ledger.verify_repair_cycles >= fc.ledger.max_cycles:
            fc.log.append("diagnosis_skipped", reason="verify/repair cycle bound reached", step=step)
            return None
        try:
            feedback, refreshed = run_diagnosis(fc, turn, messages=messages, step=step, envmap=envmap,
                                                trigger_id=trigger.trigger_id)
        except _PROPAGATE:
            raise
        except Exception as exc:  # arm failure degrades to control
            self._degrade("T1", exc)
            return None
        finally:
            fc.log.snapshot(fc.ledger)
        self._queue(feedback)
        return refreshed

    def _maybe_refresh(self, turn: SolverTurn, *, messages: Sequence[Mapping[str, Any]],
                       step: int, envmap: Any) -> Any:
        """T2: every window of accepted actions after T1, ask JUDGE whether progress stalled."""
        fc = self._fc
        if self._refreshes >= T2_MAX_REFRESHES:
            return None
        actions = task_actions(fc)
        if len(actions) - self._baseline < T2_WINDOW_ACTIONS:
            return None
        self._baseline = len(actions)  # one question per window, whatever the answer
        if fc.ledger.verify_repair_cycles >= fc.ledger.max_cycles:
            fc.log.append("progress_skipped", reason="verify/repair cycle bound reached", step=step)
            return None
        try:
            choice, prob = ask_progress(fc, actions, step)
        except _PROPAGATE:
            raise
        except Exception as exc:  # JUDGE progress errors are skipped, not fatal
            fc.log.append("progress_error", step=step, error_type=type(exc).__name__, error=str(exc)[:300])
            return None
        if not is_flag(choice, prob):
            fc.log.append("progress_ok", step=step, choice=choice, probability=prob)
            return None
        self._refreshes += 1
        trigger = fc.ledger.force_trigger(TriggerKind.STUCK_OR_CONTRADICTED, (f"judge_progress_{choice}",))
        fc.log.append("trigger", kind="stuck_or_contradicted", trigger_id=trigger.trigger_id, step=step,
                      source="judge_progress", refresh=self._refreshes, choice=choice, probability=prob)
        reason = f"the last {T2_WINDOW_ACTIONS} actions were judged {choice.replace('_', ' ')} ({prob:.2f})"
        try:
            feedback, refreshed = run_diagnosis(fc, turn, messages=messages, step=step, envmap=envmap,
                                                trigger_id=trigger.trigger_id, refresh=reason)
        except _PROPAGATE:
            raise
        except Exception as exc:  # arm failure degrades to control
            self._degrade("T2", exc)
            return None
        finally:
            fc.log.snapshot(fc.ledger)
        self._queue(feedback)
        return refreshed

    def _past_deadline_margin(self, remaining_sec: Callable[[], float | None] | None) -> bool:
        remaining = remaining_sec() if remaining_sec is not None else None
        return remaining is not None and remaining < DEADLINE_ADMIT_REMAINING_SEC

    def on_finish_attempt(self, turn: SolverTurn, *, messages: Sequence[Mapping[str, Any]],
                          step: int, remaining_sec: Callable[[], float | None] | None = None) -> bool:
        """Return True when the finish is held (the loop then continues to the next solver turn).

        ``remaining_sec`` (challenger_v2) returns the packet's remaining_run_sec when deadline visibility
        is active, else None. P1: past the hold cap a finish is still held while a hold signal is
        near-certain, but never past the deadline margin and never past the hard hold limit."""
        fc = self._fc
        events = fc.ledger.observe_action(ActionObservation(
            action_id=f"finish@{step}", accepted=True,
            state_fingerprint=f"gen:{fc.binding.exec_ledger.task_state_generation()}",
            finish_intent=True))
        trigger = next((e for e in events if e.kind == TriggerKind.FINISH_INTENT), None)
        if trigger is None:
            return False
        observed_state = None
        if self._finish_review_mode != CONTROL:
            observed_state = self._capture_finish_state_snapshot(f"finish:{step}", step=step)
        elif self._progress_mode == V2 or self._state_snapshot_mode == "v1":
            self._capture_auxiliary_snapshot(f"finish:{step}", elapsed_fraction=0.0)
        extended = self._v2 and self._holds >= MAX_HOLD_CYCLES
        if extended:
            has_deadline = remaining_sec is not None and remaining_sec() is not None
            limit = HARD_HOLD_LIMIT_WITH_DEADLINE if has_deadline else HARD_HOLD_LIMIT_NO_DEADLINE
            if self._holds >= limit:
                fc.log.append("finish_admitted", reason="hard hold limit reached", holds=self._holds,
                              limit=limit, step=step)
                return False
            if self._past_deadline_margin(remaining_sec):
                fc.log.append("finish_admitted", reason="deadline margin: best-effort submission",
                              holds=self._holds, remaining_sec=remaining_sec(), step=step)
                return False
        elif self._holds >= MAX_HOLD_CYCLES:
            fc.log.append("finish_admitted", reason="hold cap reached", holds=self._holds, step=step)
            return False
        if fc.ledger.verify_repair_cycles >= fc.ledger.max_cycles:
            # Reviews that did not hold (advisory, admitted, degraded) also use ledger cycles.
            fc.log.append("finish_admitted", reason="verify/repair cycle bound reached",
                          cycles=fc.ledger.verify_repair_cycles, step=step)
            return False
        fc.log.append("trigger", kind=trigger.kind.value, trigger_id=trigger.trigger_id, step=step)
        try:
            decision, feedback = run_completion_review(
                fc, messages=messages, step=step, trigger_id=trigger.trigger_id,
                hold_no=self._holds + 1,
                embedded_card=getattr(turn, "completion_card", None) if self._finish_card else None,
                final_claim=str(getattr(turn, "claim", "") or getattr(turn, "summary", "")),
                finish_review_mode=self._finish_review_mode,
                observed_state=observed_state,
                unverified_threshold=(UNVERIFIED_HOLD_THRESHOLD
                                      if self._v3 and self._unverified_holds < MAX_UNVERIFIED_HOLDS else None))
        except _PROPAGATE:
            raise
        except Exception as exc:  # arm failure degrades to control
            self._degrade("T4", exc)
            return False
        finally:
            fc.log.snapshot(fc.ledger)
        if extended and decision.kind == ActionKind.HOLD_FINISH:
            # The review took time and the P1 rule needs near-certainty: neither may leave a stale hold behind.
            reason = (
                "deadline margin: best-effort submission" if self._past_deadline_margin(remaining_sec)
                else None if decision.strongest >= CERTAIN_THRESHOLD
                else f"hold cap reached; no hold signal at or above {CERTAIN_THRESHOLD}")
            if reason:
                fc.log.append("finish_admitted", reason=reason, holds=self._holds,
                              strongest=decision.strongest, step=step)
                return False
        self._queue(feedback)
        if feedback:
            fc.log.append("feedback", kind=feedback["kind"], text=feedback["text"])
        if decision.kind != ActionKind.HOLD_FINISH:
            return False
        self._holds += 1
        if decision.failure_mode == UNVERIFIED_MODE:
            self._unverified_holds += 1
        fc.binding.exec_ledger.record(Receipt(
            receipt_id=f"step-{step}:challenger_finish_hold:{self._holds}", step=step,
            kind="challenger_finish_hold", success=True,
            summary=f"completion held by claim-ledger review ({hold_label(self._holds)})",
            payload={"held_criteria": list(decision.held)}))
        return True
