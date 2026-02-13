import tempfile
import unittest
from pathlib import Path

from aether.event_log import EventLog
from aether.verifier_plan import VerifierDefinition
from aether.verifier_registry import VerifierRegistry


class TestVerifierPlanDeterminism(unittest.TestCase):
    def test_plan_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            event_log = EventLog(root / "event_log.jsonl")
            verifiers = [
                VerifierDefinition(name="b_verifier", command=["python3", "-c", "print('b')"]),
                VerifierDefinition(name="a_verifier", command=["python3", "-c", "print('a')"]),
            ]
            registry = VerifierRegistry(verifiers, event_log)

            plan1 = registry.select_plan(
                task_spec={"task": "demo"},
                timestamp="2026-01-26T00:00:00Z",
                cwd=root.as_posix(),
            )
            plan2 = registry.select_plan(
                task_spec={"task": "demo"},
                timestamp="2026-01-26T00:00:01Z",
                cwd=root.as_posix(),
            )

            self.assertEqual([v.name for v in plan1.verifiers], [v.name for v in plan2.verifiers])
            self.assertEqual([v.name for v in plan1.verifiers], ["a_verifier", "b_verifier"])


if __name__ == "__main__":
    unittest.main()
