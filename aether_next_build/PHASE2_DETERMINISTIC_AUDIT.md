# Aether-Next — Deterministic-Layer Audit (did the code-driven parts capture the right things?)

Companion to `PHASE2_FULL_AUDIT.md`. This audits the **deterministic** machinery that runs
before/around the model — `envmap_builder`, `analysis.py` (ObjectiveGraphBuilder +
EvalIndexer), `completion.py` (the gate), `kernel_messages.build_architect_request`, and the
system prompts — against what the 10 tasks actually require. Evidence: the captured traces +
the real task prompts.

## TL;DR

The deterministic gate logic and the system prompts are **well-designed and on-target**.
The failure is in **deterministic capture**: the objective-graph / eval-index extractors
populate almost nothing for these tasks, so the gate is fed an empty objective and rubber-
stamps everything. The criteria are *right there in every prompt* and are deterministically
extractable — the extractors are just too brittle to catch them.

---

## 1. Did deterministic VERIFICATION capture the correct things? — **No (1/10).**

The completion gate (`completion.py`) is correct: it blocks on missing required artifacts,
integrity violations, failed/missing authoritative checks, schema mismatch, unmet
thresholds, open obligations, and no-recent-progress. Good list. But `ready = not blockers`,
and **every blocker source was empty**, so it returned `ready=True` on first submit in all
"completed" runs (0 authoritative checks executed across 20 runs).

Why empty — traced to source:

- **`envmap_builder` populates no structured criteria.** It sets `grader_hints={}` and no
  `task_metadata` (correct: must never read the hidden grader). But that kills *every*
  structured path the builders rely on (required_artifacts, thresholds, output_schema,
  services, immutable_paths). Only free-text regexes on the prompt remain.
- **`EvalIndexer` found 0 authoritative checks** in all 10 tasks. Its sources:
  `grader_hints.verify_commands` (empty), a "run `X` to verify" regex (no task is phrased
  that way), visible **test files** (it scans `workspace_dir`, not the task dir — so the
  hidden `/tests` are correctly *not* ingested → no grader-peek, but also no checks), and
  make targets (none). Net: nothing to run.
- **`ObjectiveGraphBuilder` captured the required artifact in only 1/10 tasks**, via the
  brittle `_PROMPT_DELIVERABLE_RE` that needs the filename to *immediately* follow the verb.

Prompt-states-output vs deterministic-capture, per task:

| task | prompt explicitly names output | artifact captured? |
|---|---|---|
| constraints-scheduling | `/app/meeting_scheduled.ics` | ✅ yes |
| filter-js | "Create a python **file** /app/filter.py" | ❌ missed |
| raman-fitting | 'write them to a file called **"/app/results.json"**' | ❌ missed |
| gcode-to-text | "Write the output to **/app/out.txt**" | ❌ missed |
| extract-elf | "Write me a program **extract.js**" (+ `out.json`) | ❌ missed |
| openssl | numbered list: `/app/ssl/server.{key,crt,pem}` … | ❌ missed |
| log-summary | output file described in prose | ❌ missed |
| sparql-university | output query/result file in prose | ❌ missed |
| train-fasttext | model file **< 150 MB**, **≥ 0.62 accuracy** | ❌ missed (artifact + thresholds) |

So 9/10 objective graphs reduced to a single generic obligation, `integrity:clean`. The
gate had nothing task-specific to verify. **The deterministic verifier did not capture the
correct things — it captured almost nothing**, despite the criteria being explicit and
parseable. Notably:
- **Thresholds**: train-fasttext states "< 150 MB" and "≥ 0.62 accuracy" — exactly the
  `MetricThreshold` shape the gate already supports — but threshold extraction only reads
  `grader_hints` (empty), so 0 captured.
- **Schema**: raman ("x0, gamma, amplitude, offset"), extract-elf ("JSON object with …") —
  extractable output schemas — but schema extraction only reads `grader_hints` → 0 captured.

## 2. Did the deterministic ARCHITECT / first-step capture the correct things? — **Under-served.**

`build_architect_request` is well-formed: it hands the architect `task_prompt`, full
`envmap`, `capability_index`, the `objective_graph`, the `eval_index`, and the required IR
field list. The structure is correct. The problem is the **payload is near-empty** (§1):
the objective graph is just `integrity:clean`, the eval index has 0 checks. So the
deterministic first-step gives the model no requirement scaffolding — the model must
re-derive every deliverable/criterion from raw prose. codex partly did (proof_plan of
6–9 items); mini didn't. The deterministic layer offloaded its job to the model.

The only deterministic thing the architect path does well: it correctly **does not** leak
the grader (workspace-only scan), preserving the invariant.

## 3. Were the plans / config / system prompt correct and on target? — **Prompts yes; one structural wiring flaw.**

- **ARCHITECT_SYSTEM_PROMPT**: clear, complete, with good task-shape→workflow guidance
  (service_stabilize / artifact_extract / optimize_search / reverse_engineer_local / …).
  On target. **Structural flaw:** it ties `check_plan` to "check_id strings from
  eval_index authoritative_check_ids." Since the eval index is empty (§1), the architect
  *cannot* author an executable check plan — it can only write a free-text `proof_plan`,
  which the gate never executes. So executable verification is structurally unreachable
  whenever deterministic check extraction yields nothing (i.e. always, here).
- **SOLVER_SYSTEM_PROMPT**: correct rule — "Do NOT submit_outcome until required artifacts
  exist and planned checks would pass." But with no artifacts/checks defined, the rule is
  vacuous: the solver has no concrete definition of done. This directly produces the two
  observed failure modes — codex never submitting openssl (no signal it's done) and mini
  submitting wrong answers (nothing to fail it).
- **Config defaults** (ProcessPolicy stateless_shell, completion_policy with
  allow_evidence_fallback=True): reasonable, but `allow_evidence_fallback=True` + empty
  checks = the rubber stamp. With real checks it would be fine.

## 4. Verdict

| component | correct things captured? | assessment |
|---|---|---|
| envmap_builder (structured criteria) | no (by construction) | misses extractable artifacts/thresholds/schema |
| EvalIndexer (authoritative checks) | no (0/10) | regex-only; correctly avoids grader-peek but finds nothing |
| ObjectiveGraphBuilder (deliverables) | 1/10 | regex too brittle for natural phrasing |
| CompletionGate (logic) | yes | correct checks; starved of inputs → vacuous |
| build_architect_request (structure) | yes | well-formed but near-empty payload |
| ARCHITECT/SOLVER prompts | yes | on-target; check_plan↔eval_index coupling makes exec-verification unreachable |
| grader-peek safety | yes | scans workspace, not task dir — invariant held |

**Bottom line:** the deterministic verification and first-step capture did **not** capture
the correct things — not because the design is wrong (the gate and prompts are sound) but
because the **extractors that feed them are too weak**. Every task prompt contains explicit,
deterministically-extractable acceptance criteria (named output files, size/accuracy
thresholds, JSON field schemas); the current code catches ~1/10. Fixing extraction is the
unlock: it makes the gate real, gives the solver a concrete "done," and feeds the architect
genuine scaffolding — all without ever touching the hidden grader.

## 5. Concrete fixes (deterministic layer)

1. **Robust deliverable extraction**: replace `_PROMPT_DELIVERABLE_RE` immediate-adjacency
   matching with a path-scanner that pulls any `/app/...ext` or quoted `"…ext"` /
   `` `…ext` `` token in the prompt, attributed to a create/write/save/output verb anywhere
   in the sentence. Would take 9/10 → ~9/10 here.
2. **Threshold extraction** from prose: patterns like `≥/at least/<\s*N\s*(MB|%|accuracy)`
   → `MetricThreshold`. Captures train-fasttext deterministically.
3. **Output-schema extraction**: when the prompt enumerates JSON fields ("x0, gamma,
   amplitude, offset") and names a `.json` target, populate `output_schema` +
   `output_schema_target` so the gate's existing schema check fires.
4. **Existence checks for captured deliverables**: the gate already blocks on
   `missing_artifacts` — once deliverables are captured, `[ -f /app/filter.py ]`-style
   existence/parse checks become real (and are not grader-peeking).
5. **Wire `proof_plan` → executable assertions**: let the architect's proof obligations be
   compiled into shell checks the gate runs, so the model's own success criteria are
   enforced (decouples executable verification from the empty eval_index).
6. **Tighten the prompt coupling**: allow the architect to author `check_plan` commands
   (not only eval_index ids), validated as safe local assertions.
