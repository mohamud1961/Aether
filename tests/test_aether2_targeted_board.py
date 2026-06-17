from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from tools import aether2_targeted_board as mod


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_MANIFEST_PATH = (
    REPO_ROOT
    / "tracking"
    / "collab"
    / "aether2_g5_implementation_orchestration_20260613"
    / "targeted_board_manifest.example.json"
)


def _load_example_manifest() -> dict:
    return json.loads(EXAMPLE_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_example_manifest_validates_and_serializes():
    manifest = _load_example_manifest()

    assert manifest == mod.build_example_targeted_board_manifest()

    report = mod.validate_targeted_board_manifest(manifest)
    assert report["status"] == "pass"
    assert report["manifest"]["registration_status"] == "preregistered_only"
    assert report["manifest"]["execution_state"] == "not_executed"
    assert len(report["manifest"]["tasks"]) == 3

    serialized = mod.serialize_targeted_board_manifest(manifest)
    assert json.loads(serialized) == report["manifest"]


def test_oversized_manifest_is_rejected():
    manifest = mod.build_example_targeted_board_manifest()
    manifest["tasks"] = manifest["tasks"] + [deepcopy(manifest["tasks"][0]) for _ in range(8)]
    for index, task in enumerate(manifest["tasks"]):
        task["task_id"] = f"{task['task_id']}_{index}"

    report = mod.validate_targeted_board_manifest(manifest)

    assert report["status"] == "fail"
    assert any("at most 10 tasks" in error for error in report["errors"])


def test_scheduler_constraints_validate_and_serialize():
    scheduler = deepcopy(mod.build_example_targeted_board_manifest()["scheduler"])

    report = mod.validate_targeted_board_scheduler(scheduler)
    assert report["status"] == "pass"
    assert report["scheduler"]["concurrency_limits"] == {
        "light_containers": 3,
        "heavy_builds": 1,
        "qemu_service_sensitive": 1,
    }

    serialized = mod.serialize_targeted_board_scheduler(scheduler)
    assert json.loads(serialized) == report["scheduler"]


def test_scheduler_rejects_light_container_oversubscription():
    scheduler = deepcopy(mod.build_example_targeted_board_manifest()["scheduler"])
    scheduler["concurrency_limits"]["light_containers"] = 4

    report = mod.validate_targeted_board_scheduler(scheduler)

    assert report["status"] == "fail"
    assert any("light_containers" in error and "<= 3" in error for error in report["errors"])
