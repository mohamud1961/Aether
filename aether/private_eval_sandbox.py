"""Contamination-safe candidate execution for private eval grading.

Trusted grader logic stays on the host. Untrusted candidate bytes and withheld
input cases execute in a fresh Docker container with no host mounts, no network,
no inherited provider environment, dropped Linux capabilities, and no access to
the grader source/expected answers. This module never decides task semantics;
it is an execution-custody boundary for independently-authored graders.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from typing import Sequence


DEFAULT_IMAGE = "aether-heldout-private-python-v1:20260916"
_PROVIDER_ENV_PREFIXES = ("OPENAI_", "AZURE_OPENAI_", "AETHER_PROVIDER_")


@dataclass(frozen=True)
class CandidateRun:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CandidateSandbox:
    """One fresh no-mount Docker container for a single candidate grade.

    The container is deliberately separate from the Solver task container. This
    prevents candidate code executed by a grader from mutating the submitted
    task world or reading trusted grader/answer files from the host checkout.
    """

    def __init__(
        self,
        candidate_path: str | Path,
        *,
        image: str = DEFAULT_IMAGE,
        memory_mb: int = 768,
        cpus: float = 1.0,
    ) -> None:
        self.candidate_path = Path(candidate_path).resolve(strict=True)
        if not self.candidate_path.is_file() or self.candidate_path.is_symlink():
            raise RuntimeError("candidate must be one regular file")
        self.image = str(image)
        self.memory_mb = int(memory_mb)
        self.cpus = float(cpus)
        self.docker = shutil.which("docker") or ""
        self.container_id = ""
        self.container_name = f"aether-private-grade-{uuid.uuid4().hex[:12]}"
        self._scratch = Path(tempfile.mkdtemp(prefix="aether-private-grade-host-"))
        self.candidate_remote = f"/candidate/{self.candidate_path.name}"
        self.inspection: dict[str, object] = {}

    def _host_run(
        self,
        args: Sequence[str],
        *,
        timeout: float = 60,
        check: bool = False,
        text: bool = True,
    ) -> subprocess.CompletedProcess:
        if not self.docker:
            raise RuntimeError("Docker CLI unavailable for certified private grading")
        result = subprocess.run(
            [self.docker, *list(args)],
            text=text,
            capture_output=True,
            timeout=timeout,
        )
        if check and result.returncode != 0:
            stderr = result.stderr if isinstance(result.stderr, str) else ""
            stdout = result.stdout if isinstance(result.stdout, str) else ""
            raise RuntimeError(
                f"Docker candidate sandbox command failed rc={result.returncode}: "
                + (stderr or stdout)[-1200:]
            )
        return result

    def __enter__(self) -> "CandidateSandbox":
        if not self.docker:
            raise RuntimeError("Docker CLI unavailable for certified private grading")
        # Fail closed if the exact base image is not already available. Certified
        # grading must not gain an undeclared network dependency by pulling here.
        image_check = self._host_run(["image", "inspect", self.image], timeout=20)
        if image_check.returncode != 0:
            raise RuntimeError(
                f"certified private grading image is unavailable locally: {self.image}"
            )
        create = self._host_run([
            "create",
            "--name", self.container_name,
            "--network", "none",
            "--pids-limit", "128",
            "--memory", f"{self.memory_mb}m",
            "--cpus", str(self.cpus),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--workdir", "/work",
            self.image,
            "python3", "-c", "import time; time.sleep(86400)",
        ], timeout=30, check=True)
        self.container_id = str(create.stdout).strip()
        if not self.container_id:
            raise RuntimeError("Docker candidate sandbox did not return a container id")
        try:
            self._host_run(["start", self.container_id], timeout=30, check=True)
            self.inspection = self._inspect_and_validate()
            self.mkdir("/candidate")
            self.mkdir("/work")
            self.put_bytes(self.candidate_remote, self.candidate_path.read_bytes())
            return self
        except BaseException:
            self.close()
            raise

    def _inspect_and_validate(self) -> dict[str, object]:
        result = self._host_run(["inspect", self.container_id], timeout=20, check=True)
        payload = json.loads(result.stdout)
        if not isinstance(payload, list) or len(payload) != 1:
            raise RuntimeError("candidate sandbox Docker inspect shape invalid")
        row = payload[0]
        mounts = row.get("Mounts") or []
        host = row.get("HostConfig") or {}
        config = row.get("Config") or {}
        env_rows = [str(value) for value in (config.get("Env") or [])]
        inherited_provider = [
            value.split("=", 1)[0]
            for value in env_rows
            if any(value.startswith(prefix) for prefix in _PROVIDER_ENV_PREFIXES)
        ]
        checks = {
            "zero_mounts": mounts == [],
            "network_none": str(host.get("NetworkMode") or "") == "none",
            "pid_namespace_not_host": str(host.get("PidMode") or "").lower() != "host",
            "not_privileged": host.get("Privileged") is not True,
            "no_added_capabilities": not (host.get("CapAdd") or []),
            "provider_environment_not_inherited": not inherited_provider,
            "docker_socket_not_mounted": all(
                str(item.get("Destination") or "") not in {"/var/run/docker.sock", "/run/docker.sock"}
                for item in mounts if isinstance(item, dict)
            ),
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise RuntimeError("candidate grading sandbox isolation failed: " + ",".join(failed))
        return {
            "container_id_sha256": __import__("hashlib").sha256(
                self.container_id.encode("utf-8")
            ).hexdigest(),
            "image": self.image,
            "image_id": str(row.get("Image") or ""),
            "checks": checks,
        }

    def mkdir(self, remote: str) -> None:
        self._host_run(
            ["exec", self.container_id, "mkdir", "-p", str(remote)],
            timeout=20,
            check=True,
        )

    def put_bytes(self, remote: str, data: bytes) -> None:
        parent = str(Path(remote).parent).replace("\\", "/")
        self.mkdir(parent)
        local = self._scratch / f"upload-{uuid.uuid4().hex}"
        local.write_bytes(bytes(data))
        try:
            self._host_run(
                ["cp", str(local), f"{self.container_id}:{remote}"],
                timeout=30,
                check=True,
            )
        finally:
            local.unlink(missing_ok=True)

    def put_text(self, remote: str, text: str) -> None:
        self.put_bytes(remote, str(text).encode("utf-8"))

    def get_bytes(self, remote: str) -> bytes:
        local = self._scratch / f"download-{uuid.uuid4().hex}"
        try:
            result = self._host_run(
                ["cp", f"{self.container_id}:{remote}", str(local)],
                timeout=30,
            )
            if result.returncode != 0:
                raise FileNotFoundError(remote)
            return local.read_bytes()
        finally:
            local.unlink(missing_ok=True)

    def get_text(self, remote: str) -> str:
        return self.get_bytes(remote).decode("utf-8", errors="strict")

    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float = 60,
        cwd: str = "/work",
    ) -> CandidateRun:
        result = self._host_run(
            ["exec", "-w", cwd, self.container_id, *[str(value) for value in args]],
            timeout=timeout,
        )
        return CandidateRun(
            args=tuple(str(value) for value in args),
            returncode=int(result.returncode),
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
        )

    def run_detached(self, args: Sequence[str], *, cwd: str = "/work") -> CandidateRun:
        result = self._host_run(
            ["exec", "-d", "-w", cwd, self.container_id, *[str(value) for value in args]],
            timeout=30,
        )
        return CandidateRun(
            args=tuple(str(value) for value in args),
            returncode=int(result.returncode),
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
        )

    def close(self) -> None:
        if self.docker and (self.container_id or self.container_name):
            target = self.container_id or self.container_name
            try:
                self._host_run(["rm", "-f", target], timeout=30)
            except Exception:
                pass
        self.container_id = ""
        shutil.rmtree(self._scratch, ignore_errors=True)

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["CandidateRun", "CandidateSandbox", "DEFAULT_IMAGE"]
