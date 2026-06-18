# CLAUDE.md

Contributor and agent guide for HarnessEng.

## Architecture

Four groups, strict one-way dependency flow:

```
eval_suite  →  runner  →  harness/aether2
                              ↑
                         (no upward imports)
```

- **`harness/aether2/`** — Active Python harness line. The agent runtime:
  control loop, tool dispatch, model routing, traces, skills, hooks.
  Generic and task-agnostic. No benchmark-specific hardcoding here.
- **`runner/`** — Eval execution engine. Loads task packs from `eval_suite/`,
  sets up sandboxes, runs agents, collects grader scores. CLI entry:
  `python -m runner run-eval`.
- **`eval_suite/`** — Task packs, graders, schemas, adapters, and result
  evidence. Organized by capability family (`tooling/`, `retrieval/`,
  `filesystem/`, `environment/`) and `whole_harness/` surface. Self-contained:
  no imports from `runner/` or `harness/`.
- **`variants/`** — Mechanism-family and whole-harness variant cards,
  scoreboards, and evidence. References harness code; does not duplicate it.
- **`research/`** — Promoted synthesis outputs, mechanism maps, failure
  taxonomies, case studies.
- **`workflows/`** — AI-native engineering operating system: orchestration,
  skills, synthesis protocols, review and handoff templates.

### Dependency rule

Imports flow downward only: `eval_suite → runner → harness/aether2`.
No module may import upward. No cycles. Verify with:

```bash
grep -rn 'from runner\.' eval_suite/   # must be empty
grep -rn 'from eval_suite\.' harness/  # must be empty
```

## Key Commands

```bash
# Install (editable mode)
pip install -e .

# Run full test suite (65 tests, the verification floor)
python3 -m pytest -q

# Run an eval offline (zero credentials needed)
python3 -m runner run-eval \
  --task-pack eval_suite/mcp_registry_contract_smoke \
  --agent stub --offline

# Public readiness checks (cold-start + smoke + focused tests)
make public-readiness

# Focused public-readiness pytest slice
make public-tests

# Build wheel
python3 -m pip wheel --no-deps -w dist .
```

## Module Size Cap

Every Python module must be ≤ 500 lines of code. Modules over this limit
are decomposed along real responsibility boundaries. Check with:

```bash
find harness/aether2 -name '*.py' | xargs wc -l | sort -rn | head -10
```

## Eval Discipline

- No variant without a target eval, a prediction, and named sentinels.
- Separate environment failures from capability failures.
- Record failed predictions; do not reinterpret them into wins.
- Scoreboards and result rows are the source of truth for promotion.
- Promotion authority lives with scored eval evidence, not trace aesthetics.

## Aether-2 Principle

> The model pilots. The harness instruments. The verifier reflects.
> The ledger remembers. The grader decides.

No task-specific hardcoding in `harness/aether2/`. No benchmark-name
affordances. No harness-side completion veto theater.

## Engineering Standards

Full standards: [`docs/engineering-standards.md`](docs/engineering-standards.md).

Key points: types first, inject dependencies, 500 LOC cap, no dead code,
no duplication across packages, every meaningful run leaves inspectable
evidence.

## Commit Discipline

Commit in coherent slices. Do not bury unrelated work in one giant
checkpoint. Material changes should emit a `RAW_LEDGER_UPDATE` under
`tracking/ledger/inbox/`.
