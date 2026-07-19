from __future__ import annotations

import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_verifier_knownbad_eval.py"
_SPEC = importlib.util.spec_from_file_location("run_verifier_knownbad_eval", _SCRIPT)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


def test_workspace_translation_failure_invalidates_model_measurement() -> None:
    valid, issues = _MODULE._inspection_environment_validity([{
        "requests": [],
        "results": [{
            "kind": "overlay_run_command",
            "stderr": "bash: line 1: cd: /app: No such file or directory",
        }],
    }])

    assert valid is False
    assert issues == ("inspection_workspace_path_unavailable",)


def test_task_inspection_failure_without_workspace_translation_stays_scoreable() -> None:
    valid, issues = _MODULE._inspection_environment_validity([{
        "requests": [],
        "results": [{
            "kind": "probe_port",
            "stdout": "closed rc=111",
        }],
    }])

    assert valid is True
    assert issues == ()


def test_historical_launch_extraction_replays_only_explicit_background_command() -> None:
    commands = _MODULE._historical_launch_commands({
        "steps": [{
            "turn": {
                "actions": [{
                    "arguments": {
                        "command": (
                            "python3 prepare.py\n"
                            "nohup python3 /app/server.py >/app/server.log 2>&1 &\n"
                            "python3 probe.py"
                        ),
                    },
                }],
            },
        }],
    })

    assert commands == ("nohup python3 /app/server.py >/app/server.log 2>&1 &",)


def test_historical_launch_extraction_uses_full_execution_receipt_when_action_is_truncated() -> None:
    commands = _MODULE._historical_launch_commands({
        "steps": [{
            "turn": {"actions": [{"arguments": {"command": "build... [truncated]"}}]},
            "observations": [{
                "summary": (
                    "command exit=0: python3 build.py\n"
                    "nohup python3 /app/server.py >/app/server.log 2>&1 &"
                ),
            }],
        }],
    })

    assert commands == ("nohup python3 /app/server.py >/app/server.log 2>&1 &",)
