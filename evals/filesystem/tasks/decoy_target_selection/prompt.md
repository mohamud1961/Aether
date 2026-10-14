# Raise the production timeout for the live service

Requests to the service that is live in production are being cut off at 30 seconds. Raise that
service's effective production timeout to 300 seconds. Other services must keep their current
behaviour.

The repo is in the current directory. The deploy manifest records what is currently deployed.
Service config is layered, so work out which file actually sets the effective production timeout
for the live service. Some notes and older files in the repo may be out of date.

Write `out/final_submission.json` (create `out/` if needed). It must be a JSON object with these keys:

- `patched_target`: the relative path of the one file you changed.
- `effective_timeout_s`: integer, the effective production timeout of the live service after your change.
- `verifier_command`: the exact command you ran to check the submission, which is
  `python3 checks/visible_check.py --candidate out/final_submission.json`.
- `decoy_untouched`: `true` if every other file is unchanged, otherwise `false`.

Rules:

- Change exactly one file, and only its `timeout` value. Do not modify any other existing file,
  including other services' configs, profiles, docs, logs, and `checks/`.
- After writing the submission, run `python3 checks/visible_check.py --candidate out/final_submission.json`
  from the workspace root and confirm it reports `passed`.

Public dataset identifier: harness-evals-public-8f02a7e9cf0ddb96.
