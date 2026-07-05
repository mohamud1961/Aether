# Automatic Memory + Verifier Replay Slice Audit

Date: 2026-07-01

## Scope

Implemented a bounded diagnostic slice after the architect-as-skill work:

- close the remaining architect-only 10/10 prompt/config gaps with narrow live architect runs;
- add automatic memory repeat-collision evidence for repeated file/command/check/write actions;
- remove live runtime instructions that made `query_memory` a solver ritual;
- expose automatic-memory findings in solver context and verifier packets;
- add a verifier-prompt replay diagnostic comparing generic vs architect-authored verifier prompts;
- validate with deterministic tests and fake verifier evals only.

Out of scope: full benchmark runs, fresh task attempts, VM/Azure boards, promotion claims.

## Code Changes

- `aether_next/automatic_memory.py`
  - New generic target inference and repeat-collision receipt helper.
  - Infers targets from optional action `target` metadata or existing action arguments.
  - Covers `read_file`, `write_file`, `run_command`, and `run_check`.

- `aether_next/runtime_ir.py`
  - Added optional `ActionRequest.target` metadata.

- `aether_next/kernel.py`
  - Records `automatic_memory` receipts before dispatching matching repeated actions.
  - First version is advisory/visible, not a hard veto.

- `aether_next/context_compiler.py`
  - Adds `automatic_memory_available`, `automatic_memory_guidance`, and `automatic_memory_findings`.
  - Supports `automatic_memory_findings` in context recipes.
  - Keeps active verifier findings/pending checks/automatic memory findings safety-preserved.

- `aether_next/verifier_packets.py`
  - Adds `automatic_memory_findings` to verifier packets.

- `aether_next/model_hooks.py` and `aether_next/compiler.py`
  - Replaced manual “call query_memory before repeats” solver guidance with automatic-memory target guidance.
  - Solver JSON prompt now documents optional action `target` metadata.

- `aether_next/memory_query.py`
  - Fixed an undefined variable bug in `repeat_guard`.

- `run_verifier_prompt_replay_eval.py`
  - New deterministic replay diagnostic.
  - Saves `verifier_packet.json`, `raw_output.json`, `parsed_result.json`, `active_findings_after.json`, and `judgement.json` for each variant.

- Tests updated/added:
  - `tests/test_memory_loop_fixes.py`
  - `tests/test_verifier_prompt_replay_eval.py`
  - `tests/test_vnext_configurability.py`
  - `tests/test_vnext_memory_context_verifier.py`

## Architect 10/10 Diagnostic

Previous 15-task latest-successful gate had four tasks at 9.67/10:

- `install-windows-3.11`
- `gpt2-codegolf`
- `extract-moves-from-video`
- `financial-document-processor`

Narrow rerun:

- `architect_only_eval_architect_skill_remaining4_v8_auto_memory/ARCHITECT_EVAL_REPORT.md`
- Results:
  - `install-windows-3.11`: 10/10
  - `gpt2-codegolf`: 10/10
  - `extract-moves-from-video`: 10/10
  - `financial-document-processor`: failed due provider output truncation at 32k, not a scored config failure

Single rerun for the truncated task:

- `architect_only_eval_architect_skill_financial_v9_48k/ARCHITECT_EVAL_REPORT.md`
- Result:
  - `financial-document-processor`: 10/10

Conclusion: the architect-as-skill prompt/config rubric reaches 10/10 on the remaining-gap subset. The only observed issue was output budget/verbosity on `financial-document-processor`, resolved by a 48k output cap.

## Verifier Replay Diagnostic

Command:

```bash
python3 run_verifier_prompt_replay_eval.py --out-dir verifier_prompt_replay_eval_fake_auto_memory_final
```

Artifact:

- `verifier_prompt_replay_eval_fake_auto_memory_final/VERIFIER_PROMPT_REPLAY_REPORT.md`
- `verifier_prompt_replay_eval_fake_auto_memory_final/verifier_prompt_replay_eval.json`

Result:

- `generic`: `uncertain_missing_evidence`, `finding_count=0`, `evidence_bound=false`, `specific_repair=false`
- `architect_prompt`: `needs_repair`, `finding_count=1`, `evidence_bound=true`, `specific_repair=true`
- `architect_prompt_improved_actionability=true`

Interpretation: with the same frozen evidence packet, the architect-authored verifier prompt produces more specific, evidence-bound repair feedback in this deterministic diagnostic.

## Fake Verifier Eval

Command:

```bash
python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_fake_auto_memory_arch_verifier
python3 validate_verifier_only_eval.py verifier_only_eval_fake_auto_memory_arch_verifier --report VERIFIER_ONLY_FAKE_AUTO_MEMORY_ARCH_VERIFIER_VALIDATION.md
```

Result:

- Validation `ok=true`.
- All 5 fake verifier cases parsed.
- Expected active findings were saved for repair cases.
- `insufficient_evidence` correctly produced `uncertain_missing_evidence`.

## Test Evidence

Commands:

```bash
python3 -m compileall -q aether_next run_verifier_prompt_replay_eval.py run_verifier_only_eval.py run_architect_only_eval.py
python3 -m pytest -q tests/test_memory_loop_fixes.py tests/test_verifier_prompt_replay_eval.py
python3 -m pytest -q --ignore=tests/test_docker_runner.py
```

Final results:

- focused memory/replay tests: `7 passed`
- full non-Docker suite: `213 passed`
- compileall: passed

## Review Notes

The `codex-review` skill was considered for closeout, but the parent checkout has a very large unrelated dirty/untracked surface and `codex review --uncommitted` would review unrelated work instead of this contained build tree. I performed a targeted manual closeout review over the touched kernel/context/verifier/replay files.

Accepted review fix:

- Hardened `automatic_memory_receipt()` so non-mapping `ActionRequest.target` values cannot crash repeat-justification lookup.

Remaining limitations:

- Automatic memory is advisory/visible in this slice; it does not yet hard-block repeated actions.
- Command fingerprinting is whitespace-normalized exact matching only.
- Replay diagnostic is deterministic fake replay, not a live model-verifier A/B.
- The build tree remains untracked from the parent repo perspective (`?? aether_next_build/`).

## Gate Status

This slice is green for its bounded scope:

- architect-only remaining-gap reruns reached 10/10;
- automatic memory is wired through action dispatch, context, and verifier packets;
- manual query-memory solver guidance was removed from live runtime prompts;
- verifier prompt replay diagnostic works and writes evidence artifacts;
- deterministic tests and fake verifier validation pass.
