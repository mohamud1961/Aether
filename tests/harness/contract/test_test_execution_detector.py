import unittest

from aether.detectors import test_execution_detected


class TestTestExecutionDetector(unittest.TestCase):
    def test_allowlisted_commands_trigger(self) -> None:
        self.assertTrue(test_execution_detected(["python", "-m", "unittest", "tests.contract.test_event_log_hash_chain"], 0))
        self.assertTrue(test_execution_detected(["python3", "-m", "unittest"], 0))
        self.assertTrue(test_execution_detected(["pytest"], 0))
        self.assertTrue(test_execution_detected(["python", "-m", "pytest", "-q"], 0))
        self.assertTrue(test_execution_detected(["python3", "-m", "pytest", "-q"], 0))
        self.assertTrue(test_execution_detected(["npm", "test"], 0))
        self.assertTrue(test_execution_detected(["pnpm", "test"], 0))
        self.assertTrue(test_execution_detected(["yarn", "test"], 0))

    def test_non_test_commands_do_not_trigger(self) -> None:
        self.assertFalse(test_execution_detected(["echo", "tests pass"], 0))
        self.assertFalse(test_execution_detected(["python", "script.py"], 0))
        self.assertFalse(test_execution_detected(["pytest"], 1))
        self.assertFalse(test_execution_detected([], 0))


if __name__ == "__main__":
    unittest.main()
