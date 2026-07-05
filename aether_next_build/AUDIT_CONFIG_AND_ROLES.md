# Config Realization + Role Performance Audit (Phase C traces)

## Audit 1: Config Realization — "Does the harness obey the architect?"

Across all 20 Phase C runs (10 tasks × mini + codex):

| config knob | declared? | realized? | evidence |
|---|---|---|---|
| **context_policy.include_sections** | yes (custom) | ✅ yes | all 20 runs show gated sections in context_seen |
| **verification checks** | yes (check_plan) | ✅ yes | 18+ checks executed per model |
| **forbidden_paths** | yes | ✅ yes | integrity guard enforces |
| **tool filtering** (action_schema) | architect selects caps | ❌ **NO** | ALL 20 runs show ALL(10) action kinds in solver prompt |
| **query_memory** tool | n/a | ❌ **DOESN'T EXIST** | 0 query_memory receipts across all runs |
| **solver identity** (persona) | architect extracts task understanding | ❌ **HARDCODED** | all 20 runs show generic "careful software engineer" |
| **advisory_notes** (constraints, failure hypotheses) | extracted by contract | ❌ **NOT WIRED** | advisory=no in all 20 runs |
| **failure feedback** (repair_hint, repeated_actions, files_already_read) | added by Codex | ⚠️ **PARTIAL** | pending_checks appears; repair_hint/repeated/files_read not present in these pre-fix traces |

**Verdict:** the harness is **~40% configurable**. Verification and context sections are real.
Tool filtering, memory access, solver identity, advisory notes, and rich failure feedback
were all declared or extracted but not realized in these runs. **Fixes 2a+2b built this
session close the tool + memory + identity + advisory gaps.** Next runs will show the delta.

## Audit 2: Role Performance — per task

### Summary table

| task | model | reward | architect | solver | verification | key flag |
|---|---|---|---|---|---|---|
| openssl | mini | **1.0** | ✅ 7 obligs, 8 checks | ✅ 12st, 0 rep | ✅ 8 checks, gate ready | CLEAN SOLVE |
| openssl | codex | **1.0** | ✅ 7 obligs, 8 checks | ✅ 1st, auto-submit | ✅ 15 checks, 7 probes | CLEAN SOLVE + AUTO-SUBMIT |
| log-summary | mini | 0 | ✅ 2 obligs, 2 checks | ❌ 28 reconfigures, 1 cmd | ⚠️ schema check caught it | solver parse failures dominated |
| log-summary | codex | 0 | ✅ 2 obligs, 2 checks | ⚠️ 4 repeated cmds | ⚠️ auto-submit accepted (structural pass) | SEMANTIC MISS |
| fix-git | mini | 0 | ⚠️ wrong wf (artifact_extract), bad explicit check | ❌ 86 checks, never submitted | ❌ explicit check always failed | architect + verification failure |
| fix-git | codex | 0 | ✅ reverse_engineer_local | ❌ 57 cmds, never wrote/submitted | ❌ 0 checks (never created files) | solver exploration without convergence |
| filter-js | mini | 0 | ✅ 1 check | ✅ 1st auto-submit | ⚠️ structural pass only | SEMANTIC MISS |
| filter-js | codex | 0 | ❌ bad explicit check (`<html_file>`) | ❌ 14 rep, 8 re-reads, stuck | ❌ 79 failed checks blocking gate | architect poisoned verification |
| gcode | mini | 0 | ✅ artifact_extract, 1 check | ⚠️ 19st but wrote output | ⚠️ auto-submit (structural) | SEMANTIC MISS |
| gcode | codex | 0 | ✅ artifact_extract, 1 check | ❌ 30st, 0 writes, paralyzed | ❌ 0 checks (no output created) | large-file context flooding |
| extract-elf | mini | 0 | ✅ reverse_eng, 2 checks | ⚠️ 10st, auto-submit | ⚠️ structural pass | SEMANTIC MISS |
| extract-elf | codex | 0 | ✅ reverse_eng, 2 checks | ❌ 9 rep, 9 re-reads, no write | ❌ 0 checks | solver stuck inspecting |
| raman | mini | 0 | ✅ artifact_extract, 4 checks | ❌ never created output | ❌ 0 checks | solver couldn't install deps |
| raman | codex | 0 | ⚠️ direct_build (should be artifact_extract) | ❌ 8 rep, never created output | ❌ 0 checks | same: solver + deps |
| sparql | mini | 0 | ✅ explore_first, 1 check | ✅ 2st, auto-submit | ⚠️ structural pass | SEMANTIC MISS |
| sparql | codex | 0 | ⚠️ direct_build (should be explore_first) | ❌ 3 rep, never wrote query | ❌ 0 checks | solver stuck reading TTL |
| constraints | mini | **1.0** | ✅ explore_first, 1 check | ✅ 4st, submitted | ✅ gate ready | CLEAN SOLVE |
| constraints | codex | **1.0** | ✅ direct_build, 6 checks | ✅ 14st, submitted | ✅ 6 checks, gate ready | CLEAN SOLVE |
| train-fasttext | mini | 0 | ✅ 2 checks (exist + size) | ❌ 2 reconfigs, never produced model | ❌ 0 checks | solver couldn't bootstrap deps |
| train-fasttext | codex | 0 | ✅ 2 checks (exist + size) | ❌ 34 cmds, never produced model | ⚠️ 2 probes (both failed) | solver couldn't produce model |

### Cross-cutting findings

**Architect layer:**
- Contract extraction is strong (deliverables 10/10 correct for both models)
- Workflow selection sometimes wrong: codex chose `direct_build` for sparql (should be explore_first) and raman (should be artifact_extract)
- **Explicit checks are the remaining poison** — fix-git mini and filter-js codex were both stuck on broken model-authored explicit checks that always fail. These are now removed in the latest code.
- Advisory notes (constraints, failure_hypotheses, tooling_notes) were extracted by the contract but **dropped** — never reached the solver prompt. Now wired.

**Solver layer:**
- **Mini: decisive but shallow.** 0-1 repeats per task. Writes early, auto-submits fast. Gets wrong answers on hard tasks but doesn't churn. Good control policy, limited capability.
- **Codex: thorough but stuck.** 3-14 repeats per task. Re-reads files 8-9×, re-runs checks manually. Never writes deliverables on 5/10 tasks (filter-js, gcode, extract-elf, raman, sparql). **Root cause: no memory tool → re-derives by re-reading; no "you already know this" signal.**
- Codex's repeat pattern: inspect → fail → inspect same thing → fail → ... (no strategy pivot)
- Mini's weakness: produces output too quickly without verifying correctness (sparql: 2-step auto-submit with wrong query)

**Verification layer:**
- **Real checks executing** — the Phase C pipeline runs 1-86 check_results per task
- **Probes fire correctly** on file-modifying steps (openssl codex: 7 probes)
- **Auto-submit works** — fires on 6/10 mini tasks, 2/10 codex tasks
- **Gate blocks correctly** on failed checks (log-summary mini schema fail, fix-git mini explicit check)
- **Remaining gap:** structural-pass/semantic-miss — 5 mini tasks pass structural checks but fail the grader (file exists, right format, wrong content). This is the honest verification ceiling without task-visible smoke tests.

### What the fixes just built will change (next run prediction)

| fix | expected impact |
|---|---|
| Tool filtering (action_schema → selected caps only) | solver sees only relevant tools; may reduce confusion |
| query_memory tool | codex can ask "what do I already know?" instead of re-reading → should reduce 9-repeat patterns |
| Solver identity wired (task-specific persona) | solver gets success definition + constraints in its identity |
| Advisory notes wired (failure_hypotheses, tooling, stop_conditions) | solver knows "likely failures: deps missing" and "submit when: file exists + size OK" |
| Explicit checks removed (already shipped) | filter-js codex + fix-git mini unblocked |
| CSV schema fix (already shipped) | log-summary mini schema check should work correctly |

### Handoff quality

| handoff | quality | evidence |
|---|---|---|
| Architect → Solver | ⚠️ partial | contract extracted well but identity/advisory/tools not reaching solver in Phase C runs |
| Architect → Verifier | ✅ good | deliverables → obligations → checks → gate pipeline works |
| Verifier → Solver | ⚠️ partial | pending_checks visible but repair_hint/repeated_actions not present in these runs |
| Solver → Verifier | ✅ good | when solver creates artifacts, probe/submit checks execute correctly |

## What to do next

1. **Run Phase C again** with the config-realization fixes (tool filtering, memory, identity, advisory). Measure whether codex's repeat-churn drops and whether mini's semantic quality improves with task-specific guidance.
2. **Use resumable replay** at the 5 failure checkpoints to A/B test enriched context vs model-hint feedback with real execution (not vibes-scoring).
3. **Add task-visible smoke tests** for semantic verification (run filter.py on sample HTML, parse SPARQL syntax, validate ICS structure) — the architect should specify these.
