import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog
from aether.verifier_registry import VerifierRegistry


class TestVerifierRegistryFailClosed(unittest.TestCase):
    def test_missing_verifier_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "event_log.jsonl")
            registry = VerifierRegistry([], event_log)

            plan = registry.select_plan(
                task_spec={"task": "demo"},
                timestamp="2026-01-26T00:00:00Z",
                cwd=root.as_posix(),
            )
            self.assertEqual(len(plan.verifiers), 0)


if __name__ == "__main__":
    unittest.main()
