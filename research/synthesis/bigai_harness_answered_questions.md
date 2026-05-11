# BigAI Answered Questions

Generated from the BigAI post-hoc trace layer. Confidence labels distinguish observation, strong synthesis, partial answers, and irrecoverable gaps.

## Observable Architecture
Confidence: observed
Addresses:
- ARCH-01 Is the observable harness consistently planner, executor, verifier, or are there role variants? [answered]
- ARCH-02 Does every parseable run start with planner activity before executor activity? [answered]
- ARCH-07 Are there any role-boundary violations, like planners doing executor work? [answered]
Why: The corpus shows a stable observable role protocol rather than ad hoc single-agent behavior.
Evidence:
- Observed role set across parseable runs: Executor/executor-0, Executor/executor-1, Executor/executor-2, Executor/executor-3, Executor/executor-4, Planner/default, Verifier/verifier-0.
- 312/312 parseable runs show planner-before-executor ordering. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:3 / step:5.
- Planner almost never performs executor-style tool work directly; the only observed planner operational outlier is one `run_command` call. Citations: [private-source: trajectory]/BigAI/torch-tensor-parallelism/0aea45fe-4938-45ae-9f64-b59d6ebc1182.tar.gz::step:34:tool:0.
Counterevidence / ambiguity:
- This is an observable role contract, not proof of hidden controller implementation details.
Unknowns:
- True internal scheduler logic and hidden branches remain unknown.

## Verifier Presence And Absence
Confidence: observed
Addresses:
- ARCH-03 How often is verifier present, and in which tasks is it absent? [answered]
Why: Verifier presence is directly countable and strongly associated with successful parseable runs.
Evidence:
- Verifier is present in 272/312 parseable runs.
- Verifier is present in 247/255 parseable passes, but only 21/52 parseable fails.
- Verifier-absent tasks are concentrated in timeout-heavy and hard tasks such as caffe-cifar-10, make-doom-for-mips, mteb-leaderboard, qemu-startup, torch-pipeline-parallelism, and train-fasttext.
Counterevidence / ambiguity:
- Presence does not guarantee final success; verifier-absent runs can still pass and verifier-present runs can still fail.
Unknowns:
- Verifier absence may reflect truncation, timeout, or controller policy; the corpus cannot fully distinguish them.

## Executor Fanout And Branching
Confidence: strong_inference
Addresses:
- ARCH-04 How many executors are actually used per run? [answered]
- ARCH-05 Are multi-executor runs associated with harder tasks, failures, or recovery loops? [answered]
- ARCH-06 Is there evidence of true branching behavior, or only sequential reassignment? [partial]
Why: Executor ids, end_execution events, and recovery loops show branching support, but not true concurrency internals.
Evidence:
- Single-executor runs: 189. Multi-executor runs: 123. Max observed executor fanout: 5.
- Single-executor parseable runs succeed at 0.878; multi-executor parseable runs succeed at 0.724. This suggests harder tasks are more likely to branch.
- Direct executor-to-executor coordination is rare; only one run uses the explicit `ask` tool. Citations: [private-source: trajectory]/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08.tar.gz::step:108-119.
Counterevidence / ambiguity:
- Branching is observable through multiple executor ids, but the traces do not prove true parallel execution.
Unknowns:
- Internal queueing, scheduling, and branch cancellation remain hidden.

## Early Planning
Confidence: observed
Addresses:
- PLAN-01 What does the planner do before first meaningful progress? [answered]
- PLAN-02 How early does the planner save the first plan? [answered]
Why: The harness consistently plans before handing work to executors.
Evidence:
- First `save_plan` appears at step 3 in 310 runs and step 4 in 2 runs.
- In practical terms, every parseable run is planner-first before the first executor branch starts. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:3 / step:5.
Unknowns:
- This shows ordering, not the hidden reasoning process behind the first plan.

## Planning Dynamics
Confidence: strong_inference
Addresses:
- PLAN-03 What is the first-plan style by task: safety-first, test-first, setup-first, exploration-first, direct-action? [answered]
- PLAN-04 How granular are planner todos? [answered]
- PLAN-05 How often does the planner update the plan after executor feedback? [answered]
- PLAN-06 What kinds of events trigger replanning? [answered]
- PLAN-07 How often does the planner mark task_finished=true before verification completes? [answered]
- PLAN-08 How often does the planner collapse multiple todos into one executor completion via extra_finished_todo_indexes? [answered]
Why: Plan styles, replan counts, and task-finished markers are visible enough to reconstruct broad planning doctrine.
Evidence:
- Initial plan styles across parseable runs: {"direct_action": 30, "exploration_first": 97, "safety_first": 31, "setup_first": 100, "test_first": 54}.
- Median initial todo count is 4.0, with mean 3.86 and range 1-8.
- 297/312 parseable runs replan at least once; average replan count is 1.62.
- 258/258 runs with `finish_verification` mark `task_finished=true` before the last verifier finish event.
- 249 runs and 262 `end_execution` calls use `extra_finished_todo_indexes`, showing executors can opportunistically close multiple todos.
Counterevidence / ambiguity:
- Todo granularity is visible, but exact hidden planner criteria for todo splitting are not.
Unknowns:
- Replan triggers can be inferred from patterns like failed shell commands and verifier failures, but the hidden trigger policy remains unobserved.

## Handoff Structure And Context
Confidence: strong_inference
Addresses:
- ORCH-01 What is the exact observable planner-to-executor handoff structure? [answered]
- ORCH-02 Does the executor always receive task, plan, and task history? [answered]
- ORCH-03 What does the verifier receive that executors do not? [answered]
- ORCH-04 How often do executor-to-executor interactions happen? [answered]
- ORCH-05 Are executor branches reused after verifier failure? [answered]
- ORCH-06 Do some tasks produce repeated planner-executor-verifier cycles while others stay linear? [answered]
- ORCH-07 Is the harness more serialized or more branch-heavy across the corpus? [answered]
- ORCH-08 Are there task clusters where planner handoff quality appears stronger or weaker? [partial]
- CTX-01 What context is visibly packaged into executor prompt packets? [answered]
- CTX-02 What context is visibly packaged into verifier prompt packets? [answered]
- CTX-03 Does task history appear to accumulate cleanly across replans? [answered]
- CTX-04 Are there signs of context loss, forgetting, or reintroduction? [partial]
- CTX-05 Does the planner summarize prior work compactly or redundantly? [answered]
- CTX-06 Does verifier feedback get folded back into later plans cleanly? [answered]
Why: Prompt packets reveal a stable handoff contract and partial memory packaging policy.
Evidence:
- Executor packet coverage across parseable runs: task 312/312, plan 312/312, task_history 123/312, basic_env_info 312/312.
- Verifier packet coverage across parseable runs: task 272/272 verifier runs, basic_env_info 272/272.
- Task history is common but not universal, which means executor context packaging is structured but not fully fixed. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::run, [private-source: trajectory]/BigAI/regex-log/c95c9d0b-5e53-4349-8ed6-92fd45596148.tar.gz::step:5.
- 66/312 parseable runs show repeated verifier cycles, indicating planner-executor-verifier loops rather than strictly linear runs.
Counterevidence / ambiguity:
- The corpus shows rendered packets, not the hidden prompt assembler or any compressed context that was omitted.
Unknowns:
- Context loss, forgotten branches, and retrieval policy remain only weakly inferable.

## Tool Surface
Confidence: observed
Addresses:
- TOOL-01 What tools are actually used across the corpus? [answered]
- TOOL-02 Which tools are role-specific versus shared? [answered]
- TOOL-03 Which tools dominate successful runs? [answered]
- TOOL-04 Which tools correlate with failure-heavy runs? [answered]
- TOOL-05 What are the most common shell-command intents: discovery, setup, execution, test, cleanup, backup? [answered]
- TOOL-06 How often are long-running shell processes used? [answered]
- TOOL-07 How often are waits, kills, or interactive shell sessions needed? [answered]
- TOOL-08 How often are multimodal or batch LLM tools used? [answered]
Why: Tool usage is richly logged and role separation is visible in the tool surface itself.
Evidence:
- Tool call counts: {"ask": 1, "call_llm_batch": 14, "end_execution": 416, "finish_verification": 334, "interact_with_shell": 78, "kill_shell_command": 128, "read_file": 19, "read_media": 128, "replace_file": 29, "run_command": 1, "run_shell_command": 17286, "save_plan": 818, "wait_shell_command": 810, "write_file": 115}.
- Long-running shell control is real: 810 waits, 128 kills, and 78 interactive shell calls.
- Multimodal and auxiliary LLM use is sparse but real: media-tagged runs 21, batch-tagged runs 8.
- Planner is mostly limited to `save_plan`; verifier owns `finish_verification`; shell operations are dominated by executors and verifier.
- Tool/result correlations are suggestive rather than causal: backup-tagged runs succeed at 32/34, while tty-tagged runs succeed at 4/9.
Counterevidence / ambiguity:
- Tool correlations are confounded by task difficulty and task type.
Unknowns:
- The tool wrapper implementation itself is still hidden.

## Discovery Patterns
Confidence: strong_inference
Addresses:
- DISC-01 What reconnaissance steps are usually performed first? [answered]
- DISC-02 How often does the agent inspect the repository before acting? [answered]
- DISC-03 How often does it inspect environment or dependency state before coding? [answered]
- DISC-04 How often does it look at tests or output files before implementation? [answered]
- DISC-05 Which tasks get heavy discovery and which get almost none? [answered]
Why: The corpus shows near-universal discovery behavior before implementation, even when plan styles differ.
Evidence:
- Discovery-tagged runs: 312/312 parseable runs.
- Setup-tagged runs: 138/312 parseable runs.
- Typical early moves are repository inspection, environment probing, dependency checks, and only then implementation or testing.
Counterevidence / ambiguity:
- The trace layer can see discovery commands, but not unlogged internal orientation reasoning.
Unknowns:
- Discovery intensity varies, but the corpus lacks a precise formal taxonomy for task families.

## Debugging And Search
Confidence: strong_inference
Addresses:
- DEBUG-01 Does BigAI debug empirically or mostly reason in text? [answered]
- DEBUG-02 How often does it create minimal repros, throwaway scripts, or experiments? [answered]
- DEBUG-03 How often does it switch tactics after a failed attempt? [answered]
- DEBUG-04 Are failed branches abandoned cleanly or revisited repeatedly? [partial]
- DEBUG-05 Which task clusters show the best search discipline? [partial]
- DEBUG-06 Which failures look like stuckness versus hard task limits? [answered]
Why: BigAI is much more empirical than purely textual: it uses shells, tests, retries, and verifier loops to search the space.
Evidence:
- Median step count is 59 for parseable passes versus 84.5 for parseable fails.
- Median shell error count is 3 for passes versus 7.5 for fails.
- Repeated plans, shell failures, and verifier retries indicate hypothesis-test-refine behavior rather than pure armchair reasoning. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:57-71.
Counterevidence / ambiguity:
- Minimal repros and discarded branches are only partially visible because hidden branches are not logged.
Unknowns:
- Search-discipline comparisons by task cluster remain moderate rather than high confidence.

## Verification Regime
Confidence: strong_inference
Addresses:
- VER-01 What exactly does verifier check, based on visible commands and checklists? [answered]
- VER-02 Is verifier behavior standardized across tasks? [answered]
- VER-03 How often does verifier only run once versus multiple times? [answered]
- VER-04 How often does verifier catch real issues after apparent completion? [answered]
- VER-05 What kinds of failures does verifier catch: wrong output, leftover artifacts, broken tests, state corruption? [answered]
- VER-06 How often does verifier pass runs that still later fail overall? [answered]
- VER-07 How often does verifier never appear in failed runs? [answered]
- VER-08 Is final stopping more verifier-gated or planner-gated in practice? [answered]
Why: Verification is standardized enough to reconstruct a real verifier regime, not just ad hoc checking.
Evidence:
- Verification status counts across finish_verification calls: {"FAILED": 68, "PASSED": 261, "STEPS_EXHAUSTED": 5}.
- Verifier cycles per run: one-shot 192, multi-cycle 66, no finish_verification 54.
- Top checklist families recur heavily; the largest three checklist templates account for 286 finish_verification calls.
- 63 runs show verifier failure; 57 of those later recover to a passing verifier state.
- 17 parseable runs contain a verifier `PASSED` status sequence but still end with a failed overall result, so verifier pass is not identical to final reward success.
- Verifier explicitly checks side effects and often delivery-directory cleanliness. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:57-71, [private-source: trajectory]/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53.tar.gz::verifier/ctrf.json.
Counterevidence / ambiguity:
- Verifier outputs show what was checked, but not the hidden verifier controller policy or all possible rejected branches.
Unknowns:
- Some failed runs never reach visible verifier completion, especially timeout-heavy ones.

## Safety And Discipline
Confidence: strong_inference
Addresses:
- SAFE-01 How often does the agent back up state before risky actions? [answered]
- SAFE-02 Which task clusters trigger explicit backup or isolation behavior? [answered]
- SAFE-03 How often does verifier care about workspace cleanliness or side effects? [answered]
- SAFE-04 How often does the agent clean up debug artifacts before finish? [answered]
- SAFE-05 Does the agent show restraint on destructive operations? [answered]
- SAFE-06 Are stateful recovery tasks handled differently from ordinary coding tasks? [answered]
Why: Safety behavior is observable and strongest on stateful tasks.
Evidence:
- Backup-tagged runs: 34 total, with 32/34 parseable successes.
- Delivery-directory cleanliness appears in 162 finish_verification checklists and side-effect safety appears in 312.
- Stateful recovery tasks such as db-wal-recovery, password-recovery, sqlite-db-truncate, git-leak-recovery, and sanitize-git-repo visibly bias toward safety-first or backup-aware behavior. Citations: [private-source: trajectory]/BigAI/db-wal-recovery/47f2454e-2528-4427-94c8-6b13f8c63f53.tar.gz::step:1-20, [private-source: trajectory]/BigAI/password-recovery/7262df7d-2192-4a5e-b98d-c2509973e8a9.tar.gz::run.
- The clearest cleanup loop is verifier-driven rather than purely executor-driven. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:57-71.
Counterevidence / ambiguity:
- The traces show discipline and cleanup, but they do not prove absence of all destructive side effects.
Unknowns:
- Workspace diffs are missing, so safety assessment is limited to logged commands and verifier findings.

## Recovery And Adaptation
Confidence: strong_inference
Addresses:
- REC-01 How often do verifier failures lead to successful recovery? [answered]
- REC-02 What does a typical failure-recovery loop look like? [answered]
- REC-03 How many replans are typical before recovery succeeds? [answered]
- REC-04 Are recovery tactics mostly cleanup, reimplementation, or extra testing? [answered]
- REC-05 Which tasks show sophisticated adaptation versus shallow retries? [answered]
- REC-06 Which failure modes almost never recover? [answered]
Why: Recovery is one of the clearest observable harness doctrines in the corpus.
Evidence:
- Runs with verifier failure: 63. Recovered to final verifier pass: 57 (0.905).
- Recovered runs have median replan count 3 and mean 3.33.
- Typical loop: planner marks progress, verifier rejects on tests or side effects, planner replans, executor fixes or cleans, verifier reruns. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:57-71, [private-source: trajectory]/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08.tar.gz::step:108-144.
- Nonrecovering failure modes skew toward timeout-heavy and systems-heavy tasks such as torch-pipeline-parallelism, train-fasttext, gpt2-codegolf, make-doom-for-mips, and qemu-startup.
Counterevidence / ambiguity:
- Recovery sophistication is visible behaviorally, but the hidden retry policy remains unobserved.
Unknowns:
- Abandoned internal tactics that never surfaced in the trace are irrecoverable.

## Stopping And Termination
Confidence: strong_inference
Addresses:
- STOP-01 What does end_execution actually mean behaviorally? [answered]
- STOP-02 When does an executor terminate relative to planner updates? [answered]
- STOP-03 When does the planner decide the task is done? [answered]
- STOP-04 When does verifier run relative to planner completion claims? [answered]
- STOP-05 Are there recognizable stopping doctrines across successful runs? [answered]
- STOP-06 Are failures often due to no stopping signal, bad stopping signal, or timeout? [answered]
Why: Stopping is multi-layered: executor branches stop locally, planner claims task completion, verifier may still audit afterward.
Evidence:
- `end_execution` is local to executor branches, with 416 observed calls and 262 calls carrying extra_finished_todo_indexes.
- 272 parseable runs include an explicit planner `task_finished=true` signal.
- 258/258 runs with visible finish_verification place the planner done signal before the last verifier finish event.
- Timeouts dominate visible explicit exception modes: 61 timeout exceptions across AgentTimeoutError and VerifierTimeoutError.
Counterevidence / ambiguity:
- Global stopping policy cannot be reconstructed exactly from end_execution alone.
Unknowns:
- The corpus does not expose hidden stop heuristics or cancellation logic.

## Success And Failure Patterns
Confidence: strong_inference
Addresses:
- OUT-01 Which observable behaviors correlate most strongly with success? [answered]
- OUT-02 Which observable behaviors correlate most strongly with failure? [answered]
- OUT-05 Are longer runs generally better, or just more stuck? [answered]
- OUT-06 Do multi-executor runs outperform single-executor runs? [answered]
- OUT-07 Do verifier-heavy runs outperform verifier-light runs? [answered]
- OUT-08 Are timeout failures concentrated in specific task types? [answered]
Why: The strongest outcome signals are verifier presence, timeout concentration, run length, shell-error burden, and task difficulty proxies.
Evidence:
- Verifier-present parseable runs succeed at 0.908 versus 0.2 for verifier-absent parseable runs.
- Single-executor parseable success rate is 0.878 versus 0.724 for multi-executor runs; likely a task-difficulty effect rather than a pure fanout penalty.
- Median step count: passes 59, fails 84.5, unknown 102.
- Median shell-error count: passes 3, fails 7.5.
- Timeouts cluster on a small set of hard tasks: [('torch-pipeline-parallelism', 5), ('train-fasttext', 4), ('gpt2-codegolf', 4), ('caffe-cifar-10', 4), ('tune-mjcf', 3), ('make-doom-for-mips', 3), ('query-optimize', 3), ('filter-js-from-html', 3), ('raman-fitting', 3), ('path-tracing', 2)]. Citations: [private-source: trajectory]/BigAI/query-optimize/08183f0c-2f59-44ef-a14d-43494a1a2d09.tar.gz::result.json / exception.txt.
Counterevidence / ambiguity:
- Correlations are real but not causal; task mix is a major confound.
Unknowns:
- The corpus does not provide normalized difficulty labels.

## Task Clusters And Rhythm Breakers
Confidence: moderate_inference
Addresses:
- OUT-03 What is the success rate by task cluster? [partial]
- OUT-04 What is the failure rate by task cluster? [partial]
- DOCT-03 Which task clusters induce safety-first planning? [answered]
- DOCT-04 Which task clusters induce test-first behavior? [answered]
- DOCT-05 Which task clusters induce exploration-heavy search? [answered]
- DOCT-06 Which tasks break the normal planner-executor-verifier rhythm? [answered]
Why: Cluster-level answers are possible only at a coarse, behavior-based level because the corpus has no formal task taxonomy.
Evidence:
- Safety-first patterns cluster around stateful recovery tasks: db-wal-recovery, password-recovery, sqlite-db-truncate, git-leak-recovery, sanitize-git-repo, and some cobol-modernization runs.
- Test-first patterns show up in regex, filter, vulnerability-fix, polyglot, and some correctness-sensitive implementation tasks.
- Exploration-first patterns dominate broad search or analysis tasks such as cryptanalysis, dataset counting, path-tracing, MTEB tasks, and some media-heavy tasks.
- Rhythm breakers include provenance-only runs, runs with no visible verifier completion, timeout-heavy systems tasks, and the single direct executor-to-executor ask run. Citations: [private-source: trajectory]/BigAI/gcode-to-text/dbe74a7d-ff87-450f-94f7-72bdf5e6dba8.tar.gz::agent/trajectory.json, [private-source: trajectory]/BigAI/video-processing/a23553a3-e08e-43cf-bf9f-ef8146237a11.tar.gz::agent/trajectory.json, [private-source: trajectory]/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08.tar.gz::step:108-119.
Counterevidence / ambiguity:
- These cluster labels are analyst-imposed and should be treated as coarse behavior groupings, not official benchmark families.
Unknowns:
- Without official task source, some family distinctions remain approximate by design.

## Observable Doctrine Versus Hidden Mechanism
Confidence: strong_inference
Addresses:
- HIDE-01 Which repeated behaviors look controller-driven rather than model-habit-driven? [answered]
- HIDE-02 Which behaviors vary enough that they are probably task-conditioned rather than hardcoded? [answered]
- HIDE-03 Does the stable handoff format imply strong controller packaging policy? [answered]
- HIDE-04 Does planner-first sequencing imply a real orchestration contract? [answered]
- HIDE-05 Does verifier recovery suggest explicit controller retry logic? [answered]
- HIDE-06 Where is the boundary between observable doctrine and hidden mechanism? [answered]
Why: Some behaviors are stable enough to attribute to controller policy, while others clearly vary by task.
Evidence:
- Likely controller-driven motifs: stable role set, planner-first ordering, prompt packet structure, planner dominance over save_plan, verifier ownership of finish_verification, and explicit recovery loops after verifier failure.
- Likely task-conditioned motifs: initial plan style, executor fanout, media/batch/tty usage, safety intensity, and whether the run remains mostly linear or branches heavily.
- The stable handoff format strongly suggests controller-level context packaging rather than incidental model habit. Citations: [private-source: trajectory]/BigAI/adaptive-rejection-sampler/c05344ea-9a06-490d-9310-937670fb7b4a.tar.gz::step:5 / run, [private-source: trajectory]/BigAI/regex-log/c95c9d0b-5e53-4349-8ed6-92fd45596148.tar.gz::step:5.
Counterevidence / ambiguity:
- This is still behavioral reconstruction, not source-level proof of controller code.
Unknowns:
- Scheduler logic, prompt assembly internals, and memory-manager implementation remain hidden.

## Stable And Variable Doctrines
Confidence: strong_inference
Addresses:
- DOCT-01 What motifs are stable enough to treat as true harness doctrine? [answered]
- DOCT-02 What motifs are clearly task-dependent? [answered]
Why: The trace layer is strong enough to separate stable harness doctrine from task-conditioned variation.
Evidence:
- Stable doctrines: planner-first execution, explicit role separation, heavy shell-based empirical work, verifier as an external audit role, frequent replanning, and recurring side-effect checks.
- Variable doctrines: plan style, safety intensity, media/batch use, executor fanout, verifier presence on hardest runs, and how many verification cycles a run needs.
- Safety-first planning has the highest raw success rate in the current corpus snapshot (29/31), but that almost certainly reflects task mix as well as good discipline.
Counterevidence / ambiguity:
- Stable doctrine is observable; hidden mechanism behind it is still partly unknown.
Unknowns:
- Per-family doctrine claims beyond coarse behavioral groupings remain moderate rather than high confidence.

## Irrecoverable Gaps
Confidence: unknown
Addresses:
- GAP-01 Which harness questions remain impossible without true control-plane traces? [irrecoverable]
- GAP-02 What exact traces are missing for scheduler observability? [irrecoverable]
- GAP-03 What exact traces are missing for memory/context observability? [irrecoverable]
- GAP-04 What exact traces are missing for workspace-state observability? [irrecoverable]
- GAP-05 What exact traces are missing for prompt-construction observability? [irrecoverable]
- GAP-06 What exact traces are missing for branch pruning and hidden retries? [irrecoverable]
Why: Several high-value harness questions remain irrecoverable without true control-plane traces.
Evidence:
- Scheduler observability needs explicit assign, queue, cancel, retry, and parent/child branch trace events.
- Memory observability needs prompt-fragment provenance, context compaction records, retrieval decisions, and shared-memory diffs.
- Workspace observability needs per-step file diffs or filesystem snapshots, not just final verifier outputs.
- Prompt observability needs full rendered prompts plus hidden scaffold provenance, not only recorded visible packets.
- Branch observability needs discarded-branch logs, hidden retries, and branch-pruning events.
Counterevidence / ambiguity:
- The post-hoc trace layer can reconstruct observable doctrine, but it cannot recreate hidden control-plane state.
Unknowns:
- Two provenance-only bundles lack JSON trajectory content entirely.

