# Aether Core engineering plan (13 Oct 2026)

Agreed with Mohamud after Codex GPT-6-Astra's audit (`audit_output/aether_worldclass_20261013/AETHER_AUDIT.md`)
and the Claude review of it. The authoritative copy is this file; the Gateway charter is not used.

## Goal

The code never hinders the model. Engineering quality (system design, code quality, reliability,
context engineering, tooling) comparable to strong agent runtimes within a declared, narrow scope.
Nothing the model can use is removed.

Scope (the declared envelope): one-shot runs in a Docker task container through Harbor; one
OpenAI-compatible provider path; a clean abort is enough on failure (no restart-resume).

## Budget rule

No new GLM solver runs until step 7. Deterministic tests can establish engineering contracts for truthfulness, substrate, retrieval and
accounting. Optional capabilities still carry schema/context/choice costs; ignore-ability does not establish
no harm to model performance. Task-solving improvements require separate measured evidence.
Changes to model behaviour (context policy, output cap, parallel calls on by default) are built and
tested offline but stay off until step 7 measures them.

## Kept

Model capabilities: named PTY terminals with full logs; the persistent Python REPL (`sh`, `read`,
`write`, `edit`, `llm()`); file read/write/edit; `view_image`; projected and CLM context with
checkpoint compaction; deadline visibility; the reviewer progress review (optional, informs the model).
Lessons: a `docs/LESSONS.md` in the package (clone routing, wrong-check compliance, claim-free
review, cut-turn recovery, V4 corrections).

## Removed

Harness judgment that lost or was invalidated: the state verifier, the V2/V3 contract variants, and
the authority of generated checks to block a finish. Checks may still be shown as information.

## Steps

1. **Truthfulness.** Missing exit code is unknown, not 0; reviewer answers validated on receipt
   (unknown choice, confidence outside [0,1], missing criteria are errors, never pass); missing usage
   is unknown, not 0; `Retry-After` honoured up to the remaining deadline; every attempt counted
   (failed, timed out, rejected); every request sent to the model, from every role, logged exactly
   (sizes and hashes in the trace, full bodies in a sidecar file).
2. **Verification informs, never blocks.** Delete the losing modes; generated checks lose hold power.
3. **Real-Linux fault suite on the VM.** Terminal stdin/interrupt/flood/descendants, worker vs clone
   identity, mounts, deadline propagation, cleanup of abandoned clones and processes.
4. **Context engineering.** Replay V4 traces through both builders and inspect every request; raw
   history immutable under CLM edits, recall by turn; prompt-cache prefix stability and cached-input
   share measured; request size and build time at 10/100/500 turns; flag edits that removed an
   observation later needed.
5. **Tooling.** Schema clarity; repairable errors; malformed/fragmented call streams; truncation
   always with a retrieval handle; binary and huge output; background jobs with handles (optional
   capability); read-only parallel calls (off by default).
6. **Standalone package.** One folder: `pyproject.toml`, lockfile, `src/aether`, `tests`, `docs`,
   `examples`. No imports from the research tree (`review.py`/`oversight.py` currently import
   the research runtime). Proven by building a wheel, installing it outside the repo in a clean environment
   and running real tools with scripted provider responses.
7. **One matched model run** with the remaining budget (about £3.8): hardened Core vs V4 Core. A bundled comparison can measure the package; it cannot separately settle context mode, output cap
   and background-job effects. No provider calls are launched by the current deterministic takeover; a
   later run requires its exact source, route, cases, attempts and spend cap sealed first.

Later: a video tool.

## Progress

- Steps 1-3 done (commits 0b1b5b4ce..26c443b9e).
- Step 4, context bench (`python -m tools.aether_program.core_context_bench`, report
  `CONTEXT_BENCH_V4_20261013.json`): 55 V4 runs, 2023 requests, replayed with no model calls. CLM replay matches
  the recorded request sizes (median drift 0.0%; one run diverges at an edit made through the terminal). Both
  builders keep about 89-90% of each request identical to the previous one (the recorded provider cache hit was
  69% median; character-prefix share is not token-cache share and does not attribute the gap). CLM sends 34% fewer characters (82M vs 124M). The task is in
  every request. Build time is negligible (3.6 ms per request at 500 turns). Repeated-lookup candidates found: 2 trimmed results
  (default builder) and 5 results removed by CLM edits or checkpoints that the model later re-fetched; 3 of
  those 5 were short results with no copy anywhere. Fixed: long results are saved exactly in the sandbox
  (21fabe85c), and under CLM every message as first shown is written to `HISTORY.txt` before any edit,
  rollback or checkpoint, and the model is told where it is. Replay predicts copies for these 7 candidates; this is not proof that all repetitions were caused by lost context or that the runtime writes succeeded.
  Not changed: dropping the newest turn's replayed reasoning breaks the cache prefix at that one turn (28% of
  CLM turns); the cost is that one turn's text, so it stays.

## Acceptance for every change

What becomes better for the model; which module owns it; what complexity leaves callers; which
realistic failure the test exercises; a known-bad that fails the test.

## Codex takeover — 13 October 2026

User transferred implementation ownership after Claude reached its usage limit. Continue in the existing
the working branch worktree, on `codex/aether-core-takeover`, from 4d8239285 and the preserved unfinished zombie-liveness
patch. No agents, browser access or provider runs. The former review heartbeat is absent in the app.

Queue: finish and verify interrupted liveness repair; close reproduced accounting/context/advisory findings;
complete tooling contracts and optional background/read-only concurrency; build standalone package with
installed-wheel real-tool proof; reconcile Linux qualification and remaining model-evaluation authority.
Steps 1–4 are implemented checkpoints, not blanket acceptance: review findings remain until reproduced fixes pass.

Immediate acceptance: actual shell/file effects remain correct under reviewer objection; historical tool
observations cannot be changed through mutable context aliases; interrupted accounting retains committed
attempts and marks truncation; malformed complete log records still fail. Local pipe checks do not qualify Linux PTY.

### Deterministic takeover checkpoint

- Step 3 requalified on Linux for the new wheel: 17 real Docker fault tests passed; includes unreaped
  zombie liveness and between-call restart. Exact image/wheel hashes and logs are preserved.
- Step 5: native argument types checked before effects; explicit zero wait honored; named terminals
  prove background command + independent work + handle polling with exactly one command execution.
  Keys for a lost interactive program are never replayed into a fresh shell. Optional read batches run
  at most four `read_file` calls concurrently, preserve response IDs/order and do not cross writes.
  `CoreConfig.parallel_reads` is false by default; broader concurrency is not enabled.
- Step 6: canonical source is `aether-core/`, with src/aether, pyproject.toml, uv.lock, tests, docs and
  examples. `aether/core` is only a research compatibility symlink. A wheel was installed outside the
  repository; real tools, filesystem effects and immutable attempt reconstruction were exercised.
- No GLM/the reviewer calls were made. Step 7 is deliberately unexecuted: no claim of model-performance gain.
  A live comparison needs an exact sealed route/case/spend manifest and reconciliation of the principal's
  no-model restriction; this engineering takeover does not invent additional spend authority.

Residual scope: full Harbor-runner and live the reviewer/provider qualification remain distinct from the direct
Docker/installed-wheel checks. The context replay is diagnostic, not a solver-score or loss-causality proof.

- Context recall now remains available through read_history even after a failed HISTORY.txt write. Pages
  preserve exact structured messages; later context annotations cannot mutate the stored observations.
- VM has been deallocated after clean completion and evidence retrieval. See docs/core/VALIDATION.md
  for exact wheel versions, platform coverage and remaining boundaries.
