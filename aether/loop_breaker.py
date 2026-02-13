from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from .event_log import EventLog
from .hashing import hash_canonical_json
from .policy_config import PolicyConfig


@dataclass(frozen=True)
class LoopBreakerOutcome:
    should_break: bool
    triggers_fired: List[str]
    explanation: Optional[str]

    @property
    def active_signals(self) -> int:
        return len(self.triggers_fired)


@dataclass(frozen=True)
class ReanchorSignature:
    trigger_code: str
    workspace_hash: str
    last_deny_reason_code: str
    last_verifier_id_params_hash: str
    last_attempted_action_fingerprint: str

    def signature_key(self) -> str:
        return "|".join(
            [
                self.trigger_code,
                self.workspace_hash,
                self.last_deny_reason_code,
                self.last_verifier_id_params_hash,
                self.last_attempted_action_fingerprint,
            ]
        )


@dataclass(frozen=True)
class ReanchorRepeatResult:
    triggered: bool
    action_taken: Optional[str]
    repeat_count: int


@dataclass(frozen=True)
class TransitionLoopResult:
    triggered: bool
    transition_denials_active: bool
    transition_only_turns: int
    trigger_code: Optional[str]
    action_taken: Optional[str]


@dataclass(frozen=True)
class LoopBreakerV2Outcome:
    triggered: bool
    deny_reason_code: Optional[str]
    message: Optional[str]
    consecutive_count: int
    threshold: int
    action_fingerprint: Optional[str]


@dataclass(frozen=True)
class _LoopBreakerV2State:
    last_action_fingerprint: Optional[str]
    last_workspace_fingerprint_hash: Optional[str]
    consecutive_no_delta_count: int


class LoopBreakerV2:
    """Deterministic action loop breaker: identical action + zero fingerprint delta."""

    def __init__(self, event_log: EventLog, policy: PolicyConfig) -> None:
        self.event_log = event_log
        self.policy = policy
        self._state = _LoopBreakerV2State(
            last_action_fingerprint=None,
            last_workspace_fingerprint_hash=None,
            consecutive_no_delta_count=0,
        )
        self._active_denial_action_fingerprint: Optional[str] = None
        self._active_denial_workspace_fingerprint_hash: Optional[str] = None

    def observe_action(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        workspace_fingerprint_hash_before: Optional[str],
        workspace_fingerprint_hash_after: Optional[str],
        fingerprint_delta: int,
        timestamp: str,
        cwd: str,
        phase: str,
    ) -> LoopBreakerV2Outcome:
        if not self.policy.feature_flags.ff_loop_breaker:
            return LoopBreakerV2Outcome(False, None, None, 0, self._threshold(), None)

        action_fingerprint = self._action_fingerprint(tool_name=tool_name, tool_args=tool_args)
        no_delta = (
            isinstance(workspace_fingerprint_hash_before, str)
            and bool(workspace_fingerprint_hash_before)
            and workspace_fingerprint_hash_before == workspace_fingerprint_hash_after
            and int(fingerprint_delta) == 0
        )

        prior = self._state
        if (
            no_delta
            and prior.last_action_fingerprint == action_fingerprint
            and prior.last_workspace_fingerprint_hash == workspace_fingerprint_hash_before
        ):
            streak = prior.consecutive_no_delta_count + 1
        elif no_delta:
            streak = 1
        else:
            streak = 0

        self._state = _LoopBreakerV2State(
            last_action_fingerprint=action_fingerprint,
            last_workspace_fingerprint_hash=workspace_fingerprint_hash_after,
            consecutive_no_delta_count=streak,
        )

        if not no_delta or streak < self._threshold():
            return LoopBreakerV2Outcome(
                False,
                None,
                None,
                streak,
                self._threshold(),
                action_fingerprint,
            )

        self._active_denial_action_fingerprint = action_fingerprint
        self._active_denial_workspace_fingerprint_hash = workspace_fingerprint_hash_after
        message = (
            f"LOOP_DETECTED: repeated `{tool_name}` action with unchanged workspace fingerprint "
            f"for {streak} consecutive executions. Choose a different state-changing action."
        )
        self.event_log.append_event(
            {
                "event_type": "loop_breaker_trigger",
                "timestamp": timestamp,
                "cwd": cwd,
                "phase": phase,
                "trigger_code": "LOOP_DETECTED",
                "deny_reason_code": "LOOP_DETECTED",
                "action_taken": "DENY_REPEATED_ACTION_UNTIL_FINGERPRINT_DELTA",
                "trigger_explanation": message,
                "tool_name": tool_name,
                "tool_args": dict(tool_args),
                "action_fingerprint": action_fingerprint,
                "workspace_fingerprint_hash_before": workspace_fingerprint_hash_before,
                "workspace_fingerprint_hash_after": workspace_fingerprint_hash_after,
                "workspace_fingerprint_hash": workspace_fingerprint_hash_after,
                "fingerprint_delta": int(fingerprint_delta),
                "consecutive_count": streak,
                "threshold": self._threshold(),
            }
        )
        return LoopBreakerV2Outcome(
            True,
            "LOOP_DETECTED",
            message,
            streak,
            self._threshold(),
            action_fingerprint,
        )

    def should_deny(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        workspace_fingerprint_hash: Optional[str],
    ) -> LoopBreakerV2Outcome:
        if not self.policy.feature_flags.ff_loop_breaker:
            return LoopBreakerV2Outcome(False, None, None, 0, self._threshold(), None)
        if (
            not self._active_denial_action_fingerprint
            or not self._active_denial_workspace_fingerprint_hash
        ):
            return LoopBreakerV2Outcome(False, None, None, self._state.consecutive_no_delta_count, self._threshold(), None)

        current_action = self._action_fingerprint(tool_name=tool_name, tool_args=tool_args)
        if (
            current_action != self._active_denial_action_fingerprint
            or workspace_fingerprint_hash != self._active_denial_workspace_fingerprint_hash
        ):
            return LoopBreakerV2Outcome(False, None, None, self._state.consecutive_no_delta_count, self._threshold(), current_action)

        message = (
            "LOOP_DETECTED: repeated action denied until workspace fingerprint changes. "
            "Take a different action that creates a workspace delta."
        )
        return LoopBreakerV2Outcome(
            True,
            "LOOP_DETECTED",
            message,
            self._state.consecutive_no_delta_count,
            self._threshold(),
            current_action,
        )

    def clear_on_workspace_delta(self, *, workspace_fingerprint_hash: Optional[str]) -> None:
        if (
            self._active_denial_workspace_fingerprint_hash
            and workspace_fingerprint_hash
            and workspace_fingerprint_hash != self._active_denial_workspace_fingerprint_hash
        ):
            self._active_denial_action_fingerprint = None
            self._active_denial_workspace_fingerprint_hash = None

    def _threshold(self) -> int:
        return max(2, int(self.policy.loop_breaker.repetitive_action_threshold))

    @staticmethod
    def _action_fingerprint(*, tool_name: str, tool_args: Dict[str, Any]) -> str:
        normalized_args = LoopBreakerV2._canonicalize_tool_args_for_fingerprint(
            tool_name=tool_name, tool_args=tool_args
        )
        payload = {
            "tool_name": str(tool_name),
            "tool_args": normalized_args,
        }
        return hash_canonical_json(payload)

    @staticmethod
    def _canonicalize_tool_args_for_fingerprint(*, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(tool_args, dict):
            return {}

        normalized: Dict[str, Any] = {}
        for key, value in tool_args.items():
            # These fields are documentation-only and allow trivial fingerprint evasion.
            if key in {"assistant_note", "rationale"}:
                continue

            if tool_name == "run" and key == "command":
                normalized[key] = LoopBreakerV2._canonicalize_run_command_for_fingerprint(value)
                continue

            normalized[key] = value
        return normalized

    @staticmethod
    def _canonicalize_run_command_for_fingerprint(command: Any) -> Any:
        if not isinstance(command, list):
            return command

        parts = [str(part) for part in command]
        if len(parts) != 3:
            return parts

        shell = parts[0].split("/")[-1].strip().lower()
        flag = parts[1].strip()
        script = parts[2]
        if shell not in {"sh", "bash"}:
            return parts

        # Only normalize trivial `sh -c "cmd"` wrappers with no shell operators.
        if not flag.startswith("-") or "c" not in flag:
            return parts

        shell_operators = ("&&", "||", "|", ">>", ">", "<<", "<", ";", "\n")
        if any(op in script for op in shell_operators):
            return parts

        try:
            inner = shlex.split(script)
        except ValueError:
            return parts

        return inner if inner else parts


class LoopBreaker:
    """Deterministic loop breaker with formal re-anchor repeat signature detection."""

    def __init__(self, event_log: EventLog, policy: PolicyConfig) -> None:
        self.event_log = event_log
        self.policy = policy
        self._signature_history: List[tuple[int, str, ReanchorSignature]] = []
        self._transition_only_window: List[bool] = []
        self._transition_only_streak: int = 0
        self._transition_denials_active: bool = False

    # Compatibility shim for existing tests/callers.
    def check_loop(
        self,
        current_fingerprint_hash: Optional[str],
        recent_stderr_classes: Optional[List[str]] = None,
    ) -> LoopBreakerOutcome:
        if not self.policy.feature_flags.ff_loop_breaker:
            return LoopBreakerOutcome(False, [], None)

        signals: List[str] = []
        if self._is_repeated_workspace_hash(current_fingerprint_hash):
            signals.append("no_file_diffs")
        if self._check_same_command(count=3):
            signals.append("same_command_count")
        if recent_stderr_classes and len(recent_stderr_classes) >= 3:
            window = recent_stderr_classes[-3:]
            if len(set(window)) == 1:
                signals.append("same_stderr_class_count")

        should_break = "no_file_diffs" in signals and len(signals) >= 2
        explanation = None
        if should_break:
            explanation = f"Loop breaker triggered: {', '.join(signals)}"
        return LoopBreakerOutcome(should_break=should_break, triggers_fired=signals, explanation=explanation)

    def evaluate_reanchor_repeat(
        self,
        *,
        signature: ReanchorSignature,
        step_id: int,
        timestamp: str,
        cwd: str,
    ) -> ReanchorRepeatResult:
        key = signature.signature_key()
        self._signature_history.append((step_id, key, signature))

        window = int(self.policy.loop_breaker.reanchor_repeat_w)
        k_value = int(self.policy.loop_breaker.reanchor_repeat_k)
        lower_bound = step_id - window + 1
        self._signature_history = [
            entry for entry in self._signature_history if entry[0] >= lower_bound
        ]

        repeat_count = sum(1 for _, existing_key, _ in self._signature_history if existing_key == key)
        if repeat_count < k_value:
            return ReanchorRepeatResult(triggered=False, action_taken=None, repeat_count=repeat_count)

        action_taken = "PLAN_UPDATE"
        self.event_log.append_event(
            {
                "event_type": "REANCHOR_REPEAT_DETECTED",
                "timestamp": timestamp,
                "cwd": cwd,
                "trigger_code": signature.trigger_code,
                "workspace_fingerprint_hash": signature.workspace_hash,
                "deny_reason_code": signature.last_deny_reason_code,
                "last_verifier_id_params_hash": signature.last_verifier_id_params_hash,
                "last_attempted_action_fingerprint": signature.last_attempted_action_fingerprint,
                "action_taken": action_taken,
                "repeat_count": repeat_count,
                "window_steps": window,
            }
        )
        return ReanchorRepeatResult(triggered=True, action_taken=action_taken, repeat_count=repeat_count)

    def transition_denials_active(self) -> bool:
        return self._transition_denials_active

    def note_concrete_tool_use(self) -> None:
        self._transition_denials_active = False
        self._transition_only_window.clear()
        self._transition_only_streak = 0

    def evaluate_transition_loop(
        self,
        *,
        transition_only_turn: bool,
        evidence_generated: bool,
        timestamp: str,
        cwd: str,
        phase: str,
    ) -> TransitionLoopResult:
        window_size = max(1, int(self.policy.loop_breaker.transition_only_window_size))
        active_flag = bool(transition_only_turn and not evidence_generated)
        self._transition_only_window.append(active_flag)
        if len(self._transition_only_window) > window_size:
            self._transition_only_window = self._transition_only_window[-window_size:]

        if active_flag:
            self._transition_only_streak += 1
        else:
            self._transition_only_streak = 0
            if evidence_generated:
                self._transition_denials_active = False

        should_trigger = (
            len(self._transition_only_window) >= window_size
            and all(self._transition_only_window)
        )
        if not should_trigger:
            return TransitionLoopResult(
                triggered=False,
                transition_denials_active=self._transition_denials_active,
                transition_only_turns=self._transition_only_streak,
                trigger_code=None,
                action_taken=None,
            )
        if self._transition_denials_active:
            return TransitionLoopResult(
                triggered=False,
                transition_denials_active=True,
                transition_only_turns=self._transition_only_streak,
                trigger_code=None,
                action_taken=None,
            )

        self._transition_denials_active = True
        trigger_code = "TRANSITION_ONLY_LOOP"
        action_taken = "DENY_TRANSITIONS_UNTIL_CONCRETE_TOOL"
        self.event_log.append_event(
            {
                "event_type": "loop_breaker_trigger",
                "timestamp": timestamp,
                "cwd": cwd,
                "trigger_code": trigger_code,
                "triggers_fired": ["transition_only_no_evidence_window"],
                "trigger_explanation": (
                    "Detected repeated transition-only turns without evidence; "
                    "transition requests are denied until a concrete tool call succeeds."
                ),
                "deny_reason_code": "TRANSITION_LOOP_ACTIVE",
                "transition_only_turns": self._transition_only_streak,
                "window_size": window_size,
                "action_taken": action_taken,
                "phase": phase,
            }
        )
        return TransitionLoopResult(
            triggered=True,
            transition_denials_active=True,
            transition_only_turns=self._transition_only_streak,
            trigger_code=trigger_code,
            action_taken=action_taken,
        )

    def _is_repeated_workspace_hash(self, current_fingerprint_hash: Optional[str]) -> bool:
        if not isinstance(current_fingerprint_hash, str) or not current_fingerprint_hash:
            return False
        events = self.event_log.events
        count = 0
        for event in reversed(events):
            if event.get("workspace_fingerprint_hash") != current_fingerprint_hash:
                continue
            count += 1
            if str(event.get("event_type", "")).lower() in {"state_transition", "repair_attempt"}:
                return True
            if count >= 2:
                return True
        return False

    def _check_same_command(self, *, count: int) -> bool:
        events = self.event_log.events
        candidates: List[tuple[str, str]] = []
        for event in reversed(events):
            event_type = str(event.get("event_type", "")).lower()
            if event_type not in {"tool_call", "tool_execution"}:
                continue
            tool_name = event.get("tool_name")
            tool_args = event.get("tool_args")
            if not isinstance(tool_name, str) or not isinstance(tool_args, dict):
                continue
            candidates.append((tool_name, str(tool_args)))
            if len(candidates) >= count:
                break
        if len(candidates) < count:
            return False
        first = candidates[0]
        return all(candidate == first for candidate in candidates)
