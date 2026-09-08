from __future__ import annotations

from types import SimpleNamespace

from aether.kernel import AetherNextKernel
from aether.kernel_turns import _invalidate_runtime_capabilities_after_dispatch


class _Executor:
    def __init__(self, *, available: bool = False) -> None:
        self.available = available
        self.calls = 0

    def computer_available(self) -> bool:
        self.calls += 1
        return self.available


def test_dynamic_computer_probe_is_cached_until_explicit_invalidation() -> None:
    executor = _Executor(available=False)
    kernel = AetherNextKernel(max_steps=1)

    assert kernel._live_runtime_capability_ids(executor) == set()
    assert kernel._live_runtime_capability_ids(executor) == set()
    assert executor.calls == 1

    executor.available = True
    # The cache remains factual for the decision boundary that created it.
    assert kernel._live_runtime_capability_ids(executor) == set()
    assert executor.calls == 1

    kernel.invalidate_runtime_capability_cache()
    assert kernel._live_runtime_capability_ids(executor) == {"computer_control"}
    assert executor.calls == 2


def test_only_process_session_job_actions_invalidate_dynamic_capability_cache() -> None:
    class Kernel:
        def __init__(self) -> None:
            self.invalidations = 0

        def invalidate_runtime_capability_cache(self) -> None:
            self.invalidations += 1

    kernel = Kernel()
    for kind in ("read_file", "read_output", "inspect_artifact"):
        _invalidate_runtime_capabilities_after_dispatch(kernel, SimpleNamespace(kind=kind))
    assert kernel.invalidations == 0

    for kind in (
        "write_file", "run_command", "start_terminal_session", "terminal_send", "terminal_read",
        "terminal_wait", "terminal_interrupt", "terminal_close", "bootstrap_acquire",
        "launch_process", "start_job", "probe_job", "probe_service", "stop_process",
        "run_experiment",
    ):
        _invalidate_runtime_capabilities_after_dispatch(kernel, SimpleNamespace(kind=kind))
    assert kernel.invalidations == 15
