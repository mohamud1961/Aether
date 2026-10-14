import unittest

from ledgerkit.money import allocate, percent_of


class TestAllocate(unittest.TestCase):
    def test_allocate_weighted(self):
        self.assertEqual(allocate(10, [1, 1]), [5, 5])

    def test_allocate_preserves_total(self):
        shares = allocate(100, [1, 1, 1])
        self.assertEqual(sum(shares), 100)

    def test_allocate_rejects_empty(self):
        with self.assertRaises(ValueError):
            allocate(10, [])


class TestPercent(unittest.TestCase):
    def test_percent_of_rounds_half_up(self):
        self.assertEqual(percent_of(250, 10), 25)


if __name__ == "__main__":
    unittest.main()
