from __future__ import annotations

import importlib.resources
import json
from pathlib import Path

import pytest

import aether.harbor_agent as harbor_agent


def test_packaged_harbor_agent_has_single_stable_selector_and_no_checkout_path_injection() -> None:
    assert harbor_agent.AetherHarborAgent.name() == "aether"
    assert harbor_agent.AetherHarborAgent.version(object.__new__(harbor_agent.AetherHarborAgent)) == "s3-harbor-v1"
    source = Path(harbor_agent.__file__).read_text(encoding="utf-8")
    assert "sys.path" not in source
    assert "aether_build" not in source
    assert "runner." not in source


def test_harbor_runtime_lock_binds_qualified_lifecycle_authority() -> None:
    text = importlib.resources.files("aether").joinpath("harbor_runtime_lock.json").read_text(encoding="utf-8")
    lock = json.loads(text)
    assert lock == {
        "schema_version": "aether.harbor_runtime_lock.v1",
        "harbor_version": "0.20.0",
        "agent_selector": "aether.harbor_agent:AetherHarborAgent",
        "lifecycle_authority": "harbor",
        "grader_authority": "harbor_official_task_grader",
        "aether_owns_benchmark_lifecycle": False,
        "aether_owns_grading": False,
    }


def test_missing_harbor_dependency_fails_before_agent_work() -> None:
    if harbor_agent._HARBOR_IMPORT_ERROR is None:
        pytest.skip("Harbor is installed on this test surface")
    with pytest.raises(RuntimeError, match="Harbor import unavailable"):
        harbor_agent.AetherHarborAgent(logs_dir=Path("/tmp/no-provider-work"))


def test_harbor_agent_import_keeps_execution_graph_lazy() -> None:
    """Importing the adapter must not eagerly own the whole Aether runtime graph."""
    import json
    import subprocess
    import sys

    code = (
        "import json,sys; "
        "import aether.harbor_agent; "
        "print(json.dumps(sorted(k for k in sys.modules if k == 'aether' or k.startswith('aether.'))))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(completed.stdout)
    assert loaded == [
        "aether",
        "aether.environment_extensions",
        "aether.harbor_agent",
        "aether.harbor_runtime",
        "aether.model_profile",
    ]
