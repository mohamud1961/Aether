import unittest
from pathlib import Path


class TestExecutionGate(unittest.TestCase):
    def test_proof_file(self):
        path = Path("proof.txt")
        self.assertTrue(path.exists(), "proof.txt missing")
        self.assertEqual(path.read_text(encoding="utf-8").strip(), "ok")


if __name__ == "__main__":
    unittest.main()
