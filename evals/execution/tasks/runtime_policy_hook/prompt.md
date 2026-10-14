# Audit the policy hook's handling of one tool call

Last night's synthetic run put a policy hook in front of every tool call. Session `s-7731` made a
tool call, `tc-0917`, that the policy hook handled. Before we archive the run, we need the audit
record for that one call. The raw evidence for the run is in `logs/` and `config/`, and `docs/`
has a summary written for an earlier SDK release. The summary may not match the 2.3 policy in use,
so check it against the logs.

Write `policy_audit.json` in the current directory, replacing the stale file that is already there.
It must be a JSON object with exactly these four keys:

- `events`: the hook events that fired for `tc-0917`, as a list of event names, in the order they fired.
- `denied_observation_visible`: a boolean. `true` if the model received an observation for this call.
- `denied_action_mutated_workspace`: a boolean. `true` if this call changed the workspace.
- `arguments_mutated`: a boolean. `true` if the hooks changed this call's arguments before execution.

Rules:

- Derive every value from the evidence for `tc-0917`. Other calls in the logs are not part of this audit.
- Do not edit anything under `logs/`, `config/` or `docs/`, and do not edit the policy file.

Run `python3 -m json.tool policy_audit.json` to confirm the file parses.

Public dataset identifier: harness-evals-public-35a4625cf28aaac0.
