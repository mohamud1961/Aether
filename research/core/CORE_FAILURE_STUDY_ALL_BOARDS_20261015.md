# Failure study across all local TB 2.1 boards (15 October 2026)

Asked for by the principal ("widen the failure study first: classify wrong finishes across all our TB 2.1 boards").
Offline, no model calls. Index: `tools/aether_program/core_failure_index.py` over every local evidence archive
(B1, T1, S4–S6, L0–L2, N1 a3/p2, N2; N1 p1 is VM-only). Infra-invalid rows dropped; fixed-state benches (A1, R1,
Q1, S1–S3, J1) excluded. **221 solver runs, 9 development tasks** (held-out tasks untouched). Model identity is taken
from the call logs (`response_model`), not launcher labels: L0–L2 rows are labelled GLM by the launcher but called
GPT-6-Luna. Grader assertions are read from each trial's `test-stdout.txt`.

## Pass rates by task and model (same harness family, same task text)

| Task | GLM 5.3 Flash (Aether) | GPT-6-Luna (Aether) | GLM (Terminus) |
|---|---|---|---|
| net-fit | **1/12** (11 wrong finishes) | **22/22** | 1/2 |
| binary-extract | **11/12** | **0/14** (14 wrong finishes) | 2/2 |
| construct-assembly | 2/11 (8) | 1/13 (10) | 0/2 |
| seq-assembly | 0/11 (6) | 5/17 (12) | 0/2 |
| graph-query-catalog | 7/12 (5) | 11/12 (1) | 2/2 |
| credential-recovery-recovery | 10/12 (2) | — | 1/2 |
| cipher-diff-attack, repair-history, dual-language-build | 33/36 (0) | 19/19 | 5/6 |
| **Total** | **64/106, 33 wrong finishes** | **58/97, 37 wrong finishes** | 11/18 |

## Where the 70 Aether wrong finishes are

**Four tasks hold 61 of 70 (87%)**: construct-assembly 18, seq-assembly 18, binary-extract 15, net-fit 11. Remaining: graph-query-catalog 6, credential-recovery 2.
Non-finishes (timeouts, no output) are separate: about 13 rows, mostly GLM on seq-assembly/protein/feal.

## What they fail on (grader assertions)

| Task | Grader assertion (count) | Type |
|---|---|---|
| net-fit (GLM) | Learned DAG ≠ expected: 8 with the whole DAG reversed (rows written parent-first under the task's `to,from` header), 4 with one edge flipped (R→M vs M→R; the task states the tie-break rule) | **Explicit instruction misread** (format column order; stated tie-break) |
| binary-extract (GPT-6-Luna) | 0.00% of expected values (12, plus 2 without an E line): rebased to 0x400000 | **Unstated convention + example taken as content** (upstream issue #194) |
| construct-assembly (both) | "order flag–donor–dhfr–acceptor–snap" (15), start ≠ FLAG (1): the antibody target (FLAG) and/or the benzylguanine binder (SNAP) not identified, or sequences not those components | **Domain inference** |
| seq-assembly (both) | pair Tm > 5 °C with matching overhang bases counted (5), BsaI site missing (4), clamp before BsaI (3), reverse primer site (2), assembly ≠ output (1), Tm range (1) | **Domain design rules** (Golden Gate primer design) |
| graph-query-catalog (GLM 5, GPT-6-Luna 1) | query results ≠ reference | Semantic (not yet classified further) |

## Findings

1. **Outcomes are nearly deterministic per (model, task).** GPT-6-Luna: binary-extract 0/14 across L1, L2, N1, N2 and
   every arm; GLM: net-fit 1/12 across B1, S4, S5, S6 and every arm. Prompt arms, ledgers, reasoning settings did not move
   them. Resampling or retrying the same model will not fix these tasks.
2. **The two "reading" failures are model-specific and flip between models.** On net-fit, GLM misreads and GPT-6-Luna is
   right 22/22; on binary-extract, GPT-6-Luna imports the example's convention and GLM is right 11/12. Same text, same
   harness: the reading is a model prior. This is why same-model checks, verifiers and judges confirm it (N1 smokes,
   Q1-R, J1): they share the prior. **A second model disagrees exactly here.**
3. **The two "domain" failures are shared by both models** (construct-assembly, seq-assembly). A second model would not catch them; it
   has the same gap. These need evidence acquisition (looking the fact up, aligning the sequence) or knowledge the
   model lacks.
4. Execution failures (timeouts, missing outputs) are a separate, smaller class, mostly GLM.

## What this implies (for discussion, nothing built)

- Two different problems with different remedies: **model-prior misreadings** (cross-model disagreement is a
  measurable signal; testable offline-cheaply by asking the other model for its reading of the same requirement)
  and **shared domain gaps** (no reader helps; only an observation that settles the fact).
- A dev board of 9 tasks is too small and too correlated to tune on: 4 tasks dominate, one is a benchmark defect.
  Any lever must be judged on held-out or new tasks, with the per-(model, task) determinism in mind.

Limits: 221 rows are not independent (same 9 tasks, repeated). graph-query-catalog and the "no E line" rows are not classified
further. N1 p1 rows are not in the local archives.

## Offline cross-model disagreement test (same day; user: "test cross-model disagreement offline on saved data")

No model calls. Final artifacts are not archived, so each run's decisive answer is reconstructed from its own tool
outputs (never the grader): net-fit = the six-edge set as last printed under its `to,from`/`from,to` header; binary-extract
= whether the printed output keys start at ≥ 0x400000; construct-assembly = antigen and molecule-binder names in the finish
summary. A run is **flagged** when its answer differs from the other model's majority answer. Script:
`tools/aether_program/core_cross_model_offline.py`. Not pre-registered (exploratory, free).

| Task | Wrong finishes flagged | Right finishes flagged | Unscored |
|---|---|---|---|
| net-fit | **9/11** (2 unflagged GLM runs have the correct DAG and fail another test) | 1/17 | 4 |
| binary-extract | **13/13** (all GPT-6-Luna) | **6/6** (every scored GLM pass) | 5 |
| construct-assembly | 15 flagged, but inconclusive (below) | — | 3 |

- **Disagreement finds the disputed readings almost perfectly** (net-fit 9 of the 9 reading failures; binary-extract 13/13).
- **It cannot say which side is right.** On binary-extract every correct GLM run is flagged too: the dispute is
  symmetric. As a gate it would hold correct work of whichever model is right; as a trigger it says only "this
  decision is contested, settle it".
- **construct-assembly: the feature is too crude**, and it overturns a claim: GLM names FLAG and SNAP in 9 of 10 finish
  summaries yet fails 8, so GLM's construct-assembly failures are *not* antigen identification (sequence or component choice,
  not yet classified). GPT-6-Luna's summaries mostly do not name them. The earlier "domain inference for both models"
  is withdrawn for GLM.
- Live use would need the second model's answer on the decisive decision. A full second solve doubles cost; a
  cheaper form (ask the other model only for its reading of the contested choice) is untested.
