Here is the full architectural design proposal.

---

# OPTIMAL HARNESS ARCHITECTURE FOR TBENCH 2.0
### Model: claude-sonnet-4-5-mini | Target: Maximum Score | Design Class: Model-Led, Minimal, Research-Grounded

---

## SECTION 1: CURRENT STATE — LEADER AND RUN ANALYSIS

### External Leaderboard Position

- **A-Evolve**: 76.5% on TB2.0 (~#7 globally). Uses `adaptive_skill` algorithm with workspace-as-filesystem contract. Claude Opus-4.6. Zero manual harness engineering. Key insight: "The workspace IS the interface" — agent reads state from filesystem, evolver writes skills as YAML+Markdown.
- **BigAI**: Top performer. Observable architecture: planner → executor(s) → verifier. 312/312 runs show stable planner-first control. Multi-executor fanout (max 5, 189 single / 123 multi). Verifier present in 272/312 runs; 57/63 verifier-rejection recoveries succeeded. Source-opaque.
- **KIRA/Terminus**: Double-confirmation before completion. Re-injects original task in final turn.

### Aether-2 Measured Performance

- **Best measured run**: 7/22 scoreable tasks (31.8%). No validated leaderboard score. No Docker backend on local Mac invalidated numerous "certified" runs throughout project history.
- **G5 full run (full_twice_20260612T200830Z)**: 457/482 attempts invalid (ModuleNotFoundError on `runner`). Only 24/241 authoritative rows. 5 passes. Valid-scored pass rate: 5/19 = **26.3%**.
- **Targeted board (14 tasks, 2026-06-15)**: 6 pass, 4 fail. All 6 grader passes had `verifier_clean=False` — verifier is false-blocking passes, not protecting them.
- **G5 Advisory verifier precision**: 14/19 false-clean verdicts = **~26% precision**. The verifier signal is inverted: it blocks legitimate passes more than it catches failures.

### Verifier/Grader Agreement Matrix (22-task run)

| Verifier clean | Grader pass | Count | Interpretation |
|---|---|---|---|
| True | True | 6 | Genuine clean pass |
| False | False | 7 | Genuine fail |
| True | False | 8 | False-clean (fake progress dominant) |
| False | True | 1 | False-blocking (doctrine pollution) |

The clean-fail gap (8 tasks) is the dominant failure mode by count. The false-blocking failure is less common but produced a measured 6/6 pattern in the targeted board run (all 6 passes had `verifier_clean=False`).

### Promotion Status

No production winner. `family_winner_registry_count: 0`. Phases 0-7 explored without a promotable harness running on valid Docker backend at scale.

---

## SECTION 2: ARCHITECTURE ANALYSIS

### Aether-2 Architecture (Current)

**Execution model**: Single-agent flat loop. `STEP_CAP=120`, `MAX_VERIFICATION_ROUNDS=3`. One model call per turn with full context.

**Context structure**:
- Prefix (frozen): system_prompt + task_instruction + orientation_snapshot + tool_schemas
- Transcript (mutable): growing turn-by-turn trace
- Tail (dynamic): JSON telemetry injected each turn — plan, fuel_gauge, evidence_ledger, derived_state, mirror_note

**Tools**: `read_file`, `write_file`, `run_command`, `start_job`, `job_status`, `session_start`, `session_send`, `session_read`, `wait`, `task_done`

**Control mechanisms**:
- Blind retry blocker: same failed command signature blocked until state changes
- Mirror: semantic no-progress detector, emits `[mirror_note]` system messages
- Evidence ledger: per-requirement status + evidence_strength + evidence_provenance
- Compaction: triggered at 15% context window remaining OR >8 receipts
- Completion contract: per-turn injection of `unresolved_requirements`, `verifier_blockers`, `weak_evidence`, `next_required_evidence`
- `_ReadOnlyVerificationContext`: restricted shell for verifier (ls/cat/grep/find/stat/wc/file/ps/df/sha256sum/jq/pwd only)

**Control plane** (`kernel_control_plane.py`): `REQUIRED_PINNED_KEYS` = task_prompt, success_criteria, workspace_contract, verifier_state, artifact_state, known_failed_attempts, open_obligations, service_obligations, tool_contract_state, latest_recovery_card, unresolved_contradictions, raw_trace_pointers.

**Verification** (`verify_fresh_context`): model-based post-task verification using `RequirementResult` with verdict, evidence_strength, evidence_provenance. `DiscrepancyReport.has_unresolved_gaps` drives re-entry.

**Governed gates** (`kernel_gates.py`): `GOVERNED_STATUSES` = governed_pass, ungoverned_model_claim, verifier_failed, artifact_gate_failed, provenance_gate_failed, native_tool_contract_failed, service_not_ready, invalid_environment, budget_exhausted_open_obligations.

### A-Evolve Architecture (Competitor)

**Execution model**: 5-phase loop — Solve → Observe → Evolve → Gate → Reload. Skills as lazy-loaded YAML+Markdown. Memory as append-only JSONL. Git versioning for rollback.

**Key insight**: No harness infrastructure complexity. The agent writes to the filesystem and reads back. The workspace state IS the state machine. No evidence ledger, no control plane, no completion contract. The model reasons about what is in the files.

**Score**: 76.5% with zero harness engineering using a larger model. The lesson is not "use their architecture" — it is that **harness complexity is not additive to score**.

### BigAI Architecture (Leader, Source-Opaque)

**Observable contracts**:
1. Planner-first always (310/312 write explicit plan at step 3)
2. Executor fanout grows with task complexity (1-5 executors)
3. Verifier is external audit role with checklist families (not inline inline check)
4. Recovery is a real recurring loop (57/63 verifier rejections successfully recovered)
5. State-sensitive tasks trigger backup/isolation before mutation

**Key pattern**: Role separation enforces discipline. The planner cannot also verify. The verifier cannot modify state. Recovery is a named loop, not a fallback. These are **behavioral constraints**, not infrastructure complexity.

### Architecture Gap Analysis

| Dimension | Aether-2 | A-Evolve | BigAI (reconstructed) | Gap direction |
|---|---|---|---|---|
| Role separation | None (monolithic) | None (simple) | Planner/Executor/Verifier | Missing role discipline |
| Evidence provenance | Tracked but ignored | Not needed (FS is ground truth) | External audit | Evidence faked without consequence |
| Verifier authority | Advisory (26% precision) | N/A | Blocking (57/63 recovery) | Verifier has no real authority |
| Completion gate | `task_done` tool with schema | Workspace delivery | Double-confirmation | No independent completion check |
| Context management | Compaction at 15% | Rolling JSONL | Unknown | Compaction may lose state |
| Doctrine/task separation | Mixed in system prompt | Clean | Unknown | Doctrine text treated as requirements |

---

## SECTION 3: ROOT FAILURE CAUSE ANALYSIS

### F1: Fake Progress (dominant — 8/22 clean-fail tasks)

**Root**: The model writes output, reads it back, confirms it exists, and calls `task_done`. The check exercises a nearby symptom (file existence, `--help` output, import-only success) rather than the actual claimed behavior. The harness counts this as evidence because `exit_code=0` is the only check.

**Evidence path**: gcode-to-text, db-wal-recovery, kv-store-grpc, bn-fit-modify, build-cython-ext, dna-insert. All show model-authored check → exit 0 → verifier accepts → grader rejects.

**Mechanism failure**: Evidence provenance is tracked but the gate does not enforce independence. A model-authored check against model-authored output has `evidence_provenance = ["model_self_check"]` and `evidence_strength = "weak"` but `verdict = "satisfied"` — which makes `has_unresolved_gaps = False` and cleans the verifier.

### F2: Verifier False-Blocking (6/6 passes had verifier_clean=False on targeted board)

**Root**: The verifier model receives the system prompt and task prompt, and treats harness doctrine bullets ("work in /app", "do not read solution files", "use provided tests") as unresolved task requirements. These are harness operating constraints, not benchmark success criteria.

**Evidence path**: 12 `task_done` dispatch errors for `unsupported requirements/limitations fields`. Multiple `verification_read_only_violation` on benign read commands (ls, cat). Verifier blocks passes that the grader accepts.

**Mechanism failure**: The system prompt + task prompt are injected together into the verifier context. The verifier has no way to distinguish doctrine text (how to operate the harness) from benchmark criteria (what constitutes task success).

### F3: Environment/Launch Substrate Failures (457/482 in G5)

**Root**: Missing `sys.path` bootstrap in `tools/run_aether2_g3_official.py:30`. After VM reboot/autorestart, PYTHONPATH is not exported. All attempts after reboot crash at import.

**Evidence path**: Byte-identical `ModuleNotFoundError: No module named 'runner'` across 457 attempts. G5 pass rate collapses from 5/22 to 5/482 after the reboot event.

**Mechanism failure**: Launch script has no self-check. No `invalid_launch` row emitted. Tournament continues without detecting mass failure mode.

### F4: Doctrine Pollution in Completion Contract

**Root**: The per-turn completion contract injects `unresolved_requirements` by parsing the evidence ledger, which was populated by extracting requirements from the full context including system prompt boilerplate. Requirements like "work in /app", "verify with provided tests", "confirm environment before running" appear as unresolved task requirements.

**Mechanism failure**: Requirement extraction is not scoped to the benchmark task description. The evidence ledger conflates harness operating rules with benchmark success criteria.

### F5: Verifier Self-Referential Check Acceptance

**Root**: The `_ReadOnlyVerificationContext` runs commands in the live environment but the verifier model is asked to design and interpret those checks. A verifier model that wrote the code it is verifying can design a check that confirms its own assumptions. Example: `kv-store-grpc` self-client — the model starts a gRPC server, writes a client, runs the client against its own server, gets exit 0, and the verifier accepts this as confirmation that the gRPC interface works.

**Mechanism failure**: The verifier is the same model that executed the task. The "fresh context" framing does not prevent self-referential reasoning.

### F6: Tool Mismatch on New Background Tools (MLPCP v3)

**Root**: When new tools (`start_job`, `job_status`) were added to the harness for background process management, the model ignored them and continued using foreground `run_command` for long-running tasks. This caused `extract-moves-from-video` and `install-windows-3.11` to score 0.0 despite the tools being available.

**Mechanism failure**: Tool introduction requires prompt and behavioral guidance, not just schema addition. The model defaults to familiar patterns.

### F7: Compaction State Loss

**Root**: At 15% remaining context window (or >8 receipts), the harness triggers compaction/rebase which summarizes the transcript. Summarization can lose fine-grained state — specific file paths written, specific service ports, specific environment variables set. The model after rebase has a summary, not the actual trace.

**Evidence**: Wave 03 synthesis: "compaction/summarization should be modeled as an explicit state operator failure surface." Post-compaction instruction loss is candidate-level concern.

**Mechanism failure**: Compaction summarizes text but does not preserve typed state (path → content mappings, service endpoints, installed packages). The workspace itself preserves state, but the model's memory of what it put there does not.

### F8: Recovery Loop Fragility

**Root**: On verifier rejection, Aether-2 enters a recovery round (up to 3). But the recovery prompt re-injects `unresolved_requirements` from the same polluted evidence ledger. The model's recovery attempts target doctrine bullets, not real gaps.

**Mechanism failure**: Recovery is not structured as "what specifically failed and what is the minimum delta to fix it." It is "here are the unresolved requirements, please address them."

### F9: Step Budget Pressure on Long Tasks

**Root**: `STEP_CAP=120` is a hard ceiling. Tasks like qemu-startup, compile-compcert, make-doom-for-mips, and torch-pipeline-parallelism have legitimate long-running compilation or setup phases. The budget may be consumed by diagnostic overhead before the actual work begins.

**Evidence**: `3d-model-format-legacy` stopped at 25 steps with `implicit_stop`. `accelerate-maximal-square` stopped at 6 steps.

**Mechanism failure**: Budget is uniform across all task types. Long-horizon tasks need a different allocation strategy.

---

## SECTION 4: RESEARCH SYNTHESIS — KEY FINDINGS

### Finding 1: Harness Complexity is Decorative Without Provenance Gates

Aether-2 has more harness infrastructure than A-Evolve and scores lower (31.8% vs 76.5%). The infrastructure — evidence ledger, completion contract, control plane, verifier rounds — is only valuable if the evidence it tracks is actually gated on independence and strength. Without a hard gate on evidence provenance, the machinery tracks fake progress with high fidelity.

**Design implication**: Every piece of harness state must be either (a) gated on independently-sourced evidence or (b) stripped out. Untriggered machinery that processes unverified claims is worse than nothing because it produces false confidence.

### Finding 2: Role Separation is the Only Behavioral Control That Scales

BigAI's stable 312/312 planner-first architecture is the strongest behavioral signal in the dataset. Role separation works because it constrains what each role CAN say and DO, not just what it should say and do. A planner that cannot execute cannot fake execution evidence. A verifier that cannot modify state cannot author the checks it validates.

**Design implication**: The new harness must enforce role separation at the API level — separate system prompts, separate tool sets, separate model calls per role. The model cannot be trusted to self-police roles within a single context.

### Finding 3: The Verifier Must Not Share Context With the Executor

All false-clean failures trace to the verifier having access to (or being the same model as) the executor that wrote the code. The verifier adopts the executor's frame and confirms the executor's assumptions. An external verifier with only the task description and read-only access to the workspace, with no knowledge of what the executor did, is a meaningfully different check.

**Design implication**: The verifier call must receive: (1) the benchmark task description only (no system prompt, no executor transcript), (2) read-only tool access to the live workspace, and (3) no prior context beyond the task. This is the `_ReadOnlyVerificationContext` model but applied to the verifier's system prompt too, not just its tool access.

### Finding 4: Doctrine Separation Requires Structural Enforcement

The distinction between "how to operate the harness" and "what the benchmark task requires" cannot be maintained through prompt phrasing alone. The verifier sees one context and extracts requirements from it. If the context contains doctrine, the verifier treats doctrine as requirements.

**Design implication**: The verifier's context must contain exactly and only the benchmark task description. It must not contain the system prompt, operating constraints, working directory rules, or any other harness doctrine. These are structurally different inputs that must not be concatenated.

### Finding 5: Workspace-as-State is More Robust Than In-Memory State

A-Evolve's core insight — "the workspace IS the interface" — survives compaction, recovery, and role handoff better than in-memory data structures. The workspace does not get summarized. The filesystem does not lose state. If the executor writes a file, the verifier can read it without relying on any in-memory trace.

**Design implication**: Harness state that needs to survive across roles and context windows should be written to the workspace, not maintained in the Python process or the model context. The model's job is to act on the workspace, not to maintain state in its context.

### Finding 6: Independent Evidence is the Minimal Sufficient Gate

The only check that would have caught the 8 clean-fail tasks is: "Does the check exercise behavior that a *different agent* with no knowledge of what was done would design?" If yes, the evidence is independent. If the check was designed by the same model that wrote the implementation, it is self-referential and must not count as strong evidence.

**Design implication**: Evidence is `strong` if and only if: (a) it was produced by running provided test infrastructure, (b) it was produced by a verifier model that received the task description but not the execution trace, or (c) it independently reproduces the stated behavior from scratch (re-runs the protocol from a clean client). All other evidence is `weak`. A task cannot be considered done with only weak evidence.

### Finding 7: Completion Must Require Independent Strong Evidence

The `task_done` tool in Aether-2 can be called with only weak evidence in the ledger. The model calls it when it believes it is done, not when it can prove it is done. This belief is formed primarily from its own output and its own interpretation of that output.

**Design implication**: The harness must enforce a hard gate: `task_done` cannot be dispatched unless the evidence ledger contains at least one `strong` evidence item for each requirement. This gate must be in harness code, not in the system prompt. A prompt instruction to "only call task_done when you have strong evidence" does not work because the model cannot accurately assess evidence strength for its own work.

### Finding 8: Long-Horizon Task Classes Need Explicit Routing

TB2.0's 89 tasks span five distinct operational classes with very different completion patterns: (1) build/compile (long foreground, check output binary), (2) service/daemon (launch + probe from external client), (3) formal/math (produce proof/answer, verify formally), (4) data transformation (run pipeline, verify output), (5) system admin (configure system, verify via read-only audit). A single step budget and completion strategy does not serve all five.

**Design implication**: The harness should detect task class at startup and route to a task-class-appropriate strategy. This affects: step budget allocation, which evidence counts as strong, and what the verifier checks for.

---

## SECTION 5: THE OPTIMAL HARNESS PROPOSAL

### Design Constraints

- Model: claude-sonnet-4-5-mini (128k context window, cost-constrained)
- Must be model-led: the model drives strategy, not harness logic
- Must be minimal: complexity only where it directly addresses a root failure
- Must run on Docker backend (the only substrate that produces valid TB2.0 results)
- No local Mac testing — only Azure VM Docker backend is valid

### A. System Architecture

**Three-role architecture, structurally separated:**

```
[Planner] → plan.md written to workspace
[Executor] → acts on workspace, produces artifacts
[Verifier] → reads workspace and benchmark task only, produces verdict
```

Each role is a separate model call with:
- A separate system prompt appropriate to that role
- A separate tool set (Executor: full tools; Verifier: read-only only)
- No shared transcript — roles communicate through the workspace and typed handoff files

**Workspace as state machine**: All inter-role state lives in the workspace:
- `.harness/plan.md` — planner output (requirements, strategy, acceptance criteria)
- `.harness/evidence.jsonl` — append-only evidence log (provenance, strength, timestamp, command)
- `.harness/verdict.json` — verifier's final structured verdict

**Harness Python keeps minimal state**: run_id, step_count, role_state (planning/executing/verifying), evidence_log path. No in-memory evidence ledger. No completion contract generation in Python.

**Loop structure:**
```
1. Planning phase (1 model call): Executor reads task, writes plan.md
2. Execution loop (up to N steps): Executor acts, appends to evidence.jsonl
3. Soft gate check (harness code): Does evidence.jsonl contain any strong evidence?
   - No → continue execution loop
   - Yes → proceed to verification
4. Verification phase (1 model call): Verifier reads task + workspace only
   - Verdict: pass / fail with specific gaps
5. On pass: governed completion
6. On fail: targeted recovery (1 recovery round, structured)
7. On budget exhaust: best-effort closure
```

**Why three roles over monolithic**: The failure modes (fake progress, false-blocking, self-referential checks) all require the same fix — a boundary between the entity that did the work and the entity that assesses it. Three roles with separated contexts create that boundary structurally.

### B. Context Engineering

**Planner context** (one call, short):
- System prompt: role-specific planner prompt (see Section 6)
- Task description: benchmark task description only
- Workspace snapshot: `ls -la /app` and key file listing
- Output contract: must write structured plan to `.harness/plan.md`

**Executor context** (multi-turn loop):
- System prompt: executor prompt (see Section 6)
- Prefix: task description + plan.md contents + tool schemas
- Transcript: growing turn-by-turn trace (compacted at 20% remaining)
- Tail: minimal telemetry — step count, fuel gauge, current phase, last evidence entry

**Verifier context** (one call after execution):
- System prompt: verifier prompt (see Section 6)
- Context: benchmark task description ONLY — no executor transcript, no plan, no system operating rules
- Tool access: read-only workspace commands (ls, cat, grep, find, stat, wc, sha256sum, file, ps, df, du)
- Evidence.jsonl: NOT shown to verifier (verifier must form independent judgment)

**Doctrine isolation**: System operating constraints (Docker cwd, solution file rules, test infrastructure location) are injected ONLY into the executor prompt. The verifier receives NONE of these. This structurally prevents doctrine-pollution of verifier requirements.

**Compaction policy**: Executor transcript compacted at 20% remaining context (vs current 15%). Compaction preserves: last plan.md content, last 10 evidence.jsonl entries, current step count, installed packages list, active service endpoints. These are extracted as typed structured fields before the summary is generated.

**Token allocation** (128k context):
- Prefix (frozen): ~15k tokens (task + plan + tool schemas)
- Transcript: up to ~90k tokens before compaction triggers
- Tail telemetry: ~2k tokens per turn
- Verifier context: ~10k tokens (task + workspace listing + tool schemas)

### C. Tooling Architecture

**Executor tools** (full set):
- `run_command(cmd, timeout_sec, cwd)` — foreground command execution
- `read_file(path, offset, limit)` — file read
- `write_file(path, content)` — file write
- `start_job(cmd, label, cwd)` — background job management
- `job_status(job_id)` — check job exit status / stdout
- `session_start(shell)` — PTY session for interactive work
- `session_send(session_id, input)` — send input to PTY
- `session_read(session_id)` — read PTY output
- `wait(seconds)` — explicit wait for long-running operations
- `task_done(summary)` — SIMPLIFIED: no schema fields for evidence, requirements, checks. Just a brief summary string.
- `log_evidence(requirement, command, result, provenance_type)` — NEW: explicit evidence append to `evidence.jsonl`

**Critical change — `log_evidence` as a required toll gate**: The model must call `log_evidence` before `task_done`. The harness enforces this: `task_done` is only dispatched if evidence.jsonl contains at least one `strong` entry. `log_evidence` has a `provenance_type` enum: `provided_test`, `external_client`, `fresh_reproduction`, `self_check`. Only `provided_test`, `external_client`, and `fresh_reproduction` count as `strong`. This forces the model to categorize its own evidence, and the harness can enforce the category against what commands were actually run.

**Verifier tools** (read-only only):
- `run_command(cmd, timeout_sec)` — restricted to a whitelist: ls, cat, head, tail, grep, find, stat, wc, file, ps, df, du, sha256sum, jq, pwd, python -c (no file writes)
- `read_file(path, offset, limit)`
- `verdict(pass_or_fail, requirements_status, gaps)` — structured completion of verifier role

**Tool changes from Aether-2**:
- Remove: `task_done` fields for `requirements`, `checks`, `limitations` (they feed fake evidence)
- Add: `log_evidence` with explicit `provenance_type`
- Simplify: `task_done` to just `summary` string
- Keep: all session/job/wait tools (necessary for service and long-running tasks)
- Keep: `_ReadOnlyVerificationContext` restriction for verifier

### D. Workflow/Orchestration

**Planning phase** (always, non-optional):
```
call: planner_model(task_description + workspace_snapshot)
receive: structured plan with requirements, acceptance criteria, task class
write: .harness/plan.md
```

Plan must include:
- Task class (build/compile, service/daemon, formal/math, data/transform, system/admin)
- Explicit acceptance criteria (how to confirm done, from the task description)
- Key risks (what typically goes wrong for this class)
- Step budget estimate (Low/Medium/High — maps to 40/80/120 step caps)

**Execution loop**:
```
while step < step_cap:
    check_compaction()
    build_tail()
    call: executor_model(prefix + transcript + tail)
    dispatch_tools()
    if task_done called:
        check evidence gate (strong evidence present?)
        if gate passes: break → verification phase
        if gate fails: inject "evidence gate not passed" message, continue
    append trace step
```

**Blind retry and mirror**: Keep both mechanisms. The blind retry blocker prevents the single most common waste (same failed command repeated). The mirror tracks no-progress streaks. Both are cheap and effective.

**Recovery structure** (structured, not free-form):
```
Verifier says: FAIL, gaps = [g1, g2, g3]
Recovery prompt injects:
  - The original task description
  - The specific verifier gaps (not the evidence ledger)
  - Instruction: "The verifier found these specific gaps. Address only those gaps."
  - Evidence gate reminder: "After fixing, log strong evidence before calling task_done again."
Max recovery rounds: 2 (not 3 — reduces budget consumption on terminal failures)
```

**Budget exhaustion handling**:
```
On step = step_cap:
  - Run best_effort_check() against plan.md acceptance criteria
  - Log result to evidence.jsonl
  - Call verifier on current workspace state
  - Accept verifier verdict as final
```

**Task class routing**:

| Class | Step cap | Evidence strong criteria |
|---|---|---|
| build/compile | 120 | Produced binary runs AND passes provided test |
| service/daemon | 100 | External client probe succeeds (not self-client) |
| formal/math | 60 | Formal checker accepts proof OR answer matches expected |
| data/transform | 80 | Output file passes provided test script |
| system/admin | 80 | Read-only audit confirms configuration |

### E. Prompting Strategy

**Core behavioral commitments**:
1. Planner writes the plan before any command is run (enforced — first executor turn gets plan.md)
2. Executor does not self-verify (enforced — verifier is separate call)
3. Strong evidence is always external: provided tests, external clients, or fresh reproductions
4. Self-authored checks are logged as `self_check` provenance — they do not unblock `task_done`

**Behavioral anti-patterns to explicitly block** (in executor system prompt):

> You MUST NOT call `task_done` if your only evidence is:
> - A check you wrote yourself that tests your own output
> - A file existence check on something you just wrote
> - An import-only success that does not exercise behavior
> - The exit code of a command you authored
>
> These are activity, not evidence. Log them as `self_check` provenance. They will not satisfy the evidence gate. You must find or produce independent evidence: run the provided test suite, probe from an external client, or reproduce the behavior from a fresh starting point.

**No-progress escalation** (tiered, in executor system prompt):

> After 3 turns with no new strong evidence:
>   - Re-read plan.md and assess whether the strategy is working
>   - If not, pivot strategy entirely — try a different approach, tool, or diagnostic
>
> After 5 turns with no new strong evidence:
>   - Call `run_command` with the most informative diagnostic you have not yet run
>   - Do not repeat any command with the same arguments
>
> After 8 turns with no new strong evidence:
>   - You are likely stuck in a dead-end strategy. Write a new plan in .harness/recovery.md and switch to it.

**Strategy diversity requirement** (anti-pattern specific to TB2.0):
- For build tasks: if `make` fails, try building dependencies manually before trying `make` again
- For service tasks: probe with `curl` or a fresh Python client, not `localhost` loopback from the same process
- For compilation tasks: check for missing shared libraries (`ldd`, `ldconfig`) before re-running

**Completion discipline** (short and hard):
> Call `task_done` only when:
> 1. You have called `log_evidence` with `provenance_type` in [`provided_test`, `external_client`, `fresh_reproduction`]
> 2. The evidence command's output directly confirms the stated task goal
> 3. You can state in one sentence what the grader will see that confirms success

### F. Verification Architecture

**Verifier design principles**:

1. **Separated context**: Verifier model call receives task description only. No executor transcript. No harness doctrine. No system prompt operating constraints. Just: "Here is what the task requires. Here is read-only access to the workspace. Tell me if the task is done."

2. **Adversarial posture**: The verifier system prompt explicitly assumes the executor may have produced fake evidence. The verifier must independently discover whether the requirements are met.

3. **Structured verdict**: Verifier produces a `verdict.json` with:
   ```json
   {
     "verdict": "pass" | "fail",
     "requirements_checked": [{"requirement": "...", "status": "met|unmet|unclear", "evidence_command": "...", "evidence_result": "..."}],
     "gaps": ["specific unmet requirement descriptions"],
     "confidence": "high|medium|low"
   }
   ```

4. **Confidence threshold**: If verifier confidence is `low`, treat as fail even if verdict is `pass`. Low-confidence passes are not reliable enough to submit.

5. **No self-referential checks**: The verifier system prompt explicitly instructs: "Do not design a check that only succeeds if the executor's assumptions are correct. Design checks that would work regardless of implementation path."

**Verifier prompt** (key instructions):
> You are an independent technical auditor. You have read-only access to the workspace.
> You were NOT told what the executor did. You do not have the execution trace.
> Your only context is:
> 1. The task description (what was required)
> 2. The current state of the workspace
>
> Your job: Determine independently whether the task requirements are met.
> Design checks that you would run even if you had no idea what was done.
> Check the actual behavior, not the presence of files.
>
> Adversarial assumption: the executor may have produced output that looks correct but is not.
> Check the behavior, not the claim.

**False-blocking prevention**: The verifier context MUST NOT contain harness operating constraints. If the executor was told "work in /app" or "do not read solution files", the verifier must not know about these constraints. The verifier's only context is the task requirement and the workspace state.

**Evidence gate in harness code** (not in prompt):
```python
def can_dispatch_task_done(evidence_log: list[EvidenceEntry]) -> bool:
    strong_types = {"provided_test", "external_client", "fresh_reproduction"}
    has_strong = any(e.provenance_type in strong_types for e in evidence_log)
    return has_strong
```

This runs before `task_done` is processed. If it returns False, the harness injects:
> "Evidence gate not passed. Your current evidence is logged as self_check or weak. You need to run the provided test suite, probe from an external client, or independently reproduce the behavior. Call log_evidence with the appropriate provenance type when you have independent evidence."

### G. Step/Token Efficiency

**Budget allocation strategy**:
- Planning phase: 1 model call, ~2k tokens. Non-negotiable. Saves budget by preventing wasted early steps.
- Execution phase: step cap from task class routing (40-120 steps).
- Verification phase: 1 model call, ~5k tokens. Non-negotiable.
- Recovery phase: 1-2 rounds, each ~5k tokens.

**Token efficiency mechanisms**:

1. **Tail telemetry thinning**: Current Aether-2 tail includes full evidence_ledger JSON. In the new design, tail includes only: step count, phase, last 3 evidence.jsonl entries, fuel gauge. Saves ~2k tokens per turn.

2. **Evidence.jsonl as append-only**: Harness code reads the last N entries for tail telemetry. Full evidence history is on disk, not in context. Saves memory that grows with task complexity.

3. **Completion contract removal**: The per-turn `unresolved_requirements` injection is removed. This was the primary source of doctrine pollution. The model's own plan.md serves this purpose.

4. **Tool schema minimization**: Show verifier only verifier tools. Show executor only executor tools. Currently all tools are shown to all calls. This saves ~1-2k tokens per call.

5. **Compaction with typed preservation**: Before compaction, extract structured fields (installed packages, service endpoints, file paths created, last 10 commands). Write these to `.harness/state_snapshot.json`. Compaction summary references this file rather than re-summarizing its content.

6. **Prefix deduplication**: Tool schemas for standard tools (run_command, read_file, write_file) are compressed to brief descriptors in the prefix. Full schemas only shown once at start, then referenced by name. Saves ~3k tokens per turn.

**Step budget guidance in executor prompt**:
> - Steps 1-10: Understand the environment, run diagnostics, read provided files
> - Steps 11-40: Primary implementation
> - Steps 41-80: Refinement, debugging, log_evidence attempts
> - Steps 81-120: Recovery only (if needed)
> - If still in diagnostic at step 30: you are stuck. Pivot to a different strategy.

### H. TBench 2.0 Specific Design Decisions

**Task class detection** (automated from task description keywords):
- "compile", "build", "make", "CMake", "gcc", "cargo" → build/compile class
- "server", "daemon", "service", "port", "gRPC", "HTTP", "listen" → service/daemon class
- "prove", "proof", "theorem", "formal", "coq", "lean" → formal/math class
- "convert", "transform", "process", "parse", "extract", "pipeline" → data/transform class
- "configure", "permission", "acl", "user", "nginx", "sshd" → system/admin class

**Docker workspace contract**: Executor is always told:
- Working directory: `/app` (unless task specifies otherwise)
- Do not read files matching: `solution*`, `secret*`, `*.answer`
- Provided tests are in: `tests/` directory (check with `ls tests/` before claiming no tests exist)
- Do not install packages that conflict with provided dependencies
- The grader will re-run `tests/test.sh` — make sure it passes on the current workspace state

**Service/daemon tasks** (kv-store-grpc, qemu-alpine-ssh, nginx-request-logging, etc.):
- After starting a service, ALWAYS probe from an external client (separate Python script, curl from a different port, ssh from localhost with explicit key)
- Self-client (same process connecting to same process) is `self_check` provenance, not `external_client`
- Log the external client command and its output as `external_client` evidence

**Long-running build tasks** (compile-compcert, make-doom-for-mips, build-pov-ray, build-pmars):
- Use `start_job` for builds expected to take >30 seconds
- Check `job_status` and wait until exit before inspecting output
- Binary existence is `self_check`. Running the binary on a test input is `fresh_reproduction`.

**QEMU/VM tasks** (qemu-startup, qemu-alpine-ssh, install-windows-3.11, headless-terminal):
- These tasks have specific resource requirements. Check available memory and disk before starting.
- `start_job` for qemu process (it runs indefinitely)
- SSH probe is `external_client` evidence. Console output from qemu is `self_check`.

**Formal/math tasks** (prove-plus-comm, circuit-fibsqrt, largest-eigenval, distribution-search):
- Run the provided formal checker or test immediately after producing the answer
- The checker's pass/fail IS the strong evidence — log it as `provided_test`
- Do not design your own check for a formal property — the provided checker knows the answer

**ML/compute tasks** (torch-tensor-parallelism, hf-model-inference, sam-cell-seg, llm-inference-batching-scheduler):
- Check GPU availability first: `nvidia-smi`
- Many tasks have specific output format requirements — re-read the task description after producing output
- `provided_test` if a test script exists; otherwise `fresh_reproduction` by running the inference pipeline end-to-end

**Security/vuln tasks** (fix-code-vulnerability, vulnerable-secret, git-leak-recovery, crack-7z-hash):
- Do not run `git log` with broad history if the task says not to read secrets
- Verify the fix by re-running the vulnerable path and confirming the behavior changed
- Self-authored exploit replication is `fresh_reproduction` only if it starts from a clean state

---

## SECTION 6: SYSTEM PROMPT DRAFT

Three separate system prompts are provided: Planner, Executor, Verifier.

---

### PLANNER SYSTEM PROMPT

```
You are a task planner. Your job is to analyze a benchmark task and produce a structured execution plan before any work begins.

You will receive:
1. The task description (what is required)
2. A snapshot of the current workspace

You must produce a plan written to `.harness/plan.md` using the write_file tool. The plan must include these exact sections:

## Task Class
One of: build_compile | service_daemon | formal_math | data_transform | system_admin

## Requirements
A numbered list of the specific requirements from the task description. Extract only what is stated in the task — do not add inferred requirements or operating constraints.

## Acceptance Criteria
How to confirm each requirement is met. Be specific: name the command that would produce confirming output and describe what that output looks like.

## Key Risks
The top 2-3 things that commonly go wrong for this task class.

## Step Budget
One of: Low (40 steps) | Medium (80 steps) | High (120 steps), and why.

## Completion Evidence Plan
How you will produce strong evidence that is NOT self-authored:
- For build tasks: run the produced binary against a test input
- For service tasks: probe from an external client (not self-client)
- For formal tasks: run the provided formal checker
- For data tasks: run the provided test script on the output
- For admin tasks: read-only audit confirms the configuration change

Write the plan file, then output "PLAN_COMPLETE". Do not run any other commands.
```

---

### EXECUTOR SYSTEM PROMPT

```
You are a task executor. You implement solutions to terminal benchmark tasks running in a Docker container.

## Your Role
You implement. You do NOT verify. A separate verifier will independently assess your work when you call task_done. Your job is to produce a working solution and log independent evidence that it works.

## Starting Each Task
1. Read .harness/plan.md with read_file — this is your execution plan
2. Read the task description again to confirm you understand the requirements
3. Run ls /app and ls tests/ to understand the workspace
4. Check if tests/test.sh exists — if it does, it is your primary evidence target

## Evidence Rules (CRITICAL)
You must log evidence using log_evidence before calling task_done.
Provenance types:
- provided_test: you ran tests/test.sh or another provided test and it passed
- external_client: you probed a running service from a separate client process
- fresh_reproduction: you reproduced the behavior from scratch (new process, clean state)
- self_check: you authored a check that tests your own output

ONLY provided_test, external_client, and fresh_reproduction unblock task_done.
Self_check does NOT unblock task_done. Log it for the record, then find independent evidence.

Self-check examples (do NOT treat these as sufficient):
- Writing a file and then reading it back
- Starting a server and connecting to it from the same script
- Running --help and checking for text you expect
- exit_code=0 on a command you authored
- import-only success with no behavioral exercise

## Working in This Environment
- Working directory: /app
- Do not read files named solution*, secret*, *.answer
- Provided tests are in tests/ — always check this directory first
- Use start_job for processes expected to run >30 seconds
- Use session_start for interactive terminals (QEMU, SSH, etc.)

## No-Progress Escalation
After 3 turns with no new strong evidence logged:
- Reconsider whether your strategy is working
- Try a diagnostic you have not run yet

After 5 turns with no new strong evidence logged:
- Run the most informative diagnostic available
- Do not repeat any command with the same arguments

After 8 turns with no new strong evidence logged:
- Your strategy is stuck. Completely change approach.

## Completion
Call task_done only when:
1. You have called log_evidence with provenance_type provided_test, external_client, or fresh_reproduction
2. The evidence command's output directly confirms the task goal
3. You can state in one sentence what the grader will observe

The evidence gate is enforced in code. Calling task_done without strong evidence will be rejected and you will be told to continue.

## Tool Reference
- run_command(cmd, timeout_sec, cwd) — execute a command
- read_file(path, offset, limit) — read a file
- write_file(path, content) — write a file
- start_job(cmd, label, cwd) — start background process
- job_status(job_id) — check background process
- session_start(shell) — interactive PTY session
- session_send(session_id, input) — send input to PTY
- session_read(session_id) — read PTY output
- wait(seconds) — wait for async operations
- log_evidence(requirement, command, result, provenance_type) — log evidence
- task_done(summary) — claim task complete (blocked until strong evidence logged)
```

---

### VERIFIER SYSTEM PROMPT

```
You are an independent technical auditor for a terminal benchmark task.

## Your Role
You were NOT told what the executor did. You do not have the execution trace. You do not know what commands were run or what files were created.

You have:
1. The task description (what was required)
2. Read-only access to the current workspace state

## Your Job
Independently determine whether the task requirements are met.

Design checks YOU would design to verify the task — not checks that assume you know what the executor did.

## Adversarial Assumption
The executor may have produced output that looks correct but is not. Check the actual behavior, not the presence of files. Check that behavior works, not just that it exists.

Examples:
- Don't just check if a binary exists — run it on a test input
- Don't just check if a service is listening — connect to it and exercise its interface
- Don't just check if a file was written — verify its contents are semantically correct
- Don't just check if a proof file exists — run the formal checker

## Checking Process
1. Read the task description carefully
2. List the requirements you will check
3. For each requirement, run the most direct possible check
4. Use only: ls, cat, head, tail, grep, find, stat, wc, file, ps, df, du, sha256sum, jq, pwd, python -c (no writes)

## Output
Call verdict() with:
- verdict: "pass" or "fail"
- requirements_status: list of {requirement, status: met|unmet|unclear, evidence_command, evidence_result}
- gaps: list of specific unmet requirements (empty if pass)
- confidence: high|medium|low

## Important Constraints
- If you cannot determine a requirement's status, mark it "unclear" and set confidence to low
- A low-confidence pass is treated as fail — do not report pass if you are unsure
- Do not check for things not in the task description
- Do not fail tasks because of operating constraints (working directory rules, file access rules) — only check task requirements
```

---

## SECTION 7: IMPLEMENTATION PRIORITY ROADMAP

### Priority 0 — Launch Substrate Fix (Prerequisite for any valid eval)

**What**: Fix `tools/run_aether2_g3_official.py` to insert repo root into `sys.path` before imports. Export `PYTHONPATH` in launcher/autorestart script. Add mass-failure detection that aborts tournament if >50% of first 20 attempts crash at launch.

**Why first**: All evaluation data is garbage until launch failures are eliminated. 457/482 crashes means no measurement is possible. This is a prerequisite, not a mechanism.

**Time estimate**: 1 hour. Single file change + test.

**Measurable gate**: Reach-grader rate >= 95% (from 10% baseline).

### Priority 1 — Doctrine Separation (Addresses F2, F4 — verifier false-blocking)

**What**: Separate the verifier model call from the executor system prompt. Verifier receives task description only. Remove the completion contract (per-turn `unresolved_requirements` injection from polluted evidence ledger).

**Why second**: On the targeted board, all 6 grader-passes had `verifier_clean=False`. Fixing this recovers those 6 tasks immediately. The change is purely architectural — separate model calls with separate contexts.

**Time estimate**: 4-6 hours. New verifier call function. Remove completion_contract generation.

**Measurable gate**: Verifier false-blocking rate drops below 10%. All current-passing tasks remain passing.

**Sentinels**: The 6 tasks that passed the grader but failed the verifier (from targeted board run).

### Priority 2 — Evidence Provenance Gate (Addresses F1, F5 — fake progress)

**What**: Add `log_evidence(requirement, command, result, provenance_type)` tool. Add `can_dispatch_task_done()` gate in harness code. Block `task_done` until strong evidence present. Simplify `task_done` schema to summary-only.

**Why third**: Addresses the dominant failure mode (8/22 clean-fail tasks). Requires the executor to produce and label independent evidence before completing.

**Time estimate**: 6-8 hours. New tool, gate function, evidence.jsonl schema, updated tool dispatch.

**Measurable gate**: Clean-fail rate drops below 3 tasks (from 8/22). False-clean precision improves from 26% to >80%.

**Sentinels**: gcode-to-text, db-wal-recovery, kv-store-grpc (three cleanest false-clean examples).

### Priority 3 — Planner Role Separation (Addresses long-horizon strategy failures)

**What**: Add Planning phase as a separate model call before the execution loop. Write structured `.harness/plan.md`. Include task class, requirements, acceptance criteria, evidence plan.

**Why fourth**: The planner call costs 1 model call but buys structured acceptance criteria that the verifier can use, explicit evidence plans, and task class routing for budget allocation.

**Time estimate**: 4-6 hours. New planner call, plan.md schema, task class detection.

**Measurable gate**: Tasks that previously ran out of budget without completing: step usage profile shows earlier evidence-gathering attempts.

### Priority 4 — Task Class Budget Routing (Addresses F9 — step budget exhaustion)

**What**: Use task class from plan.md to set step cap. Long build tasks: 120 steps. Short formal tasks: 60 steps. Service tasks: 100 steps with explicit service probe requirement.

**Why fifth**: After priority 3 provides task class, routing is a simple conditional. Saves budget on simple tasks, extends it on hard tasks.

**Time estimate**: 2-3 hours. Conditional step_cap based on plan.md task class.

### Priority 5 — Recovery Restructuring (Addresses F8 — recovery loop fragility)

**What**: Replace free-form recovery (re-inject full completion contract) with targeted recovery (inject specific verifier gaps + original task description + evidence gate reminder). Reduce MAX_VERIFICATION_ROUNDS from 3 to 2.

**Why fifth**: Recovery rounds consume budget and currently target doctrine bullets rather than real gaps. Structured recovery with specific gaps is more efficient.

**Time estimate**: 3-4 hours. New recovery prompt template. Update verification loop.

### Priority 6 — Compaction State Preservation (Addresses F7 — state loss)

**What**: Before compaction, extract typed fields to `.harness/state_snapshot.json`: installed packages, service endpoints, file paths created, current step count. Compaction summary references this file.

**Why sixth**: Lower priority because it affects only tasks that use enough steps to trigger compaction. But compaction state loss is silent and hard to detect.

**Time estimate**: 3-4 hours. Pre-compaction extraction hook. Update compaction summary prompt.

### Expected Implementation Order

```
Week 1: P0 (launch fix) + P1 (doctrine separation)
Week 2: P2 (evidence provenance gate) 
Week 3: P3 (planner role) + P4 (budget routing)
Week 4: P5 (recovery restructuring) + P6 (compaction preservation)
```

---

## SECTION 8: EXPECTED SCORE IMPACT

### Baseline

- Valid-scored pass rate: 5/19 = **26.3%** (G5, corrected for invalid launches)
- On 22-task targeted run: 7/22 = **31.8%**
- A-Evolve reference: 76.5% (larger model, simpler harness)

### Impact Estimate by Priority

**P0 — Launch substrate fix**: No direct score change. Prerequisite. Converts 457 crashes to 457 valid attempts. Measurement becomes possible.

**P1 — Doctrine separation**: On the targeted board, 6/6 passes had `verifier_clean=False`. These 6 tasks pass the grader already. Fixing false-blocking converts them to `verifier_clean=True` and removes incorrect recovery rounds. Direct score effect: +0 on counted score (they already pass), but removes the recovery overhead and makes the verifier signal reliable. Indirect effect: prevents recoveries from consuming budget that could be used on other tasks.

**P2 — Evidence provenance gate**: 8/22 tasks failed grader despite verifier_clean=True (clean-fail). These are fake-progress failures. Forcing the model to produce independent evidence will cause some of these to eventually find real evidence and pass. Conservative estimate: 3-4 of the 8 clean-fail tasks convert to real passes. Score delta: **+3 to +4 tasks** on a 22-task board.

**P3 — Planner role**: Harder to quantify. Primarily prevents wasted early steps and provides structured acceptance criteria. Estimate: 1-2 tasks that currently run out of budget without a clear strategy now complete. Score delta: **+1 to +2 tasks**.

**P4 — Budget routing**: Tasks in the wrong budget class get appropriate allocation. Estimate: 1 task that currently times out on a long build now completes. Score delta: **+1 task**.

**P5 — Recovery restructuring**: Recovery rounds currently burn budget on doctrine pollution. With structured recovery, 1-2 tasks that currently fail in recovery now succeed. Score delta: **+1 to +2 tasks**.

**P6 — Compaction preservation**: Addresses state loss on long tasks. Estimate: 1 task that currently loses state in compaction now completes. Score delta: **+1 task**.

### Aggregate Score Projection

| Phase | New passes added | Cumulative score (of ~22 valid tasks) |
|---|---|---|
| Baseline (P0 fixed) | — | 7/22 = 31.8% |
| + P1 (doctrine sep) | 0 direct, reduced waste | ~7/22 |
| + P2 (evidence gate) | +3 to +4 | 10-11/22 = 45-50% |
| + P3 (planner) | +1 to +2 | 11-13/22 = 50-59% |
| + P4 (budget routing) | +1 | 12-14/22 = 55-64% |
| + P5 (recovery) | +1 to +2 | 13-16/22 = 59-73% |
| + P6 (compaction) | +1 | 14-17/22 = 64-77% |

**Conservative projection**: 59-65% on TB2.0 with claude-sonnet-4-5-mini. This matches or approaches A-Evolve's score (76.5% on a larger model) with a smaller model and more structured harness.

**Optimistic projection**: 70-80% if several of the 8 clean-fail tasks turn out to be solvable with independent evidence (they failed only because the model self-checked) and if the planner role produces meaningful step savings on long-horizon tasks.

**Model ceiling consideration**: claude-sonnet-4-5-mini is smaller than Claude Opus-4.6 (A-Evolve's model). The harness architecture cannot fully compensate for capability gaps on the hardest tasks (compile-compcert, make-doom-for-mips, install-windows-3.11, torch-pipeline-parallelism). Realistic ceiling with this model, full harness implementation, and Docker backend: **75-82%**.

### What 100% Requires

The 89 TB2.0 tasks include several that require:
- Very long compilation (compile-compcert: CompCert formally verified C compiler, hours to build)
- Graphics rendering (pov-ray, make-doom-for-mips: cross-compilation for MIPS)
- QEMU VM management (headless-terminal, install-windows-3.11)
- Advanced ML with specific GPU memory requirements (sam-cell-seg, torch-pipeline-parallelism)

These are currently unsolvable not due to harness failure but due to resource constraints (timeout), model capability, or environment availability. 100% requires either: (a) the benchmark infrastructure provides adequate compute for each task class, or (b) the harness routes these tasks to specialized sub-agents or longer-running execution environments.

For the scope of this proposal (single Docker container, 120-step cap, claude-sonnet-4-5-mini), **75-82%** is the realistic optimistic ceiling. The remaining gap to 100% requires infrastructure changes (longer step caps for verified long-running tasks, GPU provisioning, larger model on hard tasks) beyond the harness architecture itself.

---

## DESIGN SUMMARY

The proposed harness departs from Aether-2 in three structural ways:

1. **Three separate model roles** (Planner, Executor, Verifier) with separate system prompts, separate tool sets, and workspace-mediated communication. This is the only structural change that addresses fake progress and false-blocking simultaneously.

2. **Evidence provenance gate in harness code** (not in prompts). The `log_evidence` tool with `provenance_type` enum, enforced by `can_dispatch_task_done()`, makes independent evidence a hard requirement rather than a behavioral aspiration.

3. **Verifier context isolation**. The verifier receives only the benchmark task description and workspace access. No executor transcript. No doctrine. This is the only change that structurally prevents doctrine-pollution of the verifier's requirement list.

Everything else (blind retry, mirror, compaction, step caps, session tools, job management) is preserved because it is effective and addresses real failure modes. The design removes infrastructure that was producing false confidence (completion contract, evidence ledger without provenance gates, self-referential verifier context) and replaces it with less machinery that is more strictly enforced.
