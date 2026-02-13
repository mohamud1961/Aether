from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from difflib import unified_diff
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .artifact_store import ArtifactStore
from .action_fingerprint import RetryTracker, compute_fingerprint
from .canonical_workdir import CanonicalWorkdirError, canonicalize_cwd
from .event_log import EventLog
from .governance_gate import GovernanceGate
from .hashing import canonical_json_bytes, hash_canonical_json
from .network_control import check_network_allowed
from .path_sandbox import PathSandboxError, resolve_sandboxed_path_for_op
from .policy_config import PolicyConfig
from .risk_classifier import classify_risk, emit_risk_eval_event, risk_classification_reason
from .rollback_truth import (
    SideEffectRecord,
    build_side_effect_records,
    summarize_side_effects,
)
from .safe_file_ops import PreimageMismatchError, SafeFileOps, SafeFileOpResult
from .script_allowlist import check_script_allowed
from .redaction import redact


@dataclass(frozen=True)
class ToolResult:
    exit_code: Optional[int | str]
    stdout_ref: str
    stderr_ref: str
    truncation: Dict[str, Dict[str, Any]]
    duration_ms: Optional[int]
    files_read: List[str]
    files_written: List[str]
    last_failed_command: Optional[str]
    event: Dict[str, Any]
    summary: Dict[str, Any] = field(default_factory=dict)
    assistant_note: Optional[str] = None
    risk_class: str = "LOW"
    observed_preimage_hashes: Dict[str, str] = field(default_factory=dict)
    re_read_required: bool = False


_TOOL_SUMMARY_STDOUT_TAIL_LINES = 8
_TOOL_SUMMARY_KEY_LINES = 6
_TOOL_SUMMARY_STDERR_EXCERPT_CHARS = 240
_TOOL_SUMMARY_LINE_CHARS = 160
_ASSISTANT_NOTE_MAX_CHARS = 280


RUN_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "run",
    "description": "Run a shell command. Use `cwd` instead of `cd ... && ...`.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Command and arguments as argv array.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory, either relative to workspace root or an absolute path under workspace root. Use this instead of cd.",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Command timeout in milliseconds. Defaults to 60000.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["command"],
    },
}

READ_FILE_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "read_file",
    "description": "Read a UTF-8 text file from the workspace using PATH_SANDBOX enforcement.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to cwd or absolute path under workspace root.",
            },
            "max_bytes": {
                "type": "integer",
                "description": "Optional max bytes to return from file content.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["path"],
    },
}

WRITE_FILE_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "write_file",
    "description": "Write UTF-8 text content to a file in workspace with PATH_SANDBOX enforcement.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to cwd or absolute path under workspace root.",
            },
            "content": {
                "type": "string",
                "description": "UTF-8 text content to write.",
            },
            "append": {
                "type": "boolean",
                "description": "Append content instead of replacing file content.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["path", "content"],
    },
}

SEARCH_FILES_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "search_files",
    "description": "Search workspace text files without shelling out, enforced by PATH_SANDBOX.",
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Substring or regex pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory path to search from; defaults to cwd.",
            },
            "glob": {
                "type": "string",
                "description": "Optional glob filter for file names (default `**/*`).",
            },
            "use_regex": {
                "type": "boolean",
                "description": "Interpret `pattern` as a regular expression when true.",
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive matching when true (default false).",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of matches returned (default 100, max 500).",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["pattern"],
    },
}

LIST_DIR_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "list_dir",
    "description": "List directory entries from the workspace with PATH_SANDBOX enforcement.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to cwd or absolute path under workspace root.",
            },
            "all": {
                "type": "boolean",
                "description": "Include dotfiles when true.",
            },
            "long": {
                "type": "boolean",
                "description": "Include size/type/mtime fields for each entry when true.",
            },
            "recursive": {
                "type": "boolean",
                "description": "Recursively list entries when true.",
            },
            "glob": {
                "type": "string",
                "description": "Optional basename glob filter (for example, '*.py').",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
    },
}

STAT_PATHS_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "stat_paths",
    "description": "Return deterministic stat metadata for workspace paths.",
    "parameters": {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Path list relative to cwd or absolute path under workspace root.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["paths"],
    },
}

DIFF_FILES_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "diff_files",
    "description": "Generate a unified diff between two UTF-8 files in workspace scope.",
    "parameters": {
        "type": "object",
        "properties": {
            "path_a": {
                "type": "string",
                "description": "First file path relative to cwd or absolute under workspace root.",
            },
            "path_b": {
                "type": "string",
                "description": "Second file path relative to cwd or absolute under workspace root.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["path_a", "path_b"],
    },
}

APPLY_PATCH_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "apply_patch",
    "description": "Apply a deterministic text patch to a workspace file.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Target file path relative to cwd or absolute under workspace root.",
            },
            "old_text": {
                "type": "string",
                "description": "Optional expected text to replace (must match exactly once when provided).",
            },
            "new_text": {
                "type": "string",
                "description": "Replacement text to write.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["path", "new_text"],
    },
}

PIPELINE_RUN_TOOL_DEFINITION: Dict[str, Any] = {
    "name": "pipeline_run",
    "description": "Execute structured argv pipelines without shell operators.",
    "parameters": {
        "type": "object",
        "properties": {
            "pipeline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Stage command argv.",
                        },
                    },
                    "required": ["command"],
                },
                "description": "Ordered argv stages; stdout is piped to next stage stdin.",
            },
            "stdin_text": {
                "type": "string",
                "description": "Optional UTF-8 stdin for first stage.",
            },
            "stdout_path": {
                "type": "string",
                "description": "Optional file path to persist final stdout.",
            },
            "stderr_path": {
                "type": "string",
                "description": "Optional file path to persist aggregated stderr.",
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["pipeline"],
    },
}

REQUEST_PHASE_TRANSITION_DEFINITION: Dict[str, Any] = {
    "name": "request_phase_transition",
    "description": "Request a phase transition through ControlPlane policy checks.",
    "parameters": {
        "type": "object",
        "properties": {
            "to_phase": {
                "type": "string",
                "enum": ["Orient", "Explore", "Plan", "Implement", "Verify", "Review"],
                "description": "Requested phase target (Orient, Explore, Plan, Implement, Verify, or Review).",
            },
            "phase_reason_code": {
                "type": "string",
                "enum": [
                    "allowlist",
                    "budget_exceeded",
                    "default_allow",
                    "default_deny",
                    "manual_request",
                    "plan_update_required",
                    "reanchor",
                    "replay_mode",
                    "timeout",
                    "verification_required",
                ],
                "description": "Model-provided reason code for the transition request.",
            },
            "backtrack_context": {
                "type": "object",
                "description": (
                    "Required for backward transitions (for example Implement -> Plan). "
                    "Must include non-empty context explaining what precondition failed."
                ),
                "additionalProperties": True,
            },
            "assistant_note": {
                "type": "string",
                "description": "Optional short rationale note for future steps.",
            },
            "rationale": {
                "type": "string",
                "description": "Alias for assistant_note.",
            },
        },
        "required": ["to_phase", "phase_reason_code"],
    },
}

_NATIVE_TOOL_NAMES = frozenset(
    {
        "read_file",
        "write_file",
        "search_files",
        "list_dir",
        "stat_paths",
        "diff_files",
        "apply_patch",
        "pipeline_run",
    }
)


class ToolGateway:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        event_log: EventLog,
        governance_gate: GovernanceGate,
        workspace_root: Path,
        policy_config: Optional[PolicyConfig] = None,
        subprocess_runner: Optional[Callable[..., subprocess.CompletedProcess[bytes]]] = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.event_log = event_log
        self.governance_gate = governance_gate
        self.workspace_root = workspace_root.resolve()
        self.policy_config = policy_config or PolicyConfig.from_env()
        self.safe_file_ops = SafeFileOps(
            self.workspace_root,
            enabled=self.policy_config.feature_flags.ff_safe_file_ops,
            artifact_store_root=self.artifact_store.root,
        )
        self._runner = subprocess_runner or subprocess.run
        self._retry_tracker = RetryTracker()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            json.loads(json.dumps(RUN_TOOL_DEFINITION)),
            json.loads(json.dumps(READ_FILE_TOOL_DEFINITION)),
            json.loads(json.dumps(WRITE_FILE_TOOL_DEFINITION)),
            json.loads(json.dumps(SEARCH_FILES_TOOL_DEFINITION)),
            json.loads(json.dumps(LIST_DIR_TOOL_DEFINITION)),
            json.loads(json.dumps(STAT_PATHS_TOOL_DEFINITION)),
            json.loads(json.dumps(DIFF_FILES_TOOL_DEFINITION)),
            json.loads(json.dumps(APPLY_PATCH_TOOL_DEFINITION)),
            json.loads(json.dumps(PIPELINE_RUN_TOOL_DEFINITION)),
            json.loads(json.dumps(REQUEST_PHASE_TRANSITION_DEFINITION)),
        ]

    def execute(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timestamp: str,
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        timeout_ms: Optional[int] = None,
        read_paths: Optional[Iterable[Path]] = None,
        write_paths: Optional[Iterable[Path]] = None,
        preimage_hashes: Optional[Dict[str, str]] = None,
        max_output_bytes: Optional[int] = None,
        plan_id: Optional[str] = None,
        plan_version_id: Optional[int] = None,
        plan_step_id: Optional[str] = None,
        observed_workspace_hash_before: Optional[str] = None,
    ) -> ToolResult:
        if not isinstance(tool_args, dict) or not tool_args:
            raise ValueError("tool_args must be a non-empty mapping")

        canonical_tool_args = _canonicalize_tool_args(tool_args)
        command_input = canonical_tool_args.get("command")
        effective_tool_name = tool_name
        effective_tool_args = canonical_tool_args
        normalization: Optional[Dict[str, Any]] = None
        if tool_name == "run":
            normalization = _normalize_readonly_run(canonical_tool_args)
            if normalization.get("applied"):
                effective_tool_name = str(normalization.get("to_tool_name"))
                normalized_args = normalization.get("to_tool_args")
                if not isinstance(normalized_args, dict):
                    raise ValueError("normalization produced invalid tool args")
                effective_tool_args = _canonicalize_tool_args(normalized_args)

        native_tool = effective_tool_name in _NATIVE_TOOL_NAMES
        command: List[str] = []
        if not native_tool:
            command = _normalize_command(command_input)
        assistant_note = _extract_assistant_note(canonical_tool_args)
        risk_class = classify_risk(tool_name, canonical_tool_args, self.policy_config)
        try:
            exec_cwd = self._resolve_execution_cwd(
                tool_name=tool_name,
                requested_cwd=cwd,
                tool_args=canonical_tool_args,
            )
        except PathSandboxError as exc:
            deny_event = self._log_tool_deny(
                tool_name=tool_name,
                tool_args=canonical_tool_args,
                timestamp=timestamp,
                cwd=self.workspace_root,
                deny_reason_code="PATH_SANDBOX_VIOLATION",
                risk_class=risk_class,
                plan_id=plan_id,
                plan_version_id=plan_version_id,
                plan_step_id=plan_step_id,
                observed_workspace_hash_before=observed_workspace_hash_before,
            )
            raise PermissionError(deny_event["deny_reason_code"]) from exc

        plan_linkage = {
            "plan_id": plan_id,
            "plan_version_id": plan_version_id,
            "plan_step_id": plan_step_id,
        }
        fingerprint = compute_fingerprint(
            tool_name=tool_name,
            tool_args=canonical_tool_args,
            cwd=exec_cwd.as_posix(),
            policy_flags={
                "network_enabled": self.policy_config.network_enabled,
                "enforce_script_allowlist": self.policy_config.enforce_script_allowlist,
                "policy_profile": self.policy_config.policy_profile,
            },
            plan_linkage=plan_linkage,
            workspace_hash=observed_workspace_hash_before or "",
        )

        retry_decision = self._retry_tracker.evaluate_retry(
            fingerprint=fingerprint,
            workspace_hash=observed_workspace_hash_before,
            evidence_counter=len(self.event_log.events),
            plan_version_id=str(plan_version_id) if plan_version_id is not None else None,
            approval_counter=getattr(self.governance_gate, "approval_counter", 0),
        )
        if not retry_decision.allowed:
            deny_event = self._log_retry_deny(
                tool_name=tool_name,
                tool_args=canonical_tool_args,
                timestamp=timestamp,
                cwd=exec_cwd,
                deny_reason_code=retry_decision.deny_reason_code or "RETRY_NO_PROGRESS",
                attempted_action_fingerprint=fingerprint,
                risk_class="LOW",
                plan_id=plan_id,
                plan_version_id=plan_version_id,
                plan_step_id=plan_step_id,
                observed_workspace_hash_before=observed_workspace_hash_before,
            )
            raise PermissionError(deny_event["deny_reason_code"])

        classification_reason = risk_classification_reason(tool_name, canonical_tool_args)
        emit_risk_eval_event(
            event_log=self.event_log,
            timestamp=timestamp,
            cwd=exec_cwd.as_posix(),
            tool_name=tool_name,
            risk_class=risk_class,
            classification_reason=classification_reason,
        )

        if self.policy_config.policy_profile == "prod" and risk_class == "HIGH":
            if not self.governance_gate.has_approval(
                approval_type="HIGH_RISK_EXECUTION",
                action_fingerprint=fingerprint,
            ):
                deny_event = self._log_tool_deny(
                    tool_name=tool_name,
                    tool_args=canonical_tool_args,
                    timestamp=timestamp,
                    cwd=exec_cwd,
                    deny_reason_code="GOVERNANCE_DENY",
                    risk_class=risk_class,
                    plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    plan_step_id=plan_step_id,
                    observed_workspace_hash_before=observed_workspace_hash_before,
                    attempted_action_fingerprint=fingerprint,
                )
                self._retry_tracker.record_failure(
                    fingerprint=fingerprint,
                    workspace_hash=observed_workspace_hash_before,
                    evidence_counter=len(self.event_log.events),
                    plan_version_id=str(plan_version_id) if plan_version_id is not None else None,
                    approval_counter=getattr(self.governance_gate, "approval_counter", 0),
                )
                raise PermissionError(deny_event["deny_reason_code"])

        if risk_class in {"MED", "HIGH"} and not _has_plan_linkage(
            plan_id=plan_id,
            plan_version_id=plan_version_id,
            plan_step_id=plan_step_id,
        ):
            if self.governance_gate.has_any_decision_for_action(tool_name):
                # Backward-compatible path for existing flows that pre-record governance.
                pass
            else:
                deny_event = self._log_tool_deny(
                    tool_name=tool_name,
                    tool_args=canonical_tool_args,
                    timestamp=timestamp,
                    cwd=exec_cwd,
                    deny_reason_code="PLAN_MISSING_LINKAGE",
                    risk_class=risk_class,
                    plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    plan_step_id=plan_step_id,
                    attempted_action_fingerprint=fingerprint,
                )
                raise PermissionError(deny_event["deny_reason_code"])

        if not check_network_allowed(tool_name, canonical_tool_args, self.policy_config):
            deny_event = self._log_tool_deny(
                tool_name=tool_name,
                tool_args=canonical_tool_args,
                timestamp=timestamp,
                cwd=exec_cwd,
                deny_reason_code="NETWORK_DISABLED",
                risk_class=risk_class,
                plan_id=plan_id,
                plan_version_id=plan_version_id,
                plan_step_id=plan_step_id,
                attempted_action_fingerprint=fingerprint,
            )
            raise PermissionError(deny_event["deny_reason_code"])

        if self._should_enforce_script_allowlist(canonical_tool_args):
            script_content = self._extract_script_content(canonical_tool_args, exec_cwd)
            allowlist_hashes = self._script_allowlist_hashes()
            if not script_content or not check_script_allowed(script_content, allowlist_hashes):
                deny_event = self._log_tool_deny(
                    tool_name=tool_name,
                    tool_args=canonical_tool_args,
                    timestamp=timestamp,
                    cwd=exec_cwd,
                    deny_reason_code="SCRIPT_HASH_NOT_ALLOWLISTED",
                    risk_class=risk_class,
                    plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    plan_step_id=plan_step_id,
                    attempted_action_fingerprint=fingerprint,
                )
                raise PermissionError(deny_event["deny_reason_code"])

        if not native_tool:
            # Fail closed for operator-token shell composition.
            detected_shell_operators = _detect_shell_operators(command=command, raw_command=command_input)
            if detected_shell_operators:
                shell_progress_counter = _successful_tool_call_count(self.event_log.events)
                shell_fingerprint = _shell_operator_fingerprint(
                    tool_name=tool_name,
                    shell_operators=detected_shell_operators,
                    cwd=exec_cwd,
                )
                blocked_command = _stringify_command(command_input, command)
                shell_retry_decision = self._retry_tracker.evaluate_retry(
                    fingerprint=shell_fingerprint,
                    workspace_hash=observed_workspace_hash_before,
                    evidence_counter=shell_progress_counter,
                    plan_version_id=str(plan_version_id) if plan_version_id is not None else None,
                    approval_counter=getattr(self.governance_gate, "approval_counter", 0),
                )
                if not shell_retry_decision.allowed:
                    deny_event = self._log_retry_deny(
                        tool_name=tool_name,
                        tool_args=canonical_tool_args,
                        timestamp=timestamp,
                        cwd=exec_cwd,
                        deny_reason_code=shell_retry_decision.deny_reason_code or "RETRY_NO_PROGRESS",
                        attempted_action_fingerprint=shell_fingerprint,
                        risk_class=risk_class,
                        plan_id=plan_id,
                        plan_version_id=plan_version_id,
                        plan_step_id=plan_step_id,
                        observed_workspace_hash_before=observed_workspace_hash_before,
                    )
                    raise PermissionError(deny_event["deny_reason_code"])
                deny_event = self._log_tool_deny(
                    tool_name=tool_name,
                    tool_args=canonical_tool_args,
                    timestamp=timestamp,
                    cwd=exec_cwd,
                    deny_reason_code="SHELL_OPERATORS_BLOCKED",
                    risk_class=risk_class,
                    plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    plan_step_id=plan_step_id,
                    observed_workspace_hash_before=observed_workspace_hash_before,
                    attempted_action_fingerprint=shell_fingerprint,
                    evidence_counter_override=shell_progress_counter,
                    extra_event_fields={
                        "blocked_operator": detected_shell_operators[0],
                        "blocked_operators": detected_shell_operators,
                        "blocked_command": blocked_command,
                    },
                )
                raise PermissionError(deny_event["deny_reason_code"])

        last_failed_command = (
            f"{effective_tool_name}:{effective_tool_args.get('path', canonical_tool_args.get('path', ''))}"
            if native_tool
            else " ".join(str(item) for item in command)
        )

        try:
            self.governance_gate.require_decision(
                tool_name,
                canonical_tool_args,
                cwd=exec_cwd.as_posix(),
            )
        except Exception as exc:
            if str(exc).startswith("missing_governance_decision"):
                has_prior_for_action = self.governance_gate.has_any_decision_for_action(tool_name)
                safe_file_scope_rebind = bool(read_paths or write_paths)
                if (
                    (has_prior_for_action and not safe_file_scope_rebind)
                    or (
                        not self.policy_config.feature_flags.ff_evaluation_suite_mode
                        and not safe_file_scope_rebind
                    )
                ):
                    deny_event = self._log_tool_deny(
                        tool_name=tool_name,
                        tool_args=canonical_tool_args,
                        timestamp=timestamp,
                        cwd=exec_cwd,
                        deny_reason_code="GOVERNANCE_DENY",
                        risk_class=risk_class,
                        plan_id=plan_id,
                        plan_version_id=plan_version_id,
                        plan_step_id=plan_step_id,
                        attempted_action_fingerprint=fingerprint,
                    )
                    raise PermissionError(deny_event["deny_reason_code"]) from exc

                decision = self.governance_gate.evaluate(
                    action=tool_name,
                    risk_tier="standard",
                    timestamp=timestamp,
                    cwd=exec_cwd.as_posix(),
                    tool_args=canonical_tool_args,
                )
                if not decision.allow:
                    deny_event = self._log_tool_deny(
                        tool_name=tool_name,
                        tool_args=canonical_tool_args,
                        timestamp=timestamp,
                        cwd=exec_cwd,
                        deny_reason_code="POLICY_BLOCKLIST",
                        risk_class=risk_class,
                        plan_id=plan_id,
                        plan_version_id=plan_version_id,
                        plan_step_id=plan_step_id,
                        attempted_action_fingerprint=fingerprint,
                    )
                    raise PermissionError(deny_event["deny_reason_code"]) from exc
            else:
                deny_event = self._log_tool_deny(
                    tool_name=tool_name,
                    tool_args=canonical_tool_args,
                    timestamp=timestamp,
                    cwd=exec_cwd,
                    deny_reason_code="GOVERNANCE_DENY",
                    risk_class=risk_class,
                    plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    plan_step_id=plan_step_id,
                    attempted_action_fingerprint=fingerprint,
                )
                raise PermissionError(deny_event["deny_reason_code"]) from exc

        files_read: List[str] = []
        files_written: List[str] = []
        observed_preimage_hashes: Dict[str, str] = {}
        expected_preimage_hash: Optional[str] = None
        observed_preimage_hash: Optional[str] = None

        try:
            if read_paths:
                read_result = self._collect_read_paths(read_paths)
                files_read.extend(read_result.files_read)
                observed_preimage_hashes.update(read_result.observed_preimage_hashes)
            if write_paths:
                result = self._collect_write_paths(
                    write_paths,
                    preimage_hashes=preimage_hashes,
                )
                files_read.extend(result.files_read)
                files_written.extend(result.files_written)
                observed_preimage_hashes.update(result.observed_preimage_hashes)
                if files_written:
                    primary_path = files_written[0]
                    expected_preimage_hash = preimage_hashes.get(primary_path) if preimage_hashes else None
                    observed_preimage_hash = observed_preimage_hashes.get(primary_path)
        except PreimageMismatchError as mismatch:
            blocked_event = self._log_tool_deny(
                tool_name=tool_name,
                tool_args=canonical_tool_args,
                timestamp=timestamp,
                cwd=exec_cwd,
                deny_reason_code="PREIMAGE_MISMATCH",
                risk_class=risk_class,
                plan_id=plan_id,
                plan_version_id=plan_version_id,
                plan_step_id=plan_step_id,
                files_read=[mismatch.path],
                files_written=[mismatch.path],
                expected_preimage_hash=mismatch.expected_hash,
                observed_preimage_hash=mismatch.observed_hash,
                re_read_required=True,
                observed_workspace_hash_before=observed_workspace_hash_before,
                attempted_action_fingerprint=fingerprint,
            )
            self._retry_tracker.record_failure(
                fingerprint=fingerprint,
                workspace_hash=observed_workspace_hash_before,
                evidence_counter=len(self.event_log.events),
                plan_version_id=str(plan_version_id) if plan_version_id is not None else None,
                approval_counter=getattr(self.governance_gate, "approval_counter", 0),
            )
            return ToolResult(
                exit_code=None,
                stdout_ref=blocked_event.get("stdout_ref", ""),
                stderr_ref=blocked_event.get("stderr_ref", ""),
                truncation=blocked_event.get("truncation", {"stdout": {}, "stderr": {}}),
                duration_ms=None,
                files_read=[mismatch.path],
                files_written=[mismatch.path],
                last_failed_command=last_failed_command,
                summary=dict(blocked_event.get("tool_summary", {})),
                assistant_note=blocked_event.get("assistant_note"),
                observed_preimage_hashes={mismatch.path: mismatch.observed_hash},
                re_read_required=True,
                risk_class=risk_class,
                event=blocked_event,
            )
        except PathSandboxError as exc:
            deny_event = self._log_tool_deny(
                tool_name=tool_name,
                tool_args=canonical_tool_args,
                timestamp=timestamp,
                cwd=exec_cwd,
                deny_reason_code="PATH_SANDBOX_VIOLATION",
                risk_class=risk_class,
                plan_id=plan_id,
                plan_version_id=plan_version_id,
                plan_step_id=plan_step_id,
                observed_workspace_hash_before=observed_workspace_hash_before,
                attempted_action_fingerprint=fingerprint,
            )
            raise PermissionError(str(exc)) from exc

        start = time.monotonic()
        stdout_bytes = b""
        stderr_bytes = b""
        exit_code: Optional[int | str] = None
        timeout = False
        truncation_unknown = False

        resolved_timeout_ms = self._resolve_timeout_ms(
            tool_name=tool_name,
            tool_args=canonical_tool_args,
            timeout_ms=timeout_ms,
        )
        if native_tool:
            try:
                exit_code, stdout_bytes, stderr_bytes = self._execute_native_tool(
                    tool_name=effective_tool_name,
                    tool_args=effective_tool_args,
                    exec_cwd=exec_cwd,
                    files_read=files_read,
                    files_written=files_written,
                    observed_preimage_hashes=observed_preimage_hashes,
                    preimage_hashes=preimage_hashes,
                )
            except PathSandboxError as exc:
                deny_event = self._log_tool_deny(
                    tool_name=tool_name,
                    tool_args=canonical_tool_args,
                    timestamp=timestamp,
                    cwd=exec_cwd,
                    deny_reason_code="PATH_SANDBOX_VIOLATION",
                    risk_class=risk_class,
                    plan_id=plan_id,
                    plan_version_id=plan_version_id,
                    plan_step_id=plan_step_id,
                    observed_workspace_hash_before=observed_workspace_hash_before,
                    attempted_action_fingerprint=fingerprint,
                )
                raise PermissionError(deny_event["deny_reason_code"]) from exc
        else:
            run_env = env.copy() if env is not None else os.environ.copy()
            # Prevent host environment paths from overriding container-native paths
            for leaky_key in ["TMPDIR", "TMP", "TEMP", "HOME"]:
                run_env.pop(leaky_key, None)
                
            python_deps = self.workspace_root / ".harness_deps" / "python"
            if python_deps.exists():
                old_pp = run_env.get("PYTHONPATH", "")
                run_env["PYTHONPATH"] = f"{python_deps}:{old_pp}" if old_pp else str(python_deps)
            try:
                completed = self._runner(
                    command,
                    cwd=exec_cwd,
                    env=run_env,
                    capture_output=True,
                    timeout=None if resolved_timeout_ms is None else resolved_timeout_ms / 1000.0,
                    check=False,
                )
                stdout_bytes = completed.stdout or b""
                stderr_bytes = completed.stderr or b""
                exit_code = int(completed.returncode)
            except subprocess.TimeoutExpired as exc:
                timeout = True
                stdout_bytes = exc.stdout or b""
                timeout_line = (
                    f"Command timed out after {resolved_timeout_ms or 0}ms and was terminated."
                ).encode("utf-8")
                stderr_prefix = exc.stderr or b""
                if stderr_prefix and not stderr_prefix.endswith(b"\n"):
                    stderr_prefix += b"\n"
                stderr_bytes = stderr_prefix + timeout_line
                exit_code = "TIMEOUT"
            except Exception:
                truncation_unknown = True
                exit_code = None

        duration_ms = int((time.monotonic() - start) * 1000)

        stdout_meta, stdout_payload = self._apply_truncation(
            stdout_bytes, max_output_bytes, truncation_unknown
        )
        stderr_meta, stderr_payload = self._apply_truncation(
            stderr_bytes, max_output_bytes, truncation_unknown
        )
        truncation_flags = _truncation_flags(stdout_meta, stderr_meta)

        redacted_stdout_text, stdout_redactions = redact(stdout_payload.decode("utf-8", errors="replace"))
        redacted_stderr_text, stderr_redactions = redact(stderr_payload.decode("utf-8", errors="replace"))
        stdout_payload = redacted_stdout_text.encode("utf-8")
        stderr_payload = redacted_stderr_text.encode("utf-8")
        redaction_records = stdout_redactions + stderr_redactions
        if redaction_records:
            self.event_log.append_event(
                {
                    "event_type": "REDACTION_APPLIED",
                    "timestamp": timestamp,
                    "cwd": exec_cwd.as_posix(),
                    "count": sum(record.count for record in redaction_records),
                    "types": sorted({record.redaction_type for record in redaction_records}),
                    "tool_name": tool_name,
                }
            )

        stdout_artifact = self.artifact_store.put_bytes(stdout_payload, content_type="text/plain")
        stderr_artifact = self.artifact_store.put_bytes(stderr_payload, content_type="text/plain")
        tool_summary = _build_tool_receipt_summary(
            tool_name=tool_name,
            exit_code=exit_code,
            duration_ms=duration_ms,
            stdout_bytes=stdout_payload,
            stderr_bytes=stderr_payload,
            truncation={"stdout": stdout_meta, "stderr": stderr_meta},
            assistant_note=assistant_note,
            command_args=canonical_tool_args.get("command"),
        )

        last_failed = None if exit_code == 0 else last_failed_command
        side_effects = build_side_effect_records(
            tool_name=effective_tool_name,
            files_written=files_written,
            risk_class=risk_class,
        )
        side_effect_scope, reversibility = summarize_side_effects(side_effects)

        event_payload = {
            "event_type": "tool_call",
            "timestamp": timestamp,
            "cwd": exec_cwd.as_posix(),
            "tool_name": tool_name,
            "tool_args": canonical_tool_args,
            "effective_tool_name": effective_tool_name,
            "effective_tool_args": effective_tool_args,
            "normalization": normalization,
            "assistant_note": assistant_note,
            "exit_code": exit_code,
            "files_read": files_read,
            "files_written": files_written,
            "artifact_refs": [stdout_artifact.artifact_id, stderr_artifact.artifact_id],
            "truncation": {"stdout": stdout_meta, "stderr": stderr_meta},
            "stdout_ref": stdout_artifact.artifact_id,
            "stderr_ref": stderr_artifact.artifact_id,
            "stdout_hash": stdout_artifact.artifact_id,
            "stderr_hash": stderr_artifact.artifact_id,
            "truncation_flags": truncation_flags,
            "persisted_byte_counts": {
                "stdout": len(stdout_payload),
                "stderr": len(stderr_payload),
            },
            "duration_ms": duration_ms,
            "last_failed_command": last_failed,
            "observed_preimage_hashes": observed_preimage_hashes,
            "expected_preimage_hash": expected_preimage_hash,
            "observed_preimage_hash": observed_preimage_hash,
            "re_read_required": False,
            "risk_class": risk_class,
            "plan_id": plan_id,
            "plan_version_id": plan_version_id,
            "plan_step_id": plan_step_id,
            "side_effects": side_effects,
            "side_effect_scope": side_effect_scope,
            "reversibility": reversibility,
            "observed_workspace_hash_before": observed_workspace_hash_before,
            "timeout": timeout,
            "tool_timeout": timeout,
            "timeout_ms": resolved_timeout_ms,
            "resolved_cwd": exec_cwd.as_posix(),
            "tool_summary": tool_summary,
        }
        event = self.event_log.append_event(event_payload)

        if exit_code != 0 and exit_code is not None:
            self._retry_tracker.record_failure(
                fingerprint=fingerprint,
                workspace_hash=observed_workspace_hash_before,
                evidence_counter=len(self.event_log.events),
                plan_version_id=str(plan_version_id) if plan_version_id is not None else None,
                approval_counter=getattr(self.governance_gate, "approval_counter", 0),
            )

        return ToolResult(
            exit_code=exit_code,
            stdout_ref=stdout_artifact.artifact_id,
            stderr_ref=stderr_artifact.artifact_id,
            truncation={"stdout": stdout_meta, "stderr": stderr_meta},
            duration_ms=duration_ms,
            files_read=files_read,
            files_written=files_written,
            last_failed_command=last_failed,
            summary=tool_summary,
            assistant_note=assistant_note,
            observed_preimage_hashes=observed_preimage_hashes,
            re_read_required=False,
            risk_class=risk_class,
            event=event,
        )

    def _resolve_execution_cwd(
        self,
        *,
        tool_name: str,
        requested_cwd: Path,
        tool_args: Dict[str, Any],
    ) -> Path:
        base_cwd = self._resolve_cwd(requested_cwd)
        if tool_name != "run":
            return base_cwd

        tool_cwd = tool_args.get("cwd")
        if tool_cwd is None:
            return base_cwd
        if not isinstance(tool_cwd, str) or not tool_cwd.strip():
            raise PathSandboxError("PATH_SANDBOX_VIOLATION", "tool_args.cwd must be a non-empty string")

        requested = Path(tool_cwd.strip())
        if requested.is_absolute():
            resolved = requested.resolve()
            if not resolved.is_relative_to(self.workspace_root):
                raise PathSandboxError(
                    "PATH_SANDBOX_VIOLATION",
                    f"Absolute cwd {requested} is outside workspace root"
                )
            return resolved
        try:
            resolved = canonicalize_cwd(self.workspace_root, requested)
        except (CanonicalWorkdirError, FileNotFoundError, ValueError) as exc:
            raise PathSandboxError("PATH_SANDBOX_VIOLATION", "Requested cwd is outside workspace root") from exc

        if not resolved.exists() or not resolved.is_dir():
            raise PathSandboxError("PATH_SANDBOX_VIOLATION", "Requested cwd does not exist or is not a directory")
        return resolved

    def _resolve_timeout_ms(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timeout_ms: Optional[int],
    ) -> Optional[int]:
        selected = timeout_ms
        if tool_name == "run":
            if "timeout_ms" in tool_args:
                selected = tool_args.get("timeout_ms")
            elif selected is None:
                selected = getattr(self.policy_config, "run_tool_timeout_ms", 60_000)

        if selected is None:
            return None
        if not isinstance(selected, int) or selected <= 0:
            raise ValueError("timeout_ms must be a positive integer")
        return selected

    def _resolve_cwd(self, requested_cwd: Path) -> Path:
        if self.policy_config.feature_flags.ff_canonical_workdir:
            return canonicalize_cwd(self.workspace_root, requested_cwd)

        if requested_cwd.is_absolute():
            return requested_cwd.resolve()
        return (self.workspace_root / requested_cwd).resolve()

    def _collect_read_paths(self, read_paths: Iterable[Path]) -> SafeFileOpResult:
        files_read: List[str] = []
        observed_hashes: Dict[str, str] = {}
        resolved_path: Optional[Path] = None
        for path in read_paths:
            result = self.safe_file_ops.prepare_read(path)
            resolved_path = result.resolved_path
            files_read.extend(result.files_read)
            observed_hashes.update(result.observed_preimage_hashes)
        if resolved_path is None:
            raise ValueError("read_paths must not be empty")
        return SafeFileOpResult(
            resolved_path=resolved_path,
            files_read=files_read,
            files_written=[],
            observed_preimage_hashes=observed_hashes,
        )

    def _collect_write_paths(
        self,
        write_paths: Iterable[Path],
        *,
        preimage_hashes: Optional[Dict[str, str]],
    ) -> SafeFileOpResult:
        files_read: List[str] = []
        files_written: List[str] = []
        observed_hashes: Dict[str, str] = {}
        resolved_path: Optional[Path] = None
        for path in write_paths:
            expected_hash = None
            if preimage_hashes:
                expected_hash = preimage_hashes.get(path.as_posix())
            result = self.safe_file_ops.prepare_write(path, expected_preimage_hash=expected_hash)
            resolved_path = result.resolved_path
            files_read.extend(result.files_read)
            files_written.extend(result.files_written)
            observed_hashes.update(result.observed_preimage_hashes)
        if resolved_path is None:
            raise ValueError("write_paths must not be empty")
        return SafeFileOpResult(
            resolved_path=resolved_path,
            files_read=files_read,
            files_written=files_written,
            observed_preimage_hashes=observed_hashes,
        )

    def _apply_truncation(
        self, data: bytes, max_bytes: Optional[int], unknown: bool
    ) -> tuple[Dict[str, Any], bytes]:
        if unknown:
            meta = {
                "truncated": False,
                "size_bytes": len(data),
                "captured_bytes": 0,
                "unknown": True,
            }
            return meta, b""

        size_bytes = len(data)
        if max_bytes is None:
            meta = {
                "truncated": False,
                "size_bytes": size_bytes,
                "captured_bytes": size_bytes,
                "unknown": False,
            }
            return meta, data

        truncated = size_bytes > max_bytes
        payload = data[:max_bytes]
        meta = {
            "truncated": truncated,
            "size_bytes": size_bytes,
            "captured_bytes": len(payload),
            "unknown": False,
        }
        return meta, payload

    def _execute_native_tool(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        files_written: List[str],
        observed_preimage_hashes: Dict[str, str],
        preimage_hashes: Optional[Dict[str, str]],
    ) -> tuple[int, bytes, bytes]:
        if tool_name == "read_file":
            payload = self._native_read_file(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                observed_preimage_hashes=observed_preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "write_file":
            payload = self._native_write_file(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                files_written=files_written,
                observed_preimage_hashes=observed_preimage_hashes,
                preimage_hashes=preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "search_files":
            payload = self._native_search_files(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                observed_preimage_hashes=observed_preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "list_dir":
            payload = self._native_list_dir(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "stat_paths":
            payload = self._native_stat_paths(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                observed_preimage_hashes=observed_preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "diff_files":
            payload = self._native_diff_files(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                observed_preimage_hashes=observed_preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "apply_patch":
            payload = self._native_apply_patch(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                files_written=files_written,
                observed_preimage_hashes=observed_preimage_hashes,
                preimage_hashes=preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        if tool_name == "pipeline_run":
            payload = self._native_pipeline_run(
                tool_args=tool_args,
                exec_cwd=exec_cwd,
                files_read=files_read,
                files_written=files_written,
                observed_preimage_hashes=observed_preimage_hashes,
                preimage_hashes=preimage_hashes,
            )
            return 0, _to_json_bytes(payload), b""
        raise ValueError(f"unknown_native_tool:{tool_name}")

    def _native_read_file(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        observed_preimage_hashes: Dict[str, str],
    ) -> Dict[str, Any]:
        target = self._resolve_native_path(exec_cwd=exec_cwd, path_value=tool_args.get("path"))
        result = self.safe_file_ops.prepare_read(target)
        files_read.extend(result.files_read)
        observed_preimage_hashes.update(result.observed_preimage_hashes)
        data = result.resolved_path.read_bytes()

        requested_max_bytes = tool_args.get("max_bytes")
        if requested_max_bytes is not None:
            if not isinstance(requested_max_bytes, int) or requested_max_bytes <= 0:
                raise ValueError("read_file.max_bytes must be a positive integer when provided")
            payload = data[:requested_max_bytes]
            truncated = len(data) > requested_max_bytes
        else:
            payload = data
            truncated = False

        content = payload.decode("utf-8", errors="replace")
        return {
            "path": result.files_read[0] if result.files_read else result.resolved_path.as_posix(),
            "content": content,
            "encoding": "utf-8",
            "size_bytes": len(data),
            "captured_bytes": len(payload),
            "truncated": truncated,
        }

    def _native_write_file(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        files_written: List[str],
        observed_preimage_hashes: Dict[str, str],
        preimage_hashes: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        target = self._resolve_native_path(
            exec_cwd=exec_cwd,
            path_value=tool_args.get("path"),
            for_write=True,
        )
        expected_hash = None
        if isinstance(preimage_hashes, dict):
            target_key = _workspace_rel_or_abs(self.workspace_root, target)
            expected_hash = preimage_hashes.get(target_key)
        result = self.safe_file_ops.prepare_write(target, expected_preimage_hash=expected_hash)
        files_read.extend(result.files_read)
        files_written.extend(result.files_written)
        observed_preimage_hashes.update(result.observed_preimage_hashes)

        content = tool_args.get("content")
        if not isinstance(content, str):
            raise ValueError("write_file.content must be a string")
        append = bool(tool_args.get("append", False))
        mode = "a" if append else "w"
        result.resolved_path.parent.mkdir(parents=True, exist_ok=True)
        with result.resolved_path.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return {
            "path": result.files_written[0] if result.files_written else result.resolved_path.as_posix(),
            "bytes_written": len(content.encode("utf-8")),
            "append": append,
        }

    def _native_search_files(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        observed_preimage_hashes: Dict[str, str],
    ) -> Dict[str, Any]:
        pattern = tool_args.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValueError("search_files.pattern must be a non-empty string")
        root = self._resolve_native_path(
            exec_cwd=exec_cwd,
            path_value=tool_args.get("path", "."),
            require_exists=True,
        )
        if not root.is_dir():
            raise ValueError("search_files.path must resolve to a directory")
        glob_value = tool_args.get("glob", "**/*")
        if isinstance(glob_value, str):
            stripped_glob = glob_value.strip()
            glob_pattern = stripped_glob if stripped_glob else "**/*"
        elif glob_value is None:
            glob_pattern = "**/*"
        else:
            raise ValueError("search_files.glob must be a string when provided")

        use_regex = bool(tool_args.get("use_regex", False))
        case_sensitive = bool(tool_args.get("case_sensitive", False))
        max_results = tool_args.get("max_results", 100)
        if not isinstance(max_results, int) or max_results <= 0:
            raise ValueError("search_files.max_results must be a positive integer")
        max_results = min(max_results, 500)

        regex: Optional[re.Pattern[str]] = None
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags=flags)
        elif not case_sensitive:
            pattern = pattern.lower()

        matches: List[Dict[str, Any]] = []
        scanned_files = 0
        for file_path in sorted(root.glob(glob_pattern)):
            if not file_path.is_file():
                continue
            result = self.safe_file_ops.prepare_read(file_path)
            files_read.extend(result.files_read)
            observed_preimage_hashes.update(result.observed_preimage_hashes)
            scanned_files += 1
            data = result.resolved_path.read_bytes()
            if b"\x00" in data:
                continue
            text = data.decode("utf-8", errors="replace")
            rel_path = result.files_read[0] if result.files_read else result.resolved_path.as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                haystack = line if case_sensitive else line.lower()
                if regex is not None:
                    if not regex.search(line):
                        continue
                elif pattern not in haystack:
                    continue
                matches.append({"path": rel_path, "line": line_number, "text": line[:200]})
                if len(matches) >= max_results:
                    return {
                        "matches": matches,
                        "pattern": tool_args.get("pattern"),
                        "path": _workspace_rel_or_abs(self.workspace_root, root),
                        "scanned_files": scanned_files,
                        "truncated": True,
                    }
        return {
            "matches": matches,
            "pattern": tool_args.get("pattern"),
            "path": _workspace_rel_or_abs(self.workspace_root, root),
            "scanned_files": scanned_files,
            "truncated": False,
        }

    def _native_list_dir(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
    ) -> Dict[str, Any]:
        root = self._resolve_native_path(
            exec_cwd=exec_cwd,
            path_value=tool_args.get("path", "."),
            require_exists=True,
        )
        if not root.is_dir():
            raise ValueError("list_dir.path must resolve to a directory")
        include_all = bool(tool_args.get("all", False))
        long = bool(tool_args.get("long", False))
        recursive = bool(tool_args.get("recursive", False))
        glob = tool_args.get("glob")
        if isinstance(glob, str):
            stripped_glob = glob.strip()
            glob_pattern = stripped_glob if stripped_glob else None
        elif glob is None:
            glob_pattern = None
        else:
            raise ValueError("list_dir.glob must be a string when provided")

        root_rel = _workspace_rel_or_abs(self.workspace_root, root)
        files_read.append(root_rel)
        iterator = root.rglob("*") if recursive else root.iterdir()
        entries: List[Dict[str, Any]] = []
        for path in sorted(iterator, key=lambda item: item.as_posix()):
            name = path.name
            if not include_all and name.startswith("."):
                continue
            if glob_pattern and not fnmatch(name, glob_pattern):
                continue
            rel_path = _workspace_rel_or_abs(self.workspace_root, path)
            item: Dict[str, Any] = {
                "path": rel_path,
                "name": name,
                "type": "dir" if path.is_dir() else ("file" if path.is_file() else "other"),
            }
            if long:
                stats = path.stat()
                item["size_bytes"] = int(stats.st_size)
                item["mtime_ns"] = int(getattr(stats, "st_mtime_ns", int(stats.st_mtime * 1_000_000_000)))
            entries.append(item)
        return {
            "path": root_rel,
            "all": include_all,
            "long": long,
            "recursive": recursive,
            "glob": glob_pattern,
            "count": len(entries),
            "entries": entries,
        }

    def _native_stat_paths(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        observed_preimage_hashes: Dict[str, str],
    ) -> Dict[str, Any]:
        raw_paths = tool_args.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("stat_paths.paths must be a non-empty array")
        if len(raw_paths) > 200:
            raise ValueError("stat_paths.paths must not exceed 200 entries")

        entries: List[Dict[str, Any]] = []
        for raw in raw_paths:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("stat_paths.paths entries must be non-empty strings")
            resolved = self._resolve_native_path(
                exec_cwd=exec_cwd,
                path_value=raw,
                require_exists=False,
            )
            rel_path = _workspace_rel_or_abs(self.workspace_root, resolved)
            if not resolved.exists():
                entries.append({"path": rel_path, "exists": False})
                continue

            stat = resolved.stat()
            entry: Dict[str, Any] = {
                "path": rel_path,
                "exists": True,
                "type": "dir" if resolved.is_dir() else ("file" if resolved.is_file() else "other"),
                "size_bytes": int(stat.st_size),
                "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
                "mode": int(stat.st_mode),
            }
            if resolved.is_file():
                read_result = self.safe_file_ops.prepare_read(resolved)
                files_read.extend(read_result.files_read)
                observed_preimage_hashes.update(read_result.observed_preimage_hashes)
                data_hash = read_result.observed_preimage_hashes.get(read_result.files_read[0])
                if isinstance(data_hash, str):
                    entry["sha256"] = data_hash
            entries.append(entry)
        return {"entries": entries}

    def _native_diff_files(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        observed_preimage_hashes: Dict[str, str],
    ) -> Dict[str, Any]:
        path_a = tool_args.get("path_a")
        path_b = tool_args.get("path_b")
        if not isinstance(path_a, str) or not path_a.strip():
            raise ValueError("diff_files.path_a must be a non-empty string")
        if not isinstance(path_b, str) or not path_b.strip():
            raise ValueError("diff_files.path_b must be a non-empty string")

        resolved_a = self._resolve_native_path(exec_cwd=exec_cwd, path_value=path_a, require_exists=True)
        resolved_b = self._resolve_native_path(exec_cwd=exec_cwd, path_value=path_b, require_exists=True)
        read_a = self.safe_file_ops.prepare_read(resolved_a)
        read_b = self.safe_file_ops.prepare_read(resolved_b)
        files_read.extend(read_a.files_read)
        files_read.extend(read_b.files_read)
        observed_preimage_hashes.update(read_a.observed_preimage_hashes)
        observed_preimage_hashes.update(read_b.observed_preimage_hashes)

        text_a = read_a.resolved_path.read_text(encoding="utf-8", errors="replace")
        text_b = read_b.resolved_path.read_text(encoding="utf-8", errors="replace")
        diff_lines = list(
            unified_diff(
                text_a.splitlines(),
                text_b.splitlines(),
                fromfile=read_a.files_read[0] if read_a.files_read else _workspace_rel_or_abs(self.workspace_root, resolved_a),
                tofile=read_b.files_read[0] if read_b.files_read else _workspace_rel_or_abs(self.workspace_root, resolved_b),
                lineterm="",
            )
        )
        return {
            "path_a": read_a.files_read[0] if read_a.files_read else _workspace_rel_or_abs(self.workspace_root, resolved_a),
            "path_b": read_b.files_read[0] if read_b.files_read else _workspace_rel_or_abs(self.workspace_root, resolved_b),
            "different": text_a != text_b,
            "diff_line_count": len(diff_lines),
            "diff": "\n".join(diff_lines),
        }

    def _native_apply_patch(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        files_written: List[str],
        observed_preimage_hashes: Dict[str, str],
        preimage_hashes: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        path_value = tool_args.get("path")
        new_text = tool_args.get("new_text")
        old_text = tool_args.get("old_text")
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("apply_patch.path must be a non-empty string")
        if not isinstance(new_text, str):
            raise ValueError("apply_patch.new_text must be a string")
        if old_text is not None and not isinstance(old_text, str):
            raise ValueError("apply_patch.old_text must be a string when provided")

        target = self._resolve_native_path(
            exec_cwd=exec_cwd,
            path_value=path_value,
            for_write=True,
        )
        expected_hash = None
        if isinstance(preimage_hashes, dict):
            expected_hash = preimage_hashes.get(_workspace_rel_or_abs(self.workspace_root, target))
        write_receipt = self.safe_file_ops.prepare_write(target, expected_preimage_hash=expected_hash)
        files_read.extend(write_receipt.files_read)
        files_written.extend(write_receipt.files_written)
        observed_preimage_hashes.update(write_receipt.observed_preimage_hashes)

        prior_exists = target.exists()
        prior_text = target.read_text(encoding="utf-8", errors="replace") if prior_exists else ""
        replacements = 0
        if isinstance(old_text, str):
            if old_text:
                count = prior_text.count(old_text)
                if count != 1:
                    raise ValueError("apply_patch.old_text must match exactly once")
                next_text = prior_text.replace(old_text, new_text, 1)
                replacements = 1
            else:
                next_text = new_text
        else:
            next_text = new_text

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(next_text, encoding="utf-8")
        return {
            "path": write_receipt.files_written[0] if write_receipt.files_written else _workspace_rel_or_abs(self.workspace_root, target),
            "bytes_written": len(next_text.encode("utf-8")),
            "prior_exists": prior_exists,
            "replacements": replacements,
        }

    def _native_pipeline_run(
        self,
        *,
        tool_args: Dict[str, Any],
        exec_cwd: Path,
        files_read: List[str],
        files_written: List[str],
        observed_preimage_hashes: Dict[str, str],
        preimage_hashes: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        pipeline = tool_args.get("pipeline")
        if not isinstance(pipeline, list) or not pipeline:
            raise ValueError("pipeline_run.pipeline must be a non-empty array")
        if len(pipeline) > 16:
            raise ValueError("pipeline_run.pipeline must not exceed 16 stages")

        stdin_text = tool_args.get("stdin_text")
        if stdin_text is not None and not isinstance(stdin_text, str):
            raise ValueError("pipeline_run.stdin_text must be a string when provided")
        input_bytes = stdin_text.encode("utf-8") if isinstance(stdin_text, str) else b""

        stage_results: List[Dict[str, Any]] = []
        stderr_chunks: List[bytes] = []
        final_exit = 0
        for index, stage in enumerate(pipeline, start=1):
            if not isinstance(stage, dict):
                raise ValueError("pipeline_run.pipeline entries must be objects")
            stage_command = stage.get("command")
            argv = _normalize_command(stage_command)
            if _detect_shell_operators(command=argv, raw_command=stage_command):
                raise ValueError("pipeline_run stages must not contain shell operators")
            completed = self._runner(
                argv,
                cwd=exec_cwd,
                capture_output=True,
                check=False,
                input=input_bytes,
            )
            stdout_bytes = completed.stdout or b""
            stderr_bytes = completed.stderr or b""
            input_bytes = stdout_bytes
            stderr_chunks.append(stderr_bytes)
            exit_code = int(completed.returncode)
            stage_results.append(
                {
                    "index": index,
                    "command": argv,
                    "exit_code": exit_code,
                    "stdout_bytes": len(stdout_bytes),
                    "stderr_bytes": len(stderr_bytes),
                }
            )
            if exit_code != 0:
                final_exit = exit_code
                break

        final_stdout_bytes = input_bytes
        final_stderr_bytes = b"\n".join(chunk for chunk in stderr_chunks if chunk)

        stdout_path = tool_args.get("stdout_path")
        if stdout_path is not None:
            if not isinstance(stdout_path, str) or not stdout_path.strip():
                raise ValueError("pipeline_run.stdout_path must be a non-empty string when provided")
            output_target = self._resolve_native_path(
                exec_cwd=exec_cwd,
                path_value=stdout_path,
                for_write=True,
            )
            expected_hash = None
            if isinstance(preimage_hashes, dict):
                expected_hash = preimage_hashes.get(_workspace_rel_or_abs(self.workspace_root, output_target))
            write_receipt = self.safe_file_ops.prepare_write(output_target, expected_preimage_hash=expected_hash)
            files_read.extend(write_receipt.files_read)
            files_written.extend(write_receipt.files_written)
            observed_preimage_hashes.update(write_receipt.observed_preimage_hashes)
            output_target.parent.mkdir(parents=True, exist_ok=True)
            output_target.write_bytes(final_stdout_bytes)

        stderr_path = tool_args.get("stderr_path")
        if stderr_path is not None:
            if not isinstance(stderr_path, str) or not stderr_path.strip():
                raise ValueError("pipeline_run.stderr_path must be a non-empty string when provided")
            output_target = self._resolve_native_path(
                exec_cwd=exec_cwd,
                path_value=stderr_path,
                for_write=True,
            )
            expected_hash = None
            if isinstance(preimage_hashes, dict):
                expected_hash = preimage_hashes.get(_workspace_rel_or_abs(self.workspace_root, output_target))
            write_receipt = self.safe_file_ops.prepare_write(output_target, expected_preimage_hash=expected_hash)
            files_read.extend(write_receipt.files_read)
            files_written.extend(write_receipt.files_written)
            observed_preimage_hashes.update(write_receipt.observed_preimage_hashes)
            output_target.parent.mkdir(parents=True, exist_ok=True)
            output_target.write_bytes(final_stderr_bytes)

        return {
            "stage_count": len(stage_results),
            "final_exit_code": final_exit,
            "stages": stage_results,
            "stdout": final_stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": final_stderr_bytes.decode("utf-8", errors="replace"),
        }

    def _resolve_native_path(
        self,
        *,
        exec_cwd: Path,
        path_value: Any,
        for_write: bool = False,
        require_exists: bool = False,
    ) -> Path:
        if not isinstance(path_value, str) or not path_value.strip():
            raise ValueError("tool path argument must be a non-empty string")
        requested = Path(path_value.strip())
        candidate = requested if requested.is_absolute() else exec_cwd / requested
        resolved = resolve_sandboxed_path_for_op(
            self.workspace_root,
            candidate,
            for_write=for_write,
            artifact_store_root=self.artifact_store.root,
        )
        if require_exists and not resolved.exists():
            raise FileNotFoundError(f"Missing path: {resolved.as_posix()}")
        return resolved

    def _log_tool_deny(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timestamp: str,
        cwd: Path,
        deny_reason_code: str,
        risk_class: str,
        plan_id: Optional[str],
        plan_version_id: Optional[int],
        plan_step_id: Optional[str],
        files_read: Optional[List[str]] = None,
        files_written: Optional[List[str]] = None,
        expected_preimage_hash: Optional[str] = None,
        observed_preimage_hash: Optional[str] = None,
        re_read_required: bool = False,
        observed_workspace_hash_before: Optional[str] = None,
        attempted_action_fingerprint: Optional[str] = None,
        evidence_counter_override: Optional[int] = None,
        extra_event_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        stdout_meta = {
            "truncated": False,
            "size_bytes": 0,
            "captured_bytes": 0,
            "unknown": True,
        }
        stderr_meta = {
            "truncated": False,
            "size_bytes": 0,
            "captured_bytes": 0,
            "unknown": True,
        }
        stdout_artifact = self.artifact_store.put_bytes(b"", content_type="text/plain")
        stderr_artifact = self.artifact_store.put_bytes(b"", content_type="text/plain")
        assistant_note = _extract_assistant_note(tool_args)
        fingerprint = attempted_action_fingerprint or _attempted_action_fingerprint(
            tool_name=tool_name,
            tool_args=tool_args,
            cwd=cwd,
        )
        payload: Dict[str, Any] = {
            "event_type": "tool_call_blocked",
            "timestamp": timestamp,
            "cwd": cwd.as_posix(),
            "tool_name": tool_name,
            "tool_args": tool_args,
            "assistant_note": assistant_note,
            "deny_reason_code": deny_reason_code,
            "attempted_action_fingerprint": fingerprint,
            "risk_class": risk_class,
            "plan_id": plan_id,
            "plan_version_id": plan_version_id,
            "plan_step_id": plan_step_id,
            "exit_code": None,
            "files_read": files_read or [],
            "files_written": files_written or [],
            "artifact_refs": [stdout_artifact.artifact_id, stderr_artifact.artifact_id],
            "truncation": {"stdout": stdout_meta, "stderr": stderr_meta},
            "stdout_ref": stdout_artifact.artifact_id,
            "stderr_ref": stderr_artifact.artifact_id,
            "truncation_flags": "UNKNOWN",
            "persisted_byte_counts": {"stdout": 0, "stderr": 0},
            "duration_ms": None,
            "expected_preimage_hash": expected_preimage_hash,
            "observed_preimage_hash": observed_preimage_hash,
            "re_read_required": re_read_required,
            "observed_workspace_hash_before": observed_workspace_hash_before,
            "side_effects": [],
            "side_effect_scope": "WORKSPACE_LOCAL",
            "reversibility": "UNKNOWN",
            "resolved_cwd": cwd.as_posix(),
            "tool_summary": _build_tool_receipt_summary(
                tool_name=tool_name,
                exit_code=None,
                duration_ms=None,
                stdout_bytes=b"",
                stderr_bytes=b"",
                truncation={"stdout": stdout_meta, "stderr": stderr_meta},
                assistant_note=assistant_note,
                command_args=tool_args.get("command"),
            ),
        }
        if extra_event_fields:
            payload.update(extra_event_fields)
        event = self.event_log.append_event(payload)
        self._retry_tracker.record_failure(
            fingerprint=fingerprint,
            workspace_hash=observed_workspace_hash_before,
            evidence_counter=evidence_counter_override
            if isinstance(evidence_counter_override, int) and evidence_counter_override >= 0
            else len(self.event_log.events),
            plan_version_id=str(plan_version_id) if plan_version_id is not None else None,
            approval_counter=getattr(self.governance_gate, "approval_counter", 0),
        )
        return event

    def _log_retry_deny(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timestamp: str,
        cwd: Path,
        deny_reason_code: str,
        attempted_action_fingerprint: str,
        risk_class: str,
        plan_id: Optional[str],
        plan_version_id: Optional[int],
        plan_step_id: Optional[str],
        observed_workspace_hash_before: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.event_log.append_event(
            {
                "event_type": "RETRY_DENIED",
                "timestamp": timestamp,
                "cwd": cwd.as_posix(),
                "tool_name": tool_name,
                "tool_args": tool_args,
                "deny_reason_code": deny_reason_code,
                "attempted_action_fingerprint": attempted_action_fingerprint,
                "risk_class": risk_class,
                "plan_id": plan_id,
                "plan_version_id": plan_version_id,
                "plan_step_id": plan_step_id,
                "observed_workspace_hash_before": observed_workspace_hash_before,
            }
        )

    def _script_allowlist_hashes(self) -> set[str]:
        configured = getattr(self.policy_config, "script_allowlist_hashes", None)
        if isinstance(configured, (set, frozenset)):
            return {str(item) for item in configured if str(item)}
        if isinstance(configured, list):
            return {str(item) for item in configured if str(item)}
        if isinstance(configured, str):
            return {item.strip() for item in configured.split(",") if item.strip()}
        return set()

    def _should_enforce_script_allowlist(self, tool_args: Dict[str, Any]) -> bool:
        command = tool_args.get("command")
        if not isinstance(command, list) or not command:
            return False
        first = str(command[0]).lower()
        is_interpreter = first in {"python", "python3", "node", "ruby", "perl", "bash", "sh", "zsh"}
        if not is_interpreter:
            return False

        enforce_always = bool(getattr(self.policy_config, "enforce_script_allowlist", False))
        if enforce_always:
            return True

        # §7.6: interpreter exception is only meaningful when network is disabled.
        return not bool(getattr(self.policy_config, "network_enabled", True))

    def _extract_script_content(self, tool_args: Dict[str, Any], cwd: Path) -> Optional[str]:
        command = tool_args.get("command")
        if not isinstance(command, list) or not command:
            return None

        tokens = [str(item) for item in command]
        if "-c" in tokens:
            idx = tokens.index("-c")
            if idx + 1 < len(tokens):
                return tokens[idx + 1]
            return None

        if len(tokens) >= 2 and tokens[1].endswith(".py"):
            candidate = Path(tokens[1])
            script_path = candidate if candidate.is_absolute() else cwd / candidate
            try:
                resolved = script_path.resolve(strict=True)
            except FileNotFoundError:
                return None
            try:
                resolved.relative_to(self.workspace_root)
            except ValueError:
                return None
            return resolved.read_text(encoding="utf-8")

        return None


def _normalize_readonly_run(canonical_tool_args: Dict[str, Any]) -> Dict[str, Any]:
    from_payload = {
        "from_tool_name": "run",
        "from_tool_args": canonical_tool_args,
    }
    command = canonical_tool_args.get("command")
    if not isinstance(command, list) or not command:
        payload = dict(from_payload)
        payload.update({"applied": False, "reason_code": "RUN_NOT_ARGV_LIST"})
        return payload

    argv = [str(item) for item in command if str(item)]
    if not argv:
        payload = dict(from_payload)
        payload.update({"applied": False, "reason_code": "RUN_NOT_ARGV_LIST"})
        return payload

    command_name = Path(argv[0]).name.lower()
    if command_name == "ls":
        parsed = _normalize_run_ls(argv)
        if parsed is not None:
            payload = dict(from_payload)
            payload.update(
                {
                    "applied": True,
                    "reason_code": "RUN_LS_TO_LIST_DIR",
                    "to_tool_name": "list_dir",
                    "to_tool_args": parsed,
                }
            )
            return payload
        payload = dict(from_payload)
        payload.update({"applied": False, "reason_code": "RUN_LS_AMBIGUOUS"})
        return payload

    if command_name == "cat":
        parsed = _normalize_run_cat(argv)
        if parsed is not None:
            payload = dict(from_payload)
            payload.update(
                {
                    "applied": True,
                    "reason_code": "RUN_CAT_TO_READ_FILE",
                    "to_tool_name": "read_file",
                    "to_tool_args": parsed,
                }
            )
            return payload
        payload = dict(from_payload)
        payload.update({"applied": False, "reason_code": "RUN_CAT_AMBIGUOUS"})
        return payload

    if command_name == "rg":
        parsed = _normalize_run_rg(argv)
        if parsed is not None:
            payload = dict(from_payload)
            payload.update(
                {
                    "applied": True,
                    "reason_code": "RUN_RG_TO_SEARCH_FILES",
                    "to_tool_name": "search_files",
                    "to_tool_args": parsed,
                }
            )
            return payload
        payload = dict(from_payload)
        payload.update({"applied": False, "reason_code": "RUN_RG_AMBIGUOUS"})
        return payload

    if command_name == "find":
        parsed = _normalize_run_find(argv)
        if parsed is not None:
            payload = dict(from_payload)
            payload.update(
                {
                    "applied": True,
                    "reason_code": "RUN_FIND_TO_LIST_DIR",
                    "to_tool_name": "list_dir",
                    "to_tool_args": parsed,
                }
            )
            return payload
        payload = dict(from_payload)
        payload.update({"applied": False, "reason_code": "RUN_FIND_AMBIGUOUS"})
        return payload

    payload = dict(from_payload)
    payload.update({"applied": False, "reason_code": "RUN_NO_SAFE_NORMALIZATION"})
    return payload


def _normalize_run_ls(argv: List[str]) -> Optional[Dict[str, Any]]:
    if len(argv) < 1:
        return None
    include_all = False
    long = False
    path: Optional[str] = None
    seen_non_flag = False
    for token in argv[1:]:
        if token == "--":
            seen_non_flag = True
            continue
        if not seen_non_flag and token.startswith("-") and token != "-":
            for ch in token[1:]:
                if ch == "a":
                    include_all = True
                elif ch == "l":
                    long = True
                else:
                    return None
            continue
        if path is not None:
            return None
        path = token
        seen_non_flag = True
    return {
        "path": path or ".",
        "all": include_all,
        "long": long,
    }


def _normalize_run_cat(argv: List[str]) -> Optional[Dict[str, Any]]:
    if len(argv) != 2:
        return None
    path = argv[1]
    if not path or path.startswith("-"):
        return None
    return {"path": path}


def _normalize_run_rg(argv: List[str]) -> Optional[Dict[str, Any]]:
    if len(argv) not in {2, 3}:
        return None
    pattern = argv[1]
    if not pattern or pattern.startswith("-"):
        return None
    if len(argv) == 3:
        path = argv[2]
        if not path or path.startswith("-"):
            return None
    else:
        path = "."
    return {"pattern": pattern, "path": path}


def _normalize_run_find(argv: List[str]) -> Optional[Dict[str, Any]]:
    if len(argv) == 4 and argv[2] == "-name":
        path = argv[1]
        glob = argv[3]
    elif len(argv) == 3 and argv[1] == "-name":
        path = "."
        glob = argv[2]
    else:
        return None
    if not path or not glob:
        return None
    return {
        "path": path,
        "recursive": True,
        "glob": glob,
        "all": True,
    }


def _canonicalize_tool_args(tool_args: Dict[str, Any]) -> Dict[str, Any]:
    canonical = canonical_json_bytes(tool_args)
    loaded = json.loads(canonical.decode("utf-8"))
    if not isinstance(loaded, dict) or not loaded:
        raise ValueError("tool_args canonicalization failed")
    return loaded


def _attempted_action_fingerprint(*, tool_name: str, tool_args: Dict[str, Any], cwd: Path) -> str:
    return hash_canonical_json(
        {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "cwd": cwd.as_posix(),
        }
    )


def _shell_operator_fingerprint(*, tool_name: str, shell_operators: List[str], cwd: Path) -> str:
    return hash_canonical_json(
        {
            "tool_name": tool_name,
            "shell_operators": sorted(set(str(item) for item in shell_operators)),
            "cwd": cwd.as_posix(),
        }
    )


_SHELL_OPERATOR_TOKENS = ("&&", "||", "|", ">>", ">", "<<", "<", ";")


def _normalize_command(command: Any) -> List[str]:
    if isinstance(command, list) and command:
        return [str(item) for item in command]
    if isinstance(command, str):
        command_text = command.strip()
        if not command_text:
            raise ValueError("tool_args.command must be a non-empty string or list")
        try:
            parsed = shlex.split(command_text)
        except ValueError as exc:
            raise ValueError(f"tool_args.command could not be parsed: {exc}") from exc
        if not parsed:
            raise ValueError("tool_args.command must be a non-empty string or list")
        return [str(item) for item in parsed]
    raise ValueError("tool_args.command must be a non-empty string or list")


def _stringify_command(raw_command: Any, normalized_command: List[str]) -> str:
    if isinstance(raw_command, str) and raw_command.strip():
        return raw_command.strip()
    return " ".join(str(item) for item in normalized_command)


def _detect_shell_operators(*, command: List[str], raw_command: Any) -> List[str]:
    detected: List[str] = []
    for token in command:
        if token in _SHELL_OPERATOR_TOKENS and token not in detected:
            detected.append(token)

    if isinstance(raw_command, str):
        raw_text = raw_command
        for operator in _SHELL_OPERATOR_TOKENS:
            if operator in raw_text and operator not in detected:
                detected.append(operator)
    return detected


def _successful_tool_call_count(events: List[Dict[str, Any]]) -> int:
    count = 0
    for event in events:
        if str(event.get("event_type", "")).lower() != "tool_call":
            continue
        exit_code = event.get("exit_code")
        if isinstance(exit_code, int) and exit_code == 0:
            count += 1
    return count


def _has_plan_linkage(*, plan_id: Optional[str], plan_version_id: Optional[int], plan_step_id: Optional[str]) -> bool:
    if not isinstance(plan_id, str) or not plan_id.strip():
        return False
    if not isinstance(plan_version_id, int):
        return False
    if not isinstance(plan_step_id, str) or not plan_step_id.strip():
        return False
    return True


def _truncation_flags(stdout_meta: Dict[str, Any], stderr_meta: Dict[str, Any]) -> str:
    stdout_unknown = bool(stdout_meta.get("unknown"))
    stderr_unknown = bool(stderr_meta.get("unknown"))
    if stdout_unknown or stderr_unknown:
        return "UNKNOWN"

    stdout_truncated = bool(stdout_meta.get("truncated"))
    stderr_truncated = bool(stderr_meta.get("truncated"))
    if stdout_truncated and stderr_truncated:
        return "BOTH_TRUNCATED"
    if stdout_truncated:
        return "STDOUT_TRUNCATED"
    if stderr_truncated:
        return "STDERR_TRUNCATED"
    return "NONE"


def _extract_assistant_note(tool_args: Dict[str, Any]) -> Optional[str]:
    for key in ("assistant_note", "rationale"):
        value = tool_args.get(key)
        if isinstance(value, str):
            cleaned = _normalize_summary_text(value)
            if cleaned:
                return cleaned[:_ASSISTANT_NOTE_MAX_CHARS]
    return None


def _build_tool_receipt_summary(
    *,
    tool_name: str,
    exit_code: Optional[int | str],
    duration_ms: Optional[int],
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    truncation: Dict[str, Dict[str, Any]],
    assistant_note: Optional[str],
    command_args: Optional[Any] = None,
) -> Dict[str, Any]:
    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    stdout_lines = [_normalize_summary_text(line) for line in stdout_text.splitlines()]
    stderr_lines = [_normalize_summary_text(line) for line in stderr_text.splitlines()]

    non_empty_stdout = [line for line in stdout_lines if line]
    stdout_tail = non_empty_stdout[-_TOOL_SUMMARY_STDOUT_TAIL_LINES :]
    key_lines = _extract_key_lines(stderr_lines=stderr_lines, stdout_lines=stdout_lines)
    stderr_excerpt = _truncate_summary_text(
        " ".join(line for line in stderr_lines if line),
        _TOOL_SUMMARY_STDERR_EXCERPT_CHARS,
    )

    # Build bounded command synopsis for model visibility.
    command_synopsis = _command_synopsis(command_args)

    summary: Dict[str, Any] = {
        "tool_name": str(tool_name),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "stdout_line_count": len(stdout_lines),
        "stderr_line_count": len(stderr_lines),
        "stderr_excerpt": stderr_excerpt,
        "key_lines": key_lines,
        "stdout_tail": stdout_tail,
        "truncation_flags": _truncation_flags(
            truncation.get("stdout", {}),
            truncation.get("stderr", {}),
        ),
    }
    if command_synopsis:
        summary["command_synopsis"] = command_synopsis
    if assistant_note:
        summary["assistant_note"] = assistant_note
    return summary


def _command_synopsis(command_args: Optional[Any]) -> str:
    if isinstance(command_args, list) and command_args:
        raw = " ".join(str(a) for a in command_args)
    elif isinstance(command_args, str):
        raw = command_args.strip()
        if not raw:
            return ""
        try:
            parsed = shlex.split(raw)
        except ValueError:
            parsed = []
        if parsed:
            raw = " ".join(str(a) for a in parsed)
    else:
        return ""

    normalized = _normalize_summary_text(raw)
    if not normalized:
        return ""
    if len(normalized) <= 120:
        return normalized
    return normalized[:120] + "..."


def _extract_key_lines(*, stderr_lines: List[str], stdout_lines: List[str]) -> List[str]:
    keywords = ("error", "failed", "fail", "warning", "exception", "traceback", "timeout", "denied")
    lines: List[str] = []
    for candidate in stderr_lines + stdout_lines:
        if not candidate:
            continue
        lowered = candidate.lower()
        if any(keyword in lowered for keyword in keywords):
            lines.append(candidate)
        if len(lines) >= _TOOL_SUMMARY_KEY_LINES:
            break
    if lines:
        return lines

    fallback: List[str] = []
    for source in (stderr_lines, stdout_lines):
        for candidate in reversed(source):
            if candidate:
                fallback.append(candidate)
                break
    return fallback[:_TOOL_SUMMARY_KEY_LINES]


def _normalize_summary_text(text: str) -> str:
    collapsed = " ".join(text.strip().split())
    return _truncate_summary_text(collapsed, _TOOL_SUMMARY_LINE_CHARS)


def _truncate_summary_text(text: str, limit: int) -> str:
    sanitized = (
        str(text)
        .replace("<<SECTION:", "<SECTION:")
        .replace("[UNTRUSTED_BASE64_START]", "[UNTRUSTED_B64_START]")
        .replace("[UNTRUSTED_BASE64_END]", "[UNTRUSTED_B64_END]")
    )
    if len(sanitized) <= limit:
        return sanitized
    return sanitized[: max(0, limit - 1)] + "…"


def _workspace_rel_or_abs(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _to_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
