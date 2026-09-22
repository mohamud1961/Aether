"""Deterministic serial provider-throughput pacing.

This is launch-time transport admission, not a retry policy. It combines smooth
serial spacing with a conservative rolling-window reservation ledger so a
sequence of growing requests cannot exceed the declared tokens-per-window
quota. It remains task-deadline aware.
"""
from __future__ import annotations

import math
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from typing import Callable, Any

from .run_deadline import KernelRunTimeout, remaining_run_s, run_deadline_wait_exclusion_active


def _detect_boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        pass
    try:
        return subprocess.check_output(
            ["sysctl", "-n", "kern.boottime"], text=True, timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        # Fallback is stable between processes on one boot and changes when
        # the monotonic clock origin resets. The Linux VM uses boot_id above.
        return f"boot-epoch:{int(time.time() - time.monotonic())}"


_PROCESS_BOOT_ID = _detect_boot_id()


class ProviderThroughputError(RuntimeError):
    """The declared provider throughput treatment cannot admit a new create."""


class SerialTokenPacer:
    """Serial pacing against one declared token throughput limit.

    Request bytes are converted to an approximate token load only for transport
    pacing. By default, a successful response replaces that estimate with
    provider-reported input usage plus the request's output ceiling. An
    explicit challenger mode may use observed output usage instead. The
    provider remains authoritative for single-request admission.
    """

    def __init__(
        self,
        *,
        token_limit: int,
        window_s: float = 60.0,
        settlement_mode: str = "requested_output_cap",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.token_limit = int(token_limit)
        self.window_s = float(window_s)
        self.settlement_mode = str(settlement_mode)
        if self.token_limit <= 0 or self.window_s <= 0:
            raise ValueError("provider throughput limit and window must be positive")
        if self.settlement_mode not in {"requested_output_cap", "observed_output"}:
            raise ValueError(
                "serial settlement mode must be 'requested_output_cap' or 'observed_output'"
            )
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_create_monotonic = 0.0
        self._last_dispatch_monotonic: float | None = None
        self._last_reservation_index: int | None = None
        self._reservations: list[list[float | int]] = []
        self._blocked_until = 0.0

    @staticmethod
    def approximate_request_tokens(request_bytes: int, max_output_tokens: int) -> int:
        # Four UTF-8 bytes/token is only a pacing estimate, never a context
        # admission or billing claim. The output ceiling is charged in full.
        return max(1, math.ceil(int(request_bytes) / 4)) + max(0, int(max_output_tokens))

    def _spacing(self, token_load: int) -> float:
        bounded = min(max(1, int(token_load)), self.token_limit)
        return self.window_s * bounded / self.token_limit

    def _bounded_load(self, token_load: int) -> int:
        return min(max(1, int(token_load)), self.token_limit)

    def _expire(self, now: float) -> None:
        cutoff = now - self.window_s
        while self._reservations and float(self._reservations[0][0]) <= cutoff:
            self._reservations.pop(0)
            if self._last_reservation_index is not None:
                self._last_reservation_index -= 1
                if self._last_reservation_index < 0:
                    self._last_reservation_index = None

    def _sleep_checked(self, wait_s: float) -> None:
        if wait_s <= 0:
            return
        remaining = remaining_run_s()
        if remaining is not None and wait_s >= remaining:
            raise KernelRunTimeout(
                "provider throughput pacing would exceed task run deadline"
            )
        self._sleep(wait_s)

    def _rolling_capacity_wait(self, now: float, new_load: int) -> float:
        self._expire(now)
        active = sum(int(row[1]) for row in self._reservations)
        if active + new_load <= self.token_limit:
            return 0.0
        excess = active + new_load - self.token_limit
        released = 0
        for dispatched_at, tokens in self._reservations:
            released += int(tokens)
            if released >= excess:
                return max(0.0, float(dispatched_at) + self.window_s - now)
        return self.window_s

    def admit(self, *, estimated_tokens: int) -> dict[str, Any]:
        with self._lock:
            started = self._clock()
            now = started
            bounded = self._bounded_load(estimated_tokens)

            # Preserve smooth spacing to avoid short-window microbursts.
            initial_wait = max(
                0.0,
                self._next_create_monotonic - now,
                self._blocked_until - now,
            )
            self._sleep_checked(initial_wait)
            now = self._clock()

            # Then enforce the full rolling-window budget. Growing requests can
            # otherwise overflow TPM even when every adjacent pair is spaced.
            rolling_wait = self._rolling_capacity_wait(now, bounded)
            self._sleep_checked(rolling_wait)
            now = self._clock()
            self._expire(now)

            self._last_dispatch_monotonic = now
            self._reservations.append([now, bounded])
            self._last_reservation_index = len(self._reservations) - 1
            spacing = self._spacing(estimated_tokens)
            self._next_create_monotonic = max(self._next_create_monotonic, now + spacing)
            active_after = sum(int(row[1]) for row in self._reservations)
            return {
                "throughput_token_limit": self.token_limit,
                "throughput_window_s": self.window_s,
                "throughput_estimated_tokens": int(estimated_tokens),
                "throughput_wait_s": max(0.0, now - started),
                "throughput_spacing_s": spacing,
                "throughput_rolling_wait_s": rolling_wait,
                "throughput_active_reserved_tokens": active_after,
                "throughput_single_request_admission": "provider_authoritative",
            }

    def reconcile_success(
        self,
        *,
        input_tokens: int | None,
        requested_output_tokens: int,
        output_tokens: int | None = None,
    ) -> dict[str, Any]:
        if not isinstance(input_tokens, int) or input_tokens < 0:
            return {"throughput_usage_reconciled": False}
        observed_output = (
            output_tokens
            if type(output_tokens) is int and output_tokens >= 0
            else None
        )
        use_observed_output = (
            self.settlement_mode == "observed_output" and observed_output is not None
        )
        charged = input_tokens + (
            observed_output if use_observed_output else max(0, int(requested_output_tokens))
        )
        with self._lock:
            bounded = self._bounded_load(charged)
            settled_at = self._clock()
            index = self._last_reservation_index
            if index is not None and 0 <= index < len(self._reservations):
                # Provider accounting can remain live through response completion,
                # so keep the settled load reserved for one full window from here.
                self._reservations[index][0] = settled_at
                self._reservations[index][1] = bounded
            required = settled_at + self._spacing(charged)
            self._next_create_monotonic = max(self._next_create_monotonic, required)
        return {
            "throughput_usage_reconciled": True,
            "throughput_reconciled_tokens": charged,
            "throughput_window_anchor": "response_settlement",
        }

    def note_rate_limit(self) -> None:
        """Conservatively impose one full-window blackout after a 429."""
        with self._lock:
            now = self._clock()
            self._blocked_until = max(self._blocked_until, now + self.window_s)
            self._next_create_monotonic = max(self._next_create_monotonic, self._blocked_until)


class SharedDeploymentTokenPacer:
    """Cross-process, FIFO admission for workers sharing one deployment.

    State lives in a private local file on the VM. Reservations stay active
    while a provider request is in flight, then use observed input+output
    usage when available. Missing usage keeps the original conservative
    reservation for a full window. This is an opt-in transport control; it
    does not authorize a route or a provider call.
    """

    SCHEMA = "aether.provider.shared_token_limiter.v1"
    _POLL_S = 1.0
    _WAITER_STALE_S = 900.0
    # Header authority: a provider-reported remaining-quota figure younger
    # than this governs admission; older figures fall back to local accounting.
    HEADER_FRESH_S = 10.0
    HEADER_SAFETY_FRACTION = 0.9
    # Expected output reservation: p95 of observed output tokens.
    OUTPUT_INITIAL_EXPECTED_TOKENS = 4096
    OUTPUT_MIN_OBSERVATIONS = 5
    OUTPUT_MAX_OBSERVATIONS = 256
    # 429 handling.
    RATE_LIMIT_DEFAULT_RETRY_AFTER_S = 10.0
    RATE_LIMIT_TIGHTEN_S = 60.0

    @staticmethod
    def _finite_number(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )

    def __init__(
        self,
        *,
        state_path: Path,
        deployment: str,
        token_limit: int,
        request_limit: int,
        window_s: float = 60.0,
        window_anchor: str = "settlement",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        boot_id: str | None = None,
    ) -> None:
        self.state_path = Path(state_path).resolve()
        self.lock_path = self.state_path.with_name(self.state_path.name + ".lock")
        self.deployment_hash = hashlib.sha256(str(deployment).encode("utf-8")).hexdigest()
        self.token_limit = int(token_limit)
        self.request_limit = int(request_limit)
        self.window_s = float(window_s)
        self.window_anchor = str(window_anchor)
        if not deployment or self.token_limit <= 0 or self.request_limit <= 0 or self.window_s <= 0:
            raise ValueError("deployment, positive TPM/RPM limits and positive window are required")
        if self.window_anchor not in {"settlement", "dispatch"}:
            raise ValueError("provider window anchor must be 'settlement' or 'dispatch'")
        self._clock = clock
        self._sleep = sleep
        self._boot_id = boot_id or _PROCESS_BOOT_ID

    def approximate_request_tokens(self, request_bytes: int, max_output_tokens: int) -> int:
        """Input estimate plus expected (p95 observed) output, never above the cap."""
        input_estimate = max(1, math.ceil(int(request_bytes) / 4))
        return input_estimate + self.expected_output_tokens(int(max_output_tokens))

    @classmethod
    def _p95_output(cls, observations: list[int]) -> int:
        if len(observations) < cls.OUTPUT_MIN_OBSERVATIONS:
            return cls.OUTPUT_INITIAL_EXPECTED_TOKENS
        ordered = sorted(observations)
        return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]

    def expected_output_tokens(self, max_output_tokens: int) -> int:
        cap = max(0, int(max_output_tokens))
        if cap == 0:
            return 0
        p95 = self._mutate(
            lambda state: self._p95_output(state["output_observations"]), write=False,
        )
        return min(cap, p95)

    @staticmethod
    def _pid_alive(pid: Any) -> bool:
        if type(pid) is not int or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _initial_state(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "deployment_sha256": self.deployment_hash,
            "token_limit": self.token_limit,
            "request_limit": self.request_limit,
            "window_s": self.window_s,
            "window_anchor": self.window_anchor,
            "boot_id": self._boot_id,
            "last_monotonic": self._clock(),
            "next_dispatch_at": 0.0,
            "blocked_until": 0.0,
            "tightened_until": 0.0,
            "header_report": None,
            "output_observations": [],
            "waiters": [],
            "reservations": [],
        }

    def _load_state(self, fd: int) -> dict[str, Any]:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise ProviderThroughputError("shared limiter state must be a private regular file")
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, max(info.st_size, 1) + 1)
        if not raw:
            raise ProviderThroughputError(
                "shared limiter state is empty; admission fails closed"
            )
        try:
            state = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ProviderThroughputError("shared limiter state is corrupt; admission fails closed") from exc
        if not isinstance(state, dict):
            raise ProviderThroughputError("shared limiter state must be a JSON object")
        expected = self._initial_state()
        for key in (
            "schema", "deployment_sha256", "token_limit", "request_limit",
            "window_s", "window_anchor",
        ):
            if state.get(key) != expected[key]:
                raise ProviderThroughputError(f"shared limiter {key} differs from this worker")
        if not isinstance(state.get("waiters"), list) or not isinstance(state.get("reservations"), list):
            raise ProviderThroughputError("shared limiter ledgers are malformed")
        state.setdefault("tightened_until", 0.0)
        state.setdefault("header_report", None)
        state.setdefault("output_observations", [])
        report = state["header_report"]
        if (
            not self._finite_number(state["tightened_until"])
            or not isinstance(state["output_observations"], list)
            or any(type(v) is not int or v < 0 for v in state["output_observations"])
            or (report is not None and (
                not isinstance(report, dict)
                or not all(self._finite_number(report.get(k)) for k in ("at", "basis_at", "remaining_tokens"))
                or not (report.get("remaining_requests") is None or self._finite_number(report["remaining_requests"]))
            ))
        ):
            raise ProviderThroughputError("shared limiter pacing ledgers are malformed")
        if (
            not self._finite_number(state.get("next_dispatch_at"))
            or not self._finite_number(state.get("blocked_until"))
            or not self._finite_number(state.get("last_monotonic"))
            or not isinstance(state.get("boot_id"), str)
            or not state["boot_id"]
        ):
            raise ProviderThroughputError("shared limiter clocks are malformed")
        for item in state["reservations"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("reservation_id"), str)
                or not item["reservation_id"]
                or type(item.get("owner_pid")) is not int
                or item["owner_pid"] <= 0
                or item.get("status") not in {"in_flight", "settled"}
                or type(item.get("tokens")) is not int
                or item["tokens"] < 0
                or not self._finite_number(item.get("started_at"))
            ):
                raise ProviderThroughputError("shared limiter reservation is malformed")
            if item["status"] == "settled" and not self._finite_number(item.get("settled_at")):
                raise ProviderThroughputError("shared limiter settlement clock is malformed")
        for item in state["waiters"]:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("waiter_id"), str)
                or not item["waiter_id"]
                or type(item.get("owner_pid")) is not int
                or item["owner_pid"] <= 0
                or type(item.get("requested_tokens")) is not int
                or item["requested_tokens"] <= 0
                or not self._finite_number(item.get("created_at"))
                or not self._finite_number(item.get("updated_at"))
            ):
                raise ProviderThroughputError("shared limiter waiter is malformed")
        if state["boot_id"] != self._boot_id:
            self._rebase_after_boot_change(state)
        return state

    def _rebase_after_boot_change(self, state: dict[str, Any]) -> None:
        """Conservatively rebase recent reservations after monotonic reset."""
        now = self._clock()
        last = float(state["last_monotonic"])
        active = []
        for item in state["reservations"]:
            if not isinstance(item, dict) or item.get("status") not in {"in_flight", "settled"}:
                raise ProviderThroughputError("shared limiter reservation is malformed")
            settled_at = item.get("settled_at")
            quota_anchor = item.get("started_at") if self.window_anchor == "dispatch" else settled_at
            recent = (
                item.get("status") == "in_flight"
                or (
                    isinstance(quota_anchor, (int, float))
                    and math.isfinite(float(quota_anchor))
                    and float(quota_anchor) > last - self.window_s
                )
            )
            if recent:
                item["status"] = "settled"
                # Monotonic timestamps from the previous boot cannot be used
                # to measure RPM age in this boot. Rebase both quota anchors
                # so request admission waits one conservative full window.
                item["started_at"] = now
                item["settled_at"] = now
                active.append(item)
        had_pending_dispatch = float(state["next_dispatch_at"]) > last
        had_pending_backoff = float(state["blocked_until"]) > last
        state["reservations"] = active
        state["waiters"] = []
        state["next_dispatch_at"] = now + self.window_s if had_pending_dispatch else now
        state["blocked_until"] = now + self.window_s if had_pending_backoff else now
        state["header_report"] = None
        state["tightened_until"] = now
        state["boot_id"] = self._boot_id
        state["last_monotonic"] = now

    @staticmethod
    def _write_state(path: Path, state: dict[str, Any]) -> None:
        payload = (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        path = Path(path)
        temp_path: Path | None = None
        temp_fd = -1
        try:
            temp_fd, temp_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            temp_path = Path(temp_name)
            os.fchmod(temp_fd, 0o600)
            view = memoryview(payload)
            while view:
                written = os.write(temp_fd, view)
                if written <= 0:
                    raise OSError("short write while persisting shared limiter state")
                view = view[written:]
            os.fsync(temp_fd)
            fd_to_close = temp_fd
            temp_fd = -1
            os.close(fd_to_close)

            os.replace(temp_path, path)
            temp_path = None
            directory_fd = os.open(
                path.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temp_fd >= 0:
                os.close(temp_fd)
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any], *, write: bool = True) -> Any:
        self.state_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        lock_fd = os.open(self.lock_path, lock_flags, 0o600)
        try:
            os.fchmod(lock_fd, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            state_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                state_fd = os.open(self.state_path, state_flags)
            except FileNotFoundError:
                state = self._initial_state()
            else:
                try:
                    state = self._load_state(state_fd)
                finally:
                    os.close(state_fd)
            result = callback(state)
            if write:
                state["last_monotonic"] = self._clock()
                self._write_state(self.state_path, state)
            return result
        finally:
            os.close(lock_fd)

    def _prune(self, state: dict[str, Any], now: float) -> None:
        live_reservations = []
        for item in state["reservations"]:
            if not isinstance(item, dict):
                raise ProviderThroughputError("shared limiter reservation is malformed")
            status = item.get("status")
            if status == "in_flight" and not self._pid_alive(item.get("owner_pid")):
                # The provider disposition is unknown after the owner dies.
                # Keep a full-window reservation from discovery time in either
                # anchoring mode.
                item["status"] = "settled"
                item["started_at"] = now
                item["settled_at"] = now
            if status not in {"in_flight", "settled"}:
                raise ProviderThroughputError("shared limiter reservation status is invalid")
            quota_anchor = (
                float(item["started_at"])
                if self.window_anchor == "dispatch"
                else float(item.get("settled_at", now))
            )
            if item["status"] == "in_flight" or quota_anchor > now - self.window_s:
                live_reservations.append(item)
        state["reservations"] = live_reservations
        state["waiters"] = [
            item for item in state["waiters"]
            if isinstance(item, dict)
            and self._pid_alive(item.get("owner_pid"))
            and now - float(item.get("updated_at", item.get("created_at", now))) <= self._WAITER_STALE_S
        ]

    def _wait_for(self, seconds: float) -> None:
        if seconds <= 0:
            return
        if not run_deadline_wait_exclusion_active():
            remaining = remaining_run_s()
            if remaining is not None and seconds >= remaining:
                raise KernelRunTimeout("shared provider limiter wait would exceed task run deadline")
        self._sleep(min(seconds, self._POLL_S))

    def admit(self, *, estimated_tokens: int) -> dict[str, Any]:
        load = int(estimated_tokens)
        if load <= 0 or load > self.token_limit:
            raise ProviderThroughputError("request estimate exceeds the declared deployment TPM limit")
        started = self._clock()
        waiter_id = uuid.uuid4().hex
        owner_pid = os.getpid()
        def add_waiter(state: dict[str, Any]) -> None:
            now = self._clock()
            self._prune(state, now)
            state["waiters"].append({
                "waiter_id": waiter_id,
                "owner_pid": owner_pid,
                "requested_tokens": load,
                "created_at": now,
                "updated_at": now,
            })
        self._mutate(add_waiter)
        wait_by_reason = {
            "fifo_queue": 0.0,
            "dispatch_spacing": 0.0,
            "rolling_quota": 0.0,
            "request_rate": 0.0,
            "rate_limit_backoff": 0.0,
        }
        try:
            while True:
                def try_admit(state: dict[str, Any]) -> tuple[dict[str, Any] | None, float, str | None]:
                    now = self._clock()
                    self._prune(state, now)
                    position = next((i for i, item in enumerate(state["waiters"]) if item.get("waiter_id") == waiter_id), None)
                    if position is None:
                        raise ProviderThroughputError("shared limiter waiter expired before admission")
                    own = state["waiters"][position]
                    own["updated_at"] = now
                    if position != 0:
                        return None, min(self._POLL_S, 0.25), "fifo_queue"
                    reservations = state["reservations"]
                    active_tokens = sum(int(item["tokens"]) for item in reservations)
                    backoff_wait = max(0.0, float(state["blocked_until"]) - now)
                    tightened = now < float(state["tightened_until"])
                    effective_limit = max(1, self.token_limit // 2) if tightened else self.token_limit
                    report = state["header_report"]
                    header_fresh = (
                        report is not None
                        and not tightened
                        and now - float(report["at"]) <= self.HEADER_FRESH_S
                    )
                    request_wait = 0.0
                    capacity_wait = 0.0
                    if header_fresh:
                        basis = float(report["basis_at"])
                        since = [item for item in reservations if float(item["started_at"]) > basis]
                        available = (
                            float(report["remaining_tokens"]) * self.HEADER_SAFETY_FRACTION
                            - sum(int(item["tokens"]) for item in since)
                        )
                        remaining_requests = report.get("remaining_requests")
                        requests_ok = (
                            remaining_requests is None
                            or float(remaining_requests) - len(since) >= 1
                        )
                        if load > available or not requests_ok:
                            stale_in = float(report["at"]) + self.HEADER_FRESH_S - now
                            capacity_wait = max(1e-3, min(self._POLL_S, stale_in))
                        basis_label = "provider_headers"
                    else:
                        basis_label = "local_accounting"
                        recent_requests = [
                            item for item in reservations
                            if now - float(item["started_at"]) < self.window_s
                        ]
                        if len(recent_requests) >= self.request_limit:
                            oldest_request = min(float(item["started_at"]) for item in recent_requests)
                            request_wait = max(0.0, oldest_request + self.window_s - now)
                        if active_tokens + load > effective_limit:
                            excess = active_tokens + load - effective_limit
                            released = 0
                            settled = sorted(
                                (item for item in reservations if item["status"] == "settled"),
                                key=lambda item: float(
                                    item["started_at"]
                                    if self.window_anchor == "dispatch"
                                    else item["settled_at"]
                                ),
                            )
                            capacity_time = None
                            for item in settled:
                                released += int(item["tokens"])
                                if released >= excess:
                                    quota_anchor = (
                                        float(item["started_at"])
                                        if self.window_anchor == "dispatch"
                                        else float(item["settled_at"])
                                    )
                                    capacity_time = quota_anchor + self.window_s
                                    break
                            if capacity_time is None:
                                capacity_wait = self._POLL_S
                            else:
                                capacity_wait = max(0.0, capacity_time - now)
                    wait, wait_reason = max(
                        (backoff_wait, "rate_limit_backoff"),
                        (capacity_wait, "rolling_quota"),
                        (request_wait, "request_rate"),
                        key=lambda item: item[0],
                    )
                    if wait > 1e-9:
                        return None, wait, wait_reason
                    reservation_id = uuid.uuid4().hex
                    state["reservations"].append({
                        "reservation_id": reservation_id,
                        "owner_pid": owner_pid,
                        "status": "in_flight",
                        "tokens": load,
                        "started_at": now,
                    })
                    state["waiters"].pop(0)
                    active_after = sum(int(item["tokens"]) for item in state["reservations"])
                    return ({
                        "throughput_reservation_id": reservation_id,
                        "throughput_token_limit": self.token_limit,
                        "throughput_request_limit": self.request_limit,
                        "throughput_window_s": self.window_s,
                        "throughput_estimated_tokens": load,
                        "throughput_wait_s": max(0.0, now - started),
                        "throughput_spacing_s": 0.0,
                        "throughput_admission_basis": basis_label,
                        "throughput_rolling_wait_s": wait_by_reason["rolling_quota"],
                        "throughput_wait_by_reason_s": dict(wait_by_reason),
                        "throughput_active_reserved_tokens": active_after,
                        "throughput_single_request_admission": "shared_fifo_reservation",
                    }, 0.0, None)
                result, wait, wait_reason = self._mutate(try_admit)
                if result is not None:
                    return result
                before_sleep = self._clock()
                self._wait_for(wait)
                waited = max(0.0, self._clock() - before_sleep)
                if wait_reason is not None:
                    wait_by_reason[wait_reason] += waited
        except BaseException:
            self._mutate(lambda state: state.update({
                "waiters": [item for item in state["waiters"] if item.get("waiter_id") != waiter_id]
            }))
            raise

    def reconcile_observed_usage(
        self,
        *,
        reservation_id: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        requested_output_tokens: int,
    ) -> dict[str, Any]:
        if not reservation_id:
            raise ProviderThroughputError("shared limiter reservation identity is missing")
        known_usage = (
            type(input_tokens) is int and input_tokens >= 0
            and type(output_tokens) is int and output_tokens >= 0
        )
        observed = input_tokens + output_tokens if known_usage else None
        def settle(state: dict[str, Any]) -> dict[str, Any]:
            now = self._clock()
            self._prune(state, now)
            item = next((row for row in state["reservations"] if row.get("reservation_id") == reservation_id), None)
            if item is None or item.get("status") != "in_flight":
                raise ProviderThroughputError("shared limiter reservation is absent or already settled")
            reserved = int(item["tokens"])
            charged = int(observed) if observed is not None else reserved
            item["tokens"] = charged
            item["status"] = "settled"
            item["settled_at"] = now
            if known_usage:
                state["output_observations"] = (
                    list(state["output_observations"]) + [int(output_tokens)]
                )[-self.OUTPUT_MAX_OBSERVATIONS:]
            active = sum(int(row["tokens"]) for row in state["reservations"])
            return {
                "throughput_usage_reconciled": known_usage,
                "throughput_reconciled_tokens": charged,
                "throughput_usage_reconciliation_status": "observed_input_plus_output" if known_usage else "missing_usage_kept_reserved_cap",
                "throughput_requested_output_tokens": max(0, int(requested_output_tokens)),
                "throughput_window_anchor": (
                    "dispatch" if self.window_anchor == "dispatch" else "response_settlement"
                ),
                "throughput_active_reserved_tokens": active,
            }
        return self._mutate(settle)

    def mark_failed_reservation(self, *, reservation_id: str | None) -> None:
        if not reservation_id:
            return
        def fail(state: dict[str, Any]) -> None:
            now = self._clock()
            self._prune(state, now)
            item = next((row for row in state["reservations"] if row.get("reservation_id") == reservation_id), None)
            if item is None:
                raise ProviderThroughputError("failed provider reservation is missing")
            if item.get("status") == "in_flight":
                item["status"] = "settled"
                item["settled_at"] = now
        self._mutate(fail)

    def release_reservation(self, *, reservation_id: str | None) -> None:
        if not reservation_id:
            return
        def release(state: dict[str, Any]) -> None:
            item = next((row for row in state["reservations"] if row.get("reservation_id") == reservation_id), None)
            if item is None:
                return
            state["reservations"].remove(item)
        self._mutate(release)

    def note_rate_limit(self) -> None:
        def block(state: dict[str, Any]) -> None:
            until = self._clock() + self.window_s
            state["blocked_until"] = max(float(state["blocked_until"]), until)
            state["next_dispatch_at"] = max(float(state["next_dispatch_at"]), until)
        self._mutate(block)

    def report_rate_limit_headers(
        self,
        *,
        remaining_tokens: int | float | None,
        remaining_requests: int | float | None = None,
        reservation_id: str | None = None,
        observed_at: float | None = None,
    ) -> bool:
        """Record provider-reported remaining quota; returns True if stored.

        Freshness runs from ``observed_at`` (default now). Quota already
        consumed by requests dispatched after the reporting request began is
        not reflected in the header, so those reservations are subtracted: the
        reporting request's own dispatch time (looked up by ``reservation_id``)
        is the basis, falling back to ``observed_at``.
        """
        if not self._finite_number(remaining_tokens) or float(remaining_tokens) < 0:
            return False
        if remaining_requests is not None and not self._finite_number(remaining_requests):
            remaining_requests = None
        def store(state: dict[str, Any]) -> bool:
            now = self._clock()
            at = float(observed_at) if observed_at is not None else now
            item = next(
                (row for row in state["reservations"] if row.get("reservation_id") == reservation_id),
                None,
            ) if reservation_id else None
            basis = float(item["started_at"]) if item is not None else at
            previous = state["header_report"]
            if previous is not None and float(previous["at"]) > at:
                return False
            state["header_report"] = {
                "at": at,
                "basis_at": min(basis, at),
                "remaining_tokens": float(remaining_tokens),
                "remaining_requests": (
                    None if remaining_requests is None else float(remaining_requests)
                ),
            }
            return True
        return self._mutate(store)

    def note_rate_limit_response(self, *, retry_after_s: float | None = None) -> None:
        """Provider 429: block admissions for retry-after, halve the limit for 60 s."""
        delay = (
            float(retry_after_s)
            if self._finite_number(retry_after_s) and float(retry_after_s) > 0
            else self.RATE_LIMIT_DEFAULT_RETRY_AFTER_S
        )
        def block(state: dict[str, Any]) -> None:
            now = self._clock()
            state["blocked_until"] = max(float(state["blocked_until"]), now + delay)
            state["tightened_until"] = max(
                float(state["tightened_until"]), now + self.RATE_LIMIT_TIGHTEN_S,
            )
            state["header_report"] = None
        self._mutate(block)
