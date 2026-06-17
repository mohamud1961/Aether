# Raw Ledger Update

- recorded_at_utc: 2026-05-30T01:51:28.298758+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: codex
- task: verify Terminus bash-only claim and update whole-harness winner criteria
- event_type: source_analysis
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 8cfaf9da99487a7cbf54b00fa114df6c637f4f4d089cf86ac12718318882948d
- commit_message: NONE - no tracked file changes
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-05-30/015128_codex_verify-terminus-bash-only-claim-and-update-whole-harness-winner-criteria_8cfaf9da99.md

```text
RAW_LEDGER_UPDATE
- actor: codex
- task: verify Terminus bash-only claim and update whole-harness winner criteria
- event_type: source_analysis
- summary: Verified that the local baseline uses a single raw_bash tool through flat_loop, and external Terminus/Terminus-2 references describe a mono-tool interactive terminal/tmux design. Clarified that bash-only means the agent action surface, while the harness still needs sandbox, workspace, verification, trace capture, recovery, context, and budget-control layers.
- observations: blocks/tools/raw_bash.py exposes only raw_bash with a command argument; blocks/execution/flat_loop.py repeatedly sends model tool calls to available tools until no tool calls or step budget exhaustion. Repo run headers and route manifests repeatedly record tools=raw_bash and execution=flat_loop. External Terminus docs state Terminus has a single interactive tmux/headless terminal tool and completes tasks using bash/terminal commands. Current final-suite failures show raw bash is sufficient for some repo/file tasks but insufficient alone without stronger service readiness, typed action receipts, recovery, verification gates, and context state capsules.
- inference: The best next harness should keep a Terminus-like single terminal primitive as the base but wrap it with small swappable mechanisms for dependency discovery, typed command recipes, verifier-before-final, bounded recovery, context/evidence capsules, and token/step controllers. Do not equate bash-only with no harness intelligence.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/blocks/tools/raw_bash.py; /Users/mohamud/Downloads/harnesseng/blocks/execution/flat_loop.py; /Users/mohamud/Downloads/harnesseng/project_reset_operating_model.md; https://harborframework.com/docs/agents/terminus-2; https://www.tbench.ai/news/terminus; https://openreview.net/pdf/574281303882f822808ab57ac3a57a2bddfbc7a3.pdf
- affected_components: blocks/tools/raw_bash.py; blocks/execution/flat_loop.py; tracking/collab/variant_hypothesis_backlog.md; final_harness_eval_suite interpretation
- decision_change: Treat raw_bash/terminal-only as acceptable base architecture for TerminalBench, but require harness-side recovery, verification, context, service, and efficiency mechanisms before rerun/promotion.
- unresolved_questions: Which subset of the recommended mechanisms gives the best net score/cost tradeoff on the next mini-only certified run; whether benchmark rows should remain known-bad controls or be switched to solvable model-attempt mode.
- confidence: high
- commit_message: NONE - no tracked file changes
```
