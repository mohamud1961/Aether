from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from types import SimpleNamespace

from aether import harbor_runtime
from aether.harbor_runtime import (
    _runtime_identity,
    _update_agent_context,
    discover_harbor_workspace,
    literal_task_absolute_paths,
    run_harbor_aether,
)
from aether.run_cancellation import RunCancellationRequested


@dataclass
class _Completed:
    return_code: int
    stdout: str = ""
    stderr: str = ""


class _LocalAsyncEnvironment:
    """Real local OS implementation of Harbor's small public environment surface."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def exec(
        self,
        *,
        command: str,
        cwd: str | None,
        env: dict[str, str] | None,
        timeout_sec: int,
    ) -> _Completed:
        def _run() -> _Completed:
            completed = subprocess.run(
                ["/bin/sh", "-lc", command],
                cwd=cwd or str(self.workspace),
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            return _Completed(completed.returncode, completed.stdout, completed.stderr)

        return await asyncio.to_thread(_run)

    async def upload_file(self, source: Path, destination: str) -> None:
        def _copy() -> None:
            target = Path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

        await asyncio.to_thread(_copy)

    async def download_file(self, source: str, destination: Path) -> None:
        await asyncio.to_thread(shutil.copyfile, source, destination)


class _ForbiddenArchitect:
    def __call__(self, *_args, **_kwargs):
        raise AssertionError("PCR V0 must not call Architect")


class _HappySolver:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=8000):
        del max_output_tokens
        self.calls += 1
        if self.calls == 1:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "write_file",
                            "arguments": {"path": "out.txt", "content": "hello"},
                },
            })
        if self.calls == 2:
            return json.dumps({
                "kind": "act",
                "action": {
                    "kind": "read_file",
                            "arguments": {"path": "out.txt"},
                },
            })
        aliases: list[str] = []
        for message in messages:
            aliases.extend(re.findall(r"evidence:[0-9a-f]{16}", str(message.get("content", ""))))
        return json.dumps({
            "kind": "submit",
            "claim": "out.txt contains hello",
            "evidence_refs": list(dict.fromkeys(aliases)),
        })


class _InspectingVerifier:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, messages, *, max_output_tokens=12000):
        del max_output_tokens
        self.calls += 1
        if len(messages) <= 2:
            return json.dumps({
                "kind": "inspect",
                "requests": [{
                    "request_id": "read-current-out",
                    "kind": "read_file",
                    "path": "out.txt",
                    "proof_ids": [],
                }],
            })
        inspection_ids: list[str] = []
        for message in reversed(messages):
            try:
                payload = json.loads(str(message.get("content", "")))
            except json.JSONDecodeError:
                continue
            rows = payload.get("verifier_inspection_results") if isinstance(payload, dict) else None
            if isinstance(rows, list):
                inspection_ids = [
                    str(row.get("inspection_id"))
                    for row in rows
                    if isinstance(row, dict) and row.get("inspection_id")
                ]
                if inspection_ids:
                    break
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "independent exact read confirmed claim",
            "findings": [],
            "missing_evidence_requests": [],
            "completion_evidence": [{
                "requirement": "out.txt contains hello",
                "observed": "independent read returned hello",
                "inspection_refs": inspection_ids,
                "clause_ids": ["task:raw"],
                "proof_ids": [],
                "evidence_class": "exact_contract",
                "risk_refs": [],
                "requirement_status": "satisfied",
                "falsification_check": "different or missing bytes refute claim",
            }],
            "method_validity": None,
        })



def test_runtime_identity_prefers_sealed_manifest_task_and_run_identity(monkeypatch) -> None:
    class EnvMap:
        @staticmethod
        def digest() -> str:
            return "env-digest"

    context = SimpleNamespace(
        metadata={"task_id": "context-task", "source_commit": "a" * 40, "runtime_manifest_sha256": "b" * 64},
        context_id="ctx-1",
    )
    monkeypatch.setenv("AETHER_FIRST_SUBMIT_TASK_ID", "sealed-task")
    monkeypatch.setenv("AETHER_FIRST_SUBMIT_RUN_ID", "first-submit:" + "c" * 64)
    identity = _runtime_identity(context, EnvMap())
    assert identity["task_id"] == "sealed-task"
    assert identity["task_id_authority"] == "sealed_first_submit_manifest"
    assert identity["run_id"] == "first-submit:" + "c" * 64
    assert identity["run_id_authority"] == "sealed_first_submit_manifest"


def test_runtime_identity_falls_back_to_harbor_context_without_seal(monkeypatch) -> None:
    class EnvMap:
        @staticmethod
        def digest() -> str:
            return "env-digest"

    monkeypatch.delenv("AETHER_FIRST_SUBMIT_TASK_ID", raising=False)
    monkeypatch.delenv("AETHER_FIRST_SUBMIT_RUN_ID", raising=False)
    context = SimpleNamespace(metadata={"task_id": "context-task"}, context_id="ctx-2")
    identity = _runtime_identity(context, EnvMap())
    assert identity["task_id"] == "context-task"
    assert identity["task_id_authority"] == "harbor_context"
    assert identity["run_id"] == "harbor:ctx-2"
    assert identity["run_id_authority"] == "harbor_context"



def test_runtime_identity_exposes_effective_harbor_agent_timeout() -> None:
    class EnvMap:
        task_metadata = {"agent_timeout_sec": 900.0}

        @staticmethod
        def digest() -> str:
            return "env-digest"

    context = SimpleNamespace(metadata={"task_id": "context-task"}, context_id="ctx-timeout")
    identity = _runtime_identity(context, EnvMap())
    assert identity["budgets"]["agent_timeout_sec"] == 900.0


def test_harbor_async_bridge_propagates_effective_timeout_and_start(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_sync(**kwargs):
        captured.update(kwargs)
        return {"status": "completed"}

    monkeypatch.setattr(harbor_runtime, "run_harbor_aether_sync", fake_sync)

    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-timeout-") as tmp:
            root = Path(tmp).resolve()
            result = await harbor_runtime.run_harbor_aether(
                environment=_LocalAsyncEnvironment(root),
                context=SimpleNamespace(metadata={}, context_id="timeout-context"),
                instruction="unit timeout propagation",
                logs_dir=root / "logs",
                model_factory=lambda: (object(), object()),
                agent_timeout_sec=900.0,
                run_started_monotonic=123.5,
            )
            assert result == {"status": "completed"}

    asyncio.run(main())
    assert captured["agent_timeout_sec"] == 900.0
    assert captured["run_started_monotonic"] == 123.5

def test_discover_harbor_workspace_uses_live_pwd_when_standard_candidates_do_not_own_it() -> None:
    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-runtime-") as tmp:
            workspace = Path(tmp).resolve()
            facts = await discover_harbor_workspace(_LocalAsyncEnvironment(workspace))
            assert facts.pwd == str(workspace)
            assert facts.workspace_root == str(workspace)
            assert facts.git_root == ""

    asyncio.run(main())

def test_discover_harbor_workspace_prefers_live_pwd_over_incidental_app_directory() -> None:
    class Environment:
        async def exec(self, *, command, cwd, env, timeout_sec):
            del cwd, env, timeout_sec
            if command == "pwd":
                return _Completed(0, "/home/project\n")
            if command.startswith("git rev-parse"):
                return _Completed(0, "")
            if "test -d /app" in command:
                return _Completed(0, "present")
            if "test -d /workspace" in command:
                return _Completed(0, "missing")
            raise AssertionError(f"unexpected workspace probe: {command}")

    facts = asyncio.run(discover_harbor_workspace(Environment()))
    assert facts.pwd == "/home/project"
    assert facts.git_root == ""
    assert facts.existing_candidates == ("/app",)
    assert facts.workspace_root == "/home/project"



def test_update_agent_context_records_aggregates_without_claiming_atif() -> None:
    context = SimpleNamespace(
        metadata={},
        n_input_tokens=0,
        n_cache_tokens=0,
        n_output_tokens=0,
        cost_usd=0.0,
    )
    _update_agent_context(context, {
        "status": "completed",
        "step": 4,
        "classifier_label": "none",
        "runtime_identity": {"run_id": "r"},
        "run_metrics": {"x": 1},
        "model_call_telemetry": [
            {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 10, "cost_usd": 0.1},
            {"input_tokens": 200, "cached_input_tokens": 90, "output_tokens": 20, "cost_usd": 0.2},
        ],
    })
    assert context.n_input_tokens == 300
    assert context.n_cache_tokens == 130
    assert context.n_output_tokens == 30
    assert abs(context.cost_usd - 0.3) < 1e-9
    assert context.metadata["aether"]["atif_status"] == "NOT_YET_IMPLEMENTED"


def test_update_agent_context_preserves_unknown_provider_cost() -> None:
    context = SimpleNamespace(
        metadata={},
        n_input_tokens=0,
        n_cache_tokens=0,
        n_output_tokens=0,
        cost_usd=0.0,
    )
    _update_agent_context(context, {
        "status": "provider_failure",
        "step": 2,
        "classifier_label": "provider_failure",
        "runtime_identity": {"run_id": "r"},
        "run_metrics": {},
        "model_call_telemetry": [
            {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 10, "cost_usd": None},
        ],
    })
    assert context.n_input_tokens == 100
    assert context.n_cache_tokens == 80
    assert context.n_output_tokens == 10
    assert context.cost_usd is None


def test_harbor_runtime_contract_runs_canonical_pcr_kernel_on_external_world() -> None:
    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-runtime-") as tmp:
            root = Path(tmp).resolve()
            workspace = root / "workspace"
            logs = root / "logs"
            workspace.mkdir()
            (workspace / "README.md").write_text("external Harbor-like world\n", encoding="utf-8")
            context = SimpleNamespace(
                metadata={
                    "task_id": "harbor-contract",
                    "source_commit": "a" * 40,
                    "runtime_manifest_sha256": "b" * 64,
                },
                context_id="ctx-1",
                n_input_tokens=0,
                n_cache_tokens=0,
                n_output_tokens=0,
                cost_usd=0.0,
            )
            solver = _HappySolver()
            verifier = _InspectingVerifier()

            record = await run_harbor_aether(
                environment=_LocalAsyncEnvironment(workspace),
                context=context,
                instruction="Create out.txt containing hello.",
                logs_dir=logs,
                mcp_servers=(
                    {"name": "playwright", "transport": "sse", "url": "http://playwright-mcp:3080/sse"},
                ),
                max_steps=6,
                model_factory=lambda: (solver, verifier),
            )

            assert record["status"] == "completed", json.dumps(record["receipt_summary"], indent=2)
            assert (workspace / "out.txt").read_text(encoding="utf-8") == "hello"
            assert solver.calls >= 3
            assert verifier.calls >= 2
            probe = context.metadata["aether_harbor_workspace_probe"]
            assert probe["workspace_root"] == str(workspace)
            projection = record["world_state_snapshot"]
            assert projection["schema_version"] == "dynamic_world_state.v1"
            assert projection["runtime_facts"]["workspace_root"] == str(workspace)
            assert context.metadata["aether"]["atif_status"] == "ATIF-v1.7"
            trajectory_path = Path(context.metadata["aether"]["atif_trajectory_path"])
            assert trajectory_path == logs / "trajectory.json"
            trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
            assert trajectory["schema_version"] == "ATIF-v1.7"
            assert trajectory["steps"][0]["source"] == "user"
            assert trajectory["agent"]["name"] == "aether-next"
            assert record["runtime_identity"]["source_commit"] == "a" * 40

            evidence_meta = context.metadata["aether"]
            run_record_path = Path(evidence_meta["aether_run_record_path"])
            x0_path = Path(evidence_meta["x0_observability_path"])
            assert run_record_path == logs / "aether_run_record.json"
            assert x0_path == logs / "aether_x0_observability.json"
            persisted = json.loads(run_record_path.read_text(encoding="utf-8"))
            assert persisted["status"] == "completed"
            assert persisted["runtime_identity"]["source_commit"] == "a" * 40
            observed_run_sha = sha256(run_record_path.read_bytes()).hexdigest()
            assert evidence_meta["aether_run_record_sha256"] == observed_run_sha
            assert record["aether_run_record_sha256"] == observed_run_sha
            x0 = json.loads(x0_path.read_text(encoding="utf-8"))
            assert x0["schema_version"] == "aether.postmerge.x0_observability.v1"
            assert x0["source_run"]["sha256"] == observed_run_sha
            assert x0["source_run"]["runtime_identity"]["source_commit"] == "a" * 40
            solver_captures = [
                capture for capture in record["model_interface_captures"]
                if capture.get("manifest", {}).get("model_role") == "solver"
            ]
            assert solver_captures
            solver_wire = json.dumps(solver_captures[0]["messages"], sort_keys=True)
            assert "environment_extensions" in solver_wire
            assert "playwright-mcp:3080/sse" in solver_wire
            assert "harbor_task_declared_environment_extension" in solver_wire
            # PCR production keeps the action kind/arguments surface but
            # does not ask the model to author a redundant capability owner.
            assert "capability_id" not in solver_wire

            structural_marker = (
                logs / "aether_harbor" / "visible_path_projection"
            )
            assert structural_marker.exists()
            # The local structural mirror contains names only; actual task bytes
            # remain in the external world and are changed there by the executor.
            assert (structural_marker / "README.md").read_bytes() == b""

    asyncio.run(main())


def test_literal_task_absolute_paths_extracts_only_literal_unix_paths() -> None:
    text = (
        "Configure /git/server and publish to /var/www/server. "
        "Do not infer output.txt or the word server as paths. Also inspect `/app/a.txt`. "
        "Fetch https://example.com/path and http://host.invalid/also-not-a-path."
    )
    assert literal_task_absolute_paths(text) == (
        "/git/server", "/var/www/server", "/app/a.txt",
    )


def test_literal_task_absolute_paths_extracts_scp_remote_paths_without_urls() -> None:
    text = (
        "Run git clone user@server:/git/server and inspect host.example:/var/lib/data/file. "
        "Do not treat https://example.com/path or http://host.invalid/also-not-a-path as files."
    )
    assert literal_task_absolute_paths(text) == (
        "/git/server", "/var/lib/data/file",
    )


def test_literal_task_absolute_paths_covers_configure_git_webserver_task_syntax() -> None:
    text = (
        "Configure a git server so that I can run on my computer\n"
        "    git clone user@server:/git/server\n"
        "    echo \"hello world\" > hello.html\n"
        "    git push origin master\n"
        "and then curl http://server:8080/hello.html"
    )
    assert literal_task_absolute_paths(text) == ("/git/server",)



def test_harbor_cancellation_drains_worker_before_return(monkeypatch) -> None:
    """Harbor timeout cancellation cannot abandon a live Aether worker thread."""
    worker_started = threading.Event()
    worker_stopped = threading.Event()

    def fake_sync(*, cancellation_event, **_kwargs):
        worker_started.set()
        assert cancellation_event is not None
        cancellation_event.wait(timeout=2.0)
        if not cancellation_event.is_set():
            raise AssertionError("async Harbor adapter did not signal worker cancellation")
        worker_stopped.set()
        raise RunCancellationRequested("unit cancellation")

    monkeypatch.setattr(harbor_runtime, "run_harbor_aether_sync", fake_sync)

    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-cancel-") as tmp:
            root = Path(tmp).resolve()
            context = SimpleNamespace(metadata={}, context_id="cancel-context")
            task = asyncio.create_task(harbor_runtime.run_harbor_aether(
                environment=_LocalAsyncEnvironment(root),
                context=context,
                instruction="unit cancellation",
                logs_dir=root / "logs",
                model_factory=lambda: (object(), object()),
            ))
            for _ in range(1000):
                if worker_started.is_set():
                    break
                await asyncio.sleep(0.001)
            assert worker_started.is_set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Harbor cancellation must propagate")
            assert worker_stopped.is_set(), "cancellation returned before worker relinquished world"

    asyncio.run(main())


def test_harbor_repeated_cancellation_cannot_escape_worker_drain(monkeypatch) -> None:
    """Repeated outer cancellation must not abandon cleanup already in progress."""
    worker_started = threading.Event()
    cleanup_started = threading.Event()
    worker_release = threading.Event()
    worker_stopped = threading.Event()

    def fake_sync(*, cancellation_event, **_kwargs):
        worker_started.set()
        assert cancellation_event is not None
        assert cancellation_event.wait(timeout=2.0)
        cleanup_started.set()
        assert worker_release.wait(timeout=2.0)
        worker_stopped.set()
        raise RunCancellationRequested("unit repeated cancellation")

    monkeypatch.setattr(harbor_runtime, "run_harbor_aether_sync", fake_sync)

    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-repeat-cancel-") as tmp:
            root = Path(tmp).resolve()
            task = asyncio.create_task(harbor_runtime.run_harbor_aether(
                environment=_LocalAsyncEnvironment(root),
                context=SimpleNamespace(metadata={}, context_id="repeat-cancel"),
                instruction="unit repeated cancellation",
                logs_dir=root / "logs",
                model_factory=lambda: (object(), object()),
            ))
            for _ in range(1000):
                if worker_started.is_set():
                    break
                await asyncio.sleep(0.001)
            assert worker_started.is_set()
            task.cancel()
            for _ in range(1000):
                if cleanup_started.is_set():
                    break
                await asyncio.sleep(0.001)
            assert cleanup_started.is_set()
            task.cancel()
            try:
                await asyncio.sleep(0.02)
                assert not task.done(), "repeated cancellation escaped before worker drain"
            finally:
                worker_release.set()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("Harbor cancellation must propagate")
            assert worker_stopped.is_set()

    asyncio.run(main())


def test_cancellation_after_solver_decision_prevents_action_dispatch() -> None:
    """Revoked authority between model return and dispatch cannot mutate task state."""
    class CancellingSolver:
        def __init__(self) -> None:
            self.event = None

        def bind_run_cancellation(self, event) -> None:
            self.event = event

        def __call__(self, _messages, *, max_output_tokens=16000):
            del max_output_tokens
            assert self.event is not None
            self.event.set()
            return json.dumps({
                "kind": "act",
                "action": {"kind": "write_file", "arguments": {"path": "forbidden.txt", "content": "late"}},
            })

    class NeverVerifier:
        def __call__(self, *_args, **_kwargs):
            raise AssertionError("Verifier must not run after cancellation")

    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-cancel-dispatch-") as tmp:
            root = Path(tmp).resolve()
            workspace = root / "workspace"; workspace.mkdir()
            solver = CancellingSolver()
            record = await run_harbor_aether(
                environment=_LocalAsyncEnvironment(workspace),
                context=SimpleNamespace(metadata={"task_id": "cancel-dispatch"}, context_id="cancel-dispatch"),
                instruction="Create forbidden.txt.",
                logs_dir=root / "logs",
                max_steps=2,
                model_factory=lambda: (solver, NeverVerifier()),
            )
            assert record["status"] == "timeout"
            assert record["blockers"] == ["external_run_cancellation"]
            assert record["classifier_label"] == "timeout_resource_failure"
            assert (root / "logs" / "aether_run_record.json").is_file()
            assert (root / "logs" / "aether_x0_observability.json").is_file()
            assert not (workspace / "forbidden.txt").exists()

    asyncio.run(main())


def test_outer_harbor_cancellation_persists_terminal_evidence_before_propagation() -> None:
    """A Harbor timeout/cancel must drain Aether into durable timeout evidence."""
    solver_entered = threading.Event()

    class BlockingSolver:
        def __init__(self) -> None:
            self.event = None

        def bind_run_cancellation(self, event) -> None:
            self.event = event

        def __call__(self, _messages, *, max_output_tokens=16000):
            del max_output_tokens
            solver_entered.set()
            assert self.event is not None
            assert self.event.wait(timeout=10.0), "outer cancellation was not delivered"
            return json.dumps({
                "kind": "act",
                "action": {"kind": "write_file", "arguments": {"path": "late.txt", "content": "late"}},
            })

    class NeverVerifier:
        def __call__(self, *_args, **_kwargs):
            raise AssertionError("Verifier must not run after outer cancellation")

    async def main() -> None:
        with tempfile.TemporaryDirectory(prefix="aether-harbor-outer-cancel-") as tmp:
            root = Path(tmp).resolve()
            workspace = root / "workspace"; workspace.mkdir()
            task = asyncio.create_task(run_harbor_aether(
                environment=_LocalAsyncEnvironment(workspace),
                context=SimpleNamespace(metadata={"task_id": "outer-cancel"}, context_id="outer-cancel"),
                instruction="Create late.txt.",
                logs_dir=root / "logs",
                max_steps=2,
                model_factory=lambda: (BlockingSolver(), NeverVerifier()),
            ))
            for _ in range(10000):
                if solver_entered.is_set():
                    break
                await asyncio.sleep(0.001)
            assert solver_entered.is_set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            else:
                raise AssertionError("outer Harbor cancellation must still propagate")

            run_path = root / "logs" / "aether_run_record.json"
            x0_path = root / "logs" / "aether_x0_observability.json"
            assert run_path.is_file()
            assert x0_path.is_file()
            record = json.loads(run_path.read_text(encoding="utf-8"))
            assert record["status"] == "timeout"
            assert record["blockers"] == ["external_run_cancellation"]
            assert record["classifier_label"] == "timeout_resource_failure"
            assert any(
                row.get("kind") == "runtime_accounting"
                and row.get("payload", {}).get("counter") == "solver_provider_turns"
                for row in record["receipt_records"]
            )
            assert not (workspace / "late.txt").exists()

    asyncio.run(main())


def test_runtime_identity_carries_launch_custody_without_model_semantics(monkeypatch) -> None:
    class EnvMap:
        task_metadata = {}

        @staticmethod
        def digest() -> str:
            return "env-digest"

    monkeypatch.setenv("AETHER_CAMPAIGN_ID", "campaign-a")
    monkeypatch.setenv("AETHER_TASK_CLOSURE_SHA256", "e" * 64)
    monkeypatch.setenv("AETHER_PACKAGE_CLOSURE_SHA256", "f" * 64)
    context = SimpleNamespace(metadata={"task_id": "task-a"}, context_id="ctx-custody")
    identity = _runtime_identity(context, EnvMap())
    assert identity["campaign_id"] == "campaign-a"
    assert identity["task_closure_sha256"] == "e" * 64
    assert identity["package_closure_sha256"] == "f" * 64
