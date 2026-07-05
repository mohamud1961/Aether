"""Build an EnvMap from a task directory for Aether-Next runs."""
from __future__ import annotations

import os
from pathlib import Path
import re

from .runtime_ir import CapabilityDescriptor, EnvMap
from .task_capability import classify_capability_needs, flatten_task_toml, required_tool_hints


_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
_MAX_VISIBLE = 2_000
_TOOL_HINT_VOCAB: tuple[str, ...] = (
    "python", "python3", "r", "rscript", "node", "npm", "git", "ssh", "sshd",
    "nginx", "openssl", "ffmpeg", "ffprobe", "qemu", "qemu-system-i386", "qemu-system-x86_64", "qemu-img",
    "docker", "make", "cmake", "gcc", "g++", "clang", "clang++", "pkg-config",
    "curl", "wget", "sqlite3", "psql", "mysql", "java", "R", "Rscript", "julia", "octave",
    "tesseract", "pdftotext", "convert", "magick", "readelf", "objdump", "strings", "file", "gdb",
    "cargo", "rustc", "ocaml", "opam", "dune", "coqtop", "coqc", "ssh", "sshd", "telnet", "expect",
    "pip", "uv", "grpcurl",
)
_LANGUAGE_HINT_VOCAB: tuple[str, ...] = (
    "python", "javascript", "typescript", "r", "rust", "c", "c++", "java",
    "bash", "shell", "sql", "sparql", "ocaml", "cobol",
)
_PROMPT_DELIVERABLE_RE = re.compile(
    r"(?:write|create|produce|save|output|submit)\s+`?(/app/[\w./-]+)`?",
    re.IGNORECASE,
)

_SUBSTRATE_CAPABILITIES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "shell",
        "Execute shell commands via bash",
        ("run_command",),
        "cheap",
    ),
    (
        "filesystem",
        "Read and write files in the workspace",
        ("read_file", "write_file"),
        "cheap",
    ),
    (
        "managed_process",
        "Launch, probe, and stop background processes",
        ("launch_process", "probe_service", "stop_process"),
        "moderate",
    ),
    (
        "service_probe",
        "Probe liveness of running services",
        ("probe_service",),
        "cheap",
    ),
    (
        "artifact_inspection",
        "Inspect artifacts (text, binary, structured data)",
        ("inspect_artifact",),
        "moderate",
    ),
    (
        "network_fetch",
        "Fetch resources via curl/wget/git/pip",
        ("bootstrap_acquire",),
        "expensive",
    ),
)


def _scan_visible(
    base_dir: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Scan *base_dir* for visible files and directories, bounded."""
    files: list[str] = []
    dirs: list[str] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        rel_dir = os.path.relpath(dirpath, base_dir)
        if rel_dir != ".":
            dirs.append(rel_dir)
        for fname in sorted(filenames):
            files.append(os.path.relpath(os.path.join(dirpath, fname), base_dir))
            count += 1
            if count >= _MAX_VISIBLE:
                return tuple(files), tuple(dirs)
    return tuple(files), tuple(dirs)


def _build_file_tree(files: tuple[str, ...], dirs: tuple[str, ...], *, limit: int = 250) -> str:
    """Render visible paths as a compact tree for model-facing EnvMap context."""
    paths = sorted(set(dirs) | set(files))[: max(0, limit)]
    if not paths:
        return "/app\n"
    lines = ["/app"]
    for path in paths:
        depth = path.count("/")
        name = path.rsplit("/", 1)[-1]
        suffix = "/" if path in dirs else ""
        lines.append(f"{'  ' * depth}- {name}{suffix}")
    if len(set(dirs) | set(files)) > limit:
        lines.append(f"... truncated after {limit} visible paths")
    return "\n".join(lines)


def _build_file_map_summary(files: tuple[str, ...], dirs: tuple[str, ...]) -> dict[str, object]:
    """Build heuristic file-map hints without reading file contents."""
    top_level = sorted({item.split("/", 1)[0] for item in (*files, *dirs) if item})
    likely_tests = [p for p in files if any(part in p.lower() for part in ("test", "check", "verify"))][:25]
    likely_inputs = [p for p in files if any(part in p.lower() for part in ("input", "data", "sample", "graph", "log"))][:25]
    likely_existing = [p for p in files if p.lower().endswith((
        ".py", ".js", ".ts", ".sh", ".sparql", ".sql", ".c", ".cc", ".cpp", ".h", ".hpp",
        ".rs", ".ml", ".mli", ".R", ".r", ".stan", ".cbl", ".proto", ".toml",
        ".yaml", ".yml", ".html", ".css", ".java", ".go", ".rb", ".pl",
    )) or p.rsplit("/", 1)[-1].lower() in {"makefile", "cmakelists.txt", "cargo.toml", "dune"}][:25]
    return {
        "top_level": top_level[:50],
        "likely_inputs": likely_inputs,
        "likely_existing_solution_files": likely_existing,
        "likely_tests_or_checkers": likely_tests,
        "visible_file_count": len(files),
        "visible_dir_count": len(dirs),
    }


def _extract_vocab_hits(text: str, vocab: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for item in vocab:
        pattern = r"(?<![a-z0-9_])" + re.escape(item.lower()) + r"(?![a-z0-9_])"
        if re.search(pattern, lowered):
            hits.append(item)
    return hits


def _extract_output_paths(text: str, *, limit: int = 12) -> list[str]:
    raw_paths = re.findall(r"/app/[A-Za-z0-9_./-]+", text)
    paths = [path.rstrip(".,:;)") for path in raw_paths]
    return list(dict.fromkeys(paths))[:limit]


def _static_task_hints(instruction_text: str) -> dict[str, object]:
    return {
        "tool_hints": _extract_vocab_hits(instruction_text, _TOOL_HINT_VOCAB),
        "language_hints": _extract_vocab_hits(instruction_text, _LANGUAGE_HINT_VOCAB),
        "output_paths": _extract_output_paths(instruction_text),
        "prompt_declared_output_paths": list(dict.fromkeys(
            match.group(1).rstrip(".,:;)")
            for match in _PROMPT_DELIVERABLE_RE.finditer(instruction_text)
        ))[:12],
    }


def _classify_instruction_paths(
    referenced_paths: list[str],
    prompt_declared_output_paths: list[str],
    *,
    workspace_root: str,
    visible_files: tuple[str, ...],
    visible_dirs: tuple[str, ...],
) -> dict[str, list[str]]:
    visible_files_set = {path.strip("./") for path in visible_files}
    visible_dirs_set = {path.strip("./") for path in visible_dirs}
    basename_index: dict[str, list[str]] = {}
    for path in (*visible_files, *visible_dirs):
        clean = path.strip("./")
        basename_index.setdefault(clean.rsplit("/", 1)[-1], []).append(clean)
    referenced_rel = [str(path).strip().replace("\\", "/") for path in referenced_paths]
    declared_output_rel = [str(path).strip().replace("\\", "/") for path in prompt_declared_output_paths]
    normalized_referenced = [
        path[len(workspace_root.rstrip("/") + "/") :]
        if workspace_root and path.startswith(workspace_root.rstrip("/") + "/")
        else path.lstrip("/")
        for path in referenced_rel
    ]
    normalized_declared_outputs = [
        path[len(workspace_root.rstrip("/") + "/") :]
        if workspace_root and path.startswith(workspace_root.rstrip("/") + "/")
        else path.lstrip("/")
        for path in declared_output_rel
    ]

    def is_visible(path: str) -> bool:
        clean = path.strip("./")
        if clean in visible_files_set or clean in visible_dirs_set:
            return True
        parent = clean.rsplit("/", 1)[0] if "/" in clean else ""
        if parent and parent in visible_dirs_set:
            return True
        basename_matches = basename_index.get(clean.rsplit("/", 1)[-1], ())
        return len(basename_matches) == 1

    def basename_matches(path: str) -> list[str]:
        clean = path.strip("./")
        matches = basename_index.get(clean.rsplit("/", 1)[-1], ())
        return matches if len(matches) == 1 else []

    referenced_visible = [path for path in normalized_referenced if is_visible(path)]
    referenced_missing = [path for path in normalized_referenced if not is_visible(path)]
    declared_outputs_visible = [path for path in normalized_declared_outputs if is_visible(path)]
    declared_outputs_missing = [path for path in normalized_declared_outputs if not is_visible(path)]

    return {
        "instruction_referenced_paths": list(dict.fromkeys(normalized_referenced))[:20],
        "instruction_referenced_visible_paths": list(dict.fromkeys(referenced_visible))[:20],
        "instruction_referenced_missing_paths": list(dict.fromkeys(referenced_missing))[:20],
        "instruction_referenced_alias_matches": list(dict.fromkeys(
            match
            for path in normalized_referenced
            for match in basename_matches(path)
        ))[:20],
        "prompt_declared_output_paths": list(dict.fromkeys(normalized_declared_outputs))[:20],
        "prompt_declared_output_visible_paths": list(dict.fromkeys(declared_outputs_visible))[:20],
        "prompt_declared_output_missing_paths": list(dict.fromkeys(declared_outputs_missing))[:20],
        "prompt_declared_output_alias_matches": list(dict.fromkeys(
            match
            for path in normalized_declared_outputs
            for match in basename_matches(path)
        ))[:20],
    }


def _build_capabilities() -> dict[str, CapabilityDescriptor]:
    """Build the generic substrate capability descriptors."""
    result: dict[str, CapabilityDescriptor] = {}
    for cap_id, summary, tool_names, cost_hint in _SUBSTRATE_CAPABILITIES:
        result[cap_id] = CapabilityDescriptor(
            capability_id=cap_id,
            summary=summary,
            available=True,
            tool_names=tool_names,
            cost_hint=cost_hint,
        )
    return result


def build_envmap_from_task(
    task_dir: str,
    instruction_text: str,
    *,
    workspace_root: str = "/app",
    network_scope: str = "unknown",
    task_metadata: dict[str, object] | None = None,
    task_toml: dict[str, object] | None = None,
) -> EnvMap:
    """Build an ``EnvMap`` from a task directory and instruction text.

    Parameters
    ----------
    task_dir:
        Path to the task directory (used to scan for visible files).
    instruction_text:
        The task instruction / prompt text.
    workspace_root:
        The in-container workspace root (default ``/app``).
    network_scope:
        Probed network access policy. Use ``unknown`` unless a live probe proved access or denial.
    task_metadata:
        Optional structured facts from the live task environment, such as
        command/module availability probes.
    task_toml:
        Optional public task metadata/resource budgets from task.toml.

    Returns
    -------
    EnvMap
        Ready for the kernel's ``run`` method.
    """
    task_path = Path(task_dir).resolve()
    if task_path.is_dir():
        visible_files, visible_dirs = _scan_visible(str(task_path))
    else:
        visible_files = ()
        visible_dirs = ()

    capabilities = _build_capabilities()
    static_hints = _static_task_hints(instruction_text)
    summary = _build_file_map_summary(visible_files, visible_dirs)
    path_classification = _classify_instruction_paths(
        list(static_hints["output_paths"]),
        list(static_hints["prompt_declared_output_paths"]),
        workspace_root=workspace_root,
        visible_files=visible_files,
        visible_dirs=visible_dirs,
    )
    summary["instruction_tool_hints"] = list(static_hints["tool_hints"])
    summary["instruction_language_hints"] = list(static_hints["language_hints"])
    summary["instruction_output_paths"] = list(static_hints["output_paths"])
    summary.update(path_classification)
    metadata = dict(task_metadata or {})
    public_task_metadata = flatten_task_toml(task_toml)
    if public_task_metadata:
        metadata.setdefault("public_task_metadata", public_task_metadata)
        # Promote stable public metadata to top-level EnvMap task_metadata for prompt/hash simplicity.
        for key in ("category", "difficulty", "tags", "resource_budget", "agent_timeout_sec", "verifier_timeout_sec"):
            if key in public_task_metadata and key not in metadata:
                metadata[key] = public_task_metadata[key]
    metadata.setdefault("static_task_hints", dict(static_hints))
    capability_needs = classify_capability_needs(
        instruction_text,
        task_metadata=metadata,
        visible_files=visible_files,
    )
    metadata["capability_requirements"] = [need.as_dict() for need in capability_needs]
    metadata["required_tool_hints"] = list(required_tool_hints(capability_needs, static_hints["tool_hints"]))
    metadata["env_fact_policy"] = {
        "rule": "EnvMap facts must be probed_true/probed_false/unknown; capability_requirements are inferred hints, not facts",
        "capability_requirements_are_facts": False,
    }
    summary["capability_requirements"] = [need.as_dict() for need in capability_needs]
    summary["required_tool_hints"] = list(metadata["required_tool_hints"])
    probe = metadata.get("environment_probe") if isinstance(metadata.get("environment_probe"), dict) else {}
    if network_scope == "unknown" and isinstance(probe, dict):
        network_probe = probe.get("network") if isinstance(probe.get("network"), dict) else {}
        status = str(network_probe.get("status", "")).strip()
        if status == "probed_true":
            network_scope = "open_external_network"
        elif status == "probed_false":
            network_scope = "probed_no_external_network"

    return EnvMap(
        task_prompt=instruction_text,
        workspace_root=workspace_root,
        visible_files=visible_files,
        visible_dirs=visible_dirs,
        capabilities=capabilities,
        grader_hints={},
        task_metadata=metadata,
        network_scope=network_scope,
        file_tree=_build_file_tree(visible_files, visible_dirs),
        file_map_summary=summary,
    )
