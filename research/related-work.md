# Related work

How the findings sit against published work on agent harnesses and agent evaluation. Each row says where
this programme agrees with the field and what it adds.

| Finding | Related work | Agreement | What this programme adds |
|---|---|---|---|
| Cheaper calls made trajectories more expensive | HAL (cost-aware, multi-harness agent evaluation); work on context degradation in long inputs; published guidance on context engineering for agents | Cost belongs on the leaderboard; long contexts degrade | Direct evidence that per-call savings (−29% prefix) can raise whole-trajectory cost (+56% calls), so context changes must be judged per trajectory |
| A pre-registered falsifier fired on our own harness | Pre-registration practice in empirical science; calls for error bars and statistical rigour in LLM evals | Claims should be stated before the data | A sealed harness-versus-stock comparison on held-out tasks, with the negative result kept |
| A completion verifier needs its own evaluation | LLM-as-judge studies (position, verbosity and self-preference biases); reward-model benchmarks for chat | Judges are biased and must be calibrated | Calibration of *agentic completion* verifiers: catch rate and false-hold rate on 377 graded finishes, not chat preferences |
| Most measured wins were measurement artefacts | The Agentic Benchmark Checklist (task and outcome validity flaws in major agent benchmarks); reports of reward hacking by frontier agents | Many agent benchmarks pass wrong or empty answers | A catalogue of failure types in one's *own* measurement stack (rate-limit storms, launch failures, grader leaks, sampling defaults, parsing bugs) and the controls that catch them |
| Review without the agent's claims catches more | Studies of sycophancy and of models deferring to stated reasoning | Models are swayed by persuasive context | A direct ablation on agent finishes: 15/18 caught without claims vs 10/18 with them |

## Evaluation design

| Practice | Field reference | Here |
|---|---|---|
| Reliability over attempts | τ-bench (pass^k) | Invalid-row accounting first, then repetition |
| Task realism | Terminal-Bench, SWE-bench Verified, METR task suites | Small tasks, deliberately messy: decoys, stale docs, indirection, injected instructions |
| Grader validity | Agentic Benchmark Checklist | Every grader proven against known-bad states, five careless agents and a solvability check |
| Standard runners | Inspect, Harbor | Tasks export to Inspect; Harbor trial results import into the same statistics |
| Agent–computer interface | SWE-agent's interface design | Interface defects found by trajectory audit ([run-loop engineering](run-loop-engineering.md)) |

## Open questions this work leaves

1. Do harness gains shrink as models get stronger? The programme's own principle predicts they should for
   anything that is a crutch, but it was not measured across model tiers.
2. How far does claim-free review generalise beyond 18 cases?
3. Can process faithfulness (did the agent actually run the check it reports) be graded automatically
   from traces at scale?
