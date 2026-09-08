from pathlib import Path

import pytest

from evals.performance.h10_task_environment_preflight import build_command


def test_build_command_prefers_compose(tmp_path: Path):
    task = tmp_path / "t"; env = task / "environment"; env.mkdir(parents=True)
    compose = env / "docker-compose.yaml"; compose.write_text("services: {}\n")
    (env / "Dockerfile").write_text("FROM scratch\n")
    cmd = build_command(task, "t")
    assert cmd == ["docker", "compose", "-f", str(compose), "build"]


def test_build_command_uses_dockerfile(tmp_path: Path):
    task = tmp_path / "t"; env = task / "environment"; env.mkdir(parents=True)
    dockerfile = env / "Dockerfile"; dockerfile.write_text("FROM scratch\n")
    cmd = build_command(task, "t")
    assert cmd[:4] == ["docker", "build", "-f", str(dockerfile)]
    assert cmd[-1] == str(env)
    assert any(part.startswith("aether-preflight-") for part in cmd)


def test_build_command_fails_without_environment_definition(tmp_path: Path):
    task = tmp_path / "t"; (task / "environment").mkdir(parents=True)
    with pytest.raises(ValueError, match="no Dockerfile or Compose definition"):
        build_command(task, "t")


def test_build_command_fails_without_environment_directory(tmp_path: Path):
    with pytest.raises(ValueError, match="environment directory missing"):
        build_command(tmp_path / "t", "t")
