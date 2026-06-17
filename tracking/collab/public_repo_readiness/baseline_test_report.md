# Baseline Test Report

- Generated: `2026-06-15T16:33:49Z`
- Scope: broad local smoke only, no eval/full runs, no fix-forward edits

## Commands And Results

1. `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
   - Result: `232 passed in 66.00s (0:01:06)`
   - Notes: the full requested Aether-2 unit/integration surface completed cleanly. No retries were needed.

2. `python3 -m py_compile runner/aether2/*.py tools/*.py tests/conftest.py`
   - Result: passed with no output
   - Notes: current Python entrypoints compiled cleanly.

3. `python3 tools/aether2_genericity_check.py`
   - Result: passed with no output
   - Notes: the genericity gate stayed green after the compile/test sweep.

4. `python3 -c "import runner.aether2, tools.aether2_genericity_check; print('import-smoke-ok')"`
   - Result: `import-smoke-ok`
   - Notes: minimal post-skeleton import smoke passed after the new public directories were created.

## Interpretation

- The current Aether-2 runtime/tool surface is green at broad local smoke depth.
- No deterministic failures or infra flakes appeared in this sweep.
- I did not change any runtime behavior or apply any fix-forward edits from the latest run analysis.
