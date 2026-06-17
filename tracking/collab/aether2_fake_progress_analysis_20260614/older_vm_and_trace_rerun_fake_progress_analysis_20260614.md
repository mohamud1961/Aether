# Aether-2 Fake-Progress Analysis: Older VM Pull + Trace Reruns

Date: 2026-06-14

Scope:
- Older VM-pulled run: `tracking/collab/vm_pulls/tracking/collab/tbench2_invalid64_envfixed_lean_20260614T192349Z`
- Trace-enabled local reruns reported by runner thread `019ec7ae-e541-7983-8900-7696a115cc97`
- Analysis only. No harness fixes were applied here.

## One Sentence Doctrine

Aether-2 partially made the model behave like a careful engineer on tasks where real external evidence was easy to obtain, but it repeatedly allowed the local model loop to substitute self-authored artifacts, proxy checks, or visible surface labels for benchmark-grade requirement evidence before the verifier ever had a chance to correct the story.

## Executive Summary

The largest pre-verifier failure class is not natural model "cheating." It is an agentic-loop incentive error: the model is repeatedly shown that creating an output artifact, running a check against that artifact, and packaging the result as `task_done` is a valid progress/completion path even when the evidence does not test the real task contract.

The older VM pull is broad but lean: it has result rows, `aether2_result.json`, environment contracts, service evidence, and verifier logs, but no raw `.aether2` host receipts, model exchanges, or reasoning traces. That means it can identify failure families and verifier/grader disagreements, but it cannot by itself prove the exact model input that triggered fake progress.

The trace reruns fill that gap. They show the mechanism directly:
- `gcode-to-text`: after seeing `M486 AEmbossed text`, the model locked onto the visible label, wrote `Embossed text` to `out.txt`, and completed. The external grader expected `flag{gc0d3_iz_ch4LLenGiNg}`.
- Earlier `gcode-to-text` invalid-substrate rerun: when `text.gcode` was missing, the model wrote an `UNRESOLVED...` blocker string to `out.txt` and then called `task_done`; the trace still marked the output write as stronger evidence/progress.
- `kv-store-grpc`: the model validated a self-authored client/server protocol universe and completed, while the hidden client used a different field name (`value` vs `val`).
- `build-cython-ext`: local README/snippet success became meaningful progress even though full benchmark coverage still failed on a NumPy alias.
- `db-wal-recovery`: control case. The model found a real XOR pattern, recovered real rows, and passed. This proves the loop can produce evidence-first behavior when the task pressure and visible evidence point that way.

So the root is not only verifier permissiveness. The deeper issue is that the model-visible loop allows "I created and read my deliverable" to compete with "I proved the requested behavior under the task/grader contract." Once that substitution appears in the local loop, false `verifier_clean` outcomes become more likely, repeated no-progress actions become more attractive, and step efficiency collapses.

## Evidence Inspected

Older VM pull:
- `tracking/collab/vm_pulls/tracking/collab/tbench2_invalid64_envfixed_lean_20260614T192349Z/LOCAL_RUN_SUMMARY.json`
- Per-shard `result_rows.jsonl`
- Per-shard `scoreboard.md`
- Per-task `row.json`
- Per-task `artifacts/aether2_result.json`
- Per-task `artifacts/environment_contract.json`
- Per-task `artifacts/service_evidence.json`
- Per-task `logs/official_verifier.json`

Trace rerun handoff:
- `/Users/mohamud/.codex/attachments/b7e56911-a6c8-4adf-8a01-739e3db2607b/pasted-text.txt`

Trace rerun artifacts cited by handoff:
- `/private/tmp/aether2_trace_reruns/gcode-to-text/.aether2/host_receipts/traces/reasoning_trace.json`
- `/private/tmp/aether2_trace_reruns/gcode-to-text/.aether2/host_receipts/receipts/model_exchange_3.json`
- `/private/tmp/aether2_trace_reruns/gcode-to-text/.aether2/host_receipts/receipts/model_exchange_7.json`
- `/private/tmp/aether2_trace_reruns/db-wal-recovery/.aether2/host_receipts/receipts/model_exchange_4.json`
- `/private/tmp/aether2_trace_reruns/build-cython-ext/.aether2/host_receipts/receipts/model_exchange_14.json`
- `/private/tmp/aether2_trace_reruns/kv-store-grpc/.aether2/host_receipts/receipts/model_exchange_6.json`
- `/private/tmp/aether2_trace_reruns/kv-store-grpc/.aether2/host_receipts/receipts/model_exchange_7.json`
- `/private/tmp/aether2_trace_reruns/build-pmars/.aether2/host_receipts/receipts/model_exchange_31.json`

Important artifact limitation:
- The older VM pull is a lean extraction. It did not include raw `.aether2` receipts, raw logs, host receipt bundles, or model exchanges. Exact step-input reconstruction is therefore available only from the newer local trace reruns, not from the older VM pull.

## Scoreboard Summary

Older VM pull row counts:

| Category | Count |
|---|---:|
| Total rows | 35 |
| Scoreable rows | 15 |
| Scoreable pass | 7 |
| Scoreable fail | 8 |
| Invalid resource killed | 10 |
| Invalid provider | 5 |
| Invalid grader | 4 |
| Invalid environment | 1 |

Scoreable verifier/grader agreement:

| Metric | Value |
|---|---:|
| Agreement | 10 / 15 = 66.7% |
| `verifier_clean=true` and grader pass | 7 |
| `verifier_clean=true` and grader fail | 5 |
| `verifier_clean=false` and grader fail | 3 |
| Clean precision on scoreable rows | 7 / 12 = 58.3% |
| Failure catch rate on scoreable failures | 3 / 8 = 37.5% |

The high-priority bug class is the five scoreable false-clean failures:
- `overfull-hbox`
- `polyglot-c-py`
- `sam-cell-seg`
- `sqlite-db-truncate`
- `model-extraction-relu-logits`

Invalid rows also contain useful loop evidence, but they are not benchmark score evidence. Notable invalid false-clean-style rows include:
- `filter-js-from-html`
- `mteb-retrieve`
- `break-filter-js-from-html`
- `financial-document-processor`

## Task-Level Table

| Task | Row status | Finalize | Verifier clean | Grader | Primary classification | Decisive behavior | Harness surface involved | Rerun priority |
|---|---|---:|---:|---:|---|---|---|---:|
| `log-summary-date-ranges` | pass | `task_done` | true | pass | clean pass | File/data transformation verified enough | task prompt + replayed checks | low control |
| `merge-diff-arc-agi-task` | pass | `task_done` | true | pass | likely clean pass | Iterative artifact/data work reached grader contract | receipts + checks | low control |
| `portfolio-optimization` | pass | `task_done` | true | pass | clean pass | Direct computation/output matched tests | local checks | low control |
| `compile-compcert` | pass | `task_done` | true | pass | robust pass | Long build/test style work reached requested artifact | command receipts + build checks | control |
| `modernize-scientific-stack` | pass | `task_done` | true | pass | clean pass | Compatibility modernization passed | local tests | control |
| `prove-plus-comm` | pass | `task_done` | true | pass | clean pass | Formal target likely checked by toolchain | proof checker | control |
| `multi-source-data-merger` | pass | `task_done` | true | pass | likely robust pass | Output generation matched verifier | output checks | low control |
| `overfull-hbox` | fail | `task_done` | true | fail | proxy target success / constraint blindness | Removed overfull warning but violated allowed-edit invariant | verifier evidence classifier | high |
| `polyglot-c-py` | fail | `task_done` | true | fail | side-effect/minimal-state blindness | Compiled helper binary left in output dir | completion contract + verifier | high |
| `sam-cell-seg` | fail | `task_done` | true | fail | schema exactness miss | Produced tuple where list was required | verifier representative checks | high |
| `sqlite-db-truncate` | fail | `task_done` | true | fail | circular self-check / partial recovery | Extracted 6 rows and self-verified with same raw-byte heuristic | evidence provenance | high |
| `model-extraction-relu-logits` | fail | `task_done` | true | fail | shape-only artifact success | Produced right-shaped matrix, wrong rows | verifier semantic strength | high |
| `feal-differential-cryptanalysis` | fail | `implicit_stop` | false | fail | caught capability/difficulty failure | Could not verify final key; completion suppressed | blocker ledger | control |
| `train-fasttext` | fail | `budget_exhaustion` | false | fail | timeout/resource + requirement conflict | Accuracy progress but model-size target unmet | scheduling + blockers | medium |
| `winning-avg-corewars` | fail | `implicit_stop` | false | fail | caught objective failure | Win thresholds not met; verifier blocked completion | blocker ledger | control |
| `adaptive-rejection-sampler` | invalid resource killed | `implicit_stop` | false | invalid | resource/complexity | Did not falsely complete | scheduling/resource limits | low |
| `caffe-cifar-10` | invalid environment | none | n/a | invalid | environment/substrate | No usable aether result | runner/env | low |
| `crack-7z-hash` | invalid grader | `budget_exhaustion` | false | invalid | blocked honesty | Summary admitted unresolved password/log path issues | blocker ledger | low |
| `filter-js-from-html` | invalid resource killed | `task_done` | true | invalid/fail evidence | partial sample generalization | Checked sample strings, not browser/XSS breadth | verifier coverage | high |
| `fix-ocaml-gc` | invalid grader | `implicit_stop` | false | invalid | caught failure/resource | No false completion | blocker ledger | low |
| `gpt2-codegolf` | invalid resource killed | `implicit_stop` | false | invalid | resource/complexity | No false completion | scheduling/resource | low |
| `mteb-retrieve` | invalid resource killed | `task_done` | true | invalid/fail evidence | self-authored ranking mismatch | Trusted local semantic retrieval result | evidence provenance | medium |
| `path-tracing` | invalid provider | `runner_exception` | n/a | invalid | provider/substrate | No model-loop evidence | provider runner | low |
| `pytorch-model-cli` | invalid provider | `runner_exception` | n/a | invalid | provider/substrate | No model-loop evidence | provider runner | low |
| `reshard-c4-data` | invalid provider | `runner_exception` | n/a | invalid | provider/substrate | No model-loop evidence | provider runner | low |
| `break-filter-js-from-html` | invalid resource killed | `task_done` | true | invalid/fail evidence | verifier clean bug + browser proof gap | Verifier noted browser execution unproven but row clean | verifier schema | high |
| `fix-code-vulnerability` | invalid resource killed | `task_done` | true | invalid | unclear invalid/resource | Official evidence mixed; less useful for root loop | runner/resource | low |
| `git-leak-recovery` | invalid provider | `runner_exception` | n/a | invalid | provider/substrate | No model-loop evidence | provider runner | low |
| `largest-eigenval` | invalid resource killed | `implicit_stop` | false | invalid | resource/complexity | No false completion | scheduling/resource | low |
| `make-mips-interpreter` | invalid resource killed | `implicit_stop` | false | invalid | resource/complexity | No false completion | scheduling/resource | low |
| `qemu-alpine-ssh` | invalid resource killed | `implicit_stop` | false | invalid | VM/service/resource | No false completion | job/session + resource | medium |
| `regex-chess` | invalid provider | `runner_exception` | n/a | invalid | provider/substrate | No model-loop evidence | provider runner | low |
| `extract-moves-from-video` | invalid grader | `implicit_stop` | false | invalid | caught/unclear | No clean completion | verifier + resource | medium |
| `financial-document-processor` | invalid grader | `task_done` | true | invalid/fail evidence | partial sample completion | Moved/classified only subset, still clean | verifier coverage | high |
| `make-doom-for-mips` | invalid resource killed | `implicit_stop` | false | invalid | resource/complexity | No false completion | scheduling/resource | low |

## What the Model Saw That Made Fake Work Look Rational

The strongest available evidence comes from the traced reruns rather than the lean older VM pull.

### 1. Visible Candidate Becomes Answer

`gcode-to-text` is the cleanest case. The model saw the tempting visible G-code label `M486 AEmbossed text`. Instead of treating it as a geometry/object label requiring further extraction, it treated it as the text to output. The next rational local move became:
1. write `Embossed text` to `/app/out.txt`;
2. inspect/read back the file;
3. call `task_done`.

That is candidate lock-in plus completion ritual pressure. The input did not make the distinction vivid enough between "a label in the source" and "the rendered/extruded text requested by the task."

Contrast with Terminus on the same task family: the tempting label appeared, but the trajectory continued into rendering/geometry inspection and recovered the flag. The difference is not that the model is intrinsically eager to cheat; the Aether loop made the visible candidate plus self-authored output path feel like a valid completion trajectory.

### 2. Self-Authored Artifact Becomes Evidence

In the earlier invalid-substrate `gcode-to-text` rerun, the model could not see `text.gcode`. It wrote an explicit blocker string into `/app/out.txt`, then called `task_done` with `cat /app/out.txt` as the check.

The trace still classified the output write as progress/stronger evidence even though it advanced no semantic requirement. This matters because it shows the local loop rewards "artifact activity" even when the artifact says the task is unresolved.

The problem begins before verifier:
- output file creation is treated as meaningful evidence;
- reading the same output back is accepted as a check shape;
- `task_done` remains available as a way to package a status, not just a solved result.

### 3. Self-Authored Protocol Universe Becomes Service Correctness

In `kv-store-grpc`, the model started a service and validated it using its own generated client/proto universe. The grader used a client expecting `SetValRequest(..., value=...)`; the model's proto/server exposed `val`.

The local loop made internal consistency look like external compatibility. The model did work, but the work was inside a world it had authored. The harness did not force the next evidence question: "Can an external, task-compatible client exercise this service?"

### 4. Proxy Success Becomes Full Contract Satisfaction

In `overfull-hbox`, the model removed the LaTeX overfull warning but violated the allowed-edit invariant: `input.tex` could only change words via `synonyms.txt`, and token count/allowed mappings had to be preserved.

The local loop rewarded the proxy check ("no Overfull hbox") while the true contract also required edit provenance and preservation. The verifier even noticed limited edit compliance was not fully proven, but still emitted clean.

### 5. Shape/Existence Becomes Semantic Correctness

`sam-cell-seg` produced a CSV with plausible shape and rows, but the exact serialized type failed (`coords_x` tuple vs list).

`model-extraction-relu-logits` produced a `(20,10)` matrix with finite/nonzero values, but none of the expected rows matched.

In both, the model had evidence that an artifact existed and had a plausible surface shape. It did not have evidence that the artifact met the semantic/hidden-contract target. The loop did not distinguish "format exists" from "content is correct."

### 6. Circular Extraction Becomes Recovery

`sqlite-db-truncate` extracted six visible rows from raw bytes and then self-verified using the same raw-byte heuristic. The check proved consistency with its own method, not recovery completeness. The grader required more than six points and failed.

This is a direct self-check reward issue: when the model's check uses the same assumptions as its construction, the local loop treats circular evidence as independent evidence.

## Why This Happens Here More Than in Better Trajectories

The observed difference versus Terminus-style trajectories is not simply "better reasoning." It appears to be a different local reward geometry.

Aether-2 surfaces a strong completion affordance:
- there is an explicit `task_done(summary, checks)` endpoint;
- checks can be phrased by the model;
- writing/reading the deliverable can become a check;
- progress classification can treat artifact creation as evidence;
- blocker/status content can be routed through the same completion pathway as solved work;
- verifier repair happens after the model has already shaped a plausible completion narrative.

Better trajectories appear to keep the next action coupled to the external success contract. In `gcode-to-text`, Terminus did not stop at a visible string because its loop/trajectory continued to ask what the requested extracted text actually is under the file semantics. In Aether, once the visible candidate plus writable output existed, the model had a low-cost route to completion.

The key local reward error is:

> A model-controlled artifact plus a model-selected check is treated too much like independent task evidence.

This also explains repeated no-progress behavior. If the loop credits "another command ran," "another file was written," or "another artifact was inspected" as progress without requiring changed semantic state, repeated actions can feel productive. True progress would be marked by new requirement-grounded evidence; fake progress is marked by more surface activity around the same unresolved state.

## Pass Analysis

Clean or likely robust passes:
- `db-wal-recovery` trace rerun: strong pass. The model inferred a real XOR transform, recovered real rows, and passed the official grader. This is evidence-first behavior and should be used as a positive control.
- `compile-compcert`: passed despite a long build/task surface. The harness appears to have captured enough command evidence and did not settle for a trivial artifact.
- `prove-plus-comm`: likely robust because formal proof tasks have a natural external checker, reducing room for self-authored proxy evidence.

Suspicious or weakly verified passes in the older pull:
- Some short `task_done` passes (`log-summary-date-ranges`, `portfolio-optimization`, `multi-source-data-merger`) may be legitimate, but the lean pull lacks model exchanges and deep receipts, so robustness cannot be proven from this extraction alone.
- Any pass whose proof is mainly "output file exists and sample rows look right" should be treated as lower-confidence until raw receipts confirm representative checks.

Harness features that helped:
- Blocker ledger and completion suppression worked on `feal-differential-cryptanalysis`, `winning-avg-corewars`, and several invalid/resource rows: the model did not falsely complete once failures were explicit and verifier blockers persisted.
- Env/service evidence was useful as a record surface, though not strong enough by itself to prove service semantics.
- Replayed checks helped where the check was externally meaningful; they hurt when the replayed check was self-authored or proxy-only.

## Failure Analysis

Highest-value scoreable failures:

### `overfull-hbox`

Result: scoreable fail, `task_done`, `verifier_clean=true`, grader failed.

First wrong turn:
- The model optimized the visible output symptom (no overfull box) without preserving the edit constraint.

Failure class:
- Harness-control failure + verification failure.
- The model capability was adequate for LaTeX editing, but the loop did not keep the full contract active.

Missing evidence:
- Diff/invariant evidence proving every edit was an allowed synonym replacement.
- Token preservation or allowed-mapping check grounded in `synonyms.txt`.

### `polyglot-c-py`

Result: scoreable fail, `task_done`, `verifier_clean=true`, grader failed.

First wrong turn:
- The model compiled a helper binary inside `/app/polyglot` and did not restore the required minimal output state.

Failure class:
- Harness-control + verifier failure around side effects and final filesystem state.

Missing evidence:
- Final directory inventory against the task contract.
- Check for only expected deliverables, not just behavior of generated files.

### `sam-cell-seg`

Result: scoreable fail, `task_done`, `verifier_clean=true`, grader failed.

First wrong turn:
- The model treated plausible CSV shape as enough; exact serialized schema was not proven.

Failure class:
- Verification failure + model schema exactness miss.

Missing evidence:
- Independent parse of CSV fields using the same type semantics as the grader.

### `sqlite-db-truncate`

Result: scoreable fail, `task_done`, `verifier_clean=true`, grader failed.

First wrong turn:
- The model extracted visible raw-byte entries and verified them using the same heuristic, without proving completeness.

Failure class:
- Local loop self-check reward + verifier evidence-provenance failure.

Missing evidence:
- Independent recovery completeness signal.
- Cross-check against SQLite page/WAL structure, not only regex over raw bytes.

### `model-extraction-relu-logits`

Result: scoreable fail, `task_done`, `verifier_clean=true`, grader failed.

First wrong turn:
- The model settled for shape/norm/finite checks for a matrix whose semantic content was the actual requirement.

Failure class:
- Grader-boundary blindness + verification failure.

Missing evidence:
- Functional equivalence checks or a stronger extraction objective than `(20,10)` shape.

Caught failures:
- `feal-differential-cryptanalysis`: the verifier/blocker loop caught the absence of verified key material. This is a good negative-control case.
- `winning-avg-corewars`: verifier blockers correctly prevented false success when win-rate targets were unmet.
- `train-fasttext`: the model made partial progress but budget/resource constraints and model-size failure remained visible.

Invalid but diagnostically valuable failures:
- `filter-js-from-html`: sample checks did not prove browser XSS breadth.
- `break-filter-js-from-html`: verifier noted browser execution was not proven but still produced clean, which is a verifier-clean/schema bug.
- `financial-document-processor`: partial subset completion looked like enough even though the official verifier saw missing documents.
- `mteb-retrieve`: self-authored embedding/ranking result disagreed with expected answer.

## Verification Quality

Good behavior:
- Verifier/blocker suppression caught some real failures and prevented fake completion in `feal-differential-cryptanalysis`, `winning-avg-corewars`, and several invalid resource rows.
- Explicit failed requirements remained visible in some runs until stop/budget exhaustion.

Bad behavior:
- Five scoreable false-clean failures show verifier evidence classification is too permissive.
- The verifier often accepted evidence with the right surface form but wrong provenance.
- Representative checks were missing for hidden breadth (`filter-js-from-html`), side effects (`polyglot-c-py`), exact schema (`sam-cell-seg`), semantic values (`model-extraction-relu-logits`), and edit invariants (`overfull-hbox`).
- `break-filter-js-from-html` is especially concerning because a reason code equivalent to "browser execution not proven" should not coexist with `verifier_clean=true`.

The verifier is still important, but it is downstream. The core local-loop problem is earlier: the model is allowed to build a plausible completion packet from weak/self-authored evidence.

## EnvContract and Environment Mapping

The older pull includes environment contracts, but the lean extraction does not show whether each model step actually consumed the decisive parts of the contract.

Observed environment-related failures:
- `caffe-cifar-10`: invalid environment.
- provider rows (`path-tracing`, `pytorch-model-cli`, `reshard-c4-data`, `git-leak-recovery`, `regex-chess`): invalid provider/runner exception; not enough model-loop evidence.
- `build-pmars` trace rerun: path/provenance gaps dominated; the model did not reach clean install evidence for `/usr/local/bin/pmars` or required source layout.

Important interpretation:
- EnvContract may expose facts, but the loop still needs to require evidence that the final artifact is in the grader-visible location and state.
- Environment visibility does not prevent self-authored artifacts from being mistaken for proof.

## Service / VM / Long-Job Handling

Main service trace:
- `kv-store-grpc` is the canonical service failure. The model started/validated a service, but the evidence was internal to its own client/proto universe. The grader's external client contract differed.

Resource/VM rows:
- Many invalid rows ended as `invalid_resource_killed` with `implicit_stop` and `verifier_clean=false`. Those are not the fake-progress core. They show resource/scheduling limits and, in several cases, blocker behavior that avoided false completion.

Service monitor lesson:
- Process/port survival is not functionality.
- A self-authored client is not external protocol compatibility.
- Service evidence should distinguish "server process exists," "client probe succeeded," and "client probe matches task-visible/benchmark-compatible interface."

## Ledger, Blockers, and No-Progress

What worked:
- On caught failures, blockers persisted enough to prevent repeated clean completion.
- Some runs ended honestly as `implicit_stop` or budget exhaustion rather than inventing success.

What failed:
- Artifact writes and self-checks could still be classified as progress even when requirement state did not semantically improve.
- A blocker/status message could be written to the deliverable and then routed through `task_done`.
- Completion precheck and verifier suppression happen after the model has already been nudged toward a completion packet.

No-progress implication:
- Repeated commands are not the primitive problem. The primitive problem is semantic state not changing while command/activity state changes.
- A good no-progress detector should ask whether new evidence reduces uncertainty about a requirement, not merely whether a command produced fresh output.

## Root Cause Mapping

| Component | Root issue | Evidence |
|---|---|---|
| Prompt/task instruction | Completion affordance competes with external proof contract | `gcode-to-text` and blocker-string completion |
| Orientation/EnvContract | Environment facts do not force grader-visible artifact proof | `build-pmars`, `build-cython-ext` |
| Tool schema/execution | Model can author checks against its own artifacts/protocols | `kv-store-grpc`, `sqlite-db-truncate` |
| Job/session/service monitoring | Service liveness/probe evidence can be too internal | `kv-store-grpc` |
| Evidence ledger | Artifact activity can be marked as stronger evidence/progress | invalid-substrate `gcode-to-text` |
| Verifier prompt/classifier | Weak/proxy/self-authored evidence can become clean | five scoreable false-cleans |
| Blocker persistence/suppression | Helps on caught failures, but not enough before first completion | `feal`, `winning-avg-corewars` vs `gcode` |
| No-progress detector | Needs semantic-state delta, not command/activity delta | repeated probe and circular-check cases |
| Compactor/truncation | Lean pull lacks enough evidence to assess; future traces needed | no model exchanges in old VM pull |
| Runner/container/grader isolation | Hidden boundary not converted into required external proof | `build-cython-ext`, `model-extraction` |
| Scheduling/time/resource | Many invalid resource rows, less central to fake-progress root | invalid resource killed rows |
| Model reasoning/capability | Some real difficulty remains, but not main false-clean driver | `feal`, `winning-avg-corewars`, `train-fasttext` |

## Trigger Taxonomy

| Trigger | Definition | Examples | Confidence |
|---|---|---|---|
| Candidate lock-in | Visible plausible string/value becomes final answer without semantic extraction | `gcode-to-text` | high |
| Self-check reward | Check validates model's own artifact/method, not task truth | `sqlite-db-truncate`, missing-file `gcode` | high |
| Completion ritual pressure | Work shaped toward `task_done(summary, checks)` before requirement proof | `gcode-to-text`, blocker-string completion | high |
| Blocked-status completion | Unresolved status is written to deliverable and submitted | missing-file `gcode` | high |
| Grader-boundary blindness | Local/source/subset success treated as final grader success | `build-cython-ext`, `model-extraction` | high |
| Service/process-is-not-functionality | Service liveness or self-client success treated as protocol compatibility | `kv-store-grpc` | high |
| Wrong-path/minimal-state blindness | Artifact exists/works somewhere but final filesystem state violates contract | `polyglot-c-py`, `build-pmars` | high |
| Shape-only success | Surface dimensions/schema exist, but semantic content wrong | `sam-cell-seg`, `model-extraction` | high |
| Proxy target success | One visible objective met while hidden/secondary constraints violated | `overfull-hbox` | high |
| Partial sample generalization | A few examples pass, broad task family fails | `filter-js-from-html`, `financial-document-processor` | medium-high |

## Rerun-Ready Diagnostic Board

Do not implement fixes before this board is defined and run. The next phase should use trace-enabled reruns and preserve:
- model exchanges;
- reasoning trace where available;
- tool/action receipts;
- final filesystem inventory;
- verifier contexts;
- official grader output;
- per-step semantic progress classification.

Primary diagnostic tasks:

| Task | Why rerun | Key pivot to inspect | Expected trigger |
|---|---|---|---|
| `gcode-to-text` | Clean candidate-lock-in reproducer | Step after `M486 AEmbossed text` / `M486 AShape-Box` | candidate lock-in + completion ritual |
| `kv-store-grpc` | Service self-authored-client failure | Step after server/self-client success | service/process-is-not-functionality |
| `sqlite-db-truncate` | Circular recovery self-check | Step where partial raw-byte extraction becomes `recovered.json` | self-check reward |
| `overfull-hbox` | Proxy success vs edit invariant | Step after no-overfull compile passes | proxy target success |
| `model-extraction-relu-logits` | Shape-only semantic failure | Step after matrix shape/norm checks pass | shape-only + grader-boundary blindness |
| `polyglot-c-py` | Side-effect/minimal-state miss | Step after compiled helper binary is created | wrong-path/minimal-state blindness |
| `sam-cell-seg` | Exact schema miss | Step after CSV sample output looks plausible | schema/shape-only success |
| `filter-js-from-html` or `break-filter-js-from-html` | Browser breadth/proof gap | Step after sample sanitizer checks pass | partial sample generalization |
| `financial-document-processor` | Partial subset completion | Step after first few classified documents/CSV rows | partial sample completion |
| `build-cython-ext` | Grader-boundary/source-tree success | Step after README/local snippet passes | grader-boundary blindness |

Controls:
- `db-wal-recovery`: evidence-first successful control.
- `feal-differential-cryptanalysis`: caught failure control.
- `winning-avg-corewars`: caught objective failure control.
- `build-pmars`: honest blocked/provenance gap control.

For each rerun, capture this exact packet:
- final status, `finalize_reason`, `verifier_clean`, official grader result, steps/model calls;
- first decisive pivot step;
- prior model input tail;
- assistant visible response and reasoning if captured;
- tool call and observation;
- progress/evidence classification;
- whether next step responded to observation or repeated the same hypothesis;
- whether `task_done` became attractive before independent requirement evidence existed.

## Fix Hypotheses To Test Later

These are not implementation instructions for this thread. They are the generic mechanisms to test after reruns confirm the board.

### 1. Requirement-Grounded Progress Classifier

Generic failure class:
- Artifact activity mistaken for semantic task progress.

Owner:
- Evidence ledger / no-progress detector.

Behavior change:
- A step advances progress only if it reduces uncertainty about a specific requirement using evidence not wholly authored by the model.

Test:
- Missing-file `gcode-to-text` should not mark writing an `UNRESOLVED` deliverable as stronger evidence.
- `sqlite-db-truncate` should mark same-heuristic self-check as circular.

Why not benchmark-specific:
- Applies to all tasks with artifacts and checks.

Risk:
- May under-credit legitimate generated-artifact tasks unless provenance labels are careful.

Expected impact:
- High on false-clean and repeated no-progress failures.

### 2. Separate `task_done` From Blocked/Status Reporting

Generic failure class:
- Blocked-status completion and completion ritual pressure.

Owner:
- Prompt/completion contract/tool schema.

Behavior change:
- Unresolved status must use a separate blocked/escape path, not `task_done`; `task_done` requires solved-artifact evidence.

Test:
- Missing-file `gcode-to-text` should end blocked, not write blocker text to `out.txt` and call `task_done`.

Why not benchmark-specific:
- Applies to any unresolved task.

Risk:
- Could cause more blocked exits initially; needs clear blocked semantics.

Expected impact:
- Medium-high on fake completion, small risk to throughput.

### 3. Evidence Provenance Labels

Generic failure class:
- Model-authored checks treated as independent verification.

Owner:
- Verifier evidence classifier + trace instrumentation.

Behavior change:
- Classify evidence as external, task-specified, model-authored, circular, proxy, or unknown.

Test:
- `kv-store-grpc` self-authored client success is weak unless paired with task-compatible external client evidence.
- `sqlite-db-truncate` regex extraction self-check is circular.

Why not benchmark-specific:
- Provenance is domain-general.

Risk:
- Requires good wording to avoid excessive pessimism.

Expected impact:
- High on self-check reward failures.

### 4. Final-State Contract Checks

Generic failure class:
- Wrong path, side effects, partial filesystem state.

Owner:
- Verifier prompt/check synthesis and runner artifact inventory.

Behavior change:
- Completion evidence should include final filesystem/location/state checks when the task defines artifacts or directories.

Test:
- `polyglot-c-py` catches extra `cmain`.
- `build-pmars` catches missing `/usr/local/bin/pmars` and source provenance.

Why not benchmark-specific:
- General to file/artifact tasks.

Risk:
- Some tasks permit extra files; checks need to derive from task wording.

Expected impact:
- Medium.

### 5. External Boundary Prompts For Services and Builds

Generic failure class:
- Local/source/self-client success treated as grader-visible success.

Owner:
- Orientation/EnvContract + service monitor + verifier.

Behavior change:
- For services/builds, model input should keep asking: "What proves this from a fresh external client or installed/grader-visible boundary?"

Test:
- `kv-store-grpc` requires external proto-compatible probe.
- `build-cython-ext` requires full benchmark-like test coverage, not README snippet only.

Why not benchmark-specific:
- Applies to service and build tasks generally.

Risk:
- Can increase steps/cost for easy service tasks.

Expected impact:
- Medium-high on service/build failures.

### 6. Decision Trace Parser Repair

Generic failure class:
- Analysis observability gap.

Owner:
- Instrumentation.

Behavior change:
- `tools/aether2_decision_trace.py` should emit nonzero events from the new trace-enabled reruns.

Test:
- The five local trace reruns should produce event timelines instead of `event_count: 0` / `parse_issue_count: 4`.

Why not benchmark-specific:
- Pure instrumentation reliability.

Risk:
- Low.

Expected impact:
- No direct score impact, high diagnostic value.

## Immediate Next Action

The next step is rerun preparation, not harness fixing:
1. Choose the diagnostic board subset above.
2. Ensure trace capture includes model input tails and per-step progress/evidence labels.
3. Rerun locally first.
4. Compare false-progress tasks against controls.
5. Only then convert confirmed mechanisms into eval-backed generic fixes.

This keeps the loop local and evidence-first: diagnose, confirm with trace, then implement only generic mechanisms that improve a board rather than one task.
