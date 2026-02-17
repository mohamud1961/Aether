from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from aether.evals.utils.events import Event
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash

from .ingest import open_harness_run_view

SCHEMA_VERSION = "frugal_chop_shop_search.v1"
DEFAULT_K_VALUES: Tuple[int, ...] = (5, 10, 20)
DEFAULT_MAX_REPO_FILES = 2000
BASELINE_PREDICTOR_ID = "deterministic_path_overlap_v1"


class SearchSuiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchTask:
    task_id: str
    source_run_id: str
    source_tier: str
    prompt: str
    repo_map: Dict[str, Any]
    gold_files: List[str]
    gold_derivation: str
    scoring: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gold_derivation": self.gold_derivation,
            "gold_files": list(self.gold_files),
            "prompt": self.prompt,
            "repo_map": dict(self.repo_map),
            "scoring": dict(self.scoring),
            "source_run_id": self.source_run_id,
            "source_tier": self.source_tier,
            "task_id": self.task_id,
        }


def build_t1_search_tasks(
    *,
    runs_root: str | Path,
    out_path: str | Path,
    k_values: Sequence[int] = DEFAULT_K_VALUES,
    max_repo_files: int = DEFAULT_MAX_REPO_FILES,
    intersect_patch_changed: bool = False,
) -> Dict[str, Any]:
    root = Path(runs_root)
    if not root.exists() or not root.is_dir():
        raise SearchSuiteError(f"runs_root does not exist or is not a directory: {root}")
    if max_repo_files < 1:
        raise SearchSuiteError("max_repo_files must be >= 1")

    parsed_k = _normalize_k_values(k_values)
    run_dirs = _discover_run_dirs(root)
    if not run_dirs:
        raise SearchSuiteError(f"No harness run directories found under: {root}")

    tasks: List[SearchTask] = []
    for run_dir in run_dirs:
        tasks.append(
            _build_task_from_t1_run(
                run_dir=run_dir,
                k_values=parsed_k,
                max_repo_files=max_repo_files,
                intersect_patch_changed=intersect_patch_changed,
            )
        )
    tasks = sorted(tasks, key=lambda item: item.task_id)
    _write_jsonl((task.to_dict() for task in tasks), out_path)

    return {
        "runs_processed": len(run_dirs),
        "tasks_written": len(tasks),
        "out_path": Path(out_path).as_posix(),
    }


def score_search_predictions(
    *,
    predictions_path: str | Path,
    tasks_path: str | Path,
    report_path: str | Path,
) -> Dict[str, Any]:
    tasks = _load_tasks(tasks_path)
    predictions = _load_predictions(predictions_path)

    per_task: List[Dict[str, Any]] = []
    by_tier: Dict[str, List[Dict[str, Any]]] = {"T1": [], "T2": []}

    for task in tasks:
        prediction = predictions.get(task.task_id, [])
        metrics = _score_task(task=task, ranked_files=prediction)
        row = {
            "task_id": task.task_id,
            "source_tier": task.source_tier,
            "gold_count": len(task.gold_files),
            "prediction_count": len(prediction),
            "metrics": metrics,
        }
        per_task.append(row)
        by_tier.setdefault(task.source_tier, []).append(row)

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tasks_path": Path(tasks_path).as_posix(),
        "predictions_path": Path(predictions_path).as_posix(),
        "tier_reports": {
            tier: _aggregate_tier(rows)
            for tier, rows in sorted(by_tier.items())
        },
        "all_tiers_combined_labeled": _aggregate_tier(per_task),
        "per_task": per_task,
    }
    Path(report_path).write_text(canonical_json_dumps(report) + "\n", encoding="utf-8")
    return {
        "tasks_scored": len(tasks),
        "report_path": Path(report_path).as_posix(),
    }


def generate_baseline_search_predictions(
    *,
    tasks_path: str | Path,
    out_path: str | Path,
) -> Dict[str, Any]:
    """Generate deterministic Search-only predictions without reading task gold labels."""
    prediction_inputs = _load_baseline_prediction_inputs(tasks_path)
    rows: List[Dict[str, Any]] = []
    for item in prediction_inputs:
        ranked = _rank_files(
            prompt=item["prompt"],
            task_id=item["task_id"],
            files=item["repo_files"],
        )
        rows.append(
            {
                "predictor": BASELINE_PREDICTOR_ID,
                "task_id": item["task_id"],
                "source_run_id": item["source_run_id"],
                "ranked_files": ranked,
            }
        )

    rows = sorted(rows, key=lambda payload: str(payload["task_id"]))
    _write_jsonl(rows, out_path)
    return {
        "tasks_scored": len(rows),
        "out_path": Path(out_path).as_posix(),
        "predictor": BASELINE_PREDICTOR_ID,
    }


def adapt_t2_external_run(
    *,
    external_run_dir: str | Path,
    out_path: str | Path,
    task_id: str | None = None,
    k_values: Sequence[int] = DEFAULT_K_VALUES,
    max_repo_files: int = DEFAULT_MAX_REPO_FILES,
) -> Dict[str, Any]:
    root = Path(external_run_dir)
    if not root.exists() or not root.is_dir():
        raise SearchSuiteError(f"external_run_dir does not exist or is not a directory: {root}")
    if max_repo_files < 1:
        raise SearchSuiteError("max_repo_files must be >= 1")

    parsed_k = _normalize_k_values(k_values)
    resolved_task_id = task_id or root.name

    prompt_file = root / "prompt.txt"
    workspace_root = root / "workspace"
    patch_file = root / "patch.diff"
    if not prompt_file.exists():
        raise SearchSuiteError(f"T2 adapter requires prompt.txt: {prompt_file}")
    if not workspace_root.exists() or not workspace_root.is_dir():
        raise SearchSuiteError(f"T2 adapter requires workspace/ directory: {workspace_root}")
    if not patch_file.exists():
        raise SearchSuiteError(f"T2 adapter requires patch.diff: {patch_file}")

    prompt = prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        raise SearchSuiteError(f"T2 adapter prompt.txt is empty: {prompt_file}")

    repo_map = _build_repo_map(workspace_root, max_repo_files=max_repo_files)
    gold_files = sorted(_extract_patch_paths(patch_file.read_text(encoding="utf-8")))
    if not gold_files:
        raise SearchSuiteError(f"T2 adapter could not derive patch-derived gold files from: {patch_file}")

    task = SearchTask(
        task_id=resolved_task_id,
        source_run_id=resolved_task_id,
        source_tier="T2",
        prompt=prompt,
        repo_map=repo_map,
        gold_files=gold_files,
        gold_derivation="patch_derived",
        scoring=_scoring_payload(parsed_k),
    )
    _write_jsonl([task.to_dict()], out_path)
    return {
        "tasks_written": 1,
        "out_path": Path(out_path).as_posix(),
        "task_id": resolved_task_id,
    }


def _build_task_from_t1_run(
    *,
    run_dir: Path,
    k_values: Sequence[int],
    max_repo_files: int,
    intersect_patch_changed: bool,
) -> SearchTask:
    view = open_harness_run_view(run_dir)
    events = view.load_events()

    run_id = _extract_run_id(events, run_dir.name)
    prompt = _extract_prompt(events, run_id)
    workspace_root = _resolve_workspace_root(run_dir, events)
    repo_map = _build_repo_map(workspace_root, max_repo_files=max_repo_files)

    gold_files = _derive_t1_gold_files(events=events, workspace_root=workspace_root)
    gold_derivation = "trace_derived"
    workspace_patch_files = _collect_patch_files(workspace_root)
    if intersect_patch_changed:
        if workspace_patch_files:
            gold_files = sorted(set(gold_files).intersection(workspace_patch_files))
    if not gold_files:
        baseline_patch_files = _collect_baseline_patch_files(run_dir=run_dir, workspace_root=workspace_root)
        if baseline_patch_files:
            gold_files = sorted(baseline_patch_files)
            gold_derivation = "patch_derived"
        elif workspace_patch_files:
            gold_files = sorted(workspace_patch_files)
            gold_derivation = "patch_derived"
    if not gold_files:
        raise SearchSuiteError(f"{run_dir}: empty gold_files after deterministic derivation")

    return SearchTask(
        task_id=run_id,
        source_run_id=run_id,
        source_tier="T1",
        prompt=prompt,
        repo_map=repo_map,
        gold_files=gold_files,
        gold_derivation=gold_derivation,
        scoring=_scoring_payload(k_values),
    )


def _derive_t1_gold_files(*, events: Sequence[Event], workspace_root: Path) -> List[str]:
    gold: set[str] = set()
    for event in events:
        if event.event_type not in {"TOOL_CALL", "TOOL_DENY", "VERIFIER_RESULT"}:
            continue
        payload = event.payload
        for field in ("files_read", "files_written"):
            values = payload.get(field)
            if not isinstance(values, list):
                continue
            for raw_path in values:
                normalized = _normalize_path(raw_path, workspace_root)
                if normalized is not None:
                    gold.add(normalized)
    return sorted(gold)


def _resolve_workspace_root(run_dir: Path, events: Sequence[Event]) -> Path:
    default_workspace = run_dir / "workspace"
    if default_workspace.exists() and default_workspace.is_dir():
        return default_workspace.resolve()

    for event in events:
        task_spec = event.payload.get("task_spec")
        if isinstance(task_spec, dict):
            workspace_raw = task_spec.get("workspace_root")
            workspace = _as_existing_dir(workspace_raw)
            if workspace is not None:
                return workspace

    for event in events:
        workspace = _as_existing_dir(event.payload.get("cwd"))
        if workspace is not None and _is_descendant_or_equal(workspace, run_dir):
            return workspace
    return run_dir.resolve()


def _build_repo_map(workspace_root: Path, *, max_repo_files: int) -> Dict[str, Any]:
    files: List[str] = []
    for path in sorted(workspace_root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        files.append(path.relative_to(workspace_root).as_posix())

    total_files = len(files)
    visible = files[:max_repo_files]
    return {
        "format": "file_list.v1",
        "root": workspace_root.as_posix(),
        "files": visible,
        "truncation": {
            "policy": "max_files",
            "max_files": max_repo_files,
            "total_files": total_files,
            "truncated": total_files > max_repo_files,
        },
    }


def _extract_prompt(events: Sequence[Event], run_id: str) -> str:
    for event in events:
        task_spec = event.payload.get("task_spec")
        if isinstance(task_spec, dict):
            prompt = task_spec.get("prompt")
            if isinstance(prompt, str) and prompt.strip():
                return prompt.strip()
    for event in events:
        for key in ("prompt", "task_description", "issue"):
            value = event.payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return f"Search task for run {run_id}"


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


def _normalize_k_values(values: Sequence[int]) -> List[int]:
    if not values:
        raise SearchSuiteError("k_values must not be empty")
    normalized = sorted({int(value) for value in values if int(value) > 0})
    if not normalized:
        raise SearchSuiteError("k_values must include at least one positive integer")
    return normalized


def _scoring_payload(k_values: Sequence[int]) -> Dict[str, Any]:
    return {
        "k_values": list(k_values),
        "metric": "recall_at_k",
        "secondary_metrics": ["hit_at_k", "mrr"],
    }


def _load_baseline_prediction_inputs(path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise SearchSuiteError(f"tasks line {line_no}: expected JSON object")

        task_id = _require_str(payload, "task_id", line_no, source_name="tasks")
        source_run_id = payload.get("source_run_id", task_id)
        if not isinstance(source_run_id, str) or not source_run_id:
            raise SearchSuiteError(f"tasks line {line_no}: missing required string field source_run_id")
        prompt = _require_str(payload, "prompt", line_no, source_name="tasks")

        repo_map = payload.get("repo_map")
        if not isinstance(repo_map, dict):
            raise SearchSuiteError(f"tasks line {line_no}: repo_map must be object")
        repo_files = repo_map.get("files")
        if not isinstance(repo_files, list):
            raise SearchSuiteError(f"tasks line {line_no}: repo_map.files must be list")

        rows.append(
            {
                "task_id": task_id,
                "source_run_id": source_run_id,
                "prompt": prompt,
                "repo_files": [path for path in (_normalize_prediction_path(item) for item in repo_files) if path],
            }
        )

    return sorted(rows, key=lambda item: str(item["task_id"]))


def _rank_files(*, prompt: str, task_id: str, files: Sequence[str]) -> List[str]:
    prompt_tokens = set(_tokenize(prompt))
    scored: List[Tuple[int, int, int, int, str]] = []
    for path in files:
        path_tokens = _tokenize(path)
        overlap = len(prompt_tokens.intersection(path_tokens))
        token_count = len(path_tokens)
        depth = path.count("/")
        tie_hash = int(stable_hash({"task_id": task_id, "path": path})[:12], 16)
        scored.append((-overlap, -token_count, depth, tie_hash, path))
    scored.sort()
    return [item[4] for item in scored]


def _tokenize(value: str) -> List[str]:
    return [token for token in re.findall(r"[A-Za-z0-9_]+", value.lower()) if len(token) > 1]


def _score_task(*, task: SearchTask, ranked_files: Sequence[str]) -> Dict[str, Any]:
    gold = set(task.gold_files)
    normalized_pred = [path for path in (_normalize_prediction_path(item) for item in ranked_files) if path]

    by_k: Dict[str, Dict[str, float]] = {}
    for k in task.scoring.get("k_values", DEFAULT_K_VALUES):
        k_int = int(k)
        top_k = normalized_pred[:k_int]
        hits = len(gold.intersection(top_k))
        recall = (float(hits) / float(len(gold))) if gold else 0.0
        hit = 1.0 if hits > 0 else 0.0
        by_k[str(k_int)] = {"recall_at_k": recall, "hit_at_k": hit}

    mrr = 0.0
    for rank, candidate in enumerate(normalized_pred, start=1):
        if candidate in gold:
            mrr = 1.0 / float(rank)
            break

    return {"by_k": by_k, "mrr": mrr}


def _aggregate_tier(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "task_count": 0,
            "mean_metrics": {"mrr": 0.0},
        }

    sample_metrics = rows[0]["metrics"]["by_k"]
    k_keys = sorted(sample_metrics.keys(), key=lambda item: int(item))

    mean_by_k: Dict[str, Dict[str, float]] = {}
    for k in k_keys:
        recall_values = [float(row["metrics"]["by_k"][k]["recall_at_k"]) for row in rows]
        hit_values = [float(row["metrics"]["by_k"][k]["hit_at_k"]) for row in rows]
        mean_by_k[k] = {
            "recall_at_k_mean": sum(recall_values) / len(recall_values),
            "hit_at_k_mean": sum(hit_values) / len(hit_values),
        }

    mrr_values = [float(row["metrics"]["mrr"]) for row in rows]
    return {
        "task_count": len(rows),
        "mean_metrics": {
            "by_k": mean_by_k,
            "mrr": sum(mrr_values) / len(mrr_values),
        },
    }


def _load_tasks(path: str | Path) -> List[SearchTask]:
    tasks: List[SearchTask] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise SearchSuiteError(f"tasks line {line_no}: expected JSON object")
        source_tier = payload.get("source_tier")
        if source_tier not in {"T1", "T2"}:
            raise SearchSuiteError(f"tasks line {line_no}: invalid source_tier {source_tier!r}")
        gold_derivation = payload.get("gold_derivation")
        if gold_derivation not in {"trace_derived", "patch_derived"}:
            raise SearchSuiteError(f"tasks line {line_no}: invalid gold_derivation {gold_derivation!r}")

        task_id = _require_str(payload, "task_id", line_no, source_name="tasks")
        source_run_id = _require_str(payload, "source_run_id", line_no, source_name="tasks")
        prompt = _require_str(payload, "prompt", line_no, source_name="tasks")
        repo_map = payload.get("repo_map")
        if not isinstance(repo_map, dict):
            raise SearchSuiteError(f"tasks line {line_no}: repo_map must be object")
        gold_files = payload.get("gold_files")
        if not isinstance(gold_files, list) or not gold_files:
            raise SearchSuiteError(f"tasks line {line_no}: gold_files must be non-empty list")
        scoring = payload.get("scoring")
        if not isinstance(scoring, dict):
            raise SearchSuiteError(f"tasks line {line_no}: scoring must be object")

        tasks.append(
            SearchTask(
                task_id=task_id,
                source_run_id=source_run_id,
                source_tier=source_tier,
                prompt=prompt,
                repo_map=repo_map,
                gold_files=sorted({_normalize_prediction_path(item) for item in gold_files if _normalize_prediction_path(item)}),
                gold_derivation=gold_derivation,
                scoring=scoring,
            )
        )
    return sorted(tasks, key=lambda item: item.task_id)


def _load_predictions(path: str | Path) -> Dict[str, List[str]]:
    predictions: Dict[str, List[str]] = {}
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise SearchSuiteError(f"predictions line {line_no}: expected JSON object")
        raw_task_id = payload.get("task_id", payload.get("source_run_id"))
        if not isinstance(raw_task_id, str) or not raw_task_id:
            raise SearchSuiteError(f"predictions line {line_no}: missing task_id or source_run_id")
        ranked_files = payload.get("ranked_files")
        if not isinstance(ranked_files, list):
            raise SearchSuiteError(f"predictions line {line_no}: ranked_files must be list")
        predictions[raw_task_id] = [path for path in (_normalize_prediction_path(item) for item in ranked_files) if path]
    return predictions


def _normalize_prediction_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("\\", "/").lstrip("./")
    return normalized if normalized else None


def _normalize_path(raw_path: Any, workspace_root: Path) -> str | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    candidate = Path(raw_path.strip())
    if not candidate.is_absolute():
        normalized = candidate.as_posix().lstrip("./")
        return normalized or None

    candidate_resolved = candidate.resolve()
    workspace_resolved = workspace_root.resolve()
    if not _is_descendant_or_equal(candidate_resolved, workspace_resolved):
        return None
    return candidate_resolved.relative_to(workspace_resolved).as_posix()


def _is_descendant_or_equal(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _collect_patch_files(workspace_root: Path) -> set[str]:
    git_dir = workspace_root / ".git"
    if not git_dir.exists():
        return set()
    try:
        completed = subprocess.run(
            ["git", "-C", workspace_root.as_posix(), "diff", "--name-only", "--relative"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return set()
    if completed.returncode != 0:
        return set()
    return {
        line.strip().replace("\\", "/")
        for line in completed.stdout.splitlines()
        if line.strip()
    }


def _collect_baseline_patch_files(*, run_dir: Path, workspace_root: Path) -> set[str]:
    task_slug = _extract_task_slug(run_dir.name)
    if task_slug is None:
        return set()

    baseline_root = _repo_root() / "official_tasks" / task_slug / "environment"
    if not baseline_root.exists() or not baseline_root.is_dir():
        return set()

    try:
        completed = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "diff",
                "--no-index",
                "--name-only",
                baseline_root.as_posix(),
                workspace_root.as_posix(),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return set()

    if completed.returncode not in {0, 1}:
        return set()

    changed: set[str] = set()
    for raw in completed.stdout.splitlines():
        normalized = _normalize_baseline_diff_path(
            raw_path=raw,
            baseline_root=baseline_root,
            workspace_root=workspace_root,
        )
        if normalized is not None:
            changed.add(normalized)
    return changed


def _normalize_baseline_diff_path(*, raw_path: str, baseline_root: Path, workspace_root: Path) -> str | None:
    candidate = raw_path.strip().replace("\\", "/")
    if not candidate:
        return None

    workspace_prefix = workspace_root.as_posix().rstrip("/") + "/"
    if candidate.startswith(workspace_prefix):
        rel = candidate[len(workspace_prefix):]
        return rel or None

    baseline_prefix = baseline_root.as_posix().rstrip("/") + "/"
    if candidate.startswith(baseline_prefix):
        rel = candidate[len(baseline_prefix):]
        return rel or None

    return _normalize_prediction_path(candidate)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _extract_task_slug(run_name: str) -> str | None:
    match = re.match(r"(.+)_\d{8}_\d{6}$", run_name)
    if match is None:
        return None
    return match.group(1)


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


def _require_str(payload: Mapping[str, Any], key: str, line_no: int, source_name: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SearchSuiteError(f"{source_name} line {line_no}: missing required string field {key}")
    return value


def _as_existing_dir(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.exists() and candidate.is_dir():
        return candidate.resolve()
    return None


def _write_jsonl(records: Iterable[Mapping[str, Any]], out_path: str | Path) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(canonical_json_dumps(dict(record)))
            handle.write("\n")


def _discover_run_dirs(runs_root: Path) -> List[Path]:
    if (runs_root / "event_log.jsonl").exists() or (runs_root / "events.jsonl").exists():
        return [runs_root]
    run_dirs: List[Path] = []
    for entry in sorted(runs_root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        if (entry / "event_log.jsonl").exists() or (entry / "events.jsonl").exists():
            run_dirs.append(entry)
    return run_dirs
