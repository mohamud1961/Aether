from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aether.private_eval_sandbox import CandidateSandbox


def _candidate(tmp_path: Path) -> Path:
    path = tmp_path / "candidate.py"
    path.write_text("print('ok')\n", encoding="utf-8")
    return path


def test_candidate_sandbox_create_contract_has_no_mount_or_network_escape(
    monkeypatch, tmp_path: Path,
) -> None:
    sandbox = CandidateSandbox(_candidate(tmp_path))
    monkeypatch.setattr(sandbox, "docker", "/usr/bin/docker")
    calls: list[list[str]] = []

    inspect_payload = [{
        "Mounts": [],
        "Image": "sha256:image",
        "HostConfig": {
            "NetworkMode": "none",
            "PidMode": "",
            "Privileged": False,
            "CapAdd": [],
        },
        "Config": {"Env": ["PATH=/usr/bin"]},
    }]

    def fake_host_run(args, **kwargs):
        row = [str(item) for item in args]
        calls.append(row)
        if row[:2] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="[]", stderr="")
        if row and row[0] == "create":
            return SimpleNamespace(returncode=0, stdout="container-1\n", stderr="")
        if row and row[0] == "inspect":
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(inspect_payload),
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sandbox, "_host_run", fake_host_run)
    monkeypatch.setattr(sandbox, "mkdir", lambda _path: None)
    monkeypatch.setattr(sandbox, "put_bytes", lambda _path, _data: None)

    with sandbox:
        assert sandbox.inspection["checks"]["zero_mounts"] is True
        create = next(row for row in calls if row and row[0] == "create")
        assert "--network" in create and create[create.index("--network") + 1] == "none"
        assert "--cap-drop" in create and create[create.index("--cap-drop") + 1] == "ALL"
        assert "--security-opt" in create
        assert "no-new-privileges:true" in create
        assert "--mount" not in create
        assert "-v" not in create
        assert "--volume" not in create


@pytest.mark.parametrize(
    "mutation, expected",
    [
        ({"Mounts": [{"Destination": "/grader"}]}, "zero_mounts"),
        ({"HostConfig": {"NetworkMode": "bridge"}}, "network_none"),
        ({"HostConfig": {"Privileged": True}}, "not_privileged"),
        ({"Config": {"Env": ["OPENAI_API_KEY=secret"]}}, "provider_environment_not_inherited"),
    ],
)
def test_candidate_sandbox_inspection_fails_closed_on_isolation_drift(
    monkeypatch, tmp_path: Path, mutation: dict, expected: str,
) -> None:
    sandbox = CandidateSandbox(_candidate(tmp_path))
    monkeypatch.setattr(sandbox, "docker", "/usr/bin/docker")
    row = {
        "Mounts": [],
        "Image": "sha256:image",
        "HostConfig": {
            "NetworkMode": "none",
            "PidMode": "",
            "Privileged": False,
            "CapAdd": [],
        },
        "Config": {"Env": ["PATH=/usr/bin"]},
    }
    for key, value in mutation.items():
        if isinstance(value, dict) and isinstance(row.get(key), dict):
            row[key].update(value)
        else:
            row[key] = value

    monkeypatch.setattr(
        sandbox,
        "_host_run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps([row]), stderr=""
        ),
    )
    with pytest.raises(RuntimeError, match=expected):
        sandbox._inspect_and_validate()
