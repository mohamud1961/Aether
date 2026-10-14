"""Pre-registration: seal a plan, detect any later change to it, and refuse analysis when it changed.

A plan is a YAML file in the harness_evals.miniyaml subset: flat keys, scalars and block lists only.
Arms are quoted strings of space-separated key=value pairs, for example
  - "name=candidate agent=minimal model=example-model"
Task paths are relative to the plan file's directory.

Plan keys, all required:
  question        text of the question the plan answers
  arms            exactly two arm strings; each has a name=<arm> pair and any other key=value pairs
  baseline        name of the reference arm
  candidate       name of the arm under test (must differ from baseline)
  tasks           task directory paths
  sentinels       non-empty list of task ids that must not regress (each must be in tasks)
  k               trials per arm per task (integer >= 1)
  primary_metric  pass_rate
  falsifier       expression; if it holds, the claim is FALSIFIED (see prereg_expr)
  promotion_bar   expression; the claim is SUPPORTED only when it holds and nothing falsifies it

The seal file (plan.sealed.json by default) records the plan's sha256, the settings, each arm's config,
each task's task_hash and grader_hash, the seal time given with --at, and prereg_hash: a sha256 over the
rest of the record. Nothing here reads a clock. verify() reports every item that differs from the seal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from harness_evals import miniyaml
from harness_evals.miniyaml import MiniYamlError
from harness_evals.prereg_expr import ExpressionError
from harness_evals.prereg_expr import parse as parse_expression
from harness_evals.task import Task, TaskFormatError, load_task, task_hash

SEAL_FILE = "plan.sealed.json"
SEAL_SCHEMA = "harness-evals.prereg/1"
PRIMARY_METRICS = ("pass_rate",)
PLAN_KEYS = frozenset(
    {
        "question",
        "arms",
        "baseline",
        "candidate",
        "tasks",
        "sentinels",
        "k",
        "primary_metric",
        "falsifier",
        "promotion_bar",
    }
)
_DIGEST_SKIP_SUFFIXES = (".pyc",)


class PlanError(ValueError):
    """A plan, seal or trial file is missing, malformed, or cannot be sealed."""


@dataclass(frozen=True)
class Plan:
    question: str
    arms: dict[str, dict[str, str]]
    baseline: str
    candidate: str
    tasks: tuple[str, ...]
    sentinels: tuple[str, ...]
    k: int
    primary_metric: str
    falsifier: str
    promotion_bar: str

    def settings(self) -> dict[str, Any]:
        return {
            "baseline": self.baseline,
            "candidate": self.candidate,
            "k": self.k,
            "primary_metric": self.primary_metric,
            "falsifier": self.falsifier,
            "promotion_bar": self.promotion_bar,
            "sentinels": list(self.sentinels),
        }


@dataclass(frozen=True)
class Verification:
    seal: dict[str, Any]
    changes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.changes


def load_plan(path: Path) -> tuple[Plan, str]:
    """Parse a plan file. Returns the plan and the sha256 of the file bytes it was parsed from."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise PlanError(f"cannot read plan {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PlanError(f"plan {path} is not UTF-8: {exc}") from exc
    return parse_plan(text), hashlib.sha256(raw).hexdigest()


def parse_plan(text: str) -> Plan:
    try:
        data = miniyaml.parse(text)
    except MiniYamlError as exc:
        raise PlanError(f"plan: {exc}") from exc
    missing = sorted(PLAN_KEYS - set(data))
    unknown = sorted(set(data) - PLAN_KEYS)
    if missing:
        raise PlanError(f"plan is missing keys {missing}")
    if unknown:
        raise PlanError(f"plan has unknown keys {unknown}")
    arms = _arms(data["arms"])
    baseline = _text(data, "baseline")
    candidate = _text(data, "candidate")
    if baseline == candidate or set(arms) != {baseline, candidate}:
        raise PlanError(
            "arms must be exactly two, named by baseline and candidate, and the names must differ"
        )
    tasks = _names(data, "tasks")
    task_ids = [Path(entry).name for entry in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise PlanError("tasks lists the same task directory name twice")
    sentinels = _names(data, "sentinels")
    if len(set(sentinels)) != len(sentinels):
        raise PlanError("sentinels lists a task twice")
    absent = sorted(set(sentinels) - set(task_ids))
    if absent:
        raise PlanError(f"sentinels {absent} are not in tasks")
    k = data["k"]
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise PlanError("k must be an integer of at least 1")
    primary = _text(data, "primary_metric")
    if primary not in PRIMARY_METRICS:
        raise PlanError(
            f"primary_metric must be one of {list(PRIMARY_METRICS)}, got {primary!r}"
        )
    falsifier = _expression(data, "falsifier")
    promotion_bar = _expression(data, "promotion_bar")
    return Plan(
        question=_text(data, "question"),
        arms=arms,
        baseline=baseline,
        candidate=candidate,
        tasks=tuple(tasks),
        sentinels=tuple(sorted(sentinels)),
        k=k,
        primary_metric=primary,
        falsifier=falsifier,
        promotion_bar=promotion_bar,
    )


def seal(
    plan_path: Path, *, at: str, seal_path: Path, replace: bool = False
) -> dict[str, Any]:
    """Write the seal file for a plan and return the record. Refuses to overwrite unless replace is set."""
    sealed_at = _timestamp(at)
    if seal_path.exists() and not replace:
        raise PlanError(f"{seal_path} already exists; pass replace to overwrite it")
    plan, plan_sha = load_plan(plan_path)
    prints, errors = fingerprint_tasks(plan, Path(plan_path).resolve().parent)
    if errors:
        raise PlanError(
            "cannot seal a plan with unreadable tasks: " + "; ".join(errors)
        )
    record: dict[str, Any] = {
        "schema": SEAL_SCHEMA,
        "question": plan.question,
        "plan_sha256": plan_sha,
        "sealed_at": sealed_at,
        "settings": plan.settings(),
        "arms": plan.arms,
        "tasks": prints,
    }
    record["prereg_hash"] = record_hash(record)
    seal_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def verify(plan_path: Path, seal_path: Path) -> Verification:
    """Compare the plan and its task directories with the seal. Every differing item is listed."""
    plan, plan_sha = load_plan(plan_path)
    seal_record = load_seal(seal_path)
    prints, errors = fingerprint_tasks(plan, Path(plan_path).resolve().parent)
    changes = _diff(seal_record, plan, plan_sha, prints, errors)
    return Verification(seal=seal_record, changes=tuple(changes))


def load_seal(seal_path: Path) -> dict[str, Any]:
    try:
        record = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanError(
            f"no seal at {seal_path}; run 'harness-evals prereg seal' first"
        ) from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"seal {seal_path} is unreadable: {exc}") from exc
    if not isinstance(record, dict):
        raise PlanError(f"seal {seal_path} is not a JSON object")
    return record


def fingerprint_tasks(
    plan: Plan, plan_dir: Path
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Return {task_id: {path, task_hash, grader_hash}} and one error line per unreadable task."""
    prints: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for rel in plan.tasks:
        try:
            task = load_task(plan_dir / rel)
        except (TaskFormatError, OSError) as exc:
            errors.append(f"task {rel}: cannot load: {exc}")
            continue
        prints[task.id] = {
            "path": rel,
            "task_hash": task_hash(task),
            "grader_hash": grader_hash(task),
        }
    return prints, errors


def grader_hash(task: Task) -> str:
    """sha256 over every file in the task's grader/ directory, in sorted relative-path order."""
    grader_dir = task.root / "grader"
    files = sorted(
        path
        for path in grader_dir.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not path.name.endswith(_DIGEST_SKIP_SUFFIXES)
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(grader_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def record_hash(record: dict[str, Any]) -> str:
    """sha256 of the canonical JSON of a seal record, excluding its own prereg_hash field."""
    body = {key: value for key, value in record.items() if key != "prereg_hash"}
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _diff(
    sealed: dict[str, Any],
    plan: Plan,
    plan_sha: str,
    prints: dict[str, dict[str, str]],
    errors: list[str],
) -> list[str]:
    changes: list[str] = []
    if sealed.get("schema") != SEAL_SCHEMA:
        changes.append(
            f"seal schema is {sealed.get('schema')!r}, expected {SEAL_SCHEMA!r}"
        )
    if sealed.get("prereg_hash") != record_hash(sealed):
        changes.append(
            "seal record altered: prereg_hash does not match the record contents"
        )
    if sealed.get("plan_sha256") != plan_sha:
        changes.append(
            f"plan file changed: sealed sha256 {_short(sealed.get('plan_sha256'))}, now {_short(plan_sha)}"
        )
    if sealed.get("question") != plan.question:
        changes.append(
            f"question changed: sealed {sealed.get('question')!r}, now {plan.question!r}"
        )
    changes.extend(
        _compare_flat("setting", _as_dict(sealed, "settings", changes), plan.settings())
    )
    changes.extend(_compare_arms(_as_dict(sealed, "arms", changes), plan.arms))
    changes.extend(_compare_tasks(_as_dict(sealed, "tasks", changes), prints, plan))
    changes.extend(errors)
    return changes


def _compare_flat(
    label: str, sealed: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    out: list[str] = []
    for key in sorted(set(sealed) | set(current)):
        if sealed.get(key) != current.get(key):
            out.append(
                f"{label} {key}: sealed {sealed.get(key)!r}, now {current.get(key)!r}"
            )
    return out


def _compare_arms(
    sealed: dict[str, Any], current: dict[str, dict[str, str]]
) -> list[str]:
    out: list[str] = []
    for name in sorted(set(sealed) | set(current)):
        if name not in sealed:
            out.append(f"arm {name}: added to plan")
        elif name not in current:
            out.append(f"arm {name}: removed from plan")
        else:
            out.extend(
                _compare_flat(
                    f"arm {name} config", _as_mapping(sealed[name]), current[name]
                )
            )
    return out


def _compare_tasks(
    sealed: dict[str, Any], prints: dict[str, dict[str, str]], plan: Plan
) -> list[str]:
    out: list[str] = []
    for task_id in sorted(set(sealed) | set(prints)):
        new = prints.get(task_id)
        if task_id not in sealed:
            out.append(f"task {task_id}: added to plan")
            continue
        old = _as_mapping(sealed[task_id])
        if new is None:
            if old.get("path") in plan.tasks:
                out.append(f"task {task_id}: sealed but not readable now")
            else:
                out.append(f"task {task_id}: removed from plan")
            continue
        if old.get("path") != new["path"]:
            out.append(
                f"task {task_id}: path sealed {old.get('path')!r}, now {new['path']!r}"
            )
        if old.get("task_hash") != new["task_hash"]:
            out.append(
                f"task {task_id}: task files changed (task_hash {_short(old.get('task_hash'))}, "
                f"now {_short(new['task_hash'])})"
            )
        if old.get("grader_hash") != new["grader_hash"]:
            out.append(
                f"task {task_id}: grader changed (grader_hash {_short(old.get('grader_hash'))}, "
                f"now {_short(new['grader_hash'])})"
            )
    return out


def _as_dict(record: dict[str, Any], key: str, changes: list[str]) -> dict[str, Any]:
    value = record.get(key, {})
    if not isinstance(value, dict):
        changes.append(f"seal field {key!r} is malformed")
        return {}
    return value


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _short(digest: Any) -> str:
    return str(digest)[:12] if digest is not None else "none"


def _arms(value: Any) -> dict[str, dict[str, str]]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, str) for item in value)
    ):
        raise PlanError("arms must be a list of exactly two quoted 'name=...' strings")
    arms: dict[str, dict[str, str]] = {}
    for item in value:
        pairs: dict[str, str] = {}
        for token in item.split():
            key, sep, setting = token.partition("=")
            if not sep or not key or not setting:
                raise PlanError(f"arm {item!r}: every token must be key=value")
            if key in pairs:
                raise PlanError(f"arm {item!r}: key {key!r} appears twice")
            pairs[key] = setting
        name = pairs.pop("name", None)
        if name is None:
            raise PlanError(f"arm {item!r} has no name=<arm> pair")
        if name in arms:
            raise PlanError(f"arm name {name!r} is declared twice")
        arms[name] = pairs
    return arms


def _names(data: dict[str, Any], key: str) -> list[str]:
    value = data[key]
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise PlanError(f"{key} must be a non-empty list of strings")
    return list(value)


def _text(data: dict[str, Any], key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{key} must be a non-empty string")
    return value


def _expression(data: dict[str, Any], key: str) -> str:
    text = _text(data, key)
    try:
        parse_expression(text)
    except ExpressionError as exc:
        raise PlanError(f"{key}: {exc}") from exc
    return text


def _timestamp(text: str) -> str:
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise PlanError(f"--at must be an ISO 8601 timestamp, got {text!r}") from exc
    return text
