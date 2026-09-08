from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import posixpath
from typing import TYPE_CHECKING, Any, Mapping

from .raw_task_authority import (
    build_binding,
    task_contract_payload,
    validate_solver_messages,
)

if TYPE_CHECKING:
    from .proof_contract import CompiledProofRequirement
    from .task_contract import TaskContract


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True)


def normalize_relpath(path: str, workspace_root: str = "") -> str:
    """Normalize one workspace-local path and reject lexical escapes.

    The return value is consumed by receipt, state, and executor surfaces, so
    it cannot silently turn ``../outside`` or an unrelated absolute path into
    something that merely *looks* workspace-relative.  Executor resolvers
    still perform their own realpath/symlink checks; this is the shared
    lexical boundary before any receipt is emitted.
    """
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        return ""
    root = str(workspace_root or "").strip().replace("\\", "/").rstrip("/")
    if root and raw == root:
        return "."
    if root and raw.startswith(root + "/"):
        # Strip the root exactly once, while allowing redundant separators at
        # that one boundary (for example a Windows-normalized ``/app//src``).
        raw = raw[len(root) :].lstrip("/")
    elif raw == "/app" or raw.startswith("/app/"):
        # Task contracts conventionally speak in the container's /app
        # namespace even when deterministic tests or an in-process executor
        # bind that namespace to a temporary physical workspace. Treat this
        # one declared virtual root as an alias, but still run the resulting
        # path through the traversal check below.
        raw = raw[len("/app") :].lstrip("/")
    elif raw.startswith("/"):
        # An unrelated absolute path belongs to neither the declared physical
        # workspace nor the task's canonical /app namespace.
        raise ValueError(f"path is outside declared workspace: {path!r}")
    elif not root:
        # Legacy callers without a declared workspace historically used /app.
        # Once a workspace root has been applied, never strip another "app/"
        # segment: /app/app/X is a real workspace-relative path app/X.
        if raw.startswith("/app/"):
            raw = raw[5:]
        elif raw.startswith("app/"):
            raw = raw[4:]
        elif raw in ("/app", "app"):
            return "."
    normalized = posixpath.normpath(raw)
    if normalized == "/":
        return "."
    if normalized == ".." or normalized.startswith("../"):
        raise ValueError(f"path escapes declared workspace: {path!r}")
    if normalized.startswith("/"):
        raise ValueError(f"path is outside declared workspace: {path!r}")
    return normalized or "."


SOLVER_TURN_PROTOCOLS = frozenset({"pcr_v0"})


ACTION_SCHEMA: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("read_file", ("path",)),
    ("read_file_page", ("path",)),
    ("read_output", ("handle",)),
    ("grep_output", ("handle", "pattern")),
    ("write_file", ("path", "content")),
    ("run_command", ("command",)),
    ("start_terminal_session", ("session_name", "command")),
    ("terminal_send", ("session_id", "data")),
    ("terminal_read", ("session_id",)),
    ("terminal_wait", ("session_id",)),
    ("terminal_interrupt", ("session_id",)),
    ("terminal_close", ("session_id",)),
    ("bootstrap_acquire", ("manager",)),
    ("launch_process", ("service_name", "command")),
    ("start_job", ("service_name", "command")),
    ("probe_job", ("target",)),
    ("probe_service", ("target",)),
    ("stop_process", ("target",)),
    ("inspect_artifact", ("path", "mode")),
    ("computer_action", ("actions",)),
    ("register_candidate", ("candidate_id", "summary")),
    ("run_experiment", ("candidate_id", "command")),
    ("query_history", ("query",)),
    ("query_artifact_history", ("path",)),
    ("inspect_diff", ("path",)),
    # A Solver may truthfully report that the task is incomplete or blocked
    # without asserting that the harness needs to change.  The required fields
    # bind that report to observed reality; any recovery suggestion is optional
    # and never a precondition for this non-success route.
    ("report_blocker", ("blocker", "evidence")),
)

ALWAYS_AVAILABLE_ACTION_KINDS = frozenset({
    "query_history",
    "query_artifact_history",
    "inspect_diff",
    "report_blocker",
    # Information-retrieval primitives: full outputs and files must always be
    # retrievable by handle regardless of the configured tool subset -- no
    # configuration may reintroduce information destruction.
    "read_output",
    "grep_output",
    "read_file_page",
})
KERNEL_INTERNAL_ACTION_KINDS = frozenset({"register_candidate", "run_experiment"})

# Only these operations may be children of one observation batch.  No shell
# command, HTTP request, check execution, process action, write, or unknown
# helper is assumed read-only merely from its name.
CERTIFIED_READ_ONLY_ACTION_KINDS = frozenset({
    "read_file",
    "read_file_page",
    "read_output",
    "grep_output",
    "query_history",
    "query_artifact_history",
    "inspect_diff",
    "inspect_artifact",
    "probe_service",
    "probe_job",
})

# One generic action surface is owned by the kernel.  Architect output may
# describe workflow and evidence, but it cannot add, remove, or select these
# actions.  Keep this derived from the canonical action schema so prompts,
# compilation, and receipts cannot drift into separate tool inventories.
FIXED_KERNEL_TOOL_SURFACE: tuple[str, ...] = tuple(
    name for name, _args in ACTION_SCHEMA
    if name not in KERNEL_INTERNAL_ACTION_KINDS
)


def action_schema_for_kinds(kinds: set[str] | frozenset[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((name, args) for name, args in ACTION_SCHEMA if name in kinds)


@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str
    summary: str
    available: bool = True
    tool_names: tuple[str, ...] = ()
    cost_hint: str = "cheap"


@dataclass(frozen=True)
class EnvMap:
    task_prompt: str
    workspace_root: str
    visible_files: tuple[str, ...] = ()
    visible_dirs: tuple[str, ...] = ()
    capabilities: Mapping[str, CapabilityDescriptor] = field(default_factory=dict)
    services: Mapping[str, Any] = field(default_factory=dict)
    resource_limits: Mapping[str, Any] = field(default_factory=dict)
    permissions: Mapping[str, Any] = field(default_factory=dict)
    grader_hints: Mapping[str, Any] = field(default_factory=dict)
    interactive_features: Mapping[str, Any] = field(default_factory=dict)
    task_metadata: Mapping[str, Any] = field(default_factory=dict)
    network_scope: str = "unknown"
    file_tree: str = ""
    file_map_summary: Mapping[str, Any] = field(default_factory=dict)

    def digest(self) -> str:
        payload = {
            "workspace_root": self.workspace_root,
            "visible_files": sorted(normalize_relpath(path, self.workspace_root) for path in self.visible_files),
            "visible_dirs": sorted(normalize_relpath(path, self.workspace_root) for path in self.visible_dirs),
            "capabilities": {
                key: asdict(self.capabilities[key]) for key in sorted(self.capabilities)
            },
            "services": dict(self.services),
            "resource_limits": dict(self.resource_limits),
            "permissions": dict(self.permissions),
            "grader_hints": dict(self.grader_hints),
            "interactive_features": dict(self.interactive_features),
            "task_metadata": dict(self.task_metadata),
            "network_scope": self.network_scope,
            "file_tree": self.file_tree,
            "file_map_summary": dict(self.file_map_summary),
        }
        return sha256(stable_json(payload).encode("utf-8")).hexdigest()[:16]

    def capability_index(self) -> tuple[dict[str, Any], ...]:
        items = sorted(self.capabilities.values(), key=lambda cap: cap.capability_id)
        return tuple(
            {
                "capability_id": cap.capability_id,
                "summary": cap.summary,
                "available": cap.available,
                "cost_hint": cap.cost_hint,
                "tool_names": list(cap.tool_names),
            }
            for cap in items
        )

    def compact_summary(self) -> dict[str, Any]:
        return {
            "workspace_root": self.workspace_root,
            "visible_file_count": len(self.visible_files),
            "visible_dir_count": len(self.visible_dirs),
            "network_scope": self.network_scope,
            "capabilities": [cap["capability_id"] for cap in self.capability_index()],
            "environment_probe_available": bool(self.task_metadata.get("environment_probe")),
            "file_tree_available": bool(self.file_tree),
        }


@dataclass(frozen=True)
class DeliverableSpec:
    path: str
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class ServiceRequirement:
    name: str
    port: int | None = None
    must_be_live: bool = True
    proof_kind: str = "probe"


@dataclass(frozen=True)
class MetricThreshold:
    name: str
    comparator: str
    target: float | int | str


@dataclass(frozen=True)
class ProofObligation:
    obligation_id: str
    kind: str
    description: str
    target: str = ""


@dataclass(frozen=True)
class ObjectiveGraph:
    deliverables: tuple[DeliverableSpec, ...] = ()
    protected_paths: tuple[str, ...] = ()
    allowed_edit_roots: tuple[str, ...] = (".",)
    service_requirements: tuple[ServiceRequirement, ...] = ()
    package_requirements: tuple[str, ...] = ()
    thresholds: tuple[MetricThreshold, ...] = ()
    output_schema: Mapping[str, str] = field(default_factory=dict)
    output_schema_target: str = ""
    obligations: tuple[ProofObligation, ...] = ()

    def summary(self) -> str:
        return stable_json(
            {
                "deliverables": [asdict(item) for item in self.deliverables],
                "protected_paths": list(self.protected_paths),
                "allowed_edit_roots": list(self.allowed_edit_roots),
                "service_requirements": [asdict(item) for item in self.service_requirements],
                "package_requirements": list(self.package_requirements),
                "thresholds": [asdict(item) for item in self.thresholds],
                "output_schema": dict(self.output_schema),
                "output_schema_target": self.output_schema_target,
            }
        )


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    label: str
    command: str
    origin: str
    authoritative: bool = True


@dataclass(frozen=True)
class EvalIndex:
    checks: tuple[CheckSpec, ...] = ()

    def authoritative_checks(self) -> tuple[CheckSpec, ...]:
        return tuple(check for check in self.checks if check.authoritative)

    def get(self, check_id: str) -> CheckSpec | None:
        for check in self.checks:
            if check.check_id == check_id:
                return check
        return None

    def summary(self) -> str:
        return stable_json([asdict(check) for check in self.checks])


@dataclass(frozen=True)
class ContextRecipeRecent:
    selector: str
    count: int


@dataclass(frozen=True)
class ContextRecipe:
    always_include: tuple[str, ...] = ()
    include_recent: tuple[ContextRecipeRecent, ...] = ()
    include_last_failure: int = 0
    preserve_exact: tuple[str, ...] = ()
    make_queryable_not_inline: tuple[str, ...] = ()
    unsupported_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextPolicy:
    mode: str = "default_bounded"
    include_sections: tuple[str, ...] = (
        "open_obligations",
        "obligation_status",
        "monitor_alerts",
        "live_processes",
        "recent_progress",
        "failure_clusters",
        "artifacts_present",
        "candidate_leaderboard",
        "installed_capabilities",
        "planned_checks",
        "pending_checks",
        "command_results",
    )
    max_recent_receipts: int = 8
    max_failure_clusters: int = 4
    max_alerts: int = 4
    max_candidates: int = 3
    # Advisory working-context threshold for mechanical externalisation only.
    # Production must never terminate a task because a local coarse token
    # estimator thinks the packet is large; the provider owns the real context
    # window. Keep the threshold high enough for 200k-class continuity and let
    # exact retrieval handles carry cold evidence.
    model_context_window_tokens: int = 200_000
    compression_trigger_ratio: float = 1.0
    recipe: ContextRecipe | None = None


@dataclass(frozen=True)
class ProcessPolicy:
    mode: str = "stateless_shell"
    protect_candidates: bool = False
    require_fresh_probe: bool = False
    destructive_restart_requires_replacement: bool = True


@dataclass(frozen=True)
class HelperToolPolicy:
    allow_creation: bool = True
    require_smoke_test: bool = True
    trust_for_completion: bool = False
    task_local_dir: str = ".aether/tools"


@dataclass(frozen=True)
class BootstrapPolicy:
    allow_acquisition: bool = True
    allowed_managers: tuple[str, ...] = (
        "apt",
        "pip",
        "uv",
        "npm",
        "cargo",
        "opam",
        "git",
        "wget",
        "curl",
        "hf",
    )
    refresh_env_after_success: bool = True


@dataclass(frozen=True)
class CompletionPolicy:
    require_authoritative_check: bool = True
    allow_evidence_fallback: bool = True
    require_all_obligations: bool = True
    require_recent_progress: bool = True
    require_clean_integrity: bool = True


@dataclass(frozen=True)
class ModelVerifierPolicy:
    enabled: bool = True
    runs_on: tuple[str, ...] = (
        "solver_submit",
    )


@dataclass(frozen=True)
class RefusalPolicy:
    allowed_local_categories: tuple[str, ...] = ()
    forbid_external_targets: bool = True


@dataclass(frozen=True)
class CompiledRuntime:
    task_prompt: str
    env_digest: str
    objective_graph: ObjectiveGraph
    eval_index: EvalIndex
    selected_capabilities: tuple[CapabilityDescriptor, ...]
    stable_prefix_sections: tuple[tuple[str, str], ...]
    context_policy: ContextPolicy
    process_policy: ProcessPolicy
    helper_tool_policy: HelperToolPolicy
    bootstrap_policy: BootstrapPolicy
    completion_policy: CompletionPolicy
    refusal_policy: RefusalPolicy
    enforced_monitors: tuple[str, ...]
    check_plan_ids: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    model_verifier_policy: ModelVerifierPolicy = field(default_factory=ModelVerifierPolicy)
    solver_model_tier: str = "mini"
    verifier_model_tier: str = "mini"
    perception_model_tier: str = "vision"
    action_schema: tuple[tuple[str, tuple[str, ...]], ...] = ACTION_SCHEMA
    solver_identity_prompt: str = ""
    success_definition: str = ""
    local_verification_limits: tuple[str, ...] = ()
    verifier_identity_prompt: str = ""
    evidence_requirements: tuple[str, ...] = ()
    false_positive_risks: tuple[str, ...] = ()
    minimum_completion_evidence: tuple[str, ...] = ()
    re_derivable_claims: tuple[str, ...] = ()
    proof_contract: tuple[Mapping[str, Any], ...] = ()
    config_realization: Mapping[str, Any] = field(default_factory=dict)
    proof_requirements: tuple["CompiledProofRequirement", ...] = ()
    proof_requirements_identity: str = ""
    task_contract: "TaskContract | None" = None
    task_contract_identity: str = ""
    task_contract_payload_sha256: str = ""

    def __post_init__(self) -> None:
        payload = task_contract_payload(self)
        binding = build_binding(self.task_prompt, payload)
        expected = binding["contract_sha256"]
        if self.task_contract_payload_sha256 and self.task_contract_payload_sha256 != expected:
            raise ValueError("task contract payload hash does not match compiled task truth")
        object.__setattr__(self, "task_contract_payload_sha256", expected)

    def prefix_messages(self) -> list[dict[str, str]]:
        binding = build_binding(
            self.task_prompt,
            task_contract_payload(self),
        )
        messages = [
            {"role": "system", "content": f"[raw_user_task]\n{self.task_prompt}"},
            {
                "role": "system",
                "content": "[raw_task_binding]\n" + stable_json(binding),
            },
        ]
        messages.extend(
            {"role": "system", "content": f"[{section_name}]\n{section_body}"}
            for section_name, section_body in self.stable_prefix_sections
            if section_name not in {"task_prompt", "raw_user_task", "raw_task_binding"}
        )
        validate_solver_messages(
            messages,
            expected_raw_task=self.task_prompt,
            expected_contract_sha256=self.task_contract_payload_sha256,
        )
        return messages

    def selected_capability_ids(self) -> set[str]:
        return {cap.capability_id for cap in self.selected_capabilities}

    def planned_checks(self) -> tuple[CheckSpec, ...]:
        ordered: list[CheckSpec] = []
        for check_id in self.check_plan_ids:
            check = self.eval_index.get(check_id)
            if check is not None:
                ordered.append(check)
        return tuple(ordered)


@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    kind: str
    capability_id: str
    arguments: Mapping[str, Any]
    intent: str
    expected_observation: str
    if_fail_next: str
    candidate_id: str = ""
    track_as_proof: bool = False
    target: Mapping[str, Any] = field(default_factory=dict)

    def validate(
        self,
        action_schema: tuple[tuple[str, tuple[str, ...]], ...] = ACTION_SCHEMA,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.action_id.strip():
            errors.append("action_id is required")
        required = dict(action_schema).get(self.kind)
        if required is None:
            errors.append(f"unknown action kind: {self.kind}")
        else:
            missing = [name for name in required if name not in self.arguments]
            if missing:
                errors.append(f"{self.kind} missing required arguments: {', '.join(missing)}")
        if not isinstance(self.capability_id, str) or not self.capability_id.strip():
            errors.append("capability_id is required")
        return tuple(errors)


@dataclass(frozen=True)
class SolverTurn:
    kind: str
    summary: str
    actions: tuple[ActionRequest, ...] = ()
    requested_check_ids: tuple[str, ...] = ()
    claimed_artifacts: tuple[str, ...] = ()
    evidence_gap: str = ""
    claim: str = ""
    evidence_refs: tuple[str, ...] = ()

    def validate(
        self,
        action_schema: tuple[tuple[str, tuple[str, ...]], ...] = ACTION_SCHEMA,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if self.kind not in {"act", "submit_outcome", "finish_intent", "finish_outcome"}:
            errors.append(f"unknown turn kind: {self.kind}")
        if not self.summary.strip():
            errors.append("summary is required")
        if self.kind == "act" and len(self.actions) != 1:
            errors.append("act turns require exactly one action frontier")
        if self.kind != "act" and self.actions:
            errors.append(f"{self.kind} turns may not carry actions")
        if self.kind in {"submit_outcome", "finish_intent", "finish_outcome"}:
            if not self.claim.strip():
                errors.append("PCR completion turns require a non-empty claim")
            if not self.evidence_refs:
                errors.append("PCR completion turns require at least one evidence reference")
            elif any(not isinstance(item, str) or not item.strip() for item in self.evidence_refs):
                errors.append("PCR evidence references must be non-empty strings")
        for action in self.actions:
            errors.extend(action.validate(action_schema))
        return tuple(errors)
