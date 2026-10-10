from __future__ import annotations

import subprocess

from aether import harbor_task_environment as hte


def _cp(args: list[str], *, rc: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, rc, out, err)


def test_exact_project_cleanup_removes_only_matching_containers_and_networks(monkeypatch):
    session = "aether-research-task-arm-deadbeef"
    calls: list[list[str]] = []
    state = {
        "containers": ["c1", "c2"],
        "networks": ["n1"],
    }

    def fake_run(args, *, text, capture_output, timeout, check):
        args = list(args)
        calls.append(args)
        if args[1:3] == ["ps", "-aq"]:
            return _cp(args, out="\n".join(state["containers"]) + ("\n" if state["containers"] else ""))
        if args[1:4] == ["network", "ls", "-q"]:
            return _cp(args, out="\n".join(state["networks"]) + ("\n" if state["networks"] else ""))
        if args[1:3] == ["rm", "-f"]:
            cid = args[3]
            state["containers"].remove(cid)
            return _cp(args)
        if args[1:3] == ["network", "rm"]:
            nid = args[3]
            state["networks"].remove(nid)
            return _cp(args)
        raise AssertionError(args)

    monkeypatch.setattr(hte.subprocess, "run", fake_run)
    receipt = hte._cleanup_compose_project(session, "docker")

    assert receipt["verified_clean"] is True
    assert receipt["before_container_count"] == 2
    assert receipt["before_network_count"] == 1
    assert receipt["removed_container_ids"] == ["c1", "c2"]
    assert receipt["removed_network_ids"] == ["n1"]
    assert receipt["remaining_container_ids"] == []
    assert receipt["remaining_network_ids"] == []
    assert all(f"label=com.docker.compose.project={session}" in call for call in calls if "--filter" in call)


def test_exact_project_cleanup_reports_remaining_resource(monkeypatch):
    session = "aether-research-task-arm-deadbeef"
    state = {"containers": ["c1"], "networks": []}

    def fake_run(args, *, text, capture_output, timeout, check):
        args = list(args)
        if args[1:3] == ["ps", "-aq"]:
            return _cp(args, out="c1\n")
        if args[1:4] == ["network", "ls", "-q"]:
            return _cp(args, out="")
        if args[1:3] == ["rm", "-f"]:
            return _cp(args, rc=1, err="busy")
        raise AssertionError(args)

    monkeypatch.setattr(hte.subprocess, "run", fake_run)
    receipt = hte._cleanup_compose_project(session, "docker")

    assert receipt["verified_clean"] is False
    assert receipt["remaining_container_ids"] == ["c1"]
    assert receipt["failures"]
    assert "container:c1:rc=1" in receipt["failures"][0]
