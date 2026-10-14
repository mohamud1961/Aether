"""Task format v2: load and fingerprint a task directory.

A task directory holds task.yaml, prompt.md, workspace/ (initial files), grader/grade.py,
reference/solve.sh, known_bad/*.sh and ceiling.md. The loader checks that every required
file exists and that each known-bad script declares its expected reason code. It does not
judge whether the grader is correct: that is the job of validate-graders.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_evals import miniyaml
from harness_evals.miniyaml import MiniYamlError

TASK_FILE = "task.yaml"
_EXPECT_LINE = re.compile(r"^# expect: ([a-z][a-z0-9_]*)$", re.MULTILINE)
_REQUIRED_FILES = ("prompt.md", "ceiling.md", "grader/grade.py", "reference/solve.sh")
_FIELD_TYPES: dict[str, type] = {
    "id": str,
    "family": str,
    "title": str,
    "summary": str,
    "timeout_s": int,
    "network": bool,
    "outputs": list,
    "tags": list,
}


class TaskFormatError(ValueError):
    """A task directory does not match the task format."""


@dataclass(frozen=True)
class KnownBad:
    path: Path
    expect: str


@dataclass(frozen=True)
class Task:
    id: str
    family: str
    title: str
    summary: str
    timeout_s: int
    network: bool
    outputs: tuple[str, ...]
    tags: tuple[str, ...]
    root: Path
    _known_bad: tuple[KnownBad, ...] = field(compare=False, repr=False)

    admission: str = "capability"

    @property
    def prompt(self) -> str:
        return (self.root / "prompt.md").read_text(encoding="utf-8")

    @property
    def workspace_dir(self) -> Path:
        return self.root / "workspace"

    @property
    def grader_path(self) -> Path:
        return self.root / "grader" / "grade.py"

    @property
    def reference_script(self) -> Path:
        return self.root / "reference" / "solve.sh"

    @property
    def known_bad(self) -> tuple[KnownBad, ...]:
        return self._known_bad

    @property
    def ceiling_path(self) -> Path:
        return self.root / "ceiling.md"


def load_task(path: Path) -> Task:
    root = Path(path).resolve()
    task_file = root / TASK_FILE
    if not task_file.is_file():
        raise TaskFormatError(f"{root}: missing {TASK_FILE}")
    try:
        data = miniyaml.parse(task_file.read_text(encoding="utf-8"))
    except MiniYamlError as exc:
        raise TaskFormatError(f"{task_file}: {exc}") from exc
    _check_fields(data, root)
    for name in _REQUIRED_FILES:
        if not (root / name).is_file():
            raise TaskFormatError(f"{root}: missing {name}")
    if not (root / "workspace").is_dir():
        raise TaskFormatError(f"{root}: missing workspace/ directory")
    return Task(
        id=data["id"],
        family=data["family"],
        title=data["title"],
        summary=data["summary"],
        timeout_s=data["timeout_s"],
        network=data["network"],
        outputs=tuple(data["outputs"]),
        tags=tuple(data["tags"]),
        root=root,
        admission=data.get("admission", "capability"),
        _known_bad=_load_known_bads(root),
    )


def find_task_dirs(root: Path) -> list[Path]:
    """Every directory under root (root included) that contains task.yaml, sorted."""
    return sorted(
        {path.parent for path in Path(root).rglob(TASK_FILE) if path.is_file()}
    )


def discover(root: Path, include_smoke: bool = False) -> list[Task]:
    tasks = [load_task(path) for path in find_task_dirs(root)]
    return [task for task in tasks if include_smoke or task.admission == "capability"]


def task_hash(task: Task) -> str:
    """SHA-256 over every file in the task directory, in sorted relative-path order."""
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in task.root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    for path in files:
        digest.update(path.relative_to(task.root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _check_fields(data: dict[str, Any], root: Path) -> None:
    missing = sorted(set(_FIELD_TYPES) - set(data))
    unknown = sorted(set(data) - set(_FIELD_TYPES) - {"admission"})
    if data.get("admission", "capability") not in {"capability", "smoke", "debug"}:
        raise TaskFormatError(f"{root}: admission must be capability, smoke or debug")
    if missing:
        raise TaskFormatError(f"{root}/{TASK_FILE}: missing fields {missing}")
    if unknown:
        raise TaskFormatError(f"{root}/{TASK_FILE}: unknown fields {unknown}")
    for name, expected in _FIELD_TYPES.items():
        value = data[name]
        if expected is bool:
            ok = isinstance(value, bool)
        elif expected is int:
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif expected is list:
            ok = isinstance(value, list) and all(
                isinstance(item, str) for item in value
            )
        else:
            ok = isinstance(value, str) and value.strip() != ""
        if not ok:
            raise TaskFormatError(
                f"{root}/{TASK_FILE}: field {name!r} has the wrong type or is empty"
            )
    if data["id"] != root.name:
        raise TaskFormatError(
            f"{root}: id {data['id']!r} must equal the directory name"
        )
    if data["timeout_s"] <= 0:
        raise TaskFormatError(f"{root}: timeout_s must be positive")


def _load_known_bads(root: Path) -> tuple[KnownBad, ...]:
    folder = root / "known_bad"
    if not folder.is_dir():
        return ()
    found: list[KnownBad] = []
    for script in sorted(folder.glob("*.sh")):
        matches = _EXPECT_LINE.findall(script.read_text(encoding="utf-8"))
        if len(matches) != 1:
            raise TaskFormatError(
                f"{script}: needs exactly one '# expect: <reason_code>' line, found {len(matches)}"
            )
        found.append(KnownBad(path=script, expect=matches[0]))
    return tuple(found)
