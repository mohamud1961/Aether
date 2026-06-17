# Aether-2 Continuity Harness — Build Spec

Status: FINAL DESIGN, ADJUDICATED. This document is the single source of truth for implementing
Aether-2. It is build-ready: every mechanism, file, interface, and acceptance test below is
predetermined. Implementation subagents should not redesign — they should build exactly this,
flag genuine ambiguities as questions rather than silent deviations, and record falsifiable exits
where called out.

Audience: implementation subagents with no prior context on this conversation. Read this document
top to bottom before writing any code.

Repo root: `/Users/mohamud/Downloads/harnesseng`. All paths below are repo-relative unless given as
absolute.

---

## 0. Mission, Principle, Posture

**Mission:** "Make the model more capable by giving it truthful perception, continuous memory,
programmable terminal hands, explicit feedback, and cheap verification, while leaving strategy to
the model."

**Principle banner:** "The model pilots. The harness instruments. The verifier reflects. The
ledger remembers. The grader decides."

**Posture note:** "The model is capable, but not self-supervising enough. The harness supplies
perception, memory, and reflection."

These three statements govern every design decision in this spec. If an implementation choice
seems to violate one of them (e.g., the harness making a strategic call, or hiding information
from the model that would help it), stop and flag it — do not proceed silently.

---

## 1. Why This Design — Evidence Summary

This section compresses the forensic investigation that produced Aether-2. All cited paths were
verified to exist at spec-writing time (2026-06-11).

### 1.1 The 30-step zero-attempt loop (extract-moves-from-video, hard task)

Run trace:
`tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/jobs/official_harbor_bgtools_hard2_20260611T112824Z/mlpcp_v2_bgtools_extract-moves-from-video_20260611T112824Z/extract-moves-from-video__UJwppUX/`

The GPT-5.4 mini agent ran for the full 30-step cap and **never attempted the task**. Receipts
(`agent/host_receipts/receipts/model_execute_request_*.json`, confirmed 30 files present) show
seven compounding, all-harness root causes:

1. **Stateless per-step context render** — each step's prompt was rebuilt with no conversation
   history, so the model could not see what it had already tried.
2. **Tool results summarized to uselessness** — typical envelope text was literally
   `"raw_bash exited 0."`, discarding stdout/stderr entirely.
3. **Inward-facing meta-tools became a loop attractor** — `search_receipts` / `view_receipt` /
   `view_file_cache` gave the model an easy, cheap, self-referential action that looked like
   progress but touched nothing in the task container. The model looped on these instead of
   doing task work.
4. **A dedup mirror returned cached fake "results"** for repeated actions — confirmed present as
   `agent/host_receipts/dedup_execution_ledger.jsonl` in the same run — meaning even when the
   model issued a real command twice, the second "result" was not a real re-execution.
5. **The background-tools patch never reached the model.** Verified via:
   `grep -l "long_running_execution_tools" .../agent/host_receipts/receipts/model_execute_request_*.json`
   → **0 of 30** files contain the string. The capability existed in code but was invisible to
   the model in this run.
6. **Strict-JSON-in-text action protocol lost steps to parse failures** — 2 of 30 steps were
   burned on action-parse errors rather than task progress.
7. **The environment map reported network/apt as `"unknown"`** and the model treated this as a
   hard wall, even though the container actually had network access. The env-map prober is in
   `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/runner/mlpcp_v2_harbor_host.py`
   (the `"REMOTE ENVIRONMENT MAP:\n"` literal at line 3654, confirmed present via grep).

### 1.2 The one real pass — and its amnesia

`tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_receipt_memory_qemu_20260611T105226Z/`
(directory confirmed present) — qemu-startup task — reward **1.000** with GPT-5.4 mini. This is
the only confirmed real TB2.0 pass with this executor model. But even this run **re-probed the
same facts at steps 5, 12, and 30** (amnesia about its own prior discoveries), and only passed at
the final step of the 30-step cap. The harness gave the model no durable memory of what it had
already established.

### 1.3 Official task anatomy (verified against `task.toml`)

- `official_tasks/extract-moves-from-video/task.toml`: `[agent] timeout_sec = 1800.0`
  (30-minute **wall-clock** budget, not a step count), `[environment] cpus = 1, memory = "2G"`.
  Graded by pytest computing Levenshtein similarity ≥ 90%, writing `/logs/verifier/reward.txt`
  as `0` or `1`.
- `official_tasks/install-windows-3.11/task.toml`: `[agent] timeout_sec = 3600.0`,
  `[environment] cpus = 2, memory = "4G"`. This task **requires services to be left running
  after the agent process exits** — the verifier runs post-exit.
- General: test/grader files are mounted at verify time and are **not visible during the run**.
  Tasks originate from `github.com/laude-institute/terminal-bench-2.git` via the Harbor framework.

The wall-clock framing (not step count) is decisive: a 30-step cap that burns steps on
self-referential meta-tools or re-probing is a harness failure, not a model capability ceiling.

### 1.4 External calibration (BigAI trace layer, 314 runs)

`research/analysis/bigai_trace_layer/output/` (directory confirmed present, contains
`answered_questions.md`, `coverage_report.json`, etc.):

- ~82% pass rate across 314 runs using a planner/executor/verifier architecture.
- **Verifier-present runs pass at 0.908 vs 0.20 for verifier-absent runs** (confirmed in
  `coverage_report.json` line 267).
- **90.5% of verifier-caught failures recover** within the run.
- **Failed runs use MORE steps** (median 84.5) **than passing runs** (median 59) — confirmed in
  `coverage_report.json` line 269. More steps does not mean more progress; it often means
  thrashing.
- A written plan (`save_plan`) appears by step 3 in **310 of 312** parseable runs (confirmed,
  `answered_questions.md` line 58).

This is the empirical basis for: (a) verification as a checkpoint that materially improves pass
rate, (b) early model-owned planning, and (c) treating "more steps used" as a warning sign, not a
sign of effort.

### 1.5 Net diagnosis

Every root cause above is a **harness** defect — context rendering, tool surface design,
information fidelity, environment truthfulness — not a model capability gap. (Per the posture
note in §0, this does not mean the model is flawless: mini-class models are weak at
self-supervision — noticing their own loops, escalating from diagnosis to action — which is
exactly why the mirror (§8) and verification feedback (§9) exist as harness-supplied reflection.)
Aether-2 is designed to remove all seven defects directly while adding nothing that resembles
the failed mechanisms (meta-tools, dedup mirror, doctrines/phase-gates, strict-JSON action DSL).

---

## 2. Architecture Overview

**One continuous agent loop ("continuity harness").** No phases, no doctrines, no gates.

### Layers

1. **Perception** — orientation probe (once, ~5s, before step 1) + typed observation envelopes
   (every tool call).
2. **Memory** — append-only transcript (the model's own conversation history) + receipts audit
   ledger (model-invisible, for post-hoc analysis).
3. **Reflection** — state-delta mirror (anti-loop, informational only) + verification feedback
   (Layer 1 self-check + Layer 2 finalize).
4. **Recovery** — truthful error classification (via `kernel_recovery.py`-derived logic), no
   silent retries, one truthful `blind_retry_blocked` signal for immediate identical-failure
   repeats.

### What Aether-2 explicitly is NOT

- NOT a doctrine/phase system. No `phase6_doctrine`-style phase gates in the new code (the
  *handoff template* from `phase6_doctrine.py` is harvested for compaction only — see §6).
- NOT an action-rewriting system. The harness never edits, reorders, or vetoes a model's chosen
  action.
- NOT a completion-vetoing system. `task_done` is a claim that triggers verification; the harness
  never overrides or blocks it pre-emptively.
- NOT a harness-side planner. Planning is model-owned (the model writes and updates its own plan
  in the tail telemetry).

**The harness never holds completion authority.** The grader (Harbor's pytest-based verifier,
external to Aether-2) is the sole authority on pass/fail. Aether-2's Layer 2 verifier is advisory
only — see §9.

---

## 3. Banned Mechanisms (prominent — do not reintroduce any of these)

The following are explicitly DELETED from the design. If you find yourself implementing something
that resembles one of these, stop:

- **Inward-facing meta-tools as model-callable actions**: `search_receipts`, `view_receipt`,
  `view_file_cache`, `search_files`, `probe_service`. These do not exist in the Aether-2 tool
  surface (§4). Full-output retrieval is via the filesystem: every envelope includes a raw-log
  path on disk, and the model greps it via `run_command`.
- **The dedup mirror**: no caching layer that returns a previous "result" for a repeated action
  instead of really executing it. Every `run_command` / `start_job` / `session_send` actually
  executes. (The narrow exception — `blind_retry_blocked` — is a *truthful refusal with an error
  message*, not a fake cached success; see §8.)
- **Any typed action DSL** (`repo_search`, `file_read`, `run_verifier`, or any other harness
  verb-based JSON action protocol) as the primary model-tool surface. Tools are exposed via
  **native provider function-calling** (tool schemas), never strict-JSON-in-text.
- **Doctrines / phase gates** as a model-facing or harness-control structure. (The *content* of
  one doctrine line and the *handoff template format* from `phase6_doctrine.py` are reused — see
  §7 and §6 — but there is no phase machinery, no phase transitions, no phase-conditioned tool
  availability.)
- **Harness-side planning** of any kind — the harness never decides task strategy, never injects
  a "next step," never reorders the model's stated plan.
- **Intent self-labeling requests to the model** — the model is never asked "what type of action
  is this?" Intent classification (`infer_action_type`) is post-hoc, harness-side, for metrics
  only (§4.11).
- **Hiding network/apt/runtime status as "unknown"** — orientation must report these as actively
  probed facts (§7).
- **Reading hidden test/grader files** — never, under any circumstance, by the executor or the
  verifier.
- **Verifier-as-oracle** — the Layer 2 verifier reports discrepancies; it cannot modify, block, or
  decide pass/fail.

---

## 4. Toolset — Exactly 10 Tools

All tools are exposed via **native provider function-calling** (e.g., OpenAI/Azure tool-call
schema), never as strict-JSON-in-text actions. Every tool returns a **typed observation envelope**
(§5).

| # | Tool | Signature | Purpose |
|---|------|-----------|---------|
| 1 | `run_command` | `run_command(cmd: str, timeout_sec: int = 120, cwd: str \| None = None)` | Foreground shell command, executed in the **TASK CONTAINER** (never the host). Returns a typed envelope. |
| 2 | `start_job` | `start_job(cmd: str, job_id: str \| None = None, cwd: str \| None = None)` | Launch a background job via `setsid`/daemonization so it **survives agent process exit** (the verifier runs after the agent exits; services must persist). Harness owns a job registry: pidfile + logfile per job. |
| 3 | `job_status` | `job_status(job_id: str)` | Returns pid-alive status, exit code if finished, and a tail of the job's log. |
| 4 | `session_start` | `session_start(session_id: str, command: str)` | Start a persistent interactive PTY (tmux-backed) for qemu monitors, telnet, REPLs, editors, installers. |
| 5 | `session_send` | `session_send(session_id: str, keys: str)` | Send keystrokes to a session. |
| 6 | `session_read` | `session_read(session_id: str)` | Read the current screen contents of a session. |
| 7 | `read_file` | `read_file(path: str, offset: int \| None = None, limit: int \| None = None)` | Bounded, honest file read. |
| 8 | `write_file` | `write_file(path: str, content: str)` | Atomic, encoding-safe write (eliminates the heredoc-mangling failure mode). |
| 9 | `wait` | `wait(seconds: int, reason: str)` | Harness sleeps **without a model call**, max 300s per call. Returns elapsed-state report (job/session changes during the sleep). Critical for boot/install/download waits under wall-clock budgets. |
| 10 | `task_done` | `task_done(summary: str, checks: list[str])` | Completion claim. `checks` is a list of shell commands the model declares as evidence its task is complete. Triggers Layer 2 finalize verification (§9). |

### 4.1 `run_command`

- Executes in the task container's working filesystem and process namespace. Never on the host
  running the harness.
- Returns the full observation envelope (§5): exit code, duration, cwd, stdout/stderr head+tail,
  raw-log path, files-changed summary, process/job/session deltas.
- Subject to the blind-retry guard (§8): an identical command that just failed, if repeated
  immediately with no intervening state change, returns `blind_retry_blocked` instead of
  re-executing.

### 4.2 `start_job`

- Harvest target: `_action_background_job` region of
  `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/runner/mlpcp_v2_harbor_host.py`
  (confirmed present — `_action_background_job` defined at line 4273, dispatched from
  `action_type in {"background_job", "start_background_job"}` at lines 3809–3810).
- Must launch with `setsid` (or equivalent double-fork/daemonize) so the process is reparented to
  init and is NOT killed when the agent process tree exits. This is non-negotiable for tasks like
  `install-windows-3.11` where services must be running at verify time.
- Registry: one pidfile + one logfile per job, keyed by `job_id` (auto-generated if not supplied).
  Registry persisted on disk under the task workspace so it survives process restarts.

### 4.3 `job_status`

- Reads the registry entry: checks `/proc/<pid>` (or equivalent) for liveness, reads exit code
  from a wait-status file written by the launcher wrapper if the process has exited, and tails the
  logfile (same head/tail bounding as §5).

### 4.4–4.6 `session_start` / `session_send` / `session_read`

- tmux-backed PTY. `session_start` creates a named tmux session running `command`.
  `session_send` sends literal keystrokes (including control sequences, e.g., `C-c`, `Enter`) via
  `tmux send-keys`. `session_read` captures the current pane via `tmux capture-pane`.
- Sessions persist across model turns and (like jobs) should survive agent exit if the task
  requires it (e.g., a qemu monitor that must stay up).

### 4.7 `read_file` / 4.8 `write_file`

- `read_file`: bounded by `offset`/`limit` (line-based or byte-based — implementation detail to
  resolve in `executor.py`, document the choice). Always returns truthful EOF/truncation info.
- `write_file`: atomic (write to temp + rename), explicit UTF-8 (or binary passthrough if content
  is base64/declared binary — resolve and document). This directly eliminates the heredoc-mangling
  failure mode seen in prior traces.

### 4.9 `wait`

- Pure harness sleep — **no model call is issued** during this tool's execution. Max 300 seconds
  per invocation (model must call it again for longer waits, giving it natural checkpoints).
- On return, includes: elapsed seconds, and a delta report of any jobs/sessions that changed state
  during the sleep (new log lines, process exit, etc.) — i.e., it reuses the delta engine (§10).

### 4.10 `task_done`

- `summary`: free-text claim of completion.
- `checks`: list of shell command strings the model asserts demonstrate completion. These are
  replayed verbatim, fresh, in Layer 2 Part A (§9.3).
- Calling `task_done` does not end the loop by itself — it triggers the finalize verification
  flow (§9), which may hand control back to the model for up to 3 rounds.

### 4.11 Post-hoc intent classification (metrics only)

- `runner/action_bus.py` contains `infer_action_type(*, tool_name: str, command: str) -> str`
  (confirmed present at line 21). Aether-2's `metrics.py` calls this **after the fact**, on
  recorded `run_command`/`start_job`/etc. invocations, purely to populate per-trial metrics
  (e.g., "how many install vs. inspect vs. test commands"). The model is never asked for this
  label and never sees its output.

---

## 5. Observation Envelope (typed result, every tool)

Every tool call returns a structured envelope with these fields:

```python
@dataclass
class ObservationEnvelope:
    tool: str                      # which of the 10 tools
    exit_code: int | None          # None for tools without a process exit (e.g., session_read)
    duration_sec: float
    cwd: str
    stdout_head: str                # up to 2KB
    stdout_tail: str                # up to 2KB
    stderr_head: str                # up to 2KB
    stderr_tail: str                # up to 2KB
    truncated: bool                 # true if head+tail < full output
    raw_log_path: str               # absolute path on disk to the FULL uncapped output
    files_changed: list[FileDelta]  # path, hash-before, hash-after, change-type
    process_delta: ProcessDelta     # jobs/sessions started, died, log growth since last step
    blind_retry_blocked: bool       # true only if this call was refused per §8
    error: ErrorInfo | None         # truthful classification, see §8 / kernel_recovery.py
```

- **Head/tail bounding**: 2KB head + 2KB tail for stdout AND stderr independently. If
  `len(output) <= 4KB`, `truncated=False` and head+tail together reconstruct the full output
  (no gap). If larger, `truncated=True` and the gap is described (e.g., "...3.2KB omitted,
  see raw_log_path...").
- **Mechanical CR-rewrite and ANSI-noise collapse**: progress bars (`\r`-based redraws, ANSI
  cursor/color escape sequences) must be collapsed to their final visible state before head/tail
  extraction — this prevents a single `apt-get install` progress bar from consuming the entire
  2KB budget with escape codes.
- **Raw stored uncapped on disk** at `raw_log_path` — this is the model's retrieval path via
  `run_command "grep ... <raw_log_path>"`. No retrieval tool is provided; the filesystem IS the
  retrieval mechanism (per the banned-mechanisms list, §3).
- **`files_changed`**: computed via the delta engine (§10) — every observation includes the
  incremental files-changed-since-last-step summary (path + hash before/after).

---

## 6. Context Engineering (cache-first)

### 6.1 Immutable cached prefix

Constructed once, at orientation time, and **never edited** for the lifetime of the run (until a
rebase, §6.3):

1. System prompt (~700 tokens) — single source of truth in `prompts.py` (§ manifest).
2. Task instruction, **verbatim** (exactly as provided by Harbor — no paraphrase, no
   summarization).
3. Orientation snapshot (§7) — the one-time perception probe results.
4. Tool schemas (the 10 tools, §4).

Target: **≤ 8k tokens** at start. This prefix is what gets prompt-cached by the provider; mutating
any byte of it kills the cache for the rest of the run, so it must be frozen immediately after
construction.

### 6.2 Append-only transcript

All subsequent turns (model messages + tool calls + observation envelopes) are appended in order.
**Earlier messages are never mutated** — mutation kills the cache prefix up to that point. The
transcript is the model's memory of what it has tried and found.

### 6.3 Tail telemetry (latest-message-only, re-rendered only on change)

A block appended as the **most recent message only** — never re-rendered into earlier turns —
containing, only when changed since last render:

- **Model-owned plan** — the model writes/updates this; the harness never edits it.
- **Fuel gauge** — elapsed wall-clock time always shown; remaining time shown only when an
  objective external budget exists (i.e., the agent timeout from `task.toml` — but see §7, task
  metadata like difficulty/category is NOT shown; the *timeout itself*, as an operational
  constraint, is a different thing and MAY be surfaced as a fuel gauge input — implementers should
  treat the wall-clock deadline as an operational fact, not "task metadata").
- **Derived-state block** — active jobs/sessions and their last-known status, current no-delta
  streak count, and **artifact/service events** (new artifact written, service started/died) since
  the last render. These events are always recorded in the ledger and surfaced here when changed —
  they do NOT trigger the Layer 2 verifier (§9.2, falsifiable exit #1) and do NOT generate
  per-event "remember to verify" nags (the single doctrine line in §7 covers self-verification
  once; repeating it per event is friction).
- **Mirror notes** — the state-delta engine's factual observations (§10), when triggered.

### 6.4 Constants (v0 defaults — tracked metrics, not dogma)

These are starting values, tunable via the day-1 calibration probe (§14) and the per-trial
scorecard. Deviating from them is allowed when metrics justify it, but every deviation must be
recorded with its evidence (same discipline as the falsifiable exits, §13). The dream is a high
pass rate with cheap mini execution — cost/efficiency fields are first-class scoreboard columns,
never afterthoughts.

| Constant | Value |
|---|---|
| Envelope head/tail size | 2KB + 2KB (stdout), 2KB + 2KB (stderr) |
| Turns never compacted (most recent) | last 10 |
| Compaction trigger | 60% of context window OR explicit model request |
| Rebased prefix target | ≤ 20k tokens |
| Expected rebases per hard task | 1–3 |
| Target fresh input tokens per hard task | ≤ 150k |
| Cache hit ratio target | ≥ 80% (tracked in metrics) |
| Step cap | ~120 (safety rail only — wall-clock from `task.toml` is the real budget) |
| Max single `wait` duration | 300 seconds |

### 6.5 Compaction = context rebase (model-led, harness-backed)

**Trigger**: 60% of context window used, OR the model explicitly requests compaction. **Never**
mid tool-call chain (i.e., never between a tool call and its result).

**Process**:
1. The **model** writes a handoff summary using the template from
   `orient_codex_style_handoff_compaction` in `blocks/orientation/phase6_doctrine.py` (confirmed
   present at line 12: `def orient_codex_style_handoff_compaction(task_prompt, env_info=None)`,
   which delegates to `_orient(..., "candidate_plus_codex_style_handoff_compaction_01",
   _context("done/next/files/commands/risk handoff"))`). The template covers: done /
   in-progress / next / key facts / files+artifacts / commands that worked / errors / risks.
2. The **harness** appends a deterministic fact ledger that the model cannot get wrong:
   - every file written + its hash,
   - jobs + their current status,
   - nonzero exits + their error lines,
   - artifact list,
   - installed packages.
   This ledger is built from the delta engine's accumulated state (§10), harvested from
   `runner/kernel_state.py` and `runner/kernel_artifacts.py`.
3. **New prefix** = system prompt + task instruction (verbatim) + orientation + fact ledger +
   model handoff + last 10 turns.
4. This causes one full-price cache read for this turn; everything re-caches from this point
   forward.

---

## 7. Orientation (once, ~5s, before step 1)

Perception only — never strategy, never injected planning. Probes (harvest target: the env-map
prober in
`tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/runner/mlpcp_v2_harbor_host.py`,
which builds the `"REMOTE ENVIRONMENT MAP:\n"` block, confirmed at line 3654 — the surrounding
function should be located by grep for `important_tools` and the env-map construction logic and
generalized):

- `cwd`
- effective user / root or non-root
- workspace root
- writable paths
- top-level directory listing
- a fixed, generic tool-presence list (e.g., `git`, `curl`, `python3`, `gcc`, `make`, `tmux`, ...
  — generic, never task-specific)
- package managers present: `apt`, `pip`, `npm`, `uv`
- **NETWORK as an actively probed fact** — e.g., attempt a real connectivity check
  (DNS resolve + TCP connect or HTTP HEAD to a known host) and report `reachable: true/false` with
  evidence, **never `"unknown"`**. This directly fixes root cause #7 (§1.1).
- language runtimes present (python version, node version, etc.)
- running processes (snapshot)
- listening ports (snapshot)

### System-prompt doctrine lines (exactly two, both included verbatim in `prompts.py`)

1. "Missing tools can usually be installed (apt/pip/npm); prefer installing or bootstrapping over
   abandoning."
2. A request for a brief written plan before acting — the plan is **model-owned and
   model-updatable** (it lives in the tail telemetry, §6.3, and the model edits it whenever it
   wants).

### Hard rule

**Task metadata (difficulty, category, tags from `task.toml`) is NEVER shown to the model.** The
agent timeout (wall-clock budget) is an operational constraint and may inform the fuel gauge
(§6.3), but difficulty/category labels must not leak into the prompt — this prevents the model
from anchoring on "this is a hard task" framing instead of just doing the work.

---

## 8. State-Delta Engine + Mirror (anti-loop, informational only)

Harvest targets: `runner/kernel_state.py` (state projection) and `runner/kernel_artifacts.py`
(artifact registry — confirmed present, e.g. `refresh_artifact_registry`,
`summarize_artifact_registry`, `_sha256_file` at lines 222/252/510).

### Per-step fingerprint

Computed after every tool call:
- files changed (path + hash before/after)
- processes started/died
- job-log growth (byte count delta per job)
- new output bytes (stdout/stderr length delta)

### No-delta streak

An **identical action signature** (same tool + same normalized command/args) that produces **zero
world-delta** (no fingerprint change) increments a streak counter. **Any** delta — even an
unrelated one — resets the streak to zero.

- **At streak = 3**: append ONE factual observation to the tail telemetry (§6.3):
  > "Steps N–M produced no state change. Already established: [ledger facts]. Not yet tried:
  > [unused affordances from tool registry]."
- **At streak = 6**: same observation, plus the fuel gauge (elapsed/remaining time).
- The mirror **never blocks, never forces, never rewrites the model's next action**. It is
  information appended to context, full stop.

### Retained narrow guard from `flat_loop.py` — `blind_retry_blocked`

Harvest target: `blocks/execution/flat_loop.py`, function `_build_blind_retry_blocked_result`
(confirmed present, referenced from line 92 with reason code
`"blind_retry_blocked_same_failed_command"` at line 196).

- If the model issues a command that is **identical** to the immediately preceding command, AND
  that preceding command **just failed** (nonzero exit / error), AND no state has changed since:
  the harness does **not** re-execute. It returns a truthful envelope with
  `blind_retry_blocked: true` and `error.reason_code = "blind_retry_blocked_same_failed_command"`,
  explaining that this exact command already failed and nothing changed — try something
  different.
- This fires **once** per repeat (i.e., it is a single truthful refusal, not a persistent ban —
  if the model tries a third time after making some other change, it is allowed to execute
  normally again, subject to its own fingerprint).
- This is the ONLY retained "blocking-ish" behavior in the entire harness, and it returns a
  truthful error rather than a fake cached result — it is fundamentally different from the banned
  dedup mirror (§3), which faked successful re-execution.

---

## 9. Verification (checkpoint, not gate)

### 9.1 Layer 1 — continuous, executor self-verification

The model is encouraged (via the system prompt doctrine, §7) to run cheap bash checks itself as
part of normal `run_command` usage. This is model-owned — the harness does not inject or require
specific checks at this layer. This is "doctrine as advice," not "doctrine as gate."

### 9.2 Layer 2 — finalize verification

Triggered by **exactly five** events (no others — do not add artifact-write or service-start
triggers; see falsifiable exit #1, §13):

1. `task_done` is called.
2. **Implicit stop** — the model emits a turn with no tool call (treated as an implicit
   completion claim, since the loop has nothing else to do).
3. **Budget exhaustion** — the wall-clock deadline (from `task.toml` `[agent].timeout_sec`) is
   reached. This is "deadline-forced": the harness runs the model's most-recently-declared
   `checks` (if any) anyway, and gives the model **one closing turn** to react to the results
   before the run ends.
4. The model explicitly requests verification.
5. Bounded re-checks during finalize rounds (i.e., rounds 2 and 3 of the flow in §9.5 are
   themselves Layer 2 invocations).

### 9.3 Part A — deterministic replay of declared checks

The exact shell commands from the most recent `task_done(checks=[...])` are replayed **fresh**,
in the live task container, by the harness. For triggers 2/3 where no `task_done` was ever
called, use the model's most-recently-declared checks if any exist (e.g., from an earlier
`task_done` in a prior verification round); only if none were ever declared is the check list
empty — in that case Part B still runs. Results (exit codes, output) are recorded.

Harvest target: `runner/kernel_layer2_audit.py` — confirmed present, contains `_clean_hidden_refs`
(line 9) applied at lines 104–106 to `success_contract`, `context_pack`, `finalization_gate`
respectively. This anti-leakage filter must be applied to **every harness-injected payload** in
Aether-2's verification flow (§9.6).

### 9.4 Part B — fresh-context verifier

A **separate** model call, same model (GPT-5.4 mini), with a **clean transcript** (no shared
history with the executor). It receives:

- the task instruction, verbatim
- the orientation snapshot
- a workspace diff (files + hashes, from the delta engine §10)
- the executor's completion claim (`summary` from `task_done`, or "implicit stop" /
  "budget exhaustion" framing for triggers 2/3)
- the declared `checks` and their Part A replay results
- a compact action digest (a condensed log of what commands were run — NOT the full executor
  transcript)

It does **NOT** receive the executor's full transcript (deliberate — keeps the verifier's context
small and unbiased by the executor's framing).

The verifier may run **read-only inspection commands** (logged, subject to the same
`_clean_hidden_refs` filter). It returns a **requirement-by-requirement discrepancy report**:
for each requirement it can identify from the task instruction, a verdict of
`satisfied | unsatisfied | unverifiable` plus supporting evidence.

**The verifier cannot modify anything, cannot block anything, cannot decide pass/fail.** Its
output is handed back to the executor as information.

### 9.5 Flow

1. Layer 2 triggers (one of the five events above).
2. Part A + Part B run.
3. If discrepancies exist and time remains: the executor receives the discrepancy report and
   continues working.
4. **Maximum 3 verification rounds.** The executor may rebut a discrepancy with evidence (e.g.,
   "the verifier ran the check in the wrong directory; here is the corrected output") in any
   round.
5. After round 3 (or earlier if the executor believes everything is satisfied and calls
   `task_done` again with no remaining discrepancies, or time runs out), the executor submits —
   "submit" here means the run ends; the actual pass/fail grading happens externally via Harbor's
   pytest-based grader against `/logs/verifier/reward.txt`, which Aether-2 does not control.
6. **Service-task special case**: for tasks requiring persisted services (e.g.,
   `install-windows-3.11`), the finalize replay's **last act** is to confirm the model's declared
   services are still alive (via `job_status` / process checks) — i.e., verify they will survive
   the agent's exit, since the external grader runs after the agent process tree terminates.

### 9.6 Anti-leakage

`_clean_hidden_refs` (from `runner/kernel_layer2_audit.py`, confirmed at line 9, recursively
strips dict/list values) is applied to **every** payload the harness injects into either the
executor's or the verifier's context. **No hidden test/grader files are ever read, by either the
executor or the verifier.** The verifier is advisory only — never an oracle (§3).

---

## 10. Delta Engine (cross-cutting)

`runner/aether2/delta.py` is the shared component computing:
- file hashes (sha256, harvest `_sha256_file` from `runner/kernel_artifacts.py:510`)
- artifact registry (`refresh_artifact_registry`, `runner/kernel_artifacts.py:222`,
  `summarize_artifact_registry`, line 252)
- process/job/session state snapshots (harvest from `runner/kernel_state.py`)

This is consumed by: the observation envelope (`files_changed`, `process_delta`), the mirror
(no-delta streak, §8), the compactor's fact ledger (§6.5), and Part B verification's workspace
diff (§9.4).

---

## 11. Genericity Enforcement (CI-gated)

Per `AGENTS.md` Rule 1 ("No hardcoded task knowledge. Nothing in `runner/` or core orchestration
should reference specific tasks by name."), Aether-2 adds a CI-gated check script:
`tools/aether2_genericity_check.py`. It must:

1. Grep `runner/aether2/` for official TB2.0 task names (e.g., `extract-moves-from-video`,
   `install-windows-3.11`, `qemu-startup`, and the full task-name list derivable from
   `official_tasks/*/`) — fail if any match.
2. Grep prompts (`runner/aether2/prompts.py` and any prompt-construction code) for benchmark
   vocabulary: `terminal-bench`, `harbor`, `TB2`, `TB2.0`, and any literal task IDs — fail if any
   match.
3. Grep configs for task-conditional affordances (any `if task_name == ...` / `if task_id in
   {...}`-style branching) — fail if any match.
4. Require that every new mechanism added to `runner/aether2/` has a one-sentence description (in
   a docstring or adjacent doc) that names **no** specific tool, file, or task.
5. Held-out homolog validation: any "fix" claimed to address a failure class must be validated
   against a homolog task it was not tuned on, before being credited.
6. A non-TB generalization board is required for promotion: BFCL / ContextBench / Letta adapters
   already exist in `runner/` (confirmed: `runner/benchmark_adapter_bfcl.py`,
   `runner/benchmark_adapter_bfcl_native.py`, `runner/benchmark_adapter_contextbench.py`,
   `runner/benchmark_adapter_contextbench_native.py`, `runner/benchmark_adapter_letta.py`,
   `runner/benchmark_adapter_letta_native.py` all present in `runner/`), plus self-authored
   real-world chores (the 5 homolog task shapes from G2, §14).

This script runs in Lane E continuously from hour 0 (it can fail-empty initially, then gain checks
as `runner/aether2/` files appear).

---

## 12. File Manifest

### 12.1 New files

| File | Purpose | Est. LoC | Harvest sources (verified) | Public interface sketch | Acceptance tests |
|---|---|---|---|---|---|
| `runner/aether2/__init__.py` | Package init | ~5 | — | — | imports cleanly |
| `runner/aether2/loop.py` | The continuous agent loop: orientation → step loop (model call → tool dispatch → envelope → context append → mirror/delta update → compaction check → Layer 2 trigger check) → finalize | ~300 | Seed: `blocks/execution/flat_loop.py` (confirmed present; reuse `_build_blind_retry_blocked_result`, `_update_failure_tracker`, the autopsy-event bookkeeping pattern minus the "doctrine" framing) | `def run_aether2_loop(task: TaskSpec, model_client, executor, *, deadline_ts: float) -> RunResult` | `tests/test_aether2_loop.py`: loop terminates on `task_done`, on implicit stop, on deadline; blind-retry guard fires exactly once per repeat; step cap is a safety rail not normally hit |
| `runner/aether2/context.py` | Prefix/transcript/tail manager; enforces cache-stability invariants (immutable prefix never mutated post-construction) | ~250 | New (interfaces inform structure from `runner/kernel_context_pack.py`, confirmed `manage`, `build_context_pack`, `render_context_pack` at lines 16/32/127) | `class ContextManager: def build_prefix(...) -> Prefix; def append_turn(...); def render_tail(...) -> str; def assert_prefix_unchanged() -> None` | `tests/test_aether2_context.py`: prefix bytes identical across N appends; tail only re-renders on change; token-count estimate of prefix ≤ 8k on synthetic task |
| `runner/aether2/compactor.py` | Context rebase: triggers at 60% window or model request; builds fact ledger + invokes model handoff template | ~200 | `runner/kernel_compaction.py` (confirmed `should_compact` line 33, `build_compaction_prompt` line 95, `create_compaction_boundary` line 145, `rehydrate_after_compaction` line 248); `runner/kernel_context_pack.py` (`build_context_pack` line 32); `blocks/orientation/phase6_doctrine.py` (`orient_codex_style_handoff_compaction` line 12) | `def should_rebase(window_used_frac: float, model_requested: bool) -> bool`; `def build_fact_ledger(delta_state) -> dict`; `def rebase(context: ContextManager, model_client) -> ContextManager` | `tests/test_aether2_compactor.py`: rebase fires at 60% threshold; new prefix ≤ 20k tokens on synthetic large transcript; fact ledger contains all written files w/ hashes |
| `runner/aether2/tools.py` | The 10 tool schemas (native function-calling format) + dispatch table to executor/jobs/sessions | ~200 | New, schemas per §4 | `TOOL_SCHEMAS: list[dict]` (provider tool-call format); `def dispatch(tool_name: str, args: dict, ctx: ExecutionContext) -> ObservationEnvelope` | `tests/test_aether2_tools.py`: exactly 10 schemas, names match §4 table exactly; dispatch routes each to the correct subsystem; unknown tool name raises |
| `runner/aether2/executor.py` | Container exec backend (foreground commands) | ~250 | New | `class ContainerExecutor: def run(cmd, timeout_sec, cwd) -> RawResult` | `tests/test_aether2_executor.py` (or folded into `test_aether2_tools.py`): **regression test asserting NO host-path reachability** — i.e., a command referencing a host-only path must fail/be invisible from inside the executor (the "shadow-workspace bug") |
| `runner/aether2/envelope.py` | Builds `ObservationEnvelope` from raw exec/job/session results: head/tail bounding, CR/ANSI collapse, raw-log persistence | ~200 | New | `def build_envelope(raw: RawResult, *, raw_log_dir: Path) -> ObservationEnvelope`; `def collapse_cr_ansi(text: str) -> str` | `tests/test_aether2_envelope.py`: 2KB+2KB bounding exact; CR-rewrite progress bar collapses to final line; raw log file written and path included; truncation flag correctness on boundary sizes |
| `runner/aether2/jobs.py` | `start_job`/`job_status` registry; setsid launch, pidfile+logfile per job | ~200 | `_action_background_job` region of `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/runner/mlpcp_v2_harbor_host.py` (confirmed, line 4273; dispatch at 3809-3810) | `class JobRegistry: def start(cmd, job_id, cwd) -> str; def status(job_id) -> JobStatus` | `tests/test_aether2_jobs_sessions.py`: job survives parent process kill (spawn, kill harness process, confirm child still running via pid); `job_status` reports correct exit code after completion |
| `runner/aether2/sessions.py` | tmux-backed PTY sessions (`session_start`/`session_send`/`session_read`) | ~200 | New (tmux CLI wrapper) | `class SessionRegistry: def start(session_id, command); def send(session_id, keys); def read(session_id) -> str` | `tests/test_aether2_jobs_sessions.py`: session persists across reads; send+read roundtrip on a simple shell; session survives if harness process restarts (tmux server independence) |
| `runner/aether2/orientation.py` | One-time perception probe: cwd/user/workspace/writable paths/listing/tool-presence/package managers/network-as-fact/runtimes/processes/ports | ~150 | mlpcp host env-map prober in `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/runner/mlpcp_v2_harbor_host.py` (locate via grep for `important_tools` and the `"REMOTE ENVIRONMENT MAP:\n"` block at line 3654; **fix**: network/apt must be probed, never `"unknown"`) | `def orient(executor: ContainerExecutor) -> OrientationSnapshot` | `tests/test_aether2_orientation.py` (or folded into loop tests): network field is never the literal string `"unknown"`; task metadata (difficulty/category) is provably absent from the snapshot dict |
| `runner/aether2/delta.py` | File-hash deltas, artifact registry, process/job/session snapshots | ~150 | `runner/kernel_state.py`; `runner/kernel_artifacts.py` (confirmed `refresh_artifact_registry` line 222, `summarize_artifact_registry` line 252, `_sha256_file` line 510) | `def snapshot(workspace_root: Path) -> StateSnapshot`; `def diff(prev: StateSnapshot, curr: StateSnapshot) -> DeltaReport` | `tests/test_aether2_delta.py` (or folded): file edit detected via hash change; no-op command produces empty `DeltaReport` |
| `runner/aether2/mirror.py` | No-delta streak counter; emits factual observations at streak 3 and 6 | ~150 | New (logic per §8) | `class Mirror: def observe(action_signature: str, delta: DeltaReport) -> MirrorNote \| None` | `tests/test_aether2_loop.py` (mirror cases): identical zero-delta action 3x → note; 6x → note + fuel gauge; any delta resets streak |
| `runner/aether2/verify.py` | Layer 2: Part A replay + Part B fresh-context verifier; applies `_clean_hidden_refs` | ~250 | `runner/kernel_layer2_audit.py` (confirmed `_clean_hidden_refs` line 9, applied at lines 104-106) | `def replay_checks(checks: list[str], executor) -> list[CheckResult]`; `def verify_fresh_context(task, orientation, diff, claim, checks_results, action_digest, model_client) -> DiscrepancyReport` | `tests/test_aether2_verify.py`: `_clean_hidden_refs` applied to all 3 injected payload types; verifier transcript contains NO executor transcript content; discrepancy report schema validated |
| `runner/aether2/model_client.py` | Wraps `runner/model_client.py` with native tool-calls, retry/backoff, TPM pacing, cache-aware message assembly | ~150 | `runner/model_client.py` (confirmed present, Azure GPT-5.4-mini route constants `AZURE_ROUTE_MODEL_TIERS`, `AZURE_ENV_GPT54_MINI_*`); `runner/kernel_tpm_pacer.py` (confirmed `class RollingTPMPacer` line 135) | `class Aether2ModelClient: def call(messages, tools, *, cache_prefix_len) -> ModelResponse` | `tests/test_aether2_loop.py` / dedicated test: TPM pacer invoked; retry on 429/5xx (per `TRANSIENT_STATUS_CODES` in `runner/model_client.py`); native tool-call format used (not text-JSON) |
| `runner/aether2/bridge_harbor.py` | Generalizes the mlpcp Harbor agent/runner pair; mounts ANY loop implementing the `loop.py` interface; propagates deadline; enforces artifact sync-back | ~250 | `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_hard4_20260610T215341Z/runner/mlpcp_v2_harbor_agent.py` (confirmed present); `.../mlpcp_v2_harbor_task_runner.py` (confirmed present) | `def run_task_via_harbor(task_dir: Path, loop_fn, *, deadline_ts: float) -> RunResult` — `run_task_via_harbor` MUST raise/fail loudly if post-run artifact sync-back is incomplete | `tests/test_aether2_bridge_harbor.py` (or folded into `test_aether2_loop.py`): synthetic task dir → loop → artifacts present in expected output location; missing-artifact case raises (does not silently pass) |
| `runner/aether2/receipts.py` | Audit capture mirroring `host_receipts` layout (per-step request/response/action/raw output), model-invisible | ~150 | Layout reference: `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/jobs/.../extract-moves-from-video__UJwppUX/agent/host_receipts/` (confirmed present: `receipts/`, `raw/` subdirs, `model_execute_request_N.json` files) | `class ReceiptWriter: def record_step(step_idx, request, response, action, raw_output)` | `tests/test_aether2_receipts.py` (or folded): receipt files written per step; receipts directory NOT referenced by any model-facing tool/prompt |
| `runner/aether2/metrics.py` | Per-trial scorecard | ~100 | `runner/action_bus.py` (`infer_action_type`, confirmed line 21) for post-hoc labeling | `def build_scorecard(run: RunResult) -> Scorecard` with fields: pass, steps, model_calls, tokens_cached, tokens_fresh, cost, wall_time, cache_hit_ratio, no_delta_streaks, verification_rounds, recoveries, compaction_count, job_survival, session_survival | `tests/test_aether2_metrics.py` (or folded): scorecard fields all populated on synthetic run; cache_hit_ratio computed correctly from token counts |
| `runner/aether2/prompts.py` | THE single system prompt + the two doctrine lines (§7); single source of truth | ~100 | New, content per §7 | `SYSTEM_PROMPT: str`; `DOCTRINE_LINES: list[str]` | `tests/test_aether2_prompts.py` (or folded into genericity test): no benchmark vocabulary, no task names, both doctrine lines present verbatim |
| `tests/test_aether2_loop.py` | Loop integration tests | — | — | — | per loop.py row above |
| `tests/test_aether2_tools.py` | Tool schema + dispatch tests | — | — | — | per tools.py row above |
| `tests/test_aether2_context.py` | Cache-stability tests | — | — | — | per context.py row above |
| `tests/test_aether2_compactor.py` | Rebase tests | — | — | — | per compactor.py row above |
| `tests/test_aether2_jobs_sessions.py` | Survival tests | — | — | — | per jobs.py/sessions.py rows above |
| `tests/test_aether2_verify.py` | Verification flow tests | — | — | — | per verify.py row above |
| `tests/test_aether2_envelope.py` | Envelope bounding tests | — | — | — | per envelope.py row above |
| `tests/test_aether2_genericity.py` | Runs `tools/aether2_genericity_check.py` against `runner/aether2/` | — | — | — | passes when `runner/aether2/` contains no banned vocabulary |
| `tools/aether2_genericity_check.py` | CI grep gates per §11 | ~150 | New | `def main() -> int` (exit code 0/1 for CI) | invoked by `tests/test_aether2_genericity.py`; also runnable standalone in CI |
| `scripts/deallocate_harnesseng_vm.sh` | VM lifecycle: deallocate the Azure VM | TBD | Convention reference: `scripts/build_harnesseng_runtime_bundle.sh` (confirmed present, uses `set -euo pipefail`, `usage()`/`log()`/`die()`/`run()` helper pattern, `--dry-run` flag) and `scripts/deploy_harnesseng_worker_runtime.sh` (confirmed present) | CLI script following the same flag/helper conventions (`--dry-run`, `--help`, `log`/`die`) | smoke test: `--dry-run --help` exit 0, prints planned `az vm deallocate` command without executing |
| `scripts/configure_harnesseng_vm_autoshutdown.sh` | VM lifecycle: configure auto-shutdown policy on the Azure VM | TBD | Same conventions as above | CLI script, `--dry-run`/`--help` per convention | smoke test: `--dry-run --help` exit 0, prints planned `az vm auto-shutdown` command without executing |
| `tracking/collab/aether2_build_spec/predictions.md` | Pre-registered predictions (verbatim from §15) | — | — | — | exists, content matches §15 verbatim |

**Note on VM scripts**: confirmed via `ls scripts/` that only `build_harnesseng_runtime_bundle.sh`
and `deploy_harnesseng_worker_runtime.sh` currently exist — `deallocate_harnesseng_vm.sh` and
`configure_harnesseng_vm_autoshutdown.sh` are confirmed ABSENT and must be created. Exact LoC is
"TBD" pending the actual `az` CLI invocations needed; implementers should follow the established
helper-function conventions (`log`, `die`, `run`, `--dry-run`, `--help`, `set -euo pipefail`) from
`scripts/build_harnesseng_runtime_bundle.sh`.

### 12.2 Files to EDIT

| File | Nature of edit |
|---|---|
| `scripts/build_harnesseng_runtime_bundle.sh` | The bundle is built via `rsync` with an exclude list (confirmed at lines 99-112: excludes `.git/`, `.venv/`, `venv/`, `.pytest_cache/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `._*`, `__MACOSX/`, `runs/`, `vm_pulled_runs/`). Since the rsync invocation copies the whole repo tree (minus excludes) rather than an explicit include-list, `runner/aether2/` will be picked up automatically by the existing rsync — **confirm this at integration time**; if an explicit include-list exists elsewhere in the script (re-check around line 120 `run rsync "${rsync_common[@]}" "$src" "$dst_parent/"`), add `runner/aether2/` and `tools/aether2_genericity_check.py` to it explicitly. Document whichever is true in a comment near the rsync invocation. |
| `AGENTS.md` | Add a short addendum section (proposed exact text below) stating Aether-2 is the active harness line, restating the principle banner, and stating the genericity CI gate requirement. |
| `runner/README.md` | Add `runner/aether2/` to the "Current Surfaces" list (confirmed current list: `runner/agent.py`, `runner/kernel_*.py`, `runner/packet04_route_manifest.py`, `runner/benchmark_adapter_*.py`, `runner/phase65_measurement_contracts.py`, `runner/phase65_measurement_grading.py`). Note: the file references `../docs/current_surface_map.md` and `../docs/deprecation_map.md` as "current-surface docs" — these links are known-broken (do not fix in this work; out of scope). |

#### Proposed `AGENTS.md` addendum text

> ## Aether-2 Continuity Harness — Active Harness Line
>
> `runner/aether2/` is the active harness line for TB2.0 work. Its governing principle:
>
> "The model pilots. The harness instruments. The verifier reflects. The ledger remembers. The
> grader decides."
>
> No phase gates, doctrines-as-control, action-rewriting, completion vetoes, or harness-side
> planning may be added to `runner/aether2/`. Any change to `runner/aether2/` must pass
> `tools/aether2_genericity_check.py` (no hardcoded TB2.0 task names, no benchmark vocabulary in
> prompts, no task-conditional affordances) before merge.

### 12.3 Files to harvest from but NEVER edit

- `blocks/execution/flat_loop.py`
- `blocks/orientation/phase6_doctrine.py`
- `runner/kernel_compaction.py`
- `runner/kernel_context_pack.py`
- `runner/kernel_state.py`
- `runner/kernel_artifacts.py`
- `runner/kernel_recovery.py`
- `runner/kernel_layer2_audit.py`
- `runner/kernel_tpm_pacer.py`
- `runner/action_bus.py`
- `runner/model_client.py`
- `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_hard4_20260610T215341Z/runner/mlpcp_v2_harbor_agent.py`
- `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_hard4_20260610T215341Z/runner/mlpcp_v2_harbor_task_runner.py`
- `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/official_harbor_bgtools_hard2_20260611T112824Z/runner/mlpcp_v2_harbor_host.py`

### 12.4 Files/dirs NOT to touch

- `blocks/` guard files generally (only `phase6_doctrine.py` and `flat_loop.py` are harvest
  sources, and those are read-only per §12.3)
- `runner/packet07_*` and `runner/successor_*` (historical, per `runner/README.md`)
- `tracking/` archives, EXCEPT the two new dirs created by this work:
  `tracking/collab/aether2_build_spec/` (this spec + predictions.md)

---

## 13. Recorded Falsifiable Exits / Pushbacks

These are deliberate, adjudicated scope decisions. Do NOT preemptively expand scope on these —
only revisit if the named evidence threshold is met.

1. **Layer 2 verification triggers stay at the five listed in §9.2.** Expand to artifact-write
   triggers ONLY if calibration traces show false mid-run confidence (executor believes it's done
   when it isn't) surviving all the way to finalize.
2. **Intent labels (`infer_action_type`) are derived post-hoc only.** Ask the model to self-label
   its own actions ONLY if scored evidence shows this improves reliability.
3. **The typed action DSL stays rejected** (§3). Revisit ONLY if argument-shape errors (malformed
   tool-call arguments) appear as a top-3 failure class in scored runs.
4. **Receipt-retrieval tools (`search_receipts`/`view_receipt`/`view_file_cache`) stay deleted.**
   Filesystem grep via `run_command` against `raw_log_path` is the retrieval path, permanently,
   unless scored evidence shows this is a material bottleneck.

---

## 14. Build Plan

### Hour 0 — Contract-first (blocking; everything depends on this)

Sign off on, before any other code is written:
- The observation envelope schema (§5) — exact field names/types.
- The 10 tool schemas (§4) — exact native function-calling JSON schema for each.
- The `loop.py` ↔ `bridge_harbor.py` interface (the `loop_fn` signature that
  `run_task_via_harbor` mounts).

### Lanes (A–D run in parallel after Hour 0; integration on Day 2)

| Lane | Files | Depends on |
|---|---|---|
| A — Loop/Context/Compaction | `loop.py`, `context.py`, `compactor.py`, `prompts.py` | Hour-0 contracts |
| B — Hands | `tools.py`, `executor.py`, `envelope.py`, `jobs.py`, `sessions.py` | Hour-0 contracts |
| C — Bridge/Infra | `bridge_harbor.py`, `orientation.py`, `receipts.py`, `metrics.py`, `model_client.py`, the two VM scripts | Hour-0 contracts |
| D — Verification | `verify.py`, `delta.py`, `mirror.py` | Hour-0 contracts |
| E — Tests/CI | all `tests/test_aether2_*.py`, `tools/aether2_genericity_check.py` | Hour-0 contracts; runs continuously thereafter |

### Phase gates

- **G1**: unit suite green (all `tests/test_aether2_*.py`) AND
  `tools/aether2_genericity_check.py` green.
- **G2**: local homolog smoke — 5 self-authored, non-TB task shapes:
  1. file-artifact task (write a file, verify content/hash)
  2. service task (start a long-lived server, verify it survives agent exit)
  3. interactive-session task (drive a REPL/PTY via session_* tools)
  4. package-install task (apt/pip install something not preinstalled, verify it works)
  5. long-running-job task (start_job + wait + job_status polling to completion)
- **G3**: Harbor inventory probe — determine how many TB2.0 tasks are servable on the Azure VM
  Docker backend, at what concurrency, with what runtimes/resource constraints — PLUS a 5-task
  official calibration run: `qemu-startup`, `extract-moves-from-video`, `install-windows-3.11`,
  one easy task, one medium service task.
- **G4**: full TB2.0 baseline at n=2, ONLY after G3 is green AND inventory shows ≥80% of TB2.0
  tasks servable.
- **G5**: failure-class iteration loop — one generic mechanism per identified failure class, each
  validated against a held-out homolog before being credited; sentinels: qemu-startup
  green-check, BFCL adapter, and the non-TB generalization board (§11).

### Day-1 calibration probe (1 hour, before/alongside Hour-0 contracts)

Establish empirically, with GPT-5.4 mini via the Azure backend (`runner/model_client.py` Azure
route, confirmed `AZURE_ROUTE_MODEL_TIERS = frozenset({"gpt-5.4-mini", "gpt-5.3-codex"})`):
- tool-calling reliability (does it reliably emit well-formed native tool calls?)
- parallel tool-call support (can it call multiple tools in one turn?)
- effective context window size
- cache pricing mechanics (prefix cache hit/miss cost ratio)
- envelope-bounding constant tuning (is 2KB+2KB the right size for this model's typical output
  patterns, or does it need adjustment before G2?)

---

## 15. Pre-Registered Predictions (verbatim — also goes in `predictions.md`)

1. **qemu-startup**: PASS in ≤ 12 model calls (was 30 at the cap in the prior architecture).
2. **extract-moves-from-video**: flip 0 → 1 (root causes were perception/memory/time-budget, all
   addressed in this design). Confidence: moderate — residual risk is OCR fidelity under 1 CPU /
   30-minute budget, which is task-hardness, not harness.
3. **install-windows-3.11**: flip 0 → 1 (needs sessions + setsid persistence + `wait`; all now
   present). Confidence: moderate.
4. **video-processing**: NO prediction — diagnose first (an environment-setup issue was flagged
   in a pause state for this task; root cause unknown, do not predict outcome until diagnosed).
5. **Cache hit ratio ≥ 80%**; **≤ 150k fresh input tokens per hard task**.

---

## 16. Acceptance Checklist (whole build)

- [ ] All 18 `runner/aether2/*.py` files present (incl. `__init__.py`), each within ~25% of its
      estimated LoC or with a documented reason for deviation.
- [ ] All 8 `tests/test_aether2_*.py` files present and green.
- [ ] `tools/aether2_genericity_check.py` present, runs in CI, currently green against
      `runner/aether2/`.
- [ ] Exactly 10 tool schemas in `tools.py`, names matching §4 table exactly, no extra tools.
- [ ] Banned-mechanisms grep (§3 list) returns zero hits in `runner/aether2/` and
      `runner/aether2/prompts.py`: no `search_receipts`, `view_receipt`, `view_file_cache`,
      `search_files`, `probe_service` as callable tools; no dedup-mirror cache-and-replay logic;
      no strict-JSON-in-text action parsing as the primary tool-call path.
- [ ] Observation envelope schema matches §5 exactly (field names/types); 2KB+2KB bounding
      verified by test; CR/ANSI collapse verified by test; raw-log path present and dereferenceable
      on every envelope.
- [ ] `start_job` processes verified to survive harness-process termination (test in
      `test_aether2_jobs_sessions.py`).
- [ ] `session_*` tools verified tmux-backed and persistent across reads.
- [ ] Orientation snapshot: network/apt/package-manager fields are real probed facts, never the
      string `"unknown"`; task metadata (difficulty/category/tags) provably absent from the
      snapshot and from the system prompt.
- [ ] Cache-stability: immutable prefix bytes identical across appends until a rebase; rebase only
      occurs at 60% window or model request, never mid tool-call.
- [ ] Compaction produces a fact ledger (files+hashes, jobs+status, nonzero exits, artifacts,
      installed packages) plus a model-written handoff using the
      `orient_codex_style_handoff_compaction` template; new prefix ≤ 20k tokens in test.
- [ ] Mirror: no-delta streak fires factual notes at 3 and 6, never blocks; `blind_retry_blocked`
      fires exactly once per identical-failed-then-repeated command.
- [ ] Layer 2 verification: triggers exactly on the five listed events; Part A replays declared
      checks fresh; Part B uses a clean transcript (no executor transcript leakage, verified by
      test); `_clean_hidden_refs` applied to all three injected payload types; verifier cannot
      mutate state (read-only enforced); max 3 rounds enforced.
- [ ] `bridge_harbor.py` fails loudly (raises) on incomplete artifact sync-back (test).
- [ ] `metrics.py` scorecard includes all fields listed in its manifest row, populated on a
      synthetic run.
- [ ] `scripts/deallocate_harnesseng_vm.sh` and `scripts/configure_harnesseng_vm_autoshutdown.sh`
      created, follow existing script conventions, `--dry-run`/`--help` work.
- [ ] `AGENTS.md` addendum added (text per §12.2).
- [ ] `runner/README.md` updated to list `runner/aether2/` under Current Surfaces (broken doc
      links left untouched, out of scope).
- [ ] `scripts/build_harnesseng_runtime_bundle.sh` confirmed (or edited) to bundle
      `runner/aether2/` and `tools/aether2_genericity_check.py`.
- [ ] `tracking/collab/aether2_build_spec/predictions.md` exists with §15 content verbatim.
- [ ] G1 (unit + genericity) green before any G2 work begins.
- [ ] G2 (5 homolog task shapes) green before any G3 work begins.
- [ ] G3 (inventory probe + 5-task official calibration) green, with ≥80% TB2.0 inventory
      servable, before G4.
- [ ] G4 (n=2 full baseline) only attempted after G3 gate passes.
- [ ] No file under §12.3 (harvest-only) modified.
- [ ] No file/dir under §12.4 (do-not-touch) modified.
