"""Truthful full-output capture: the substrate must never destroy command
output.  Full streams are kept inline up to the inline cap; beyond it the
COMPLETE stream is spooled to disk and retrievable by handle; timeouts
preserve partial output.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from aether.execution import MemoryExecutor
from aether.kernel import AetherNextKernel
from aether.ledger import ExecutionLedger, Receipt
from aether.real_executor import SubprocessExecutor, _INLINE_STREAM_CAP
from aether.runtime_ir import (
    ActionRequest,
    CapabilityDescriptor,
    CompiledRuntime,
    EnvMap,
    SolverTurn,
)


def test_output_between_old_cap_and_inline_cap_is_kept_verbatim() -> None:
    # 100k chars: destroyed under the old 20k executor cap; now full inline.
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        result = executor.run_command(
            "python3 -c \"import sys; sys.stdout.write('x' * 100000 + 'FINAL_MARKER')\"",
            timeout_s=60,
        )
    assert result.exit_code == 0
    assert result.stdout_overflow_path == ""
    assert len(result.stdout) == 100_000 + len("FINAL_MARKER")
    assert result.stdout.endswith("FINAL_MARKER")
    assert result.stdout_bytes_total == len(result.stdout)


def test_output_beyond_inline_cap_is_spooled_completely() -> None:
    total = _INLINE_STREAM_CAP + 200_000
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        result = executor.run_command(
            f"python3 -c \"import sys; sys.stdout.write('a' * {total} + 'TAIL_MARKER')\"",
            timeout_s=120,
        )
    assert result.exit_code == 0
    assert result.stdout_overflow_path, "oversized stream must be spooled"
    spooled = Path(result.stdout_overflow_path).read_text(encoding="utf-8")
    assert len(spooled) == total + len("TAIL_MARKER")
    assert spooled.endswith("TAIL_MARKER")
    assert result.stdout_bytes_total == len(spooled)
    # Inline text is a marked head+tail, not silent truncation.
    assert "spooled to" in result.stdout
    assert result.stdout.endswith("TAIL_MARKER")


def test_timeout_preserves_partial_output() -> None:
    with tempfile.TemporaryDirectory() as root:
        executor = SubprocessExecutor(root)
        # Use a shell builtin so the regression measures timeout capture, not
        # whether a second interpreter receives CPU within a two-second window
        # on a loaded certification host. The executor still launches through
        # its real shell/process-group path.
        result = executor.run_command(
            "printf 'PARTIAL_BEFORE_TIMEOUT\\n'; sleep 30",
            timeout_s=5,
        )
    assert result.exit_code == 124
    assert result.timed_out is True
    assert "PARTIAL_BEFORE_TIMEOUT" in result.stdout
    assert "timed out" in result.stderr


class _ReadBackHooks:
    """Solver: run a big command, then read the full stream back by handle."""

    def __init__(self, command: str) -> None:
        self._command = command
        self._step = 0
        self.read_output_payloads: list[dict] = []


    def solve(self, messages: list[dict[str, str]], compiled: CompiledRuntime) -> SolverTurn:
        self._step += 1
        if self._step == 1:
            return SolverTurn(kind="act", summary="run big command", actions=(ActionRequest(
                action_id="a-big", kind="run_command", capability_id="shell",
                arguments={"command": self._command, "timeout_s": 120},
                intent="produce oversized output", expected_observation="lots of output",
                if_fail_next="report blocker",
            ),), evidence_gap="The next action must resolve the current evidence gap")
        if self._step == 2:
            return SolverTurn(kind="act", summary="page the captured output", actions=(ActionRequest(
                action_id="a-read", kind="read_output", capability_id="kernel",
                arguments={"handle": "0:a-big:stdout", "offset": 10, "span": 20000},
                intent="Read one bounded page from the immutable captured stream.",
                expected_observation="A 20000-byte page from the full output.",
                if_fail_next="Inspect the retained output handle metadata.",
            ),), evidence_gap="The full spooled output page has not been observed")
        if self._step == 3:
            return SolverTurn(kind="act", summary="grep the captured output", actions=(ActionRequest(
                action_id="a-grep", kind="grep_output", capability_id="kernel",
                arguments={"handle": "0:a-big:stdout", "pattern": "TAIL_MARKER"},
                intent="Search the immutable captured stream for the required tail marker.",
                expected_observation="Exactly one TAIL_MARKER match.",
                if_fail_next="Read a later output page or report missing marker evidence.",
            ),), evidence_gap="The required tail marker has not been located")
        return SolverTurn(kind="submit_outcome", summary="done")


def test_kernel_handles_page_and_grep_across_spooled_output(tmp_path: Path) -> None:
    total = _INLINE_STREAM_CAP + 100_000
    command = f"python3 -c \"import sys; sys.stdout.write('b' * {total} + 'TAIL_MARKER')\""
    env = EnvMap(
        task_prompt="Run the big command.",
        workspace_root=str(tmp_path),
        capabilities={
            "shell": CapabilityDescriptor("shell", "Run commands"),
            "filesystem": CapabilityDescriptor("filesystem", "Files"),
        },
    )
    hooks = _ReadBackHooks(command)
    executor = SubprocessExecutor(str(tmp_path))
    result = AetherNextKernel(max_steps=4).run(env, executor, hooks)

    cmd = next(r for r in result.receipts if r.kind == "run_command")
    assert cmd.payload["stdout_overflow_path"]
    assert cmd.payload["stdout_bytes"] == total + len("TAIL_MARKER")

    read = next(r for r in result.receipts if r.kind == "read_output")
    assert read.success
    assert read.payload["bytes"] == total + len("TAIL_MARKER"), (
        "read_output must page over the FULL spooled stream, not the inline excerpt"
    )
    assert read.payload["chunk"] == "b" * 20000

    grep = next(r for r in result.receipts if r.kind == "grep_output")
    assert grep.success
    assert grep.payload["matches"] == 1
    assert "TAIL_MARKER" in grep.payload["chunk"]
