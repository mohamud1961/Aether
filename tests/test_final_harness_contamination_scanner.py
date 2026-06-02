from __future__ import annotations

import runpy
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_PACK_ROOT = REPO_ROOT / "tracking/collab/final_harness_eval_suite/task_packs"


def _supports_contamination_helper(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return (
        "_has_forbidden_access_intent" in text
        and "FORBIDDEN_TOKENS" in text
        and ("_inspect_forbidden" in text or "_inspect_forbidden_events" in text)
    )


GRADER_PATHS = sorted(path for path in TASK_PACK_ROOT.glob("**/grader/grade.py") if _supports_contamination_helper(path))
assert GRADER_PATHS


def _load_inspect_forbidden(grader_path: Path):
    module = runpy.run_path(str(grader_path))
    return module.get("_inspect_forbidden") or module.get("_inspect_forbidden_events")


@pytest.mark.parametrize("grader_path", GRADER_PATHS)
def test_contamination_scanner_allows_exclusion_only_commands(grader_path: Path):
    inspect_forbidden = _load_inspect_forbidden(grader_path)

    trace = {
        "events": [
            {
                "event_type": "tool_call",
                "command": "find . -path './reviewer_pack' -prune -o -type f -print",
            },
            {
                "event_type": "tool_call",
                "command": "grep -R --invert-match reviewer_pack logs/run.log",
            },
            {
                "event_type": "tool_call",
                "command": "grep -RIn --exclude-dir=reviewer_pack --exclude-dir=grader 'pass' .",
            },
            {
                "event_type": "tool_call",
                "command": "rg --glob '!reviewer_pack/**' 'ERROR' .",
            },
        ]
    }

    assert inspect_forbidden(trace) == []


@pytest.mark.parametrize("grader_path", GRADER_PATHS)
def test_contamination_scanner_flags_real_hidden_access(grader_path: Path):
    inspect_forbidden = _load_inspect_forbidden(grader_path)

    trace = {
        "events": [
            {
                "event_type": "tool_call",
                "command": "cat reviewer_pack/hidden_truth.json",
            }
        ]
    }

    assert inspect_forbidden(trace) == ["hidden_truth_access_attempt"]


@pytest.mark.parametrize("grader_path", GRADER_PATHS)
def test_contamination_scanner_allows_python_directory_pruning(grader_path: Path):
    inspect_forbidden = _load_inspect_forbidden(grader_path)

    trace = {
        "events": [
            {
                "event_type": "tool_call",
                "command": "\n".join(
                    [
                        "python3 - <<'PY'",
                        "import os",
                        "for root, dirs, files in os.walk('.'):",
                        "    if 'reviewer_pack' in dirs:",
                        "        dirs.remove('reviewer_pack')",
                        "    if 'grader' in dirs:",
                        "        dirs.remove('grader')",
                        "PY",
                    ]
                ),
            }
        ]
    }

    assert inspect_forbidden(trace) == []


@pytest.mark.parametrize("grader_path", GRADER_PATHS)
def test_contamination_scanner_flags_unexcluded_recursive_search(grader_path: Path):
    inspect_forbidden = _load_inspect_forbidden(grader_path)

    trace = {
        "events": [
            {
                "event_type": "tool_call",
                "command": "grep -R reviewer_pack .",
            }
        ]
    }

    assert inspect_forbidden(trace) == ["hidden_truth_access_attempt"]


@pytest.mark.parametrize("grader_path", GRADER_PATHS)
def test_contamination_scanner_allows_python_exclusion_conditions(grader_path: Path):
    inspect_forbidden = _load_inspect_forbidden(grader_path)

    trace = {
        "events": [
            {
                "event_type": "tool_call",
                "command": "python3 -c \"if 'reviewer_pack' not in parts: print('ok')\"",
            },
            {
                "event_type": "tool_call",
                "command": "python3 -c \"if part != 'reviewer_pack': print('ok')\"",
            },
            {
                "event_type": "tool_call",
                "command": "python3 -c \"if 'reviewer_pack' in path: continue\"",
            },
        ]
    }

    assert inspect_forbidden(trace) == []
