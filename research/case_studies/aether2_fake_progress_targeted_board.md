# Aether-2 13-Task Diagnostic Board

Date: 2026-06-14

Status: preregistration design only; not executed

The current targeted-board validator allows at most 10 tasks. This 13-task board is therefore staged as:

- Core board: 10 tasks.
- Environment/service extension: 3 tasks.

Both stages share the same baseline version, mechanism variant, model route, trace schema, contamination controls, and promotion decision. Results must also be reported as a combined 13-task view.

## Core Board: 10 Tasks

| # | Task | Failure family | Baseline evidence | Expected behavioral change | Resource | Timeout |
|---:|---|---|---|---|---|---:|
| 1 | `gcode-to-text` | candidate lock-in / completion ritual | traced local rerun, false clean | visible label remains a candidate until structural evidence distinguishes requested output | light | 900s |
| 2 | `kv-store-grpc` | self-authored client/protocol universe | traced local rerun, false clean | self-client remains weak; fresh compatible client evidence is sought | service | 1200s |
| 3 | `sqlite-db-truncate` | circular self-check / incomplete recovery | older scoreable false clean | same-method recovery check is labeled circular; completeness remains unresolved | light | 1200s |
| 4 | `overfull-hbox` | proxy success / constraint violation | older scoreable false clean | symptom and allowed-edit invariant remain separate requirements | light | 900s |
| 5 | `model-extraction-relu-logits` | shape-only semantic success | older scoreable false clean | matrix shape is weak evidence; functional/semantic evidence remains required | light | 1200s |
| 6 | `polyglot-c-py` | final-state side effect | older scoreable false clean | final directory inventory catches extra helper binary | light | 900s |
| 7 | `sam-cell-seg` | exact schema/type miss | older scoreable false clean | serialized type/contract is independently parsed | light | 1200s |
| 8 | `break-filter-js-from-html` | partial sample/browser proof gap | invalid row with clean contradiction | unproven browser execution cannot be clean | light | 1200s |
| 9 | `financial-document-processor` | partial subset completion | invalid grader, clean verifier | full input-set coverage remains visible; subset work is partial | light | 1200s |
| 10 | `build-cython-ext` | source-tree/grader-boundary blindness | traced local rerun | fresh-process/full-suite install evidence replaces README/subset proof | heavy build | 1800s |

## Environment and Runtime Extension: 3 Added Tasks

| # | Task | Failure family | Why added | Expected behavioral change | Resource | Timeout |
|---:|---|---|---|---|---|---:|
| 11 | `build-pmars` | EnvMap path/install/provenance | Explicit environment-map row: task path, source location, writable install target, and grader-visible binary location must remain distinct | model uses EnvContract path mapping and proves `/usr/local/bin/pmars` from a fresh process; wrong nested source success remains partial | heavy build | 1800s |
| 12 | `qemu-alpine-ssh` | VM/service/session/resource truth | Explicit service/VM row: process, VM boot, SSH readiness, session persistence, client environment, and resource termination must be attributable | uses job/session appropriately; monitor distinguishes booting, ready, crashed, replaced, timed out, and resource-killed | QEMU/service | 2400s |
| 13 | `compile-compcert` | long-build monitoring positive control | Positive control for long-running build, exit-code/log truth, polling, and scheduling | remains a pass; long log growth is not mistaken for completion and serialization does not regress it | heavy build | 3600s |

## Shared Sentinels

- `db-wal-recovery`: evidence-first semantic pass.
- `prove-plus-comm`: formal external-check pass.
- `log-summary-date-ranges`: simple file/data pass.
- `feal-differential-cryptanalysis`: verifier-caught failure.
- `winning-avg-corewars`: objective threshold caught failure.
- BFCL/tool-schema sentinel.
- missing-input blocked-status custom homolog.
- no-progress repeated-action custom homolog.

## Per-Task Required Outputs

- official result row and grader output;
- `reasoning_trace.json`;
- all `model_exchange_*.json`;
- tool/action receipts;
- orientation and EnvContract;
- final filesystem manifest;
- service/job/session evidence where applicable;
- verifier contexts and evidence-strength decisions;
- first decisive pivot event;
- semantic progress labels;
- token/model/tool/step counts;
- invalid/timeout/resource attribution.

## Board Metrics

- grader pass count;
- false-clean count;
- verifier/grader agreement;
- premature completion count;
- self-authored evidence completion count;
- average and median steps/model calls/tool calls;
- no-progress steps before and after intervention;
- blocked-status truthfulness;
- invalid and resource-killed count;
- service evidence completeness;
- EnvContract decisive unknown count;
- trace parse completeness.

## Contamination Controls

- Fresh task workspace and container per attempt.
- Immutable output directory per task/attempt.
- No reuse of model-generated solutions.
- No task names or expected answers in harness prompts.
- No hidden grader/test access.
- Public rows used only for audit/calibration.
- Mechanism development uses abstracted custom homologs with changed names, values, layouts, and distractors.

## Execution Sequence

1. Freeze current baseline with trace instrumentation repaired.
2. Run the 10-task core board.
3. Run the 3-task extension serially according to resource class.
4. Run shared controls.
5. Test one mechanism at a time.
6. Test required A/B interaction combinations.
7. Run the combined promoted candidate across all 13 tasks plus controls.
8. Promote only from official grader rows, not verifier or trace narratives.

