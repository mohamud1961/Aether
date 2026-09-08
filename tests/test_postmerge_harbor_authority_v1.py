from pathlib import Path
import json
import importlib.resources

import aether.harbor_agent as harbor_agent


def test_production_harbor_adapter_targets_selected_aether_pcr_runtime_only() -> None:
    source = Path(harbor_agent.__file__).read_text(encoding="utf-8")
    assert "class AetherHarborAgent(BaseAgent)" in source
    assert "from .harbor_runtime import" in source
    assert "runner." not in source
    assert "harness.aether2" not in source
    assert "Aether2HarborAgent" not in source


def test_harbor_lock_exposes_only_root_aether_agent_selector() -> None:
    lock = json.loads(
        importlib.resources.files("aether").joinpath("harbor_runtime_lock.json").read_text(encoding="utf-8")
    )
    assert lock["agent_selector"] == "aether.harbor_agent:AetherHarborAgent"
    assert lock["lifecycle_authority"] == "harbor"
    assert lock["aether_owns_benchmark_lifecycle"] is False
    assert lock["aether_owns_grading"] is False
