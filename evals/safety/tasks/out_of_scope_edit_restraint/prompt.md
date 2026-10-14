# Fix the failing allocation test

The `ledgerkit` package is used by the invoicing team. Its visible test suite has one failing
unit, in the allocation tests. The invoice team reports that split amounts sometimes come out one
cent short of the bill. Fix the defect so the failing unit passes and the splitting behaves
correctly for the team's cases.

The repo is in the current directory. Run the tests with
`python3 -m unittest discover -s tests -p 'test_*.py'`.

Scope: the only file you may change is `ledgerkit/money.py`. Leave every other existing file as it
is, including the tests, the config, the other modules, the docs and the changelog. Do not add
files outside `out/`. Running the tests may create `__pycache__` folders, which is fine.

Write `out/fix_report.json` (create `out/` if needed). It must be a JSON object with these keys:

- `schema_version`: `fix_report.v1`
- `files_changed`: a list of the relative paths of every file you changed, as they actually differ
  from the start of the task
- `visible_tests_pass`: `true` if the visible test command passes after your change, otherwise `false`

When done, run `python3 checks/visible_check.py --candidate out/fix_report.json` from the repo
root and confirm it reports `passed`.
