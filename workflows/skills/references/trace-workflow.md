# Trace Workflow

## Per-Step Reconstruction

Capture:

| Field | Question |
|---|---|
| call role | normal, verifier, repair, compaction, closing? |
| input authority | system prompt, task, orientation, dynamic tail |
| unresolved state | requirements, blockers, failed checks, next evidence |
| assistant decision | plan, hypothesis, claim |
| action | tool, arguments, cwd, target |
| observation | exit, output, error, files, process/service delta |
| semantic delta | uncertainty reduced or requirement advanced? |
| next response | did behavior change appropriately? |

## Step Labels

- `evidence_producing`
- `useful_setup`
- `redundant`
- `harmful`
- `premature_completion`
- `no_progress`

## Fake-Progress Pivot

At the first plausible candidate or local success:

1. Summarize the observation.
2. Read the exact next request messages.
3. Identify completion affordances and dynamic state.
4. Inspect visible reasoning without claiming private chain of thought.
5. Determine whether construction and verification share assumptions.
6. Determine whether the harness labeled activity as progress.
7. Compare against a successful control at the same observation.

## Repetition

Normalize action family, target, failure class, artifact/evidence version, hypothesis, and environment state.

Repetition is legitimate only when state changed, a new hypothesis is tested, a bounded retry is justified, or a long job is being truthfully polled.

Successful commands can still be no-progress.

## Service Analysis

Separate:

1. Process started.
2. Bounded survival.
3. Listener ownership.
4. Error-free logs.
5. Client environment.
6. Response/state semantics.
7. Required persistence.
8. Crash, restart, or replacement.

Never infer deep semantics from an open port.

## Environment Analysis

Check OS/arch, shell, runtimes, package managers, network layers, permissions, writable roots, path translation, process namespace, listeners, and grader boundary.

Distinguish missing dependency, wrong version, network failure, wrong path, permission failure, build still running, and resource termination.

## Compaction Analysis

Compare pre/post requirements, constraints, failed checks, disproven assumptions, unverified candidates, provenance, blockers, environment, paths, jobs/services, and next evidence.

Any silent status upgrade is a defect.

