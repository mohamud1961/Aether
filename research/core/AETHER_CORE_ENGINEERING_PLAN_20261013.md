# Aether Core engineering plan — reconciled 13 October 2026

## Authority and objective

Mohamud requested full engineering execution and a super self-audit after transferring ownership
from usage-limited Claude to Codex GPT-6-Astra. Latest direct instruction: **“Keep no GLM runs; finish
engineering only.”** No subagents or browser. This local plan supersedes its earlier checkpoints;
the Gateway charter is background evidence, not execution authority.

The aspiration is that code never hinders the model. The deliverable is a faithful, capable,
maintainable runtime within a declared envelope. A finite fault suite cannot prove that engineering
will never fail or certify parity with another agent. No model-performance claim follows from these tests.

Envelope: one-shot Linux Docker task runs through Harbor 0.20.0; one OpenAI-compatible provider
interface; truthful partial evidence and clean abort on failure. Universal coordinator restart/resume,
production activation, new skills/subagents, video, and model-policy selection are outside this scope.
A package is self-contained source, with declared Python dependencies and explicit OS prerequisites;
it does not bundle an operating system, Docker daemon or provider service.

## Engineering acceptance and disposition

| Step | Delivered behavior | Inspectable acceptance evidence | Disposition |
|---|---|---|---|
| 1. Truthfulness | Unknown process status and usage remain unknown; every requested reviewer answer validated; every attempt reserved before dispatch, including failed/cancelled/open attempts; exact client arguments and partial responses retained; bounded Retry-After | Installed-wheel truth/HTTP/adapter tests; real SDK request JSON versus call-log reconstruction; absent-usage native Harbor rows | Implemented and validated |
| 2. Advisory verification | State-verifier and losing V2/V3 modes removed; generated checks and the reviewer have no finish veto; requested criteria remain visible; reviewer opinion never becomes verified task correctness | Real-file loop controls with a confidently wrong objection and a confidently wrong “complete”; contract clone checks; independent native good/bad grader | Implemented and validated |
| 3. Linux substrate | PTY stdin/Ctrl-C/flood, named shell state, zombies/death recovery, REPL recovery, worker/clone host identity, compose isolation, mount boundaries, cancellation, descendant/resource cleanup and shared deadlines | Real Docker/Linux fault suite; original whole-wheel gate 134 passed, zero skips; new atomic-rename gate frozen below | Implemented and validated |
| 4. Context | Immutable original structured messages; stable history IDs and paging; long-result copies; configured mirror paths and indirect terminal edits; failed saves are explicit and recall still works; replay/size/prefix diagnostics | Exact 36-row V4 replay, 1459 requests; planted-observation/history/real-file controls; 10/100/500-turn measurements | Engineering contracts implemented; solver effects and cache causality unproven |
| 5. Tools | Runtime argument validation before side effects; useful repair errors; fragmented stream assembly; long-line/binary/large output handling; full log handles survive terminal restart; background command polling without resubmission; optional ordered read batches | Real shell/file loop checks; actual SDK/HTTP controls; PTY/Docker faults; per-call IDs/order and write-fence control | Implemented and validated |
| 6. Standalone package | One canonical aether-core folder with src, pyproject, lock, tests, docs and examples; no research/sibling imports; one owner per runtime boundary; wheel works outside repo | Final installed-wheel suite: 119 passed, 22 explicit platform skips; bytewise source/wheel equality; real native Harbor gate | Implemented and validated |
| 7. Matched GLM comparison | Originally proposed approximately GBP3.80 comparison | No run performed | **Excluded by latest user instruction; not marked done** |

Final code checkpoint: d0192a38bf3fd5c3ed86083f26d2eb532958b6af on
codex/aether-core-takeover. Frozen wheel SHA256:
51ea9a134e2140e9f45320f0ebfa8454e5e8d634ef298043972153bae13e33a9.
The final real Linux/Harbor batch passed: 141 tests, zero skips, plus native reward 1/0 controls. It is recorded in
`audit_output/aether_worldclass_20261013/full_engineering/VM_TERMINAL_CLOSEOUT_PLAN.json`.
It follows reproduced atomic-directory and reviewer-verdict findings; old whole-wheel qualification
is not silently extended to changed bytes. No source changes during that batch.

## Preserved capability and design cost

Named PTY terminals retain full logs, Ctrl-C and persistent state. Existing names also identify
background jobs: start once, continue useful work elsewhere, poll by name. There is no second job
registry. The Python REPL retains sh/read/write/edit/llm; files, images, projected context, CLM,
checkpoint compaction, deadline visibility, and optional the reviewer advice remain available.

The loop owns ordering/lifecycle; provider owns transport; call log owns attempts/usage; environment
owns bounded I/O and process primitives; tools own their substrate; context owns original snapshots
and editable views; Harbor owns framework adaptation. No duplicate world-state/recovery platform added.
Read batches are bounded to four contiguous read_file calls and cannot cross a write or other tool.
They remain off by default. Optional schema/context costs can still affect a model; ignore-ability is
not proof of no harm. Existing model policies/caps/recovery prompts are retained pending evaluation.

## Corrected context evidence

The earlier “55 V4 rows” report mixed old variants. Preserve it as historical evidence, not current
acceptance. The reconciled V4 cohort has 36 rows from source
3fa72b26885e6b766688902b3a3c38e78956833a and 1459 worker requests. Replaying the current compiler keeps
the task present in every request. Projected history sends 95,115,632 characters; CLM sends 62,797,067,
about 34% fewer in this replay. The median of per-row median size drift is 1.97% for CLM and 15.385%
for projected history against recorded CLM requests. One old terminal edit cannot be reconstructed.

Median per-row character-prefix share is about 84–85%; historical recorded cached-input share is
about 68.6%. These are different denominators/units; old absent cache telemetry may already have been
collapsed to zero. They cannot localize a caching fault. Identical-argument re-fetches are candidates,
not proof an observation was needed, lost, or caused task failure. Saved/history coverage in replay is
not proof a past runtime save succeeded. Fresh runtime tests establish current retrieval instead.
At 500 synthetic turns, the final builder call took 5.168 ms (project) / 0.339 ms (CLM) locally;
these fixtures and timings do not establish live latency or solver improvement.

## Failure taxonomy boundary

Concrete engineering failures are repaired/tested: invented verification authority, false success,
unknown accounting, lost history, malformed call side effects, dead tool substrates, wrong-container
routing, deadline overruns and leaked owned resources. The historical synthesis taxonomy remains
an exploratory source of diagnostic cases. It does not prove current incidence of every family.
Premature completion, semantic misunderstanding, failed generalization, policy choice, and the
model's response to fallible advice still require independently graded model runs. We do not build
speculative helpers or declare those model failures eliminated by passing code tests.

## Closeout rule

Reconcile every self-audit finding in docs/core/SELF_AUDIT.md, seal final source/wheel/evidence,
verify all owned processes/containers terminal, deallocate the VM, and deliver one clean package.
No merge, promotion, production change or public release. No live GLM/the reviewer calls. Further live
comparison requires new explicit authority plus its exact source, route, cases, attempts and budget.

## Final ownership checkpoint

All owned tests, native fixture servers, Docker containers and clones are terminal. Required evidence
was retrieved and hash-verified; Azure instance view confirms the run VM is deallocated. Existing
unrelated exited containers were preserved. No active worker agent.

The principal subsequently requested a source/architecture comparison with Prime Agent, Unreal Agent,
Codex, Hermes and OpenCode, then return implementation ownership to the existing Opus task with:
“you have £5 budget, youre in charge\ntest and improve aether as much as possible”.
That is next-phase authority for Opus; GPT-6-Astra's completed engineering gate used no live model calls.
Opus must seal the exact source, route, cases, attempt/retry policy and a spend plan within that
total ceiling before starting model tests. No merge, production activation or public release authority
is implied. The original step 7 remained unexecuted in this engineering phase.
