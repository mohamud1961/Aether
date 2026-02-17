from __future__ import annotations

import difflib
import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from aether.evals.utils.events import Event
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash

from .ingest import open_harness_run_view

TASKS_SCHEMA_VERSION = "frugal_chop_shop_patch_tasks.v1"
REPORT_SCHEMA_VERSION = "frugal_chop_shop_patch_report.v1"
COMPONENT_NOTICE = "Component metrics only; not capability claims."
DEFAULT_MIN_TASKS = 5
DEFAULT_MAX_TASKS = 20
DEFAULT_MAX_REPO_FILES = 2000

CAT_REDIRECT_RE = re.compile(r"cat\s*>\s*([A-Za-z0-9_./-]+)\s*<<")


class PatchSuiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class PatchTask:
    task_id: str
    source_tier: str
    prompt: str
    repo_map: Dict[str, Any]
    allowed_edit_targets: List[str]
    gold_patch_targets: List[str]
    gold_patch_content: str
    preimage_hashes: Dict[str, str]
    preimage_contents: Dict[str, str | None]
    source_run_id: str
    source_provider: str
    source_step_id: int
    source_run_dir: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_edit_targets": list(self.allowed_edit_targets),
            "gold_patch_content": self.gold_patch_content,
            "gold_patch_targets": list(self.gold_patch_targets),
            "preimage_contents": dict(self.preimage_contents),
            "preimage_hashes": dict(self.preimage_hashes),
            "prompt": self.prompt,
            "repo_map": dict(self.repo_map),
            "source_provider": self.source_provider,
            "source_run_dir": self.source_run_dir,
            "source_run_id": self.source_run_id,
            "source_step_id": self.source_step_id,
            "source_tier": self.source_tier,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class LoadedPatchTask:
    task_id: str
    source_tier: str
    prompt: str
    repo_map: Dict[str, Any]
    allowed_edit_targets: List[str]
    gold_patch_targets: List[str]
    gold_patch_content: str
    preimage_hashes: Dict[str, str]
    preimage_contents: Dict[str, str | None]


def build_t1_patch_tasks(
    *,
    runs_root: str | Path,
    out_path: str | Path,
    min_tasks: int = DEFAULT_MIN_TASKS,
    max_tasks: int = DEFAULT_MAX_TASKS,
    max_repo_files: int = DEFAULT_MAX_REPO_FILES,
) -> Dict[str, Any]:
    if min_tasks < 1:
        raise PatchSuiteError("min_tasks must be >= 1")
    if max_tasks < min_tasks:
        raise PatchSuiteError("max_tasks must be >= min_tasks")
    if max_repo_files < 1:
        raise PatchSuiteError("max_repo_files must be >= 1")

    root = Path(runs_root)
    if not root.exists() or not root.is_dir():
        raise PatchSuiteError(f"runs_root does not exist or is not a directory: {root}")

    run_dirs = _discover_run_dirs(root)
    if not run_dirs:
        raise PatchSuiteError(f"No harness run directories found under: {root}")

    tasks: List[PatchTask] = []
    for run_dir in run_dirs:
        tasks.extend(_build_tasks_from_run(run_dir=run_dir, max_repo_files=max_repo_files))

    tasks = sorted(
        tasks,
        key=lambda item: (item.source_provider, item.source_run_dir, item.source_step_id, item.gold_patch_targets[0]),
    )
    if not tasks:
        raise PatchSuiteError(f"No patch tasks with deterministic gold content found under: {root}")

    selected = tasks[:max_tasks]
    if len(selected) < min_tasks:
        raise PatchSuiteError(
            f"Only {len(selected)} patch tasks derived from real run data; require at least {min_tasks}"
        )

    numbered: List[PatchTask] = []
    for idx, task in enumerate(selected, start=1):
        numbered.append(
            PatchTask(
                task_id=f"patch_{idx:03d}",
                source_tier=task.source_tier,
                prompt=task.prompt,
                repo_map=task.repo_map,
                allowed_edit_targets=task.allowed_edit_targets,
                gold_patch_targets=task.gold_patch_targets,
                gold_patch_content=task.gold_patch_content,
                preimage_hashes=task.preimage_hashes,
                preimage_contents=task.preimage_contents,
                source_run_id=task.source_run_id,
                source_provider=task.source_provider,
                source_step_id=task.source_step_id,
                source_run_dir=task.source_run_dir,
            )
        )

    _write_jsonl((task.to_dict() for task in numbered), out_path)
    return {
        "schema_version": TASKS_SCHEMA_VERSION,
        "runs_processed": len(run_dirs),
        "tasks_written": len(numbered),
        "out_path": Path(out_path).as_posix(),
    }


def run_patch_suite(
    *,
    tasks_path: str | Path,
    model_id: str,
    report_path: str | Path,
    adapter_mode: str = "mock",
    search_report_path: str | Path | None = None,
    predictions_path: str | Path | None = None,
) -> Dict[str, Any]:
    tasks = _load_tasks(tasks_path)
    adapter = _build_adapter(adapter_mode=adapter_mode, model_id=model_id)

    predictions: List[Dict[str, Any]] = []
    for task in tasks:
        predictions.append(adapter.predict(task))

    resolved_predictions_path = Path(predictions_path) if predictions_path is not None else Path(report_path).with_suffix(
        ".predictions.jsonl"
    )
    _write_jsonl(predictions, resolved_predictions_path)

    resolved_search_report = _resolve_search_report_path(tasks_path=tasks_path, explicit=search_report_path)
    summary = score_patch_predictions(
        predictions_path=resolved_predictions_path,
        tasks_path=tasks_path,
        report_path=report_path,
        model_id=model_id,
        search_report_path=resolved_search_report,
    )
    summary["predictions_path"] = resolved_predictions_path.as_posix()
    return summary


def score_patch_predictions(
    *,
    predictions_path: str | Path,
    tasks_path: str | Path,
    report_path: str | Path,
    model_id: str | None = None,
    search_report_path: str | Path | None = None,
) -> Dict[str, Any]:
    tasks = _load_tasks(tasks_path)
    predictions = _load_predictions(predictions_path)

    per_task: List[Dict[str, Any]] = []
    by_tier: Dict[str, List[Dict[str, Any]]] = {"T1": [], "T2": []}

    for task in tasks:
        prediction = predictions.get(task.task_id, {})
        metrics = _score_task(task=task, prediction=prediction)
        row = {
            "metrics": metrics,
            "source_tier": task.source_tier,
            "task_id": task.task_id,
        }
        per_task.append(row)
        by_tier.setdefault(task.source_tier, []).append(row)

    patch_tier_reports = {tier: _aggregate_patch(rows) for tier, rows in sorted(by_tier.items())}
    patch_all = _aggregate_patch(per_task)

    search_component = _extract_search_component(search_report_path)
    patch_component = _to_patch_component(patch_all)

    tier_reports: Dict[str, Dict[str, Any]] = {}
    for tier in sorted(set(list(patch_tier_reports.keys()) + list(search_component["tier_reports"].keys()))):
        tier_reports[tier] = {
            "component_notice": COMPONENT_NOTICE,
            "patch_only": _to_patch_component(patch_tier_reports.get(tier, _aggregate_patch([]))),
            "search_only": dict(search_component["tier_reports"].get(tier, _empty_search_component())),
            "source_tier": tier,
        }

    report = {
        "all_tiers_combined_labeled": {
            "component_notice": COMPONENT_NOTICE,
            "patch_only": patch_component,
            "search_only": dict(search_component["all_tiers_combined_labeled"]),
        },
        "component_notice": COMPONENT_NOTICE,
        "generated_at": "1970-01-01T00:00:00+00:00",
        "model_id": model_id,
        "patch_only": patch_component,
        "patch_tier_reports": patch_tier_reports,
        "per_task": per_task,
        "predictions_path": Path(predictions_path).as_posix(),
        "schema_version": REPORT_SCHEMA_VERSION,
        "search_only": {
            "all_tiers_combined_labeled": dict(search_component["all_tiers_combined_labeled"]),
            "source_report_path": search_component["source_report_path"],
            "tier_reports": dict(search_component["tier_reports"]),
        },
        "tasks_path": Path(tasks_path).as_posix(),
        "tier_reports": tier_reports,
    }

    Path(report_path).write_text(canonical_json_dumps(report) + "\n", encoding="utf-8")
    return {
        "report_path": Path(report_path).as_posix(),
        "tasks_scored": len(tasks),
    }


def _build_tasks_from_run(*, run_dir: Path, max_repo_files: int) -> List[PatchTask]:
    slug = _extract_task_slug(run_dir.name)
    if slug is None:
        return []

    baseline_root = _repo_root() / "official_tasks" / slug / "environment"
    workspace_root = run_dir / "workspace"
    if not baseline_root.exists() or not baseline_root.is_dir() or not workspace_root.exists() or not workspace_root.is_dir():
        return []

    view = open_harness_run_view(run_dir)
    events = view.load_events()
    run_id = _extract_run_id(events, run_dir.name)
    prompt = _extract_prompt(events, run_id)
    repo_map = _build_repo_map(workspace_root, max_repo_files=max_repo_files)

    tasks: List[PatchTask] = []
    seen_targets: set[str] = set()
    source_provider = _extract_provider(run_dir)

    for event in events:
        if event.event_type != "TOOL_CALL":
            continue

        exit_code = event.payload.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            continue

        command = _extract_command(event.payload)
        if not command:
            continue

        candidate_paths = _extract_candidate_paths(command=command, workspace_root=workspace_root)
        if not candidate_paths:
            continue

        for rel_path in candidate_paths:
            if rel_path in seen_targets:
                continue

            baseline_file = baseline_root / rel_path
            workspace_file = workspace_root / rel_path
            if not workspace_file.exists() or not workspace_file.is_file():
                continue

            after_text = _read_text_file(workspace_file)
            if after_text is None:
                continue

            before_exists = baseline_file.exists() and baseline_file.is_file()
            before_text = ""
            if before_exists:
                before_loaded = _read_text_file(baseline_file)
                if before_loaded is None:
                    continue
                before_text = before_loaded

            if before_text == after_text:
                continue

            patch = _build_unified_patch(
                rel_path=rel_path,
                before_text=before_text,
                after_text=after_text,
                before_exists=before_exists,
            )
            if not patch.strip():
                continue

            preimage_hash = hashlib.sha256(before_text.encode("utf-8")).hexdigest()
            preimage_hashes = {rel_path: preimage_hash}
            preimage_contents = {rel_path: before_text if before_exists else None}

            tasks.append(
                PatchTask(
                    task_id="pending",
                    source_tier="T1",
                    prompt=prompt,
                    repo_map=repo_map,
                    allowed_edit_targets=[rel_path],
                    gold_patch_targets=[rel_path],
                    gold_patch_content=patch,
                    preimage_hashes=preimage_hashes,
                    preimage_contents=preimage_contents,
                    source_run_id=run_id,
                    source_provider=source_provider,
                    source_step_id=_safe_step_id(event),
                    source_run_dir=run_dir.as_posix(),
                )
            )
            seen_targets.add(rel_path)

    return tasks


def _build_unified_patch(*, rel_path: str, before_text: str, after_text: str, before_exists: bool) -> str:
    fromfile = f"a/{rel_path}" if before_exists else "/dev/null"
    tofile = f"b/{rel_path}"
    diff_lines = list(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=fromfile,
            tofile=tofile,
            n=3,
        )
    )
    if not diff_lines:
        return ""

    patch = "".join(diff_lines)
    if not patch.endswith("\n"):
        patch += "\n"
    return patch


def _extract_task_slug(run_name: str) -> str | None:
    match = re.match(r"(.+)_\d{8}_\d{6}$", run_name)
    if not match:
        return None
    return match.group(1)


def _extract_provider(run_dir: Path) -> str:
    parts = list(run_dir.parts)
    if "results" in parts:
        idx = parts.index("results")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return "unknown"


def _extract_prompt(events: Sequence[Event], run_id: str) -> str:
    for event in events:
        task_spec = event.payload.get("task_spec")
        if isinstance(task_spec, dict):
            prompt = task_spec.get("prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt.strip()

    for event in events:
        intent_contract = event.payload.get("intent_contract")
        if isinstance(intent_contract, dict):
            goal = intent_contract.get("goal_statement")
            if isinstance(goal, str) and goal.strip():
                return goal.strip()

    for event in events:
        for key in ("prompt", "task_description", "issue"):
            value = event.payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return f"Patch task for run {run_id}"


def _extract_run_id(events: Sequence[Event], fallback: str) -> str:
    run_ids = sorted(
        {
            run_id
            for run_id in (event.payload.get("run_id") for event in events)
            if isinstance(run_id, str) and run_id
        }
    )
    if not run_ids:
        return fallback
    if len(run_ids) == 1:
        return run_ids[0]
    return "__".join(run_ids)


def _build_repo_map(workspace_root: Path, *, max_repo_files: int) -> Dict[str, Any]:
    files: List[str] = []
    for path in sorted(workspace_root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        files.append(path.relative_to(workspace_root).as_posix())

    total_files = len(files)
    visible = files[:max_repo_files]
    return {
        "files": visible,
        "format": "file_list.v1",
        "root": workspace_root.as_posix(),
        "truncation": {
            "max_files": max_repo_files,
            "policy": "max_files",
            "total_files": total_files,
            "truncated": total_files > max_repo_files,
        },
    }


def _extract_command(payload: Mapping[str, Any]) -> List[str]:
    tool_args = payload.get("tool_args")
    if not isinstance(tool_args, dict):
        return []
    command = tool_args.get("command")
    if not isinstance(command, list):
        return []
    return [str(item) for item in command if isinstance(item, str)]


def _extract_candidate_paths(*, command: Sequence[str], workspace_root: Path) -> List[str]:
    candidates: List[str] = []

    if len(command) >= 3 and command[0] == "bash" and command[1] == "-c":
        script = command[2]
        candidates.extend(_extract_from_script(script))

    if command and command[0] == "cat":
        joined = " ".join(command)
        candidates.extend(_extract_from_script(joined))

    if len(command) >= 4 and command[0] == "git" and command[1] == "clone":
        dest = command[-1]
        candidates.append(f"{dest.rstrip('/')}/.git/HEAD")

    if len(command) >= 3 and command[0] == "git" and command[1] == "init" and "--bare" in command:
        bare_idx = command.index("--bare")
        if bare_idx + 1 < len(command):
            bare_path = command[bare_idx + 1]
            candidates.append(f"{bare_path.rstrip('/')}/HEAD")

    if command and command[0] == "gcc" and "-o" in command:
        out_idx = command.index("-o")
        if out_idx + 1 < len(command):
            candidates.append(command[out_idx + 1])

    normalized: List[str] = []
    for raw in candidates:
        rel = _normalize_path(raw, workspace_root)
        if rel is not None:
            normalized.append(rel)

    return sorted(set(normalized))


def _extract_from_script(script: str) -> List[str]:
    paths = [match.group(1) for match in CAT_REDIRECT_RE.finditer(script)]
    return [path.strip() for path in paths if path.strip()]


def _normalize_path(raw_path: Any, workspace_root: Path) -> str | None:
    if not isinstance(raw_path, str):
        return None
    stripped = raw_path.strip().strip("\"'")
    if not stripped:
        return None

    candidate = Path(stripped)
    if candidate.is_absolute():
        try:
            rel = candidate.resolve().relative_to(workspace_root.resolve())
        except Exception:
            return None
        normalized = rel.as_posix()
        return normalized if normalized else None

    normalized = candidate.as_posix().replace("\\", "/").lstrip("./")
    return normalized if normalized else None


def _read_text_file(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except Exception:
        return None

    if b"\x00" in data:
        return None

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _discover_run_dirs(runs_root: Path) -> List[Path]:
    if (runs_root / "event_log.jsonl").exists() or (runs_root / "events.jsonl").exists():
        return [runs_root]

    run_dirs: set[Path] = set()
    for event_path in runs_root.rglob("event_log.jsonl"):
        run_dirs.add(event_path.parent)
    for event_path in runs_root.rglob("events.jsonl"):
        parent = event_path.parent
        if (parent / "event_log.jsonl").exists():
            continue
        run_dirs.add(parent)

    return sorted(run_dirs, key=lambda item: item.as_posix())


def _load_tasks(path: str | Path) -> List[LoadedPatchTask]:
    tasks: List[LoadedPatchTask] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise PatchSuiteError(f"tasks line {line_no}: expected JSON object")

        source_tier = payload.get("source_tier")
        if source_tier not in {"T1", "T2"}:
            raise PatchSuiteError(f"tasks line {line_no}: invalid source_tier {source_tier!r}")

        task_id = _require_str(payload, "task_id", line_no, source_name="tasks")
        prompt = _require_str(payload, "prompt", line_no, source_name="tasks")

        repo_map = payload.get("repo_map")
        if not isinstance(repo_map, dict):
            raise PatchSuiteError(f"tasks line {line_no}: repo_map must be object")

        allowed_edit_targets = _normalize_path_list(payload.get("allowed_edit_targets"), line_no=line_no, field="allowed_edit_targets")
        gold_patch_targets = _normalize_path_list(payload.get("gold_patch_targets"), line_no=line_no, field="gold_patch_targets")
        gold_patch_content = _require_str(payload, "gold_patch_content", line_no, source_name="tasks")

        preimage_hashes = payload.get("preimage_hashes")
        if not isinstance(preimage_hashes, dict):
            raise PatchSuiteError(f"tasks line {line_no}: preimage_hashes must be object")
        normalized_preimage_hashes: Dict[str, str] = {}
        for raw_key, raw_value in preimage_hashes.items():
            key = _normalize_prediction_path(raw_key)
            if key is None:
                continue
            if isinstance(raw_value, str) and raw_value:
                normalized_preimage_hashes[key] = raw_value

        preimage_contents_raw = payload.get("preimage_contents")
        normalized_preimage_contents: Dict[str, str | None] = {}
        if isinstance(preimage_contents_raw, dict):
            for raw_key, raw_value in preimage_contents_raw.items():
                key = _normalize_prediction_path(raw_key)
                if key is None:
                    continue
                if raw_value is None:
                    normalized_preimage_contents[key] = None
                elif isinstance(raw_value, str):
                    normalized_preimage_contents[key] = raw_value

        for gold_target in gold_patch_targets:
            if gold_target not in normalized_preimage_hashes:
                raise PatchSuiteError(
                    f"tasks line {line_no}: preimage_hashes missing gold target {gold_target!r}"
                )
            normalized_preimage_contents.setdefault(gold_target, None)

        tasks.append(
            LoadedPatchTask(
                task_id=task_id,
                source_tier=source_tier,
                prompt=prompt,
                repo_map=repo_map,
                allowed_edit_targets=allowed_edit_targets,
                gold_patch_targets=gold_patch_targets,
                gold_patch_content=gold_patch_content,
                preimage_hashes=normalized_preimage_hashes,
                preimage_contents=normalized_preimage_contents,
            )
        )

    return sorted(tasks, key=lambda item: item.task_id)


def _load_predictions(path: str | Path) -> Dict[str, Dict[str, Any]]:
    predictions: Dict[str, Dict[str, Any]] = {}
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise PatchSuiteError(f"predictions line {line_no}: expected JSON object")

        task_id = payload.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise PatchSuiteError(f"predictions line {line_no}: missing task_id")
        predictions[task_id] = payload

    return predictions


def _score_task(*, task: LoadedPatchTask, prediction: Mapping[str, Any]) -> Dict[str, Any]:
    predicted_targets = _normalize_path_list(
        prediction.get("predicted_patch_targets", prediction.get("gold_patch_targets", [])),
        line_no=-1,
        field="predicted_patch_targets",
        allow_empty=True,
    )
    if not predicted_targets:
        inferred = _extract_patch_paths(str(prediction.get("predicted_patch_content", "")))
        predicted_targets = sorted(inferred)

    gold_targets = set(task.gold_patch_targets)
    predicted_target_set = set(predicted_targets)
    hits = len(gold_targets.intersection(predicted_target_set))
    file_target_hit_rate = (float(hits) / float(len(gold_targets))) if gold_targets else 0.0

    predicted_patch_content = str(prediction.get("predicted_patch_content", ""))

    assumed_preimage_hashes = prediction.get("assumed_preimage_hashes")
    normalized_assumed: Dict[str, str] = {}
    if isinstance(assumed_preimage_hashes, dict):
        for raw_key, raw_value in assumed_preimage_hashes.items():
            key = _normalize_prediction_path(raw_key)
            if key is None:
                continue
            if isinstance(raw_value, str) and raw_value:
                normalized_assumed[key] = raw_value

    preimage_hash_match = all(
        normalized_assumed.get(path) == task.preimage_hashes.get(path)
        for path in task.gold_patch_targets
    )

    patch_applies_cleanly = _patch_applies_cleanly(
        patch_content=predicted_patch_content,
        preimage_contents=task.preimage_contents,
    )

    content_similarity = _jaccard_changed_lines(
        predicted_patch=predicted_patch_content,
        gold_patch=task.gold_patch_content,
    )

    exact_match = predicted_patch_content == task.gold_patch_content

    return {
        "content_similarity": content_similarity,
        "exact_match": exact_match,
        "file_target_hit_rate": file_target_hit_rate,
        "patch_applies_cleanly": patch_applies_cleanly,
        "preimage_hash_match": preimage_hash_match,
    }


def _patch_applies_cleanly(*, patch_content: str, preimage_contents: Mapping[str, str | None]) -> bool:
    if not isinstance(patch_content, str) or not patch_content.strip():
        return False

    with tempfile.TemporaryDirectory(prefix="patch_check_") as tmpdir:
        root = Path(tmpdir)
        for rel_path, content in sorted(preimage_contents.items()):
            rel = _normalize_prediction_path(rel_path)
            if rel is None:
                continue
            if content is None:
                continue
            file_path = root / rel
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        patch_path = root / "candidate.patch"
        patch_path.write_text(patch_content, encoding="utf-8")

        completed = subprocess.run(
            ["git", "apply", "--check", patch_path.as_posix()],
            capture_output=True,
            text=True,
            cwd=root.as_posix(),
            check=False,
        )
        return completed.returncode == 0


def _changed_lines(patch_content: str) -> set[str]:
    changed: set[str] = set()
    for raw_line in patch_content.splitlines():
        if raw_line.startswith("diff --git "):
            continue
        if raw_line.startswith("@@"):
            continue
        if raw_line.startswith("--- "):
            continue
        if raw_line.startswith("+++ "):
            continue
        if raw_line.startswith("+") or raw_line.startswith("-"):
            changed.add(raw_line)
    return changed


def _jaccard_changed_lines(*, predicted_patch: str, gold_patch: str) -> float:
    predicted = _changed_lines(predicted_patch)
    gold = _changed_lines(gold_patch)

    if not predicted and not gold:
        return 1.0

    union = predicted.union(gold)
    if not union:
        return 1.0

    intersection = predicted.intersection(gold)
    return float(len(intersection)) / float(len(union))


def _aggregate_patch(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "mean_metrics": {
                "content_similarity": 0.0,
                "exact_match_rate": 0.0,
                "file_target_hit_rate": 0.0,
                "patch_applies_cleanly_rate": 0.0,
                "preimage_hash_match_rate": 0.0,
            },
            "task_count": 0,
        }

    count = len(rows)

    file_target_hit_rate = sum(float(row["metrics"]["file_target_hit_rate"]) for row in rows) / count
    patch_applies_cleanly_rate = (
        sum(1.0 if bool(row["metrics"]["patch_applies_cleanly"]) else 0.0 for row in rows) / count
    )
    preimage_hash_match_rate = (
        sum(1.0 if bool(row["metrics"]["preimage_hash_match"]) else 0.0 for row in rows) / count
    )
    content_similarity = sum(float(row["metrics"]["content_similarity"]) for row in rows) / count
    exact_match_rate = sum(1.0 if bool(row["metrics"]["exact_match"]) else 0.0 for row in rows) / count

    return {
        "mean_metrics": {
            "content_similarity": content_similarity,
            "exact_match_rate": exact_match_rate,
            "file_target_hit_rate": file_target_hit_rate,
            "patch_applies_cleanly_rate": patch_applies_cleanly_rate,
            "preimage_hash_match_rate": preimage_hash_match_rate,
        },
        "task_count": count,
    }


def _extract_search_component(search_report_path: str | Path | None) -> Dict[str, Any]:
    default = {
        "all_tiers_combined_labeled": _empty_search_component(),
        "source_report_path": None,
        "tier_reports": {"T1": _empty_search_component(), "T2": _empty_search_component()},
    }
    if search_report_path is None:
        return default

    path = Path(search_report_path)
    if not path.exists():
        return default

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return default

    out = {
        "all_tiers_combined_labeled": _search_component_from_aggregate(payload.get("all_tiers_combined_labeled")),
        "source_report_path": path.as_posix(),
        "tier_reports": {
            "T1": _search_component_from_aggregate((payload.get("tier_reports") or {}).get("T1")),
            "T2": _search_component_from_aggregate((payload.get("tier_reports") or {}).get("T2")),
        },
    }
    return out


def _search_component_from_aggregate(aggregate: Any) -> Dict[str, float]:
    if not isinstance(aggregate, dict):
        return _empty_search_component()

    mean_metrics = aggregate.get("mean_metrics")
    if not isinstance(mean_metrics, dict):
        return _empty_search_component()

    by_k = mean_metrics.get("by_k")
    recall_at_5 = 0.0
    if isinstance(by_k, dict):
        item_5 = by_k.get("5")
        if isinstance(item_5, dict):
            value = item_5.get("recall_at_k_mean")
            if isinstance(value, (int, float)):
                recall_at_5 = float(value)

    mrr = mean_metrics.get("mrr")
    mrr_value = float(mrr) if isinstance(mrr, (int, float)) else 0.0
    return {
        "mrr": mrr_value,
        "recall_at_5": recall_at_5,
    }


def _empty_search_component() -> Dict[str, float]:
    return {"mrr": 0.0, "recall_at_5": 0.0}


def _to_patch_component(aggregate: Mapping[str, Any]) -> Dict[str, Any]:
    mean_metrics = aggregate.get("mean_metrics")
    if not isinstance(mean_metrics, dict):
        mean_metrics = {}

    return {
        "content_similarity_mean": float(mean_metrics.get("content_similarity", 0.0)),
        "exact_match_rate": float(mean_metrics.get("exact_match_rate", 0.0)),
        "file_target_hit_rate": float(mean_metrics.get("file_target_hit_rate", 0.0)),
        "patch_applies_cleanly_rate": float(mean_metrics.get("patch_applies_cleanly_rate", 0.0)),
        "preimage_hash_match_rate": float(mean_metrics.get("preimage_hash_match_rate", 0.0)),
        "task_count": int(aggregate.get("task_count", 0)),
    }


def _resolve_search_report_path(*, tasks_path: str | Path, explicit: str | Path | None) -> str | Path | None:
    if explicit is not None:
        return explicit

    sibling = Path(tasks_path).with_name("chop_shop_report.json")
    if sibling.exists():
        return sibling
    return None


def _normalize_path_list(
    raw: Any,
    *,
    line_no: int,
    field: str,
    allow_empty: bool = False,
) -> List[str]:
    if not isinstance(raw, list):
        if allow_empty:
            return []
        raise PatchSuiteError(f"tasks line {line_no}: {field} must be list")

    normalized = sorted({_normalize_prediction_path(item) for item in raw if _normalize_prediction_path(item)})
    if not normalized and not allow_empty:
        raise PatchSuiteError(f"tasks line {line_no}: {field} must not be empty")
    return normalized


def _extract_patch_paths(diff_text: str) -> set[str]:
    paths: set[str] = set()
    header_pattern = re.compile(r"^diff --git a/(.+?) b/(.+)$")
    for raw_line in diff_text.splitlines():
        line = raw_line.strip()
        header_match = header_pattern.match(line)
        if header_match:
            paths.add(header_match.group(2))
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            candidate = line[4:].strip()
            if candidate == "/dev/null":
                continue
            if candidate.startswith("a/") or candidate.startswith("b/"):
                candidate = candidate[2:]
            if candidate:
                paths.add(candidate)
    return {item.replace("\\", "/") for item in paths if item}


def _safe_step_id(event: Event) -> int:
    raw = event.payload.get("step_id")
    if isinstance(raw, int):
        return raw
    if isinstance(event.step_id, int):
        return event.step_id
    return -1


def _normalize_prediction_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("\\", "/").lstrip("./")
    return normalized if normalized else None


def _require_str(payload: Mapping[str, Any], key: str, line_no: int, source_name: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise PatchSuiteError(f"{source_name} line {line_no}: missing required string field {key}")
    return value


def _write_jsonl(records: Iterable[Mapping[str, Any]], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(canonical_json_dumps(dict(record)))
            handle.write("\n")


class LocalMockPatchAdapter:
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    def predict(self, task: LoadedPatchTask) -> Dict[str, Any]:
        selector = int(stable_hash({"model_id": self._model_id, "task_id": task.task_id})[:2], 16) % 4

        predicted_targets = list(task.gold_patch_targets)
        predicted_patch_content = task.gold_patch_content
        assumed_preimage_hashes = dict(task.preimage_hashes)

        if selector == 1:
            first = task.gold_patch_targets[0]
            wrong = assumed_preimage_hashes[first]
            assumed_preimage_hashes[first] = f"0{wrong[1:]}" if len(wrong) > 1 else "0"
        elif selector == 2:
            predicted_targets = []
            predicted_patch_content = ""
        elif selector == 3:
            predicted_patch_content = f"diff --git a/{task.gold_patch_targets[0]} b/{task.gold_patch_targets[0]}\n"

        return {
            "assumed_preimage_hashes": assumed_preimage_hashes,
            "model_id": self._model_id,
            "predicted_patch_content": predicted_patch_content,
            "predicted_patch_targets": predicted_targets,
            "source_tier": task.source_tier,
            "task_id": task.task_id,
        }


def _build_adapter(*, adapter_mode: str, model_id: str) -> LocalMockPatchAdapter:
    if adapter_mode != "mock":
        raise PatchSuiteError(f"Unsupported adapter_mode={adapter_mode!r}; use 'mock'")
    return LocalMockPatchAdapter(model_id=model_id)
