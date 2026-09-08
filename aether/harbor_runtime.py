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


LUNA_ENDPOINT_ENV = PRODUCTION_PROFILE.endpoint_env
LUNA_DEPLOYMENT_ENV = PRODUCTION_PROFILE.deployment_env
LUNA_KEY_ENV = PRODUCTION_PROFILE.key_env
SEALED_TASK_ID_ENV = "AETHER_FIRST_SUBMIT_TASK_ID"
SEALED_RUN_ID_ENV = "AETHER_FIRST_SUBMIT_RUN_ID"


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

    probe = dict(probe_environment(executor, workspace_root=executor.workspace_root))
    normalized_mcp = normalize_mcp_servers(mcp_servers)
    extension_facts = extension_probe_payload(normalized_mcp)
    probe["environment_extensions"] = extension_facts
    visible_files, visible_dirs = _inventory_visible_paths(executor)
    surface = local_state_dir / "visible_path_projection"
    surface.mkdir(parents=True, exist_ok=True)
    for rel in visible_dirs:
        (surface / rel).mkdir(parents=True, exist_ok=True)
    for rel in visible_files:
        target = surface / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(exist_ok=True)

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
    envmap = build_envmap_from_task(
        str(surface),
        instruction,
        workspace_root=executor.workspace_root,
        task_metadata=task_metadata,
        task_toml=dict(task_toml or {}),
        projection_mode="factual_only",
    )
    computer_probe = getattr(executor, "computer_backend_info", None)
    computer_info = computer_probe() if callable(computer_probe) else {"available": False}
    if computer_info.get("available"):
        from .runtime_ir import CapabilityDescriptor
        capabilities=dict(envmap.capabilities)
        capabilities["computer_control"]=CapabilityDescriptor(capability_id="computer_control",summary="Control a live GUI with one native computer call: execute its ordered model-authored action sequence, then observe one fresh screenshot",available=True,tool_names=("computer_action",),cost_hint="moderate")
        metadata=dict(envmap.task_metadata); metadata["computer_control"]={"available":True,"backend":str(computer_info.get("backend") or ""),"authority":"live_executor_probe"}
        envmap=replace(envmap,capabilities=capabilities,task_metadata=metadata)
    return envmap


def build_selected_luna_models(
    profile: ModelProfile = PRODUCTION_PROFILE,
) -> tuple[Any, Any]:
    """Construct Solver/Verifier callables from one explicit frozen profile."""
    require_provider_authorization(profile)
    solver = make_azure_callable(
        deployment_env=profile.deployment_env,
        key_env=profile.key_env,
        endpoint_env=profile.endpoint_env,
        effort=profile.solver_reasoning_effort,
        role="solver",
        responses_background=profile.responses_background,
        responses_websocket=profile.responses_websocket,
        prompt_cache_mode=profile.prompt_cache_mode,
        poll_interval_s=profile.provider_poll_interval_s,
        poll_timeout_s=profile.provider_poll_timeout_s,
        max_rpm=0,
        max_retries=profile.provider_max_retries,
        sdk_max_retries=profile.provider_sdk_max_retries,
    )
    verifier = make_azure_callable(
        deployment_env=profile.deployment_env,
        key_env=profile.key_env,
        endpoint_env=profile.endpoint_env,
        effort=profile.verifier_reasoning_effort,
        role="verifier",
        responses_background=profile.responses_background,
        responses_websocket=profile.responses_websocket,
        prompt_cache_mode=profile.prompt_cache_mode,
        poll_interval_s=profile.provider_poll_interval_s,
        poll_timeout_s=profile.provider_poll_timeout_s,
        max_rpm=0,
        max_retries=profile.provider_max_retries,
        sdk_max_retries=profile.provider_sdk_max_retries,
    )
    return solver, verifier


def build_selected_luna_vision_model() -> Any:
    """Construct native Luna image perception with production zero-retry custody."""
    require_provider_authorization(PRODUCTION_PROFILE)
    return make_azure_vision_callable(
        deployment_env=LUNA_DEPLOYMENT_ENV,
        key_env=LUNA_KEY_ENV,
        endpoint_env=LUNA_ENDPOINT_ENV,
        sdk_max_retries=0,
    )


def _runtime_identity(context: Any, envmap: Any) -> dict[str, Any]:
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
    return {
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
        "budgets": budgets,
    }


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
    model_factory: Any = build_selected_luna_models,
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
    envmap = _build_structural_envmap(
        executor=executor,
        instruction=instruction,
        local_state_dir=local_state,
        task_toml=task_toml,
        mcp_servers=mcp_servers,
        agent_timeout_sec=agent_timeout_sec,
    )
    solver, verifier = model_factory()
    # Only the selected production factory implicitly enables provider-native
    # perception. Custom/offline factories remain exactly provider-free unless
    # a caller explicitly constructs perception elsewhere.
    vision = (
        build_selected_luna_vision_model()
        if model_factory is build_selected_luna_models
        else None
    )
    for model in (solver, verifier, vision):
        bind_cancel = getattr(model, "bind_run_cancellation", None)
        if callable(bind_cancel):
            bind_cancel(cancellation_event)
    logical_task_dir = local_state / "task_surface"
    logical_task_dir.mkdir(parents=True, exist_ok=True)
    selected_max_steps = (
        PRODUCTION_PROFILE.solver_turn_budget
        if model_factory is build_selected_luna_models
        else (30 if max_steps is None else int(max_steps))
    )
    if model_factory is build_selected_luna_models and max_steps is not None:
        raise ValueError(
            "production Harbor uses the official task timeout; max_steps is not configurable"
        )
    record = run_task(
        task_dir=str(logical_task_dir),
        instruction_text=instruction,
        solver_model=solver,
        verifier_model=verifier,
        vision_model=vision,
        workspace_root=workspace_root,
        max_steps=selected_max_steps,
        solver_max_output_tokens=(PRODUCTION_PROFILE.solver_max_output_tokens if model_factory is build_selected_luna_models else 16000),
        verifier_max_output_tokens=(PRODUCTION_PROFILE.verifier_max_output_tokens if model_factory is build_selected_luna_models else 12000),
        runtime_identity=_runtime_identity(context, envmap),
        executor=executor,
        envmap_override=envmap,
        close_executor=True,
        solver_reanchor_mode=(PRODUCTION_PROFILE.solver_reanchor_mode if model_factory is build_selected_luna_models else "current_full"),
        cancellation_event=cancellation_event,
        run_timeout_s=agent_timeout_sec,
        run_started_monotonic=run_started_monotonic,
    )
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
    model_factory: Any = build_selected_luna_models,
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
    "build_selected_luna_models",
    "discover_harbor_workspace",
    "run_harbor_aether",
    "run_harbor_aether_sync",
]
