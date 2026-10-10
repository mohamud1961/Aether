"""Harbor-facing runtime wiring for the canonical Aether-Next kernel."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import shlex
import threading
import time
from typing import Any, Mapping

from .model_profile import ModelProfile, PRODUCTION_PROFILE, require_provider_authorization


FRONTIER_ENDPOINT_ENV = PRODUCTION_PROFILE.endpoint_env
FRONTIER_DEPLOYMENT_ENV = PRODUCTION_PROFILE.deployment_env
FRONTIER_KEY_ENV = PRODUCTION_PROFILE.key_env
SEALED_TASK_ID_ENV = "AETHER_FIRST_SUBMIT_TASK_ID"
SEALED_RUN_ID_ENV = "AETHER_FIRST_SUBMIT_RUN_ID"
H1_REVIEW_ARM_ENV = "AETHER_RESEARCH_H1_REVIEW_ARM"
H1_MECHANICAL_ARM = "mechanical"
H1_SEMANTIC_ARM = "semantic"
H1_OFF_ARM = "off"
JUDGE_VERIFIER_ARM_ENV = "AETHER_RESEARCH_JUDGE_VERIFIER_ARM"
JUDGE_VERIFIER_CONTROL_ARM = "control"
JUDGE_VERIFIER_V3_TYPED_ARM = "v3_typed"
JUDGE_VERIFIER_MODEL_ENV = "AETHER_JUDGE_VERIFIER_MODEL"
JUDGE_VERIFIER_JOURNAL_ENV = "AETHER_JUDGE_VERIFIER_JOURNAL"
JUDGE_VERIFIER_MAX_CALLS_ENV = "AETHER_JUDGE_VERIFIER_MAX_CALLS"
JUDGE_VERIFIER_CAP_GBP_ENV = "AETHER_JUDGE_VERIFIER_CAP_GBP"
JUDGE_VERIFIER_INPUT_PRICE_ENV = "AETHER_JUDGE_VERIFIER_INPUT_GBP_PER_MILLION"
JUDGE_VERIFIER_TRANSPORT_ENV = "AETHER_JUDGE_VERIFIER_TRANSPORT"
JUDGE_VERIFIER_TRANSPORT_DIRECT = "http_direct_v1"
JUDGE_VERIFIER_TRANSPORT_FILE_BROKER = "file_broker_v1"
JUDGE_VERIFIER_BROKER_DIR_ENV = "AETHER_JUDGE_VERIFIER_BROKER_DIR"
JUDGE_VERIFIER_FROZEN_MODEL = "judge-1.13.0"
H2_WALLTIME_ARM_ENV = "AETHER_RESEARCH_H2_WALLTIME_VISIBILITY"
H2_CONTROL_ARM = "control"
H2_WALLTIME_ARM = "walltime"
H2_WALLTIME_STATUS_ARM = "walltime_status"
H3_SOLVER_REASONING_ARM_ENV = "AETHER_RESEARCH_H3_SOLVER_REASONING"
H3_CONTROL_ARM = "control"
H3_DISCRIMINATING_EXPERIMENT_ARM = "discriminating_experiment_v1"
H3_SOLVER_COMMITMENT_ARM = "commitment_v1"
H4_BOUNDARY_VERIFICATION_ARM_ENV = "AETHER_RESEARCH_H4_BOUNDARY_VERIFICATION"
H4_CONTROL_ARM = "control"
H4_BOUNDARY_VERIFICATION_ARM = "boundary_verification_v1"
P1_COMPLETION_DISPOSITION_ARM_ENV = "AETHER_RESEARCH_P1_COMPLETION_DISPOSITION"
P1_CONTROL_ARM = "control"
P1_COMPLETION_DISPOSITION_ARM = "completion_disposition_v1"
P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV = "AETHER_RESEARCH_P4_PROVIDER_FRONTIER_RECOVERY"
P4_CONTROL_ARM = "control"
P4_NO_TOOL_MAX_OUTPUT_ARM = "no_tool_max_output_v1"
SOLVER_PREFIX_RENDERER_ENV = "AETHER_RESEARCH_SOLVER_PREFIX_RENDERER"
SOLVER_PREFIX_RENDERER_CONTROL = "incumbent_context"
SOLVER_PREFIX_RENDERER_MINIMAL = "minimal_reality_loop_static_v1"
SOLVER_REALITY_TRANSPORT_ENV = "AETHER_RESEARCH_SOLVER_REALITY_TRANSPORT"
SOLVER_REALITY_TRANSPORT_CONTROL = "full_snapshot_control"
SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1 = "delta_only_v1"
SOLVER_HOSTED_TOOL_SEARCH_ENV = "AETHER_RESEARCH_SOLVER_HOSTED_TOOL_SEARCH"
SOLVER_HOSTED_TOOL_SEARCH_CONTROL = "control"
SOLVER_HOSTED_TOOL_SEARCH_V1 = "hosted_v1"
VERIFIER_ACTIVATION_CONTINUITY_ENV = "AETHER_RESEARCH_VERIFIER_ACTIVATION_CONTINUITY"
VERIFIER_ACTIVATION_CONTINUITY_CONTROL = "fresh_compact_control"
VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1 = "activation_previous_response_v1"
CONTEXT_CLEANUP_ENV = "AETHER_RESEARCH_CONTEXT_CLEANUP"
CONTEXT_CLEANUP_OFF = "off"
CONTEXT_CLEANUP_CONSERVATIVE_V1 = "conservative_v1"
SOLVER_LOOP_ENV = "AETHER_RESEARCH_SOLVER_LOOP"
SOLVER_LOOP_INCUMBENT = "incumbent"
SOLVER_LOOP_THIN = "thin"


def selected_h1_review_arm() -> str:
    """Return the explicit H1 research arm; production defaults to semantic review."""
    raw = str(os.environ.get(H1_REVIEW_ARM_ENV, H1_SEMANTIC_ARM) or H1_SEMANTIC_ARM).strip().lower()
    if raw not in {H1_SEMANTIC_ARM, H1_MECHANICAL_ARM, H1_OFF_ARM}:
        raise RuntimeError(
            f"{H1_REVIEW_ARM_ENV} must be {H1_SEMANTIC_ARM!r}, "
            f"{H1_MECHANICAL_ARM!r}, or {H1_OFF_ARM!r}, got {raw!r}"
        )
    return raw


def selected_judge_verifier_arm() -> str:
    """Return the explicit default-off Judge whole-Verifier research arm."""
    raw = str(
        os.environ.get(JUDGE_VERIFIER_ARM_ENV, JUDGE_VERIFIER_CONTROL_ARM)
        or JUDGE_VERIFIER_CONTROL_ARM
    ).strip().lower()
    allowed = {JUDGE_VERIFIER_CONTROL_ARM, JUDGE_VERIFIER_V3_TYPED_ARM}
    if raw not in allowed:
        raise RuntimeError(
            f"{JUDGE_VERIFIER_ARM_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def _required_judge_verifier_env(name: str) -> str:
    value = str(os.environ.get(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for the Judge V3 Verifier arm")
    return value


def build_selected_judge_v3_verifier() -> Any:
    """Construct the sealed V3 Judge Verifier; never used by default."""
    from .judge_verifier_policy import JudgeQuestionAdapter, TypedJudgeVerifierCallable

    model = _required_judge_verifier_env(JUDGE_VERIFIER_MODEL_ENV)
    if model != JUDGE_VERIFIER_FROZEN_MODEL:
        raise RuntimeError(
            f"{JUDGE_VERIFIER_MODEL_ENV} must equal frozen model "
            f"{JUDGE_VERIFIER_FROZEN_MODEL!r}, got {model!r}"
        )
    journal = Path(_required_judge_verifier_env(JUDGE_VERIFIER_JOURNAL_ENV))
    max_calls_text = _required_judge_verifier_env(JUDGE_VERIFIER_MAX_CALLS_ENV)
    try:
        max_calls = int(max_calls_text)
    except ValueError as exc:
        raise RuntimeError(
            f"{JUDGE_VERIFIER_MAX_CALLS_ENV} must be a positive integer"
        ) from exc
    if max_calls <= 0:
        raise RuntimeError(
            f"{JUDGE_VERIFIER_MAX_CALLS_ENV} must be a positive integer"
        )
    cap_gbp = _required_judge_verifier_env(JUDGE_VERIFIER_CAP_GBP_ENV)
    input_price = _required_judge_verifier_env(JUDGE_VERIFIER_INPUT_PRICE_ENV)

    transport_mode = str(
        os.environ.get(JUDGE_VERIFIER_TRANSPORT_ENV, JUDGE_VERIFIER_TRANSPORT_DIRECT)
        or JUDGE_VERIFIER_TRANSPORT_DIRECT
    ).strip().lower()
    if transport_mode == JUDGE_VERIFIER_TRANSPORT_DIRECT:
        from .providers.judge import HttpJudgeTransport

        transport = HttpJudgeTransport(
            model=model,
            journal=journal,
            max_calls=max_calls,
            cap_gbp=cap_gbp,
            input_gbp_per_million=input_price,
        )
    elif transport_mode == JUDGE_VERIFIER_TRANSPORT_FILE_BROKER:
        from .providers.judge_broker import FileBrokerEvaluator

        broker_dir = Path(_required_judge_verifier_env(JUDGE_VERIFIER_BROKER_DIR_ENV))
        transport = FileBrokerEvaluator(
            broker_dir=broker_dir,
            journal=journal,
            expected_result_model=model,
            max_calls=max_calls,
            cap_gbp=cap_gbp,
            input_gbp_per_million=input_price,
        )
    else:
        raise RuntimeError(
            f"{JUDGE_VERIFIER_TRANSPORT_ENV} must be one of "
            f"{[JUDGE_VERIFIER_TRANSPORT_DIRECT, JUDGE_VERIFIER_TRANSPORT_FILE_BROKER]!r}, "
            f"got {transport_mode!r}"
        )
    adapter = JudgeQuestionAdapter(transport, model=model)
    return TypedJudgeVerifierCallable(adapter)


def selected_h2_walltime_arm() -> str:
    """Return the default-off H2 research arm without changing production behavior."""
    raw = str(os.environ.get(H2_WALLTIME_ARM_ENV, H2_CONTROL_ARM) or H2_CONTROL_ARM).strip().lower()
    allowed = {H2_CONTROL_ARM, H2_WALLTIME_ARM, H2_WALLTIME_STATUS_ARM}
    if raw not in allowed:
        raise RuntimeError(
            f"{H2_WALLTIME_ARM_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_h3_solver_reasoning_mode(model_factory: Any) -> str:
    """Return the explicit default-off H3 Solver cognition treatment."""
    if model_factory is not build_selected_frontier_models:
        return H3_CONTROL_ARM
    raw = str(os.environ.get(H3_SOLVER_REASONING_ARM_ENV, H3_CONTROL_ARM) or H3_CONTROL_ARM).strip().lower()
    if raw not in {H3_CONTROL_ARM, H3_DISCRIMINATING_EXPERIMENT_ARM, H3_SOLVER_COMMITMENT_ARM}:
        raise RuntimeError(
            f"{H3_SOLVER_REASONING_ARM_ENV} must be one of "
            f"{sorted({H3_CONTROL_ARM, H3_DISCRIMINATING_EXPERIMENT_ARM, H3_SOLVER_COMMITMENT_ARM})!r}, got {raw!r}"
        )
    return raw


def selected_h4_boundary_verification_mode(model_factory: Any) -> str:
    """Return the explicit default-off H4 completion-boundary treatment."""
    if model_factory is not build_selected_frontier_models:
        return H4_CONTROL_ARM
    raw = str(
        os.environ.get(H4_BOUNDARY_VERIFICATION_ARM_ENV, H4_CONTROL_ARM)
        or H4_CONTROL_ARM
    ).strip().lower()
    allowed = {H4_CONTROL_ARM, H4_BOUNDARY_VERIFICATION_ARM}
    if raw not in allowed:
        raise RuntimeError(
            f"{H4_BOUNDARY_VERIFICATION_ARM_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_p1_completion_disposition_mode(model_factory: Any) -> str:
    """Return the explicit default-off final completion-finding disposition treatment."""
    if model_factory is not build_selected_frontier_models:
        return P1_CONTROL_ARM
    raw = str(
        os.environ.get(P1_COMPLETION_DISPOSITION_ARM_ENV, P1_CONTROL_ARM)
        or P1_CONTROL_ARM
    ).strip().lower()
    allowed = {P1_CONTROL_ARM, P1_COMPLETION_DISPOSITION_ARM}
    if raw not in allowed:
        raise RuntimeError(
            f"{P1_COMPLETION_DISPOSITION_ARM_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_p4_provider_frontier_recovery_mode(model_factory: Any) -> str:
    """Return the explicit default-off P4 mechanical provider recovery arm."""
    if model_factory is not build_selected_frontier_models:
        return P4_CONTROL_ARM
    raw = str(
        os.environ.get(P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV, P4_CONTROL_ARM)
        or P4_CONTROL_ARM
    ).strip().lower()
    allowed = {P4_CONTROL_ARM, P4_NO_TOOL_MAX_OUTPUT_ARM}
    if raw not in allowed:
        raise RuntimeError(
            f"{P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV} must be one of "
            f"{sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_solver_prefix_renderer(model_factory: Any) -> str:
    """Return the explicit default-off Solver static-prefix research arm."""
    if model_factory is not build_selected_frontier_models:
        return SOLVER_PREFIX_RENDERER_CONTROL
    raw = str(
        os.environ.get(SOLVER_PREFIX_RENDERER_ENV, SOLVER_PREFIX_RENDERER_CONTROL)
        or SOLVER_PREFIX_RENDERER_CONTROL
    ).strip().lower()
    allowed = {SOLVER_PREFIX_RENDERER_CONTROL, SOLVER_PREFIX_RENDERER_MINIMAL}
    if raw not in allowed:
        raise RuntimeError(
            f"{SOLVER_PREFIX_RENDERER_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_solver_reality_transport_mode(model_factory: Any) -> str:
    """Return the explicit default-off Solver current-state transport treatment."""
    if model_factory is not build_selected_frontier_models:
        return SOLVER_REALITY_TRANSPORT_CONTROL
    raw = str(
        os.environ.get(SOLVER_REALITY_TRANSPORT_ENV, SOLVER_REALITY_TRANSPORT_CONTROL)
        or SOLVER_REALITY_TRANSPORT_CONTROL
    ).strip().lower()
    allowed = {SOLVER_REALITY_TRANSPORT_CONTROL, SOLVER_REALITY_TRANSPORT_DELTA_ONLY_V1}
    if raw not in allowed:
        raise RuntimeError(
            f"{SOLVER_REALITY_TRANSPORT_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_solver_hosted_tool_search_mode(model_factory: Any) -> str:
    """Return the explicit default-off Solver hosted tool-search treatment."""
    if model_factory is not build_selected_frontier_models:
        return SOLVER_HOSTED_TOOL_SEARCH_CONTROL
    raw = str(
        os.environ.get(SOLVER_HOSTED_TOOL_SEARCH_ENV, SOLVER_HOSTED_TOOL_SEARCH_CONTROL)
        or SOLVER_HOSTED_TOOL_SEARCH_CONTROL
    ).strip().lower()
    allowed = {SOLVER_HOSTED_TOOL_SEARCH_CONTROL, SOLVER_HOSTED_TOOL_SEARCH_V1}
    if raw not in allowed:
        raise RuntimeError(
            f"{SOLVER_HOSTED_TOOL_SEARCH_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_verifier_activation_continuity_mode(model_factory: Any) -> str:
    """Return the explicit default-off Verifier within-activation continuity treatment."""
    if model_factory is not build_selected_frontier_models:
        return VERIFIER_ACTIVATION_CONTINUITY_CONTROL
    raw = str(
        os.environ.get(VERIFIER_ACTIVATION_CONTINUITY_ENV, VERIFIER_ACTIVATION_CONTINUITY_CONTROL)
        or VERIFIER_ACTIVATION_CONTINUITY_CONTROL
    ).strip().lower()
    allowed = {
        VERIFIER_ACTIVATION_CONTINUITY_CONTROL,
        VERIFIER_ACTIVATION_CONTINUITY_PREVIOUS_RESPONSE_V1,
    }
    if raw not in allowed:
        raise RuntimeError(
            f"{VERIFIER_ACTIVATION_CONTINUITY_ENV} must be one of {sorted(allowed)!r}, got {raw!r}"
        )
    return raw


def selected_solver_loop(model_factory: Any) -> str:
    """Return the explicit default-off matched Thin comparator arm."""
    if model_factory is not build_selected_frontier_models:
        return SOLVER_LOOP_INCUMBENT
    raw = str(os.environ.get(SOLVER_LOOP_ENV, SOLVER_LOOP_INCUMBENT) or SOLVER_LOOP_INCUMBENT).strip().lower()
    allowed = {SOLVER_LOOP_INCUMBENT, SOLVER_LOOP_THIN}
    if raw not in allowed:
        raise RuntimeError(f"{SOLVER_LOOP_ENV} must be one of {sorted(allowed)!r}, got {raw!r}")
    return raw


def selected_context_cleanup_mode(model_factory: Any) -> str:
    """Return the explicit default-off mechanical context cleanup arm."""
    if model_factory is not build_selected_frontier_models:
        return CONTEXT_CLEANUP_OFF
    raw = str(os.environ.get(CONTEXT_CLEANUP_ENV, CONTEXT_CLEANUP_OFF) or CONTEXT_CLEANUP_OFF).strip().lower()
    allowed = {CONTEXT_CLEANUP_OFF, CONTEXT_CLEANUP_CONSERVATIVE_V1}
    if raw not in allowed:
        raise RuntimeError(f"{CONTEXT_CLEANUP_ENV} must be one of {sorted(allowed)!r}, got {raw!r}")
    return raw


def selected_solver_reanchor_mode(model_factory: Any) -> str:
    """Select only the H2 model-facing clock projection; all other runtime policy is unchanged."""
    if model_factory is not build_selected_frontier_models:
        return "current_full"
    if selected_h2_walltime_arm() in {H2_WALLTIME_ARM, H2_WALLTIME_STATUS_ARM}:
        from .persistent_reanchor import CONTINUITY_FRESH_DELTA_WALLTIME_V1

        return CONTINUITY_FRESH_DELTA_WALLTIME_V1
    return PRODUCTION_PROFILE.solver_reanchor_mode


def selected_runtime_operation_status_refresh(model_factory: Any) -> bool:
    """Enable factual operation refresh only for the explicit walltime+status arm."""
    return (
        model_factory is build_selected_frontier_models
        and selected_h2_walltime_arm() == H2_WALLTIME_STATUS_ARM
    )


def budget_runtime_limits_from_env() -> dict[str, Any] | None:
    """Lazy budget seam so importing Harbor does not load provider-budget execution code."""
    from .provider_budget import budget_runtime_limits_from_env as _budget_runtime_limits_from_env

    return _budget_runtime_limits_from_env()


def make_azure_callable(**kwargs: Any) -> Any:
    """Lazy provider-construction seam retained for tests and admission guards."""
    from .providers.azure_model import make_azure_callable as _make_azure_callable

    return _make_azure_callable(**kwargs)


def make_azure_vision_callable(**kwargs: Any) -> Any:
    """Lazy vision-provider seam; importing Harbor alone never imports providers."""
    from .providers.azure_model import make_azure_vision_callable as _make_azure_vision_callable

    return _make_azure_vision_callable(**kwargs)


# Old research environment selectors are not production configuration. If one
# is present with a conflicting value, fail before provider construction rather
# than silently selecting a different treatment. The profile object remains the
# sole positive configuration authority.

def selected_harbor_treatment_manifest() -> dict[str, Any]:
    """Compatibility name for the one immutable production model profile."""
    return PRODUCTION_PROFILE.manifest()



@dataclass(frozen=True)
class HarborWorkspaceFacts:
    pwd: str
    git_root: str
    workspace_root: str
    existing_candidates: tuple[str, ...]


async def discover_harbor_workspace(environment: Any) -> HarborWorkspaceFacts:
    """Discover the task workspace with truthful remote probes only."""

    async def text(command: str, *, cwd: str | None = None) -> str:
        result = await environment.exec(
            command=command,
            cwd=cwd,
            env=None,
            timeout_sec=30,
        )
        return str(getattr(result, "stdout", "") or "").strip()

    pwd = await text("pwd")
    git_root = await text("git rev-parse --show-toplevel 2>/dev/null || true", cwd=pwd or None)
    existing: list[str] = []
    for candidate in ("/app", "/workspace"):
        observed = await text(
            f"if test -d {shlex.quote(candidate)}; then printf present; else printf missing; fi"
        )
        if observed == "present":
            existing.append(candidate)

    if git_root:
        root = git_root
    elif pwd:
        # Harbor's live working directory is direct environment authority.
        # Do not discard it merely because a conventional /app or /workspace
        # directory also exists: some task images intentionally WORKDIR
        # elsewhere while Harbor still provides incidental compatibility
        # directories. Falling back to a conventional root in that case makes
        # filesystem actions reject the very project directory that shell
        # actions can reach.
        root = pwd
    elif existing:
        root = existing[0]
    else:
        root = "/app"

    return HarborWorkspaceFacts(
        pwd=pwd,
        git_root=git_root,
        workspace_root=root,
        existing_candidates=tuple(existing),
    )


_LITERAL_ABSOLUTE_PATH_RE = re.compile(
    # ':' and '/' in the negative lookbehind keep URL authority such as
    # https://example.com/path from being misread as a task-public filesystem
    # root. Only literal Unix paths standing on their own textual boundary are
    # admitted.
    r"(?<![A-Za-z0-9_:/])/(?:[A-Za-z0-9._~+@%=-]+(?:/[A-Za-z0-9._~+@%=-]+)*)"
)
_SCP_REMOTE_ABSOLUTE_PATH_RE = re.compile(
    # SCP/Git remote syntax exposes a literal remote filesystem path after one
    # host separator, e.g. user@server:/git/server. This stays distinct from
    # URL syntax (https://...), whose double slash does not match here.
    r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9._-]+@)?[A-Za-z0-9._-]+:(/(?:[A-Za-z0-9._~+@%=-]+(?:/[A-Za-z0-9._~+@%=-]+)*))"
)


def literal_task_absolute_paths(instruction: str) -> tuple[str, ...]:
    """Return literal Unix absolute paths exposed by the exact raw task text.

    Besides standalone paths, preserve the remote absolute path encoded by
    common SCP/Git syntax such as ``user@host:/git/server``. This remains a
    lexical extraction only; it does not infer paths from task semantics.
    """
    text = str(instruction or "")
    matches: list[tuple[int, str]] = [
        (match.start(), match.group(0))
        for match in _LITERAL_ABSOLUTE_PATH_RE.finditer(text)
    ]
    matches.extend(
        (match.start(1), match.group(1))
        for match in _SCP_REMOTE_ABSOLUTE_PATH_RE.finditer(text)
    )
    rows: list[str] = []
    for _offset, raw in sorted(matches, key=lambda item: item[0]):
        value = raw.rstrip(".,;:!?")
        if value and value != "/" and value not in rows:
            rows.append(value)
    return tuple(rows)


def _inventory_visible_paths(
    executor: HarborEnvironmentExecutor,
    *,
    max_entries: int = 2_000,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return bounded real path metadata from the Harbor workspace.

    No file content is synthesized or inferred. The returned metadata is used
    only to construct EnvMap's visible-path projection; all actual reads remain
    Harbor-authoritative through the executor.
    """
    root = executor.workspace_root
    command = (
        f"find {shlex.quote(root)} -mindepth 1 "
        "\\( -name .git -o -name __pycache__ -o -name node_modules -o -name .pytest_cache \\) -prune -o -print 2>/dev/null | "
        "LC_ALL=C sort | "
        f"head -n {max(1, int(max_entries))} | "
        "while IFS= read -r p; do "
        "rel=${p#" + shlex.quote(root.rstrip("/") + "/") + "}; "
        "if [ -d \"$p\" ]; then printf 'D\\t%s\\n' \"$rel\"; "
        "elif [ -f \"$p\" ]; then printf 'F\\t%s\\n' \"$rel\"; fi; "
        "done"
    )
    result = executor.run_command(command, cwd=root, timeout_s=30)
    if not result.success:
        return (), ()
    files: list[str] = []
    dirs: list[str] = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        kind, rel = line.split("\t", 1)
        clean = rel.strip().strip("/")
        if not clean:
            continue
        if kind == "F":
            files.append(clean)
        elif kind == "D":
            dirs.append(clean)
    return tuple(sorted(set(files))), tuple(sorted(set(dirs)))


def _build_structural_envmap(
    *,
    executor: HarborEnvironmentExecutor,
    instruction: str,
    local_state_dir: Path,
    task_toml: Mapping[str, Any] | None = None,
    mcp_servers: tuple[Mapping[str, Any], ...] = (),
    agent_timeout_sec: float | None = None,
    observability: dict[str, float] | None = None,
) -> Any:
    """Build the existing EnvMap from real remote path metadata.

    ``build_envmap_from_task`` currently consumes a local directory when
    constructing file-tree metadata. We create a private structural mirror that
    contains only the real remote path names (empty placeholders, never model
    file authority) and explicitly mark that fact in task metadata. Actual file
    bytes remain accessible only through the Harbor executor.
    """
    from .envmap_builder import build_envmap_from_task
    from .environment_extensions import extension_probe_payload, normalize_mcp_servers
    from .environment_probe import probe_environment

    preflight_started = time.perf_counter()
    phase_started = time.perf_counter()
    probe = dict(probe_environment(executor, workspace_root=executor.workspace_root))
    environment_probe_elapsed_s = time.perf_counter() - phase_started
    normalized_mcp = normalize_mcp_servers(mcp_servers)
    extension_facts = extension_probe_payload(normalized_mcp)
    probe["environment_extensions"] = extension_facts
    phase_started = time.perf_counter()
    visible_files, visible_dirs = _inventory_visible_paths(executor)
    visible_path_inventory_elapsed_s = time.perf_counter() - phase_started
    phase_started = time.perf_counter()
    surface = local_state_dir / "visible_path_projection"
    surface.mkdir(parents=True, exist_ok=True)
    for rel in visible_dirs:
        (surface / rel).mkdir(parents=True, exist_ok=True)
    for rel in visible_files:
        target = surface / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)

    structural_projection_elapsed_s = time.perf_counter() - phase_started
    task_metadata: dict[str, Any] = {
        "environment_probe": probe,
        "visible_path_projection": {
            "source": "harbor_remote_find_metadata_only",
            "content_authority": False,
            "visible_file_count": len(visible_files),
            "visible_dir_count": len(visible_dirs),
        },
        "environment_extensions": extension_facts,
        "semantic_projection_mode": "factual_only",
    }
    if agent_timeout_sec is not None and float(agent_timeout_sec) > 0:
        task_metadata["agent_timeout_sec"] = float(agent_timeout_sec)
    phase_started = time.perf_counter()
    envmap = build_envmap_from_task(
        str(surface),
        instruction,
        workspace_root=executor.workspace_root,
        task_metadata=task_metadata,
        task_toml=dict(task_toml or {}),
        projection_mode="factual_only",
    )
    envmap_build_elapsed_s = time.perf_counter() - phase_started
    phase_started = time.perf_counter()
    computer_probe = getattr(executor, "computer_backend_info", None)
    computer_info = computer_probe() if callable(computer_probe) else {"available": False}
    computer_probe_elapsed_s = time.perf_counter() - phase_started
    if computer_info.get("available"):
        from .runtime_ir import CapabilityDescriptor
        capabilities=dict(envmap.capabilities)
        capabilities["computer_control"]=CapabilityDescriptor(capability_id="computer_control",summary="Control a live GUI with one native computer call: execute its ordered model-authored action sequence, then observe one fresh screenshot",available=True,tool_names=("computer_action",),cost_hint="moderate")
        metadata=dict(envmap.task_metadata); metadata["computer_control"]={"available":True,"backend":str(computer_info.get("backend") or ""),"authority":"live_executor_probe"}
        envmap=replace(envmap,capabilities=capabilities,task_metadata=metadata)
    if observability is not None:
        observability.update({
            "environment_probe_elapsed_s": environment_probe_elapsed_s,
            "visible_path_inventory_elapsed_s": visible_path_inventory_elapsed_s,
            "structural_projection_elapsed_s": structural_projection_elapsed_s,
            "envmap_build_elapsed_s": envmap_build_elapsed_s,
            "computer_backend_probe_elapsed_s": computer_probe_elapsed_s,
            "total_structural_envmap_elapsed_s": time.perf_counter() - preflight_started,
        })
    return envmap


class DisabledVerifier:
    """Fail-closed sentinel for runs whose sealed policy disables model review."""

    verifier_disabled = True

    def __call__(self, *_args: Any, **_kwargs: Any) -> str:
        raise RuntimeError("semantic verifier is disabled by the sealed run policy")


def build_selected_frontier_models(
    profile: ModelProfile = PRODUCTION_PROFILE,
) -> tuple[Any, Any]:
    """Construct Solver/Verifier callables from one explicit frozen profile."""
    require_provider_authorization(profile)
    budget_limits = budget_runtime_limits_from_env()
    provider_max_retries = (
        int(budget_limits["provider_max_retries"])
        if budget_limits is not None else profile.provider_max_retries
    )
    provider_sdk_max_retries = (
        int(budget_limits["provider_sdk_max_retries"])
        if budget_limits is not None else profile.provider_sdk_max_retries
    )
    solver = make_azure_callable(
        deployment_env=profile.deployment_env,
        key_env=profile.key_env,
        endpoint_env=profile.endpoint_env,
        credential_mode=profile.credential_mode,
        expected_model_id=profile.model_id.casefold(),
        effort=profile.solver_reasoning_effort,
        role="solver",
        responses_background=profile.responses_background,
        responses_websocket=profile.responses_websocket,
        responses_websocket_persistent=profile.responses_websocket_persistent,
        prompt_cache_mode=profile.prompt_cache_mode,
        poll_interval_s=profile.provider_poll_interval_s,
        poll_timeout_s=profile.provider_poll_timeout_s,
        max_rpm=0,
        max_retries=provider_max_retries,
        sdk_max_retries=provider_sdk_max_retries,
    )
    review_arm = selected_h1_review_arm()
    judge_verifier_arm = selected_judge_verifier_arm()
    if judge_verifier_arm == JUDGE_VERIFIER_V3_TYPED_ARM:
        if review_arm != H1_SEMANTIC_ARM:
            raise RuntimeError(
                f"{JUDGE_VERIFIER_ARM_ENV}={JUDGE_VERIFIER_V3_TYPED_ARM!r} is "
                f"incompatible with {H1_REVIEW_ARM_ENV}={review_arm!r}; "
                f"leave H1 at {H1_SEMANTIC_ARM!r} for the V3 experiment"
            )
        verifier = build_selected_judge_v3_verifier()
    elif review_arm == H1_MECHANICAL_ARM:
        from .h1_mechanical_verifier import H1MechanicalReviewVerifier

        verifier = H1MechanicalReviewVerifier()
    elif review_arm == H1_OFF_ARM:
        verifier = DisabledVerifier()
    else:
        verifier = make_azure_callable(
            deployment_env=profile.deployment_env,
            key_env=profile.key_env,
            endpoint_env=profile.endpoint_env,
            credential_mode=profile.credential_mode,
            expected_model_id=profile.model_id.casefold(),
            effort=profile.verifier_reasoning_effort,
            role="verifier",
            responses_background=profile.responses_background,
            responses_websocket=profile.responses_websocket,
            responses_websocket_persistent=profile.responses_websocket_persistent,
            prompt_cache_mode=profile.prompt_cache_mode,
            poll_interval_s=profile.provider_poll_interval_s,
            poll_timeout_s=profile.provider_poll_timeout_s,
            max_rpm=0,
            max_retries=provider_max_retries,
            sdk_max_retries=provider_sdk_max_retries,
        )
    return solver, verifier


def build_selected_frontier_vision_model() -> Any:
    """Construct native Frontier image perception with production zero-retry custody."""
    require_provider_authorization(PRODUCTION_PROFILE)
    budget_limits = budget_runtime_limits_from_env()
    sdk_max_retries = (
        int(budget_limits["provider_sdk_max_retries"])
        if budget_limits is not None else 0
    )
    return make_azure_vision_callable(
        deployment_env=FRONTIER_DEPLOYMENT_ENV,
        key_env=FRONTIER_KEY_ENV,
        endpoint_env=FRONTIER_ENDPOINT_ENV,
        sdk_max_retries=sdk_max_retries,
    )


def _runtime_identity(context: Any, envmap: Any, *, model_factory: Any | None = None) -> dict[str, Any]:
    metadata = getattr(context, "metadata", None)
    metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    source_commit = str(os.environ.get("AETHER_SOURCE_COMMIT", "") or metadata.get("source_commit", "")).strip()
    runtime_manifest = str(
        os.environ.get("AETHER_RUNTIME_MANIFEST_SHA256", "")
        or metadata.get("runtime_manifest_sha256", "")
    ).strip()
    campaign_id = str(
        os.environ.get("AETHER_CAMPAIGN_ID", "")
        or metadata.get("campaign_id", "")
    ).strip()
    task_closure_sha256 = str(
        os.environ.get("AETHER_TASK_CLOSURE_SHA256", "")
        or metadata.get("task_closure_sha256", "")
    ).strip()
    package_closure_sha256 = str(
        os.environ.get("AETHER_PACKAGE_CLOSURE_SHA256", "")
        or metadata.get("package_closure_sha256", "")
    ).strip()
    sealed_task_id = str(os.environ.get(SEALED_TASK_ID_ENV, "") or "").strip()
    sealed_run_id = str(os.environ.get(SEALED_RUN_ID_ENV, "") or "").strip()
    context_id = str(
        getattr(context, "context_id", "")
        or getattr(context, "run_id", "")
        or metadata.get("context_id", "")
        or "harbor"
    )
    task_id = str(
        sealed_task_id
        or getattr(context, "task_id", "")
        or metadata.get("task_id", "")
        or context_id
    )
    run_id = sealed_run_id or f"harbor:{context_id}"
    task_metadata = getattr(envmap, "task_metadata", None)
    task_metadata = dict(task_metadata) if isinstance(task_metadata, Mapping) else {}
    budgets: dict[str, Any] = {}
    raw_agent_timeout = task_metadata.get("agent_timeout_sec")
    try:
        if raw_agent_timeout is not None and float(raw_agent_timeout) > 0:
            budgets["agent_timeout_sec"] = float(raw_agent_timeout)
    except (TypeError, ValueError):
        pass
    provider_budget = budget_runtime_limits_from_env()
    if provider_budget is not None:
        budgets["provider_budget"] = dict(provider_budget)
    identity = {
        "task_id": task_id,
        "task_id_authority": "sealed_first_submit_manifest" if sealed_task_id else "harbor_context",
        "run_id": run_id,
        "run_id_authority": "sealed_first_submit_manifest" if sealed_run_id else "harbor_context",
        "source_commit": source_commit,
        "runtime_manifest_sha256": runtime_manifest,
        "campaign_id": campaign_id,
        "task_closure_sha256": task_closure_sha256,
        "package_closure_sha256": package_closure_sha256,
        "harbor_context_id": context_id,
        "environment_digest": envmap.digest(),
        "model_profile": PRODUCTION_PROFILE.manifest(),
        "model_profile_sha256": PRODUCTION_PROFILE.sha256(),
        "research_h1_review_arm": selected_h1_review_arm(),
        "research_h1_review_arm_authority": H1_REVIEW_ARM_ENV if H1_REVIEW_ARM_ENV in os.environ else "production_default",
        "research_judge_verifier_arm": selected_judge_verifier_arm(),
        "research_judge_verifier_arm_authority": (
            JUDGE_VERIFIER_ARM_ENV if JUDGE_VERIFIER_ARM_ENV in os.environ
            else "production_default"
        ),
        "budgets": budgets,
    }
    if H2_WALLTIME_ARM_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_h2_walltime_arm"] = selected_h2_walltime_arm()
        identity["research_h2_walltime_arm_authority"] = H2_WALLTIME_ARM_ENV
        identity["solver_reanchor_mode_selected"] = selected_solver_reanchor_mode(effective_factory)
        identity["runtime_operation_status_refresh_enabled"] = selected_runtime_operation_status_refresh(effective_factory)
    if H3_SOLVER_REASONING_ARM_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_h3_solver_reasoning_arm"] = selected_h3_solver_reasoning_mode(effective_factory)
        identity["research_h3_solver_reasoning_arm_authority"] = H3_SOLVER_REASONING_ARM_ENV
    if H4_BOUNDARY_VERIFICATION_ARM_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_h4_boundary_verification_arm"] = selected_h4_boundary_verification_mode(effective_factory)
        identity["research_h4_boundary_verification_arm_authority"] = H4_BOUNDARY_VERIFICATION_ARM_ENV
    if P1_COMPLETION_DISPOSITION_ARM_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_p1_completion_disposition_arm"] = (
            selected_p1_completion_disposition_mode(effective_factory)
        )
        identity["research_p1_completion_disposition_arm_authority"] = (
            P1_COMPLETION_DISPOSITION_ARM_ENV
        )
    if P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_p4_provider_frontier_recovery_arm"] = (
            selected_p4_provider_frontier_recovery_mode(effective_factory)
        )
        identity["research_p4_provider_frontier_recovery_arm_authority"] = (
            P4_PROVIDER_FRONTIER_RECOVERY_ARM_ENV
        )
    if SOLVER_PREFIX_RENDERER_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_solver_prefix_renderer"] = selected_solver_prefix_renderer(effective_factory)
        identity["research_solver_prefix_renderer_authority"] = SOLVER_PREFIX_RENDERER_ENV
    if CONTEXT_CLEANUP_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_context_cleanup"] = selected_context_cleanup_mode(effective_factory)
        identity["research_context_cleanup_authority"] = CONTEXT_CLEANUP_ENV
    if SOLVER_LOOP_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_solver_loop"] = selected_solver_loop(effective_factory)
        identity["research_solver_loop_authority"] = SOLVER_LOOP_ENV
    if SOLVER_REALITY_TRANSPORT_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_solver_reality_transport"] = selected_solver_reality_transport_mode(effective_factory)
        identity["research_solver_reality_transport_authority"] = SOLVER_REALITY_TRANSPORT_ENV
    if SOLVER_HOSTED_TOOL_SEARCH_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_solver_hosted_tool_search"] = (
            selected_solver_hosted_tool_search_mode(effective_factory)
        )
        identity["research_solver_hosted_tool_search_authority"] = (
            SOLVER_HOSTED_TOOL_SEARCH_ENV
        )
    if VERIFIER_ACTIVATION_CONTINUITY_ENV in os.environ:
        effective_factory = model_factory if model_factory is not None else build_selected_frontier_models
        identity["research_verifier_activation_continuity"] = (
            selected_verifier_activation_continuity_mode(effective_factory)
        )
        identity["research_verifier_activation_continuity_authority"] = (
            VERIFIER_ACTIVATION_CONTINUITY_ENV
        )
    return identity


def _update_agent_context(context: Any, record: Mapping[str, Any]) -> None:
    """Populate truthful aggregate telemetry without claiming ATIF support."""
    metrics = record.get("run_metrics") if isinstance(record.get("run_metrics"), Mapping) else {}
    telemetry = record.get("model_call_telemetry") if isinstance(record.get("model_call_telemetry"), list) else []

    input_tokens = 0
    cached_tokens = 0
    output_tokens = 0
    measured_cost_usd = 0.0
    cost_measurement_unknown = False
    for row in telemetry:
        if not isinstance(row, Mapping):
            continue
        input_tokens += int(row.get("input_tokens", 0) or 0)
        cached_tokens += int(row.get("cached_input_tokens", 0) or 0)
        output_tokens += int(row.get("output_tokens", 0) or 0)
        raw_cost = row.get("cost_usd")
        if raw_cost is None:
            cost_measurement_unknown = True
        else:
            measured_cost_usd += float(raw_cost)
    cost_usd: float | None = (
        None if telemetry and cost_measurement_unknown else measured_cost_usd
    )

    for name, value in (
        ("n_input_tokens", input_tokens),
        ("n_cache_tokens", cached_tokens),
        ("n_output_tokens", output_tokens),
        ("cost_usd", cost_usd),
    ):
        if hasattr(context, name):
            setattr(context, name, value)

    metadata = dict(getattr(context, "metadata", None) or {})
    metadata["aether"] = {
        "status": record.get("status"),
        "step": record.get("step"),
        "classifier_label": record.get("classifier_label"),
        "runtime_identity": record.get("runtime_identity"),
        "run_metrics": dict(metrics) if isinstance(metrics, Mapping) else {},
        "atif_status": "NOT_YET_IMPLEMENTED",
    }
    context.metadata = metadata


def _effective_run_limits(
    *,
    model_factory: Any,
    max_steps: int | None,
    agent_timeout_sec: float | None,
) -> dict[str, Any]:
    """Resolve production-vs-diagnostic limits without changing model identity."""
    if model_factory is build_selected_frontier_models:
        if max_steps is not None:
            raise ValueError(
                "production Harbor max_steps is launcher/profile controlled, not caller configurable"
            )
        budget_limits = budget_runtime_limits_from_env()
        if budget_limits is None:
            return {
                "budget_constrained": False,
                "budget_limits": None,
                "max_steps": PRODUCTION_PROFILE.solver_turn_budget,
                "solver_max_output_tokens": PRODUCTION_PROFILE.solver_max_output_tokens,
                "verifier_max_output_tokens": PRODUCTION_PROFILE.verifier_max_output_tokens,
                "run_timeout_s": agent_timeout_sec,
            }
        budget_timeout = float(budget_limits["agent_timeout_sec"])
        def _optional_int(name: str) -> int | None:
            raw = budget_limits.get(name)
            return None if raw is None else int(raw)

        return {
            "budget_constrained": True,
            "budget_limits": dict(budget_limits),
            "max_steps": _optional_int("solver_turn_budget"),
            "solver_max_output_tokens": _optional_int("solver_max_output_tokens"),
            "verifier_max_output_tokens": _optional_int("verifier_max_output_tokens"),
            "run_timeout_s": (
                budget_timeout
                if agent_timeout_sec is None
                else min(float(agent_timeout_sec), budget_timeout)
            ),
        }
    return {
        "budget_constrained": False,
        "budget_limits": None,
        "max_steps": 30 if max_steps is None else int(max_steps),
        "solver_max_output_tokens": 16000,
        "verifier_max_output_tokens": 12000,
        "run_timeout_s": agent_timeout_sec,
    }


def run_harbor_aether_sync(
    *,
    environment: Any,
    event_loop: asyncio.AbstractEventLoop,
    context: Any,
    instruction: str,
    logs_dir: Path,
    task_toml: Mapping[str, Any] | None = None,
    mcp_servers: tuple[Mapping[str, Any], ...] = (),
    max_steps: int | None = None,
    model_factory: Any = build_selected_frontier_models,
    cancellation_event: threading.Event | None = None,
    agent_timeout_sec: float | None = None,
    run_started_monotonic: float | None = None,
) -> dict[str, Any]:
    """Run one canonical Aether-Next task against Harbor from a worker thread."""
    from .atif_export import build_atif_trajectory, write_atif_trajectory
    from .harbor_executor import HarborEnvironmentExecutor
    from .postmerge_observability import build_x0_observability
    from .run_adapter import run_task

    workspace_root = str(getattr(context, "metadata", {}).get("aether_workspace_root", "") or "").strip()
    if not workspace_root:
        raise ValueError("Harbor workspace root must be discovered before synchronous run")
    local_state = logs_dir / "aether_harbor"
    local_state.mkdir(parents=True, exist_ok=True)
    executor = HarborEnvironmentExecutor(
        environment,
        event_loop=event_loop,
        workspace_root=workspace_root,
        local_state_dir=local_state / "executor_state",
        mcp_servers=mcp_servers,
    )
    executor.set_verifier_world_roots(literal_task_absolute_paths(instruction))
    preflight_observability: dict[str, float] = {}
    envmap = _build_structural_envmap(
        executor=executor,
        instruction=instruction,
        local_state_dir=local_state,
        task_toml=task_toml,
        mcp_servers=mcp_servers,
        agent_timeout_sec=agent_timeout_sec,
        observability=preflight_observability,
    )
    model_factory_started = time.perf_counter()
    solver, verifier = model_factory()
    preflight_observability["solver_verifier_model_factory_elapsed_s"] = (
        time.perf_counter() - model_factory_started
    )
    # Only the selected production factory implicitly enables provider-native
    # perception. Custom/offline factories remain exactly provider-free unless
    # a caller explicitly constructs perception elsewhere.
    vision = (
        build_selected_frontier_vision_model()
        if model_factory is build_selected_frontier_models
        else None
    )
    for model in (solver, verifier, vision):
        bind_cancel = getattr(model, "bind_run_cancellation", None)
        if callable(bind_cancel):
            bind_cancel(cancellation_event)
    logical_task_dir = local_state / "task_surface"
    logical_task_dir.mkdir(parents=True, exist_ok=True)
    run_limits = _effective_run_limits(
        model_factory=model_factory, max_steps=max_steps, agent_timeout_sec=agent_timeout_sec,
    )
    kernel_started = time.perf_counter()
    record = run_task(
        task_dir=str(logical_task_dir),
        instruction_text=instruction,
        solver_model=solver,
        verifier_model=verifier,
        vision_model=vision,
        workspace_root=workspace_root,
        max_steps=run_limits["max_steps"],
        solver_max_output_tokens=run_limits["solver_max_output_tokens"],
        verifier_max_output_tokens=run_limits["verifier_max_output_tokens"],
        runtime_identity=_runtime_identity(context, envmap, model_factory=model_factory),
        executor=executor,
        envmap_override=envmap,
        close_executor=True,
        solver_reanchor_mode=selected_solver_reanchor_mode(model_factory),
        context_cleanup_mode=selected_context_cleanup_mode(model_factory),
        solver_loop=selected_solver_loop(model_factory),
        solver_reasoning_mode=selected_h3_solver_reasoning_mode(model_factory),
        solver_prefix_renderer=selected_solver_prefix_renderer(model_factory),
        solver_reality_transport_mode=selected_solver_reality_transport_mode(model_factory),
        solver_hosted_tool_search_mode=selected_solver_hosted_tool_search_mode(model_factory),
        verifier_activation_continuity_mode=selected_verifier_activation_continuity_mode(model_factory),
        boundary_verification_mode=selected_h4_boundary_verification_mode(model_factory),
        completion_disposition_mode=selected_p1_completion_disposition_mode(model_factory),
        provider_frontier_recovery_mode=selected_p4_provider_frontier_recovery_mode(model_factory),
        refresh_runtime_operation_status=selected_runtime_operation_status_refresh(model_factory),
        cancellation_event=cancellation_event,
        run_timeout_s=run_limits["run_timeout_s"],
        run_started_monotonic=run_started_monotonic,
    )
    preflight_observability["kernel_run_task_elapsed_s"] = time.perf_counter() - kernel_started
    record["harbor_preflight_observability"] = {
        key: round(float(value), 6) for key, value in sorted(preflight_observability.items())
    }
    trajectory = build_atif_trajectory(
        instruction=instruction,
        run_record=record,
        agent_name="aether-next",
        agent_version="postmerge-v3",
        model_name="gpt-5.6-luna",
    )
    trajectory_path = write_atif_trajectory(logs_dir / "trajectory.json", trajectory)
    record["atif_trajectory_path"] = str(trajectory_path)
    record["atif_schema_version"] = str(trajectory.get("schema_version", ""))

    # X0 is an evidence requirement for same-source post-merge experiments.
    # Persist the complete JSON-serializable Aether run record in Harbor's agent
    # log custody before the Python object leaves this adapter, then bind the
    # deterministic X0 summary to the exact persisted record hash. No model or
    # environment action is introduced by this evidence materialization.
    run_record_path = logs_dir / "aether_run_record.json"
    x0_path = logs_dir / "aether_x0_observability.json"
    record["aether_run_record_path"] = str(run_record_path)
    record["x0_observability_path"] = str(x0_path)
    run_record_bytes = (json.dumps(record, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    run_record_path.write_bytes(run_record_bytes)
    run_record_sha256 = sha256(run_record_bytes).hexdigest()

    x0 = build_x0_observability(
        model_call_telemetry=record.get("model_call_telemetry", ()),
        model_interface_captures=record.get("model_interface_captures", ()),
        receipt_records=record.get("receipt_records", ()),
    )
    x0["source_run"] = {
        "path": str(run_record_path),
        "sha256": run_record_sha256,
        "runtime_identity": record.get("runtime_identity"),
        "status": record.get("status"),
        "step": record.get("step"),
    }
    x0_path.write_text(
        json.dumps(x0, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    record["aether_run_record_sha256"] = run_record_sha256

    _update_agent_context(context, record)
    metadata = dict(getattr(context, "metadata", None) or {})
    aether_metadata = dict(metadata.get("aether", {}) or {})
    aether_metadata.update({
        "atif_status": "ATIF-v1.7",
        "atif_trajectory_path": str(trajectory_path),
        "aether_run_record_path": str(run_record_path),
        "aether_run_record_sha256": run_record_sha256,
        "x0_observability_path": str(x0_path),
        "x0_schema_version": str(x0.get("schema_version", "")),
    })
    metadata["aether"] = aether_metadata
    context.metadata = metadata
    return record


async def run_harbor_aether(
    *,
    environment: Any,
    context: Any,
    instruction: str,
    logs_dir: Path,
    task_toml: Mapping[str, Any] | None = None,
    mcp_servers: tuple[Mapping[str, Any], ...] = (),
    max_steps: int | None = None,
    model_factory: Any = build_selected_frontier_models,
    agent_timeout_sec: float | None = None,
    run_started_monotonic: float | None = None,
) -> dict[str, Any]:
    """Discover Harbor world facts then execute the synchronous kernel off-loop."""
    if run_started_monotonic is None:
        run_started_monotonic = time.monotonic()
    facts = await discover_harbor_workspace(environment)
    metadata = dict(getattr(context, "metadata", None) or {})
    metadata["aether_workspace_root"] = facts.workspace_root
    metadata["aether_harbor_workspace_probe"] = {
        "pwd": facts.pwd,
        "git_root": facts.git_root,
        "workspace_root": facts.workspace_root,
        "existing_candidates": list(facts.existing_candidates),
    }
    context.metadata = metadata
    loop = asyncio.get_running_loop()
    cancellation_event = threading.Event()
    worker = asyncio.create_task(asyncio.to_thread(
        run_harbor_aether_sync,
        environment=environment,
        event_loop=loop,
        context=context,
        instruction=instruction,
        logs_dir=Path(logs_dir),
        task_toml=task_toml,
        mcp_servers=mcp_servers,
        max_steps=max_steps,
        model_factory=model_factory,
        cancellation_event=cancellation_event,
        agent_timeout_sec=agent_timeout_sec,
        run_started_monotonic=run_started_monotonic,
    ))
    try:
        # Shield the worker so Harbor cancellation revokes authority through the
        # shared event instead of abandoning a live thread that can race grading.
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        from .run_cancellation import RunCancellationRequested

        cancellation_event.set()
        # Harbor (or an enclosing timeout scope) may cancel this coroutine more
        # than once while the synchronous worker is unwinding. A second
        # CancelledError must not let the adapter return while that worker still
        # owns task-world authority; otherwise grading can race late mutations
        # and the timeout run record never reaches durable custody. Keep
        # shielding until the worker is actually done, then propagate the outer
        # cancellation that triggered revocation.
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except RunCancellationRequested:
                break
            except Exception:
                # Harbor owns the timeout classification. The critical
                # invariant is worker quiescence before cancellation returns;
                # the worker's own terminal error is secondary.
                break
        if worker.done():
            try:
                worker.result()
            except (RunCancellationRequested, asyncio.CancelledError):
                pass
            except Exception:
                pass
        raise


__all__ = [
    "HarborWorkspaceFacts",
    "build_selected_frontier_models",
    "discover_harbor_workspace",
    "run_harbor_aether",
    "run_harbor_aether_sync",
]
