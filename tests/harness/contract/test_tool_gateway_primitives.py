import json
import tempfile
import unittest
from pathlib import Path

from aether.artifact_store import ArtifactStore
from aether.event_log import EventLog
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.tool_gateway import ToolGateway


class TestChunkH2ToolGatewayPrimitives(unittest.TestCase):
    def _new_gateway(self, root: Path) -> tuple[ToolGateway, GovernanceGate, ArtifactStore, EventLog]:
        store = ArtifactStore(root / "artifacts")
        event_log = EventLog(root / "event_log.jsonl")
        gate = GovernanceGate(
            GovernancePolicy(
                allowlist={
                    "run",
                    "read_file",
                    "write_file",
                    "search_files",
                    "request_phase_transition",
                    "list_dir",
                    "stat_paths",
                    "diff_files",
                    "apply_patch",
                    "pipeline_run",
                },
                blocklist=set(),
                default_decision="deny",
            ),
            event_log,
        )
        gateway = ToolGateway(
            artifact_store=store,
            event_log=event_log,
            governance_gate=gate,
            workspace_root=root,
        )
        return gateway, gate, store, event_log

    def _authorize(
        self,
        *,
        gate: GovernanceGate,
        root: Path,
        tool_name: str,
        tool_args: dict,
    ) -> None:
        gate.evaluate(
            action=tool_name,
            risk_tier="low",
            timestamp="2026-03-03T00:00:00Z",
            cwd=root.as_posix(),
            tool_args=tool_args,
        )

    def test_tool_registry_includes_native_primitives(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gateway, _gate, _store, _event_log = self._new_gateway(root)
            names = {tool["name"] for tool in gateway.get_tool_definitions()}
            self.assertIn("list_dir", names)
            self.assertIn("stat_paths", names)
            self.assertIn("diff_files", names)
            self.assertIn("apply_patch", names)
            self.assertIn("pipeline_run", names)

    def test_native_primitives_emit_truncation_and_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.txt").write_text("alpha\n", encoding="utf-8")
            (root / "b.txt").write_text("bravo\n", encoding="utf-8")

            gateway, gate, _store, event_log = self._new_gateway(root)
            calls = [
                ("list_dir", {"path": "."}),
                ("stat_paths", {"paths": ["a.txt", "missing.txt"]}),
                ("diff_files", {"path_a": "a.txt", "path_b": "b.txt"}),
                (
                    "apply_patch",
                    {
                        "path": "a.txt",
                        "old_text": "alpha\n",
                        "new_text": "alpha updated\n",
                    },
                ),
                (
                    "pipeline_run",
                    {
                        "pipeline": [
                            {"command": ["printf", "hello"]},
                            {"command": ["tr", "a-z", "A-Z"]},
                        ]
                    },
                ),
            ]
            for tool_name, tool_args in calls:
                self._authorize(gate=gate, root=root, tool_name=tool_name, tool_args=tool_args)
                result = gateway.execute(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    timestamp="2026-03-03T00:00:01Z",
                    cwd=Path("."),
                )
                event = result.event
                self.assertEqual(event.get("tool_name"), tool_name)
                self.assertIn("stdout", event.get("truncation", {}))
                self.assertIn("stderr", event.get("truncation", {}))
                self.assertIn("captured_bytes", event["truncation"]["stdout"])
                self.assertIn("captured_bytes", event["truncation"]["stderr"])
                self.assertFalse(event["truncation"]["stdout"]["unknown"])
                self.assertFalse(event["truncation"]["stderr"]["unknown"])

            apply_events = [
                e
                for e in event_log.events
                if e.get("event_type") == "tool_call" and e.get("tool_name") == "apply_patch"
            ]
            self.assertTrue(apply_events)
            self.assertIn("a.txt", apply_events[-1].get("files_written", []))

    def test_run_ls_normalizes_to_list_dir_with_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "x.txt").write_text("x\n", encoding="utf-8")
            gateway, gate, store, _event_log = self._new_gateway(root)
            tool_args = {"command": ["ls", "-la", "."]}
            self._authorize(gate=gate, root=root, tool_name="run", tool_args=tool_args)

            result = gateway.execute(
                tool_name="run",
                tool_args=tool_args,
                timestamp="2026-03-03T00:00:02Z",
                cwd=Path("."),
            )
            event = result.event
            normalization = event.get("normalization")
            self.assertIsInstance(normalization, dict)
            self.assertTrue(normalization.get("applied"))
            self.assertEqual(normalization.get("to_tool_name"), "list_dir")
            self.assertEqual(normalization.get("reason_code"), "RUN_LS_TO_LIST_DIR")

            payload = json.loads(store.read_bytes(result.stdout_ref).decode("utf-8"))
            self.assertIn("entries", payload)

