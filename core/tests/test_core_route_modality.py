"""M4: image use must fit the route's measured modality when a route record is named.

Falsifiers: a record for another deployment, a record that disagrees with the switch, and a malformed record each stop
the run before any model call; the committed Luna record (measured from recorded runs) passes with images on.
"""

import json
from pathlib import Path

import pytest

from aether.core.route_modality import ROUTE_MODALITY_ENV, RouteModalityError, check

LUNA = Path(__file__).resolve().parents[2] / "research/core_hybrid_20261113/route_modality/gpt-6-luna.json"


def record(tmp_path, **kw):
    p = tmp_path / "route.json"
    p.write_text(json.dumps({"deployment": "dep", "images": True, "evidence": "probe 1", **kw}))
    return {ROUTE_MODALITY_ENV: str(p)}


def test_unset_checks_nothing():
    assert check({}, deployment="anything", images=True) == ""


def test_the_committed_luna_record_passes_with_images_on():
    fact = check({ROUTE_MODALITY_ENV: str(LUNA)}, deployment="gpt-6-luna", images=True)
    assert "matches the measured route" in fact


def test_images_on_for_a_route_measured_text_only_is_blocked(tmp_path):
    with pytest.raises(RouteModalityError, match="does not accept image parts.*set it to off"):
        check(record(tmp_path, images=False), deployment="dep", images=True)


def test_images_off_for_a_route_measured_multimodal_is_allowed(tmp_path):
    fact = check(record(tmp_path), deployment="dep", images=False)
    assert "images off" in fact and "accepts image parts" in fact


def test_a_record_for_another_deployment_is_blocked(tmp_path):
    with pytest.raises(RouteModalityError, match="measured for deployment 'dep'"):
        check(record(tmp_path), deployment="other", images=True)


@pytest.mark.parametrize("bad", ['{"deployment": "dep", "images": "yes", "evidence": "x"}',
                                 '{"deployment": "dep", "images": true}', "not json", "[]"])
def test_a_malformed_record_is_blocked(tmp_path, bad):
    p = tmp_path / "route.json"
    p.write_text(bad)
    with pytest.raises(RouteModalityError):
        check({ROUTE_MODALITY_ENV: str(p)}, deployment="dep", images=True)


def test_a_missing_record_is_blocked(tmp_path):
    with pytest.raises(RouteModalityError, match="cannot read"):
        check({ROUTE_MODALITY_ENV: str(tmp_path / "nope.json")}, deployment="dep", images=True)


def test_the_harbor_agent_stops_a_mismatched_run_before_building_a_provider(tmp_path, monkeypatch):
    import asyncio

    from aether.core import harbor_agent as adapter

    for name, value in ((adapter.REVIEW_ENV, "off"), (adapter.CONTEXT_ENV, "project"), (adapter.REPL_ENV, "off"),
                        (adapter.IMAGES_ENV, "on"), (adapter.DEPLOYMENT_ENV, "dep")):
        monkeypatch.setenv(name, value)
    monkeypatch.setenv(ROUTE_MODALITY_ENV, record(tmp_path, images=False)[ROUTE_MODALITY_ENV])
    monkeypatch.setattr(adapter, "build_provider", lambda *a, **k: pytest.fail("provider built despite a mismatch"))
    logs = tmp_path / "logs"
    agent = object.__new__(adapter.AetherCoreAgent)  # the real run(); Harbor's own constructor is not needed here
    agent.logs_dir, agent._extra_env, agent._agent_timeout_sec = logs, {}, 60.0
    with pytest.raises(RouteModalityError):
        asyncio.run(agent.run("task", None, None))
    assert json.loads((logs / "aether_run_record.json").read_text())["status"] == "configuration_error"
