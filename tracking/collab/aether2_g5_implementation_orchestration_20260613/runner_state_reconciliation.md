# Runner State Reconciliation

Date: 2026-06-13
Owner: Team R

## Scope

This note reconciles the live Mac checkout, the frozen VM snapshot, and the VM-only
prototype transcript before Team R touches any further runner/measurement tooling.

Sources used:

- `scripts/run_aether2_tournament.sh`
- `tools/run_aether2_g2.py`
- `tracking/collab/vm_pulls/tracking/collab/aether2_g5_failure_analysis_clean_20260613T121431Z/source_snapshot/tools/run_aether2_g3_official.py`
- `/Users/mohamud/.codex/attachments/c47871a9-f5eb-4baf-bf33-97c73d25fecb/pasted-text.txt`

## Live Mac Checkout

Current fingerprints:

- `scripts/run_aether2_tournament.sh`
  - sha256: `c966560afff58408ce1cfbbd2c3ae156f9948df2036094adff0ac1fd1eeea068`
  - Behavior already present locally:
    - exports `PYTHONPATH` from repo root;
    - runs a preflight `import runner.aether2.bridge_harbor`;
    - aborts on repeated fast launch failures;
    - writes `invalid_launch` marker rows when no `row.json` exists.
- `tools/run_aether2_g2.py`
  - sha256: `09570a2d87a3156e0ec24c2e31bb9d252f36faf3987a9185a6a00ca334167443`
  - Behavior already present locally:
    - self-locates the repo root with `Path(__file__).resolve().parents[1]`;
    - inserts the repo root into `sys.path` before `runner.aether2` imports;
    - writes verifier context and row payloads for homolog runs;
    - classifies obvious environment failures separately from pass/fail.

Files that are not present in the live checkout today:

- `tools/run_aether2_g3_official.py`
- `tools/aether2_decision_trace.py`
- `scripts/run_aether2_one_safe.sh`
- `runner/aether2/decision_trace.py`

The missing `runner/aether2/decision_trace.py` is expected because Team R is not
allowed to edit `runner/aether2/`.

## Frozen VM Snapshot

The frozen VM snapshot copy of the official runner entrypoint exists at:

- `tracking/collab/vm_pulls/tracking/collab/aether2_g5_failure_analysis_clean_20260613T121431Z/source_snapshot/tools/run_aether2_g3_official.py`
  - sha256: `37a75c78c7cd296e3c3cc7070a4bc36dacf634b13c2b1c756938430e2b82de31`

The snapshot confirms the launch regression that motivated L1:

- top-level `runner.aether2` imports occur before any repo-root `sys.path`
  bootstrap;
- `row_status` currently folds several failure modes into a generic
  environment/fail path;
- the VM-side script is the authoritative source for the official tournament
  launcher, but it is not present in the Mac checkout.

## Transcript Provenance

The supplied transcript contains the VM-only prototype for observable decision
tracing and the safe-run wrapper around it.

Relevant transcript evidence:

- `pasted-text.txt:272-717`
  - introduces an observable decision-trace bundle as analysis-only;
  - shows the prototype `runner/aether2/decision_trace.py`;
  - shows `tools/aether2_decision_trace.py`;
  - shows `scripts/run_aether2_one_safe.sh`.

That prototype is provenance, not a direct port target. Team R should recreate
the analysis surface outside `runner/aether2/` instead of copying the VM-only
module into the harness package.

## Recreate vs Sync

Sync or preserve:

- launcher integrity semantics already present in `scripts/run_aether2_tournament.sh`;
- g2 self-locating bootstrap pattern in `tools/run_aether2_g2.py`;
- frozen VM launcher behavior as evidence for L1.

Recreate locally as Team R-owned tooling:

- observable decision-trace extraction as `tools/aether2_decision_trace.py`;
- any mount/grader isolation helpers needed for the official-test contract;
- targeted-board manifest validation and runbook material.

Do not recreate:

- any `runner/aether2/*` prototype module;
- any benchmark-specific behavior or task-conditional affordances.

## Provenance Guardrails

- Attempt 1 remains the authoritative scoring population.
- Attempt 2 remains contaminated diagnostic evidence only.
- No score, failure count, or projected flip may merge Attempt 2 into Attempt 1.

