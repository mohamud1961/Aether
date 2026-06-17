# Codex Review Reliability Transcript

## Minimal Trace

1. Reviewed `AGENTS.md` and `codex-review` skill.
2. Confirmed the desktop `~/.codex/config.toml` was not CLI-review-safe because `service_tier = default` failed schema validation.
3. Built a fresh ephemeral `CODEX_HOME` under `/private/tmp` and copied only `auth.json` into it.
4. Wired CA roots from `certifi` via `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, and `NODE_EXTRA_CA_CERTS`.
5. Verified that `codex review --uncommitted` needs no inline prompt; prompt + `--uncommitted` is rejected by the CLI.
6. Found that `service_tier = flex` is rejected at runtime in this environment, while `service_tier = fast` lets the review proceed.
7. Ran the live-tree review successfully enough to inspect the repository and return findings.

## Final Findings

- `[P1] Translate docker job cwd into the container namespace` in [runner/aether2/jobs.py](/Users/mohamud/Downloads/harnesseng/runner/aether2/jobs.py:74)
- `[P2] Default detached jobs to the task workspace, not .aether2` in [runner/aether2/jobs.py](/Users/mohamud/Downloads/harnesseng/runner/aether2/jobs.py:62)

## Cleanup

- Ephemeral review homes under `/private/tmp` were removed.
- No checkout-local auth/session/cache artifacts were created.
