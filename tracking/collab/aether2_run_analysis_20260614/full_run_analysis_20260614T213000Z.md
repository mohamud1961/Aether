# Aether-2 latest full run analysis

Run analyzed: `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z`

Primary evidence:

- Scoreboard inputs: `clean22_summary.csv`, `run_status_counts.json`, `scoreable_rows.json`, `pass_tasks.txt`, `fail_tasks.txt`.
- Full scoreable task directories: `extracted_clean22/shard_*/*/<task>/`.
- Per-task artifacts: `row.json`, `artifacts/aether2_result.json`, `artifacts/environment_contract.json`, `artifacts/grader_isolation_contract.json`, `artifacts/service_evidence.json`, `.aether2/raw_logs/*`, `logs/official_verifier.json`.
- Source prompt/wrapper inspected in the live checkout: `runner/aether2/prompts.py`, `runner/aether2/orientation.py`, `runner/aether2/loop.py`, `runner/aether2/verify.py`, `tools/run_aether2_g3_official.py`.

## Executive summary

Aether-2 made GPT-5.4-mini behave more like a careful terminal engineer than a bare task solver: nearly every scoreable task began with workspace inspection, most tasks made small observable moves, and the model usually called `task_done` with check commands rather than a naked claim. The upgraded executor prompt and official runner wrapper were present in source and align with the observed behavior: inspect first, verify real behavior, leave services running, and avoid claiming success from file existence alone.

The run still does not preserve the careful-engineer contract end to end. On the 22 scoreable tasks, Aether-2 passed 7 and failed 15. More important than the 31.8% pass rate: the verifier was clean on 8 grader failures. These are false-positive completion gates where the harness accepted local proxy evidence even though the official grader later rejected the task. The highest-value failure class is verifier/grader disagreement on hidden-reference, semantic, package-isolation, and service-protocol tasks.

The broader full run also had substantial run-hygiene loss: aggregate counts show 52 `invalid_environment`, 7 `invalid_grader`, 4 `invalid_resource_killed`, and 1 `invalid_provider`. The latest pull only contains full directories for the 22 scoreable rows, so per-invalid task names and traces were not available in this artifact set.

Overall answer to the mission question: Aether-2 did make the model more careful locally, but the harness did not consistently keep it benchmark-careful. It let the model stop after plausible local evidence, especially when correctness required hidden/reference comparison, protocol compatibility, or package/install visibility to the grader.

## Scoreboard summary

From `run_status_counts.json`:

| Status | Count |
|---|---:|
| pass | 7 |
| fail | 15 |
| invalid_environment | 52 |
| invalid_grader | 7 |
| invalid_resource_killed | 4 |
| invalid_provider | 1 |

Scoreable denominator: 22 tasks. Scoreable pass rate: 7/22 = 31.8%.

Verifier/grader agreement on scoreable rows:

| Category | Count |
|---|---:|
| verifier clean and grader passed | 6 |
| verifier not clean and grader failed | 7 |
| verifier clean but grader failed | 8 |
| verifier not clean but grader passed | 1 |

The single "verifier not clean but grader passed" row was `constraints-scheduling`: the verifier correctly wanted stronger explicit evidence for some secondary constraints, but the official grader accepted the final artifact.

## Task-level table

| Task | Grader | Verifier clean | Finalize | Model calls / steps | Wall sec | Step-quality summary | Root cause |
|---|---:|---:|---|---:|---:|---|---|
| build-pmars | fail | true | task_done | 19 / 17 | 153.58 | Mostly evidence-producing build work, but final checks were proxy checks and missed official source placement and functional behavior. | verifier false positive; task-contract extraction; hidden semantic check |
| chess-best-move | fail | false | task_done | 18 / 13 | 165.22 | Inspected image, attempted OCR/CV/tooling, then guessed `e2e4`; verifier caught insufficient image-state proof. | model capability; verifier caught |
| cobol-modernization | pass | true | task_done | 10 / 9 | 48.17 | Strong inspection of COBOL and data, implemented Python mirror, compared COBOL vs Python outputs. | robust pass |
| constraints-scheduling | pass | false | task_done | 11 / 6 | 77.06 | Efficient parse and artifact write; verifier wanted explicit evidence for all constraints and input integrity. | suspicious pass; verifier conservative |
| db-wal-recovery | fail | true | task_done | 10 / 9 | 140.31 | Inspected DB/WAL and wrote plausible recovered JSON; failed to decrypt/apply WAL updates. | verifier false positive; hidden/reference recovery |
| dna-assembly | fail | false | task_done | 19 / 14 | 93.82 | Good sequence inspection, weak primer design; attempted primer3 only late and failed install. | model capability and dependency handling; verifier caught |
| extract-elf | fail | false | task_done | 13 / 8 | 290.00 | Real ELF inspection and JS artifact, but extraction strategy covered only 18.5% of expected values. | task difficulty; hidden reference; verifier caught uncertainty |
| kv-store-grpc | fail | true | task_done | 15 / 14 | 73.69 | Created proto/server and local client probe, but protocol fields did not match official expectations; job survival false. | verifier false positive; service/protocol contract |
| nginx-request-logging | pass | true | task_done | 14 / 13 | 77.22 | Installed nginx, configured service, probed content/log/rate limiting, official passed. | service pass, but with guard friction |
| bn-fit-modify | fail | true | task_done | 25 / 24 | 166.16 | Many diagnostics and generated artifacts, but learned/intervened DAG and sample distribution were wrong. | verifier false positive; statistical semantic correctness |
| build-cython-ext | fail | true | task_done | 20 / 19 | 143.69 | Real build/debug attempts, but installed package was not visible to official grader. | verifier false positive; package/environment boundary |
| cancel-async-tasks | pass | true | task_done | 8 / 6 | 47.66 | Implemented async scheduler, had two harmful KeyboardInterrupt checks, but artifact passed. | robust enough pass |
| circuit-fibsqrt | fail | false | task_done | 13 / 8 | 63.00 | Inspected simulator and generated netlist, but own example checks failed; still task_done. | model capability; premature completion caught |
| code-from-image | fail | false | task_done | 22 / 17 | 141.60 | Multiple OCR/image attempts, output violated visible prefix hint; still task_done. | model capability; premature completion caught |
| configure-git-webserver | pass | true | task_done | 13 / 12 | 59.88 | End-to-end clone, push, HTTP fetch; service left running. | robust service pass |
| count-dataset-tokens | pass | true | task_done | 12 / 11 | 122.19 | Inspected workspace, loaded dataset/tokenizer, recomputed and verified answer. | robust pass, network/cache dependent |
| custom-memory-heap-crash | fail | false | implicit_stop | 26 / 23 | 2220.05 | Good initial debugging, many failed fixes; blockers persisted and suppressed repeated completion. | genuine difficulty; timeout/resource scheduling |
| distribution-search | pass | true | task_done | 12 / 11 | 79.11 | Derived distribution with numeric solver and verified KLs. | robust pass |
| dna-insert | fail | true | task_done | 15 / 10 | 76.19 | Created primers and local checks, but annealed region length failed official grader. | verifier false positive; domain-specific constraint extraction |
| gcode-to-text | fail | true | task_done | 5 / 4 | 33.47 | Very premature: wrote "Embossed text" after shallow string scan; official expected flag. | verifier false positive; weak evidence accepted |
| large-scale-text-editing | fail | false | implicit_stop | 16 / 13 | 548.85 | Repeated Vim macro attempts, timeout, final artifact still wrong; blockers suppressed completion. | task difficulty; good blocker behavior |
| llm-inference-batching-scheduler | fail | false | task_done | 14 / 9 | 69.74 | Read cost model and wrote plans; own check failed to import `cost_model`; grader invalid/error due relative import. | grader/import artifact issue plus unverified thresholds |

## Verifier/grader disagreement table

High priority disagreements are rows where `verifier_clean=True` but the official grader failed.

| Task | Verifier result | Grader failure evidence | Likely harness cause |
|---|---|---|---|
| build-pmars | Clean, all 6 requirements satisfied with mixed evidence | `test_pmars_works`, `test_debian_source_used`, `test_built_from_source`; source not extracted to `/app`, warrior behavior wrong | Verifier accepted local binary smoke and source-hash checks without canonical artifact/path checks |
| db-wal-recovery | Clean, all 3 requirements satisfied | Apple value from WAL not applied; WAL update for id=1 not applied | Verifier accepted JSON shape/count/readability without requiring WAL-derived ground-truth recovery evidence |
| kv-store-grpc | Clean, all 5 requirements satisfied | "Not a real gRPC server: Protocol message SetValRequest has no `value` field"; server functionality failed | Verifier accepted local client/proto self-consistency, not benchmark protocol compatibility |
| bn-fit-modify | Clean, all 6 requirements satisfied | Learned DAG, intervened data structure, sampled data failed | Verifier over-trusted artifact shape and row counts for statistical/causal correctness |
| build-cython-ext | Clean, all 6 requirements satisfied | `pyknotid` not installed; `ModuleNotFoundError` in grader | Verifier did not require grader-environment import/install visibility |
| dna-insert | Clean after 3 rounds | Forward primer annealed part length 86 > 45 | Verifier accepted local primer checks that did not encode all official constraints |
| gcode-to-text | Clean, all 2 requirements weakly satisfied | Expected flag `flag{gc0d3_iz_ch4LLenGiNg}`, got `Embossed text` | Verifier accepted readback of guessed output, not evidence from G-code geometry/semantics |
| llm-inference-batching-scheduler | Not clean, grader errored with rc=2 | Relative import error in official test collection | This is not a false clean, but it is a grader/run-isolation problem: official grader failed before scoring task semantics |

## What was input to the model

The source inspection shows the upgraded executor prompt was present in `runner/aether2/prompts.py`. It tells the model to inspect first, plan briefly, act in small steps, verify the externally observable behavior, treat tool observations as truth, inspect raw logs if tails are truncated, respect active blockers, and use strong service evidence beyond a port/process check.

The official runner wrapper in `tools/run_aether2_g3_official.py` also contains the expected guidance:

- Current working directory is `/app`, the writable task workspace.
- The official verifier runs later in the same live container.
- Do not read hidden tests or `solution.sh`.
- Before `task_done`, run concrete checks.
- If the task requires a server, VM, or background process, leave it running.
- The appended `G3_COMPLETION_CONTRACT` adds benchmark-style warnings for services, artifacts, performance, QEMU/telnet/VNC, media, long jobs, and exact evidence commands.

The pulled rows do not include full raw model input transcripts. That is an evidence gap. I can confirm prompt/wrapper source and infer usage from row behavior, but I cannot prove the exact serialized model messages for this run from the pulled artifacts alone.

EnvContract quality:

- Row-level `environment_contract` captured container workspace root, artifact/workspace path mapping, network enabled, Python command, shell, package-manager policy, writable/read-only roots, container process model, official `/tests` and runner `/app/tests` paths, and grader isolation manifest refs.
- The model-facing orientation code also builds a richer `env_contract` with cwd translation, shell command form, Python path/version, package managers, permissions, outbound HTTPS, process sample, listeners, and runtime boundary.
- Missing or weak: OS/arch are not explicit in the row contract, R/compiler/toolchain versions are not systematically exposed before planning, package install scope is marked unknown in orientation, lifecycle owner and job persistence model are unknown, and grader-only/model-visible test paths are unknown in the model-facing orientation even though row-level grader isolation later records them.

This contract is enough to reduce vague environment guessing, but not enough to make it unacceptable. Several failures involved environment/package visibility (`build-cython-ext`), dependency install failures (`dna-assembly`, `code-from-image`), and path-boundary confusion.

## Model decision quality

Observed strengths:

- Most tasks began with inspection. Examples: `cobol-modernization` read COBOL and data files before writing; `count-dataset-tokens` enumerated workspace and possible data files before loading external dataset; `configure-git-webserver` inspected files, listeners, git, Python, and OS before setup.
- The model often selected plausible first strategies: direct semantic equivalence for COBOL, end-to-end push/fetch for git webserver, numeric solving for distribution search, local client probe for gRPC.
- The verifier did influence behavior on several tasks. `dna-assembly`, `extract-elf`, `circuit-fibsqrt`, and `code-from-image` received non-clean verifier reports with concrete reasons. `custom-memory-heap-crash` and `large-scale-text-editing` show blocker persistence and suppressed repeated verifier calls.

Observed weaknesses:

- The model still calls `task_done` after known failed checks. `circuit-fibsqrt` included checks where `./sim 208` and `./sim 20000` were wrong; `code-from-image` wrote an output that failed the visible `bee26a` prefix; `llm-inference-batching-scheduler` had a `ModuleNotFoundError` in its own threshold check.
- It often treats artifact shape as completion. `gcode-to-text` wrote "Embossed text" after shallow inspection. `bn-fit-modify` produced CSVs with right names and dimensions but wrong causal/statistical content.
- Strategy reset is present but not strong enough. `custom-memory-heap-crash` spent 2220 seconds and 26 model calls with many failed memory-management variants. `large-scale-text-editing` repeatedly tried Vim macro formulations and hit a 120s timeout before blocker suppression stopped it.

## Pass analysis

Clean passes:

1. `cobol-modernization`: robust. The model inspected COBOL source, inputs, and data files, implemented `/app/program.py`, compiled/reran the COBOL program, ran the Python implementation on copied data, and compared outputs. Harness feature that helped: inspect-first prompt and check replay.
2. `configure-git-webserver`: robust. The model built a bare git repo, configured `post-receive`, started a Python webserver, then cloned, committed, pushed, and fetched `hello.html` via HTTP. Harness feature that helped: service/job tools and service survival evidence.
3. `distribution-search`: robust. The model derived a distribution family, solved KL constraints, generated `dist.npy`, and recomputed forward/backward KL. Harness feature that helped: model-owned strategy and real numeric verification.

Suspicious or weak passes:

1. `constraints-scheduling`: grader passed, verifier not clean. The artifact was accepted, but the verifier correctly noted missing explicit evidence for input integrity, Bob/Carol constraints, and tie-breaker reasoning. This is a pass with incomplete local evidence discipline.
2. `nginx-request-logging`: official passed, but verifier evidence was mostly mixed/weak because service survival was not deeply semantic. The model did perform live curl/log/rate-limit checks. Also, the path-boundary guard blocked direct `/etc`/`/var` operations until the model wrapped them in `sh -lc`, which is harness friction.
3. `cancel-async-tasks`: official passed, but the model ran two harmful `KeyboardInterrupt` checks that exited 130 and then completed based on structural checks. The final implementation was good enough, but the local evidence did not fully exercise the exception/cancellation semantics after the failed tests.

## Highest-value failure deep dives

### 1. gcode-to-text

First decisive wrong turn: after reading only the G-code head and searching for strings, the model wrote `/app/out.txt` as `Embossed text`. It did not reconstruct toolpath geometry or produce evidence that the embossed text was decoded from the file.

Verifier behavior: false positive. It marked both requirements satisfied with weak evidence because the file existed and matched the model's own asserted string. Official grader expected `flag{gc0d3_iz_ch4LLenGiNg}`.

Root cause: verifier evidence classifier and prompt allowed self-confirming readback evidence for an extraction task. Generic fix: require provenance from source data for decode/extract tasks, not just output-file readback.

### 2. kv-store-grpc

First decisive wrong turn: the model invented a proto with `SetValRequest` fields incompatible with the official client expectations. It then verified with its own generated client, so local self-consistency passed while benchmark protocol compatibility failed.

Service handling: the model used `start_job`, but two earlier jobs exited 143 and final `job_survival` was false. The verifier still marked clean. Official grader failed protocol handshake and functionality.

Root cause: verifier and service monitor did not distinguish "server responds to self-authored client" from "server implements externally required protocol." Generic fix: for protocol/service tasks, require a fresh black-box client probe from the visible contract or require schema/endpoint compatibility evidence independent of generated client code.

### 3. build-cython-ext

First decisive wrong turn: the model built and smoke-tested `pyknotid` in the working environment, but the package was not importable in the official grader environment. Official tests reported `pyknotid is not installed` and `ModuleNotFoundError`.

Harness issue: the environment contract tells the model the grader is isolated, but local completion checks did not validate install visibility in grader-equivalent conditions. The verifier accepted imports run in the agent context.

Root cause: grader-boundary evidence gap. Generic fix: add a grader-environment dry-run/import probe contract for package-install tasks, using sanitized env and absolute Python/toolchain paths without exposing hidden tests.

### 4. build-pmars

First decisive wrong turn: the model built a working-ish binary in `/app/src/pmars-0.9.4` and installed `/usr/local/bin/pmars`, but official tests expected Debian source extracted to `/app` and correct warrior stepping behavior. Official failures included "No pmars source directory found in `/app`" and "rave.red: Expected stepping, got 0 addresses."

Root cause: task-contract/path canonicalization plus weak functional smoke. The model verified binary execution and ldd, not official artifact location and representative warrior semantics.

Generic fix: completion verifier should detect "build from source" and "artifact location" requirements and require canonical workspace placement plus representative behavioral checks, not just binary availability.

### 5. db-wal-recovery

First decisive wrong turn: the model created 11 sorted JSON records from the visible DB/base data but did not decrypt/apply WAL updates. Official tests said Apple should have value 150 and WAL update for id=1 was not applied.

Verifier behavior: false positive. It accepted JSON parse/count/sort and base SQLite readability. It did not require evidence that data came from WAL bytes.

Root cause: hidden/reference recovery task needs provenance checks. Generic fix: for recovery tasks, require evidence that the damaged/auxiliary artifact was parsed and affected final values, such as before/after records, WAL frame/decryption diagnostics, or invariant deltas from source artifact.

## Service/VM/long-job failures

Service tasks inspected: `configure-git-webserver`, `nginx-request-logging`, `kv-store-grpc`, and service-like `llm-inference-batching-scheduler`.

- `configure-git-webserver`: good. Used `start_job` for `python3 /app/webserver.py`; ran an end-to-end client session with clone, commit, push, and curl. `job_survival=True`, `session_survival=True`, official passed.
- `nginx-request-logging`: good final result, but used a shell session awkwardly after direct `/etc` commands were blocked. It validated response bodies, log output, and rate limiting. Official passed.
- `kv-store-grpc`: failed. Used `start_job`, but earlier job checks exited 143 and final `job_survival=False`. Verifier did not treat that as disqualifying because task evidence focused on local gRPC client checks. Official failed protocol compatibility.
- `llm-inference-batching-scheduler`: not a persistent service, but an execution-boundary failure. The model's own cost-model check failed to import, and the official grader itself errored during collection due attempted relative import with no known parent package. This row is best classified as `runner/grader isolation` or `invalid_grader` candidate rather than pure capability fail.

The service monitor is useful but bounded. It records container inspect, listener/process snapshots, job/session survival, and verifier stdout/stderr tails. It does not invent semantic probes. The main missing harness behavior is forcing service tasks to prove external client semantics from the right environment and treating failed job survival as a stronger blocker.

## Timeout/resource failures

Scoreable task timeouts/resource-like outcomes:

- `custom-memory-heap-crash`: 2220.05 seconds, `implicit_stop`, 26 model calls, 23 steps, 5 recoveries, 2 completion precheck rejections, 2 suppressed verifier calls. This was a long-running model/task difficulty failure, not marked `timed_out` in row JSON, but it consumed extreme wall time and ended through harness stop/blocker behavior.
- `large-scale-text-editing`: 548.85 seconds, `implicit_stop`, including a 120s Vim timeout. Blockers suppressed repeated completion without new evidence. Good harness behavior after repeated no-progress, but the model spent too long before convergence.

Aggregate non-scoreable resource status:

- `invalid_resource_killed`: 4 from `run_status_counts.json`.
- Per-task names and traces for those resource-killed rows were not included in the latest pull.

## Ledger, blockers, no-progress, and compaction

Evidence ledger/blocker behavior worked on some hard failures:

- `custom-memory-heap-crash`: active blockers persisted, repeated `task_done` was suppressed, and final row summary explicitly said new relevant evidence was required.
- `large-scale-text-editing`: same suppression behavior, with blockers tied to macro definitions, byte-for-byte transformation, and allowed-command constraints.
- `dna-assembly`, `extract-elf`, `circuit-fibsqrt`, and `code-from-image`: verifier produced reason codes and non-clean rows after repair rounds.

Weaknesses:

- Completion precheck did not prevent `task_done` after visibly failed checks on several tasks.
- Suppression appears only after verifier has concrete blockers. It does not prevent the first premature `task_done` on weak self-confirming evidence.
- No scoreable row used compaction (`compaction_count=0`), so this run does not test whether compaction preserves decisive facts.

## Cross-harness findings by component

### Prompt and task instruction

What worked: the prompt and wrapper are strong and generic. The model generally inspected first and included checks.

Gap: task_done wording is not enforced enough. The model still calls `task_done` after checks fail or after checks only validate self-created outputs. Prompt alone will not close this.

### Orientation and EnvContract

What worked: workspace roots, Python, shell, network, permissions, official/grader refs, and path mapping were captured in row artifacts.

Gap: model-facing orientation still has unknown grader boundary fields, unknown package install scope, unknown job persistence model, and no explicit OS/arch/R/compiler map. This matters for package/build tasks and install visibility.

### Tool schema and execution

What worked: foreground command envelopes, raw logs, start_job, sessions, and write_file receipts provided good traceability.

Gap: workspace-root boundary guard false-positives block legitimate system task paths (`/etc`, `/srv`, `/tmp`) and are bypassed by `sh -lc`. This wastes steps and trains shell-shape workarounds rather than principled safety.

### Job/session/service monitoring

What worked: service survival and container inspection are recorded; successful service tasks benefited.

Gap: service_monitoring is not semantic. It should not be expected to infer gRPC protocol correctness, but the verifier should treat failed job survival and self-authored client probes as weak until a contract-compatible black-box check exists.

### Evidence ledger and blocker persistence

What worked: persistent blockers stopped repeated completion in two long failures.

Gap: blockers are reactive. The first false-positive `task_done` still gets through for many tasks unless the verifier knows how to reject the evidence class.

### Verifier prompt/classifier

What worked: caught unsupported image, primer, ELF, circuit, code-image, heap, and macro claims.

Gap: eight false-clean failures. The verifier is too credulous when evidence is local, structural, or self-authored. It needs generic evidence policies for hidden-reference, extraction, protocol, package-install, statistical, and source-recovery tasks.

### Runner/container/grader isolation

What worked: rows include grader isolation contracts and sanitized grader env manifests.

Gap: `llm-inference-batching-scheduler` errored during test collection. `build-cython-ext` exposed a mismatch between agent-visible install and grader-visible import. Grader-equivalent probes should be available without hidden test exposure.

### Scheduling/time/resource limits

What worked: resource-killed rows are counted separately from scoreable failures; blocker suppression ends repeated no-progress in some rows.

Gap: no per-invalid traces in latest pull. Long hard rows can consume hundreds to thousands of seconds before implicit stop.

## Prioritized generic fix plan

1. Evidence-class gates before clean verifier status.
   - Failure class: self-confirming local evidence and proxy checks.
   - Owner: verifier evidence classifier and completion precheck.
   - Behavior change: classify extraction/recovery/protocol/statistical/package-install tasks as requiring provenance or black-box semantic evidence, not output readback.
   - New test: synthetic tasks where a guessed output file exists but source-derived proof is absent; verifier must reject.
   - Non-leakage: evidence policy is based on task verbs and artifact relationships, not task names.
   - Risk: may increase false negatives on genuinely solved tasks with sparse visible checks.
   - Likely score impact: +2 to +5 on 22-task scoreable slice by preventing false clean and driving repair.

2. Grader-equivalent visible smoke probes.
   - Failure class: package/import/install and hidden grader environment mismatch.
   - Owner: runner/grader isolation plus verifier.
   - Behavior change: expose a generic `grader_smoke` or sanitized-env command mode that runs visible import/CLI checks under grader-like env without hidden tests.
   - New test: package installed in agent venv but not importable in sanitized grader env must be caught before task_done.
   - Non-leakage: does not expose hidden tests, only environment boundary.
   - Risk: extra runtime and possible confusion if used for all tasks.
   - Likely score impact: +1 to +3, especially build/install tasks.

3. Contract-compatible service/protocol checks.
   - Failure class: services verified only by process/port/self-authored client.
   - Owner: service monitor, verifier prompt/classifier, task_done precheck.
   - Behavior change: require fresh client probes from a separate process and, for protocol/schema tasks, require compatibility with visible proto/API/schema names rather than only generated local clients. Treat `job_survival=False` as a blocker for service tasks.
   - New test: fake gRPC server passes self-client but fails contract client; verifier must reject.
   - Non-leakage: probes derive from visible contract, not hidden expected values.
   - Risk: may be hard to infer protocol contract when visible files are absent.
   - Likely score impact: +1 to +2 in this slice, higher on service-heavy boards.

4. Path-boundary guard repair.
   - Failure class: legitimate system-task operations blocked unless wrapped in `sh -lc`.
   - Owner: tool schema/execution guard.
   - Behavior change: distinguish task-allowed absolute paths from hidden-test paths; allow system configuration paths when task environment and permissions permit, while still blocking hidden grader/test files.
   - New test: nginx-style task can write `/etc/nginx/...` directly but cannot read `/tests` or `solution.sh`.
   - Non-leakage: path policy is generic by visibility/phase, not benchmark task name.
   - Risk: broader path access could weaken hidden-test isolation if implemented loosely.
   - Likely score impact: +1 to +3 via lower step waste and fewer guard-induced failures.

5. Failed-check completion veto with repair routing.
   - Failure class: `task_done` after failed or unrepresentative checks.
   - Owner: completion precheck and evidence ledger.
   - Behavior change: if any task_done-listed check exited nonzero or asserts a known expected condition failed, reject task_done before verifier unless the model explicitly marks the task unresolved and stop conditions are met.
   - New test: task_done with checks containing `assert False`, wrong expected output, or import error must trigger repair, not finalization.
   - Non-leakage: uses exit codes and model-declared checks only.
   - Risk: tasks with intentionally failing diagnostic checks need an escape path.
   - Likely score impact: +2 to +4 by preventing premature finals.

6. Run artifact completeness for invalid/resource rows.
   - Failure class: aggregate invalid counts without inspectable traces.
   - Owner: runner/pull scripts.
   - Behavior change: pull per-invalid row JSON and minimal logs/manifests, not only scoreable full dirs.
   - New test: a full-run pull with invalid rows must include names, status reasons, launch logs, and container/build status.
   - Non-leakage: evidence logistics only.
   - Risk: larger pulls.
   - Likely score impact: indirect, but high diagnostic value.

## Evidence appendix

Files inspected directly:

- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/clean22_summary.csv`
- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/run_status_counts.json`
- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/pass_tasks.txt`
- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/fail_tasks.txt`
- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/scoreable_rows.json`
- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/scoreable_dirs.txt`
- `tracking/collab/vm_pulls/tracking/collab/clean22_scoreable_20260614T192658Z/clean22_scoreable_full_dirs.tar.gz` listing
- All 22 `extracted_clean22/shard_*/*/<task>/row.json` files
- All 22 `extracted_clean22/shard_*/*/<task>/artifacts/aether2_result.json` files via row-equivalent loop summaries
- All 22 `extracted_clean22/shard_*/*/<task>/logs/official_verifier.json` files
- Representative `.aether2/raw_logs/*` and tool invocation envelopes from each scoreable row through `loop_result.tool_invocations`
- Service evidence for `kv-store-grpc`, `nginx-request-logging`, `configure-git-webserver`, and `llm-inference-batching-scheduler`
- Source: `runner/aether2/prompts.py`
- Source: `runner/aether2/orientation.py`
- Source: `runner/aether2/loop.py`
- Source: `runner/aether2/verify.py`
- Source: `tools/run_aether2_g3_official.py`

Missing artifacts / limits:

- The latest pull does not include full raw model conversation transcripts or exact serialized model input messages.
- The latest pull does not include per-invalid task directories or per-invalid row details beyond aggregate counts.
- The analysis did not read hidden tests as task-solving inputs; official verifier outputs were used as post-run grader evidence.
