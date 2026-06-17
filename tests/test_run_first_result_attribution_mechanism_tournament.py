from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_first_result_attribution_mechanism_tournament import _build_route_manifest, run_tournament


def test_tournament_manifest_swaps_only_tool_surface_for_guard_variant():
    manifest = _build_route_manifest("ignored_result_ids_guard")
    routed = {row["runtime_key"]: row for row in manifest["routed_modules"]}
    assert routed["tools_getter"]["module_import_path"] == "blocks.tools.ignored_result_ids_guard:get_tools"
    assert routed["tool_executor"]["module_import_path"] == "blocks.tools.ignored_result_ids_guard:execute_tool_call"
    assert routed["context"]["module_import_path"] == "blocks.context.path_normalized_verifier_repair_projection:manage"


def test_tournament_runner_writes_result_rows_and_summary(tmp_path, monkeypatch):
    def fake_route(*args, **kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("{}\n", encoding="utf-8")
        (run_dir / "route_manifest.json").write_text("{}", encoding="utf-8")
        return {"runtime_timing": {"model_call_count": 2, "tool_call_count": 1, "total_sec": 1.5}}

    def fake_local(command: str, *, cwd: Path):
        passed = "hidden_verifier.py" not in command
        hidden_stdout = '{"passed": true, "reason_codes": []}\n' if passed else '{"passed": false, "reason_codes": ["ignored_result_ids_mismatch"]}\n'
        return {
            "command": command,
            "cwd": str(cwd),
            "stdout": '{"passed": true}\n' if passed else hidden_stdout,
            "stderr": "",
            "exit_code": 0 if passed else 9,
            "timeout": False,
        }

    monkeypatch.setattr("tools.run_first_result_attribution_mechanism_tournament.run_reference_baseline", fake_route)
    monkeypatch.setattr(
        "tools.run_first_result_attribution_mechanism_tournament.make_azure_gpt54_mini_route_from_env",
        lambda **_: {"provider": "fake"},
    )
    monkeypatch.setattr("tools.run_first_result_attribution_mechanism_tournament._run_local", fake_local)
    monkeypatch.setattr(
        "tools.run_first_result_attribution_mechanism_tournament._docker_preflight",
        lambda: {"available": False, "exit_code": 1, "tail": "docker unavailable"},
    )

    summary = run_tournament(tmp_path)
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["row_count"] == 12
    assert scoreboard["row_count"] == 12
    assert (tmp_path / "prediction.json").exists()
    assert (tmp_path / "comparison_summary.json").exists()
