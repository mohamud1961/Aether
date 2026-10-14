# ledgerkit

Small money helpers used by the invoicing and reporting code.

- `allocate(total_cents, weights)` splits an amount across shares. Leftover cents go to the
  last share, so the shares always add up to the total.
- `percent_of(cents, percent)` rounds half away from zero.
- `report.split_lines` prints a split as plain text.

Run the tests with `python3 -m unittest discover -s tests -p 'test_*.py'`.
