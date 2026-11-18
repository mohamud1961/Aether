"""Review fixes (2026-10-26) that need a real Linux container: a write directly under ``/`` (R1) and a command body
past Linux's 128 KiB per-argv limit (T1). Skipped without Linux and docker, like the rest of the fault suite."""

from __future__ import annotations

import asyncio
import subprocess

from aether.core.transfer import put_bytes
from tests.test_core_faults_linux import _terms, box, image, pytestmark  # noqa: F401 (fixtures, skip marker)


def test_r1_a_write_directly_under_root_is_verified(box):  # noqa: F811 (fixture)
    asyncio.run(put_bytes(box, b"flag bytes\n", "/flag"))
    out = subprocess.run(["docker", "exec", box.container, "cat", "/flag"], capture_output=True).stdout
    assert out == b"flag bytes\n"


def test_t1_a_command_past_the_argv_limit_runs_in_a_container(box):  # noqa: F811 (fixture)
    body = "y" * 150_000

    async def run():
        terminals = _terms(box)
        try:
            return await terminals.use(input=f"cat > /app/big.txt <<'EOF'\n{body}\nEOF\nwc -c < /app/big.txt", wait_s=20)
        finally:
            await terminals.close()

    out = asyncio.run(run())
    assert "150001" in out and "[exit 0" in out, out
