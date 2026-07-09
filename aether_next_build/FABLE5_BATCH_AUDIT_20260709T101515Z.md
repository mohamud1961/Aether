# Fable 5 — Post-Run Audit: 15-task batch `20260709T000000_batch_15task_D16`

Auditor: Fable 5 (post-run, read-only forensics). Model under test: **gpt-5.4-mini**, effort medium, solver+architect both mini. Code: tree hash `9c274b6d34d2…` — **byte-identical to the working tree that carries my Phase-1 completion-evidence protocol**, so this batch is the first live, at-scale test of that change. Grader: official TerminalBench tests, external, post-terminal.

Every number below is from `results.json`, `run_metrics`, and the `traces/verifier_evidence/*/step_*_solver_submit/` round directories. Nothing here is taken from the prior session's closeout note, which I treat as a hypothesis and largely correct below.

---

## 0. Headline: the closeout report inverted the actual result

The prior session reported **"11/14 pass, 78.5%, incredible result."** The grader pass count is real. The framing is wrong in the way that matters most to this project:

- **11/15 official-grader passes is real.** But **only 3/15 runs had a verifier verdict that agreed with the grader** (`crack-7z-hash`, `qemu-startup`, `regex-log` — and even `regex-log` took 276 wasted steps to get there). The other 8 grader-passes are **`verifier_completion_miss`**: the solver solved the task, the external grader scored 1.0, and **the harness's own verifier never confirmed completion.** Those are not clean wins — they are the verifier failing its one job, with the external grader silently covering for it.
- **The verifier was non-functional for essentially the entire batch.** Of **482 solver-submit verification rounds, 456 (94.6%) errored without returning a verdict; 421 were Azure `rate_limit_exceeded`.** Only **26 rounds (5.4%)** ever produced a verdict.
- **Both false-cleans passed through my new Phase-1 gate.** `gcode-to-text` and `video-processing` produced valid `completion_evidence` records and my content-blind gate accepted them at 0.98/0.93 confidence. Both are grader-fails. **This is a failed prediction for Phase 1, recorded as such, not reinterpreted (§4).**

The batch did not measure what the owner wants measured (verifier judgment quality, context engineering, step efficiency as a function of prompting). It measured what happens when you run 15 model-led agents in parallel against a single rate-limited mini deployment: **a rate-limit storm that starved the agent loop.** That is the dominant root cause and it is a substrate failure, not a capability or judgment failure.

---

## 1. The dominant root cause: rate-limit starvation from 15-way parallelism on one deployment

**Evidence.**
- Verifier rounds: 482 total, **421 `rate_limit_exceeded`**, 35 other (permission/timeout), 26 clean. Per task: kv-store 58/59 errored, openssl 149/153, headless 60/63, gcode 44/45, video 31/33.
- Solver side is the same failure: `solver_parse_error_count` is **248–763 per task** (headless 627 of its 1025 total receipts = 61%). Sampling the raw `model_parse_errors`, they are `ResponseError(code='rate_limit_exceeded', … gpt-5.4-mini in eastus2 have exceeded rate limit)` surfacing as `solver_protocol_error`. The solver's model calls were 429ing as hard as the verifier's.
- All 15 tasks share one deployment (`AZURE_OPENAI_GPT54_MINI_DEPLOYMENT`, eastus2). 15 concurrent agents × (1 solver call + frequent verifier calls) per step overwhelmed the deployment's TPM.

**Mechanism of the step explosion.** When a verifier call 429s, the harness gets no verdict, so a solver `submit_outcome` cannot complete the run. The solver acts/submits again next step; that call 429s too. There is **no effective backoff or concurrency cap that resolves the storm** — 456 consecutive errors produced zero recovery. The loop runs until the 500-step cap or the 1800s wall-clock (`openssl` hit `kernel loop exceeded 1800s`). The official grader runs once, post-terminal, outside the storm, so it succeeds and "rescues" the run.

**This satisfies the vision's substrate/judgment split exactly:** a substrate failure (rate limit) must be fixed at the substrate and **never counted as a capability failure**. The classifier did the right thing — it labeled these `harness_context_failure`, not `model_limit`. The prior closeout note is what got it wrong, by reading grader-pass as harness-success.

---

## 2. The step-efficiency answer, quantified

"Why hundreds of steps / why is efficiency so poor" has a precise answer for this batch. For each task, the solver first believed it was done (`firstSubmit`) very early; everything after is waste from the verifier-dead resubmit loop:

| Task | Grader | Verifier align | First submit | Final step | **Wasted steps** | Solver 429/parse errs |
|---|---|---|---:|---:|---:|---:|
| log-summary-date-ranges | pass | completion_miss | 8 | 500 | **492 (98%)** | 763 |
| headless-terminal | pass | completion_miss | 15 | 500 | **485 (97%)** | 627 |
| git-multibranch | pass | completion_miss | 44 | 500 | **456 (91%)** | 670 |
| openssl-selfsigned-cert | pass | completion_miss | 15 | 457 | **442 (97%)** | 625 |
| code-from-image | pass | completion_miss | 168 | 500 | 332 | 735 |
| fix-git | pass | completion_miss | 22 | 320 | 298 | 530 |
| regex-log | pass | **aligned** | 35 | 311 | 276 | 501 |
| kv-store-grpc | pass | completion_miss | 10 | 262 | 252 | 390 |
| train-fasttext | **fail** | aligned | 273 | 500 | 227 | 618 |
| gcode-to-text | **fail** | false_clean | 18 | 231 | 213 | 377 |
| video-processing | **fail** | false_clean | 25 | 185 | 160 | 293 |
| crack-7z-hash | pass | aligned | 132 | 163 | 31 | 248 |
| qemu-startup | pass | aligned | 45 | 53 | 8 | 93 |
| nginx-request-logging | pass | completion_miss | 7 | 13 | 6 | 8 |
| write-compressor | — | — | — | 0 | — (killed) | — |

**Two things produce the waste, and neither is the solver's problem-solving:**
1. **Verifier-dead resubmit loops** — the solver reaches a submit-ready state, the verifier 429s, no completion, repeat. This is 90–98% of the steps in the worst tasks.
2. **Per-step 429 retries** — even a single "step" often burned multiple failed model calls (parse-error counts exceed step counts: crack-7z 248 errors in 163 steps). Each 429 is a wasted round-trip that still advances bookkeeping.

Why some tasks stopped early (`nginx` at 13, `qemu` at 53) and others ran to 500: the `solver_submit_stalemate` bound fires after 3 submits **without new evidence**. Tasks where the solver kept producing new actions between submits (headless, log-summary, git-multibranch) never tripped the bound and ran to the cap; tasks that resubmitted the same state (nginx, kv early) tripped it sooner. So the stalemate bound is real but easy to evade by accident.

---

## 3. Per-role audit

### Architect (config + prompts + EnvMap)
The architect ran on mini and produced valid configs for all graded tasks (no `architect_defect`, no repair codes in the graded rows). `expected_steps` was set sanely (6–12) — which is exactly why `step_efficiency` reads 30–60× (e.g. qemu 8 expected / 53 actual = 6.6; headless 9 / 500 = 55). The architect's estimate of task difficulty was reasonable; the harness blew past it for reasons the architect doesn't control. **I cannot fairly grade architect judgment quality from this batch** because the runs that would have exercised it (verifier reading the architect's success criteria) mostly never happened — the verifier 429'd. This is a measurement casualty of the rate-limit storm, and the honest verdict is UNMEASURED, not good/bad. The two false-cleans (§4) are the only real architect-config signal, and there the config carried the right warnings and the verifier ignored them anyway — same pattern as the 2026-07-07 sentinel.

### Solver
The solver worked and reached correct terminal state on 11/15 (grader-confirmed). It is **not** responsible for the step explosion — its wasted steps are forced by (a) verifier 429s denying completion and (b) its own 429s. Genuine solver-side thrash is small and visible where it exists: `regex-log` 37 repeated writes, `gcode`/`headless` 5 each, `kv`/`openssl` submit-without-new-evidence 10/7. These are minor next to the ~450-step infra waste. The solver did **not** get useful verifier feedback to act on — because there were almost no verifier verdicts to feed back (headless: 3 real verifier results in 500 steps, 166 memoization-skips, 627 parse errors).

### Verifier
Non-functional this batch (94.6% error). On the 26 rounds it did run:
- **3 aligned successes** (crack-7z, qemu, regex): verdict matched grader — the mechanism works when it can call the model.
- **2 false-cleans** (gcode, video): ran, produced my new `completion_evidence` record, and was **wrong** — see §4.
- The rest were single lucky verdicts buried in error storms.

### Feedback loop
**Effectively did not run.** The design (verifier findings → solver context → solver repairs) requires verifier verdicts, and there were almost none. Where the closeout imagined a solver "ignoring feedback across many loops," the reality is there was no feedback to ignore — the loops were 429 retries. `automatic_memory_advisory` and `no_progress_control` receipts fired **0 times** across headless's 500 steps despite 5 repeated writes and hundreds of failed turns: **the no-progress/auto-memory system keys on *successful* repeated actions and is blind to a 429/parse-error loop.** That is a real gap (§5).

### Prompt caching
**Not measured at all.** No cache fields in any result row; `providers/azure_model.py` does not capture `cached_tokens`/`prompt_tokens_details`. The stable-prefix split exists in code, but with the Azure Responses API in background mode there is zero telemetry proving cache hits. Given the volatile context-window default just moved to 50k, unverified caching is now a cost risk worth instrumenting.

---

## 4. Adversarial self-finding: Phase-1 completion-evidence did NOT prevent the false-cleans

This is the most important finding for my own work and I am stating it without softening.

Both false-cleans ran with my Phase-1 gate live. Both produced a structurally valid `completion_evidence` record with resolving `inspection_refs`, so my **content-blind gate accepted them**:
- **gcode-to-text** (verdict completed, 0.98): the record's `falsification_check` argues that `M486 AEmbossed text` with neighboring `M486 S0`/`S-1` lines "rules out" the metadata concern. It does not — the real answer requires decoding the toolpath geometry (`flag{gc0d3_iz_ch4LLenGiNg}`). The verifier wrote a confident, wrong falsification and my gate could not see that it was wrong.
- **video-processing** (verdict completed, 0.93): record cites `read_file` of the analyzer + an auto-realized inspection + a frame-window probe "around the reported frames" — a solver-anchored check, exactly the self-confirmation the architect config warned against. Frames were 72/90; grader ranges are 50-54/62-64.

**This is the failed-prediction case I flagged in the 2026-07-08 addendum** ("If the record is filled with boilerplate discharges of self-confirming evidence, the prediction is FAILED — record it, do not reinterpret"). Recorded here as **FAILED**. The completion-evidence record is necessary auditing infrastructure but, on a mini verifier, it is **not sufficient**: a weak model fills the required fields with plausible-wrong reasoning and the content-blind check passes it.

The concrete, still-in-vision strengthening this points to (Phase 1.5, §6): the refs already carry an inspection *kind*. For a claim the architect marks machine-re-derivable, require at least one `inspection_ref` to resolve to an **independent-derivation kind** (`overlay_run_command` / `probe_*` / the verifier's own `perceive_artifact` of the raw input) rather than `read_file`/`auto-missing-evidence` of a solver artifact. That is still content-blind (the harness checks the *kind* of the cited inspection, never the reasoning), it does not judge task truth, and it would have forced gcode's verifier to actually decode and video's to actually run the detector. It passes the stronger-model test: a strong verifier already derives independently and would never fight it.

---

## 5. Secondary findings (real, smaller)

1. **No backoff / concurrency control on model calls (substrate).** 456 consecutive 429s with no recovery. The harness needs an adaptive retry-with-backoff on solver+verifier calls and a concurrency cap per deployment. Root fix, not a workaround.
2. **No-progress/auto-memory is blind to failure-loops.** 0 advisories during a 500-step 429 loop with repeated writes. It should also count consecutive failed/parse-error turns and identical resubmits, and surface a stop.
3. **`server.key` permission error resurfaced** in openssl rounds (`[Errno 13] Permission denied … /ssl/server.key`) — the exact permission-metadata class from the 2026-07-05 openssl audit reappears in the verifier's overlay path; the earlier "fix" (stat mode/owner) does not cover this overlay read.
4. **Prompt-cache telemetry absent** (§3).
5. **`solver_submit_stalemate` is evasion-prone** — trivially avoided by emitting any new action between submits, so it did not bound the worst runs.
6. **Wall-clock budget counts model latency + retries** — openssl died on the 1800s kernel wall clock, meaning rate-limit latency ate the task's real time budget (a known debt in ROAD_TO_100, now shown to bite).

---

## 6. Execution plan (ordered; vision-tagged)

Preconditions the batch proved: (a) the verifier must be able to *run* before any verifier-quality work can be measured; (b) my Phase-1 gate needs the independence-kind strengthening; (c) rerun must be **serialized or quota-safe**, not 15-way parallel on one mini deployment.

**P-A — Substrate: make model calls survive concurrency (vision-neutral, HIGHEST PRIORITY).**
Add adaptive retry-with-exponential-backoff + jitter on 429/5xx in `providers/azure_model.py`, and a global concurrency semaphore per deployment in the batch runner. Target: <2% unrecovered model-call errors in a 15-task run. Falsification: a deliberately throttled deployment must still complete rounds. *Build (Sonnet).*

**P-B — Rerun discipline (vision-neutral).** Until P-A lands, cap batch concurrency (e.g. 3–4 tasks) or serialize; record TPM headroom. No more 15-way storms on one mini deployment. *Runs (haiku), post P-A.*

**P-C — Phase 1.5: independence-kind requirement on completion_evidence (vision-POSITIVE).** For architect-flagged machine-re-derivable claims, require ≥1 `inspection_ref` resolving to an independent-derivation inspection kind; content-blind, retry-then-refuse like the existing gate. Prove against the known-bad eval **and** the two frozen false-clean snapshots already on disk. Prediction: gcode+video convert to non-completed. *Build (Sonnet).*

**P-D — No-progress covers failure loops (vision-neutral).** Count consecutive failed/parse-error turns and identical resubmits toward a no-progress advisory + stop. *Build (Sonnet).*

**P-E — Cache + budget telemetry (vision-neutral).** Capture `cached_tokens`/prompt-token details from the provider into result rows; meter verifier latency separately from the task wall-clock. *Build (Sonnet).*

**P-F — Re-measure, quota-safe (vision-neutral).** Only after P-A/P-C: rerun a small diverse board serialized, with `AETHER_VERIFIER_EVIDENCE_DIR` set, real SHA-stamped provenance. THIS is the batch that can finally answer the owner's verifier-quality and step-efficiency questions — the current one cannot. *Runs (haiku).*

Order: **P-A → P-C in parallel (2 Sonnet agents max) → P-D/P-E → P-B/P-F reruns (haiku).**

---

## 7. Verdict

The harness solved 11/15 TerminalBench-grade tasks with a mini model — genuinely good underlying capability. But this batch is **not** a 78.5% success story; it is a **substrate-starvation story with a 5.4%-functional verifier**, and the two clean verifier judgments it did make on hard tasks were both false-cleans that slipped through my new gate. The step-efficiency catastrophe (90–98% wasted steps on the worst tasks) is 429-storm waste, not solver or context-engineering waste — that question remains genuinely unanswered and cannot be answered until the verifier can run. Fix the substrate (P-A), strengthen the gate to force independent derivation (P-C), then re-measure quota-safe (P-F). Only then do the context-engineering and prompt questions become measurable.
