import unittest

from ledgerkit.report import split_lines


class TestReport(unittest.TestCase):
    def test_header_and_first_share(self):
        lines = split_lines("Dinner", 1000, [1, 1], ["ana", "ben"])
        self.assertEqual(lines[0], "Dinner: 10.00")
        self.assertEqual(lines[1], "  ana: 5.00")


if __name__ == "__main__":
    unittest.main()
