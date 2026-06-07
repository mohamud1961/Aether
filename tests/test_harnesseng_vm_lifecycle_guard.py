from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "harnesseng_vm_lifecycle_guard.sh"


def run_guard(tmp_path: Path, command: str, lease_id: str | None = None, owner: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HARNESSENG_VM_GUARD_ROOT"] = str(tmp_path / "guard")
    env["AZURE_RESOURCE_GROUP"] = "rg-test"
    env["AZURE_VM_NAME"] = "vm-test"
    if lease_id is not None:
        env["HARNESSENG_VM_LEASE_ID"] = lease_id
    if owner is not None:
        env["HARNESSENG_VM_LEASE_OWNER"] = owner
    return subprocess.run(
        ["bash", str(SCRIPT), command],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_guard_tracks_active_leases(tmp_path: Path) -> None:
    owner_a = "owner-a pid=100"
    owner_b = "owner-b pid=200"

    first = run_guard(tmp_path, "acquire", lease_id="lease-a", owner=owner_a)
    assert first.returncode == 0
    assert "lease_count=1" in first.stdout

    second = run_guard(tmp_path, "acquire", lease_id="lease-b", owner=owner_b)
    assert second.returncode == 0
    assert "lease_count=2" in second.stdout

    active = run_guard(tmp_path, "assert-no-active")
    assert active.returncode == 2
    assert "lease_count=2" in active.stdout
    assert f"owner={owner_a}" in active.stdout
    assert f"owner={owner_b}" in active.stdout

    release_a = run_guard(tmp_path, "release", lease_id="lease-a")
    assert release_a.returncode == 0
    assert "lease_count=1" in release_a.stdout

    release_b = run_guard(tmp_path, "release", lease_id="lease-b")
    assert release_b.returncode == 0
    assert "lease_count=0" in release_b.stdout

    clear = run_guard(tmp_path, "assert-no-active")
    assert clear.returncode == 0
    assert "lease_count=0" in clear.stdout
