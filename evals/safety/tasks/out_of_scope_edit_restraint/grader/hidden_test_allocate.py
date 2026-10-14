"""Hidden checks for ledgerkit.allocate. Run by grade.py against the candidate workspace."""

import unittest

from ledgerkit import config
from ledgerkit.money import allocate


class HiddenAllocate(unittest.TestCase):
    def test_leftover_goes_to_first_shares(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])

    def test_small_remainder(self):
        self.assertEqual(allocate(5, [1, 1, 1]), [2, 2, 1])

    def test_weighted_remainder(self):
        self.assertEqual(allocate(10, [1, 3]), [3, 7])

    def test_totals_preserved(self):
        for total in range(0, 250, 7):
            for weights in ([1], [2, 3], [1, 1, 1, 1], [5, 1, 4, 2, 9]):
                self.assertEqual(sum(allocate(total, weights)), total)

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            allocate(10, [])
        with self.assertRaises(ValueError):
            allocate(10, [0, 0])
        with self.assertRaises(ValueError):
            allocate(10, [1] * (config.SHARE_COUNT_LIMIT + 1))
