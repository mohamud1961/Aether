# BigAI Harness Reconstruction

## Stable Doctrines
- Planner-first control is effectively universal in parseable runs.
- The observable architecture is planner, executor, verifier rather than a monolithic loop.
- Verification is an external audit role with repeated checklist families and frequent post-completion checks.
- Recovery after verifier rejection is a real recurring loop, not a rare exception.
- State-sensitive tasks often trigger backup or isolation behavior.

## Variable Behavior
- Initial plan style varies by task and likely reflects task-conditioned policy or model behavior.
- Executor fanout varies widely and appears to rise on harder or more ambiguous tasks.
- Media, batch, tty, and wait-heavy behavior is sparse and task-specific.
- Verifier absence clusters in timeout-heavy and hard systems tasks.

## Boundary
- Observable doctrine is strong enough to model the public operating contract of the harness.
- Hidden mechanism remains out of reach without scheduler, prompt-assembly, memory, branch, and workspace-state traces.

## Recommended Next Use
- Use `question_answers.json` to answer specific harness questions without rereading raw bundles.
- Use `exemplar_runs.json` to jump directly to the best supporting runs for a motif.
- Treat cluster-level task-family conclusions as moderate unless corroborated by more formal task taxonomy.

