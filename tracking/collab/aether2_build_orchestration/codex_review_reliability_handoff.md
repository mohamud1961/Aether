# Codex Review Reliability Handoff

## Outcome

The review reliability problem is narrowed down and the nested review path is now proven.

The key improvement was moving Codex review into a fresh ephemeral `CODEX_HOME` under `/private/tmp` with only `auth.json` copied in, plus an explicit CA bundle and a supported model/sandbox config. That removed the earlier bootstrap failures:

- no native root CA certificates found;
- unsupported `gpt-5` review model for ChatGPT auth;
- repo-local `.tmp_codex_home` residue;
- `service_tier='default'` config parse failure;
- `sandbox-exec: sandbox_apply: Operation not permitted`;
- `fork failed: resource temporarily unavailable`.

The final run completed a real `codex review --uncommitted` against the live dirty tree and returned actionable findings instead of transport/bootstrap errors.

## Working Invocation

Use a fresh 0700 home under `/private/tmp`, copy only `auth.json`, and write this minimal config:

```toml
model = "gpt-5.4-mini"
approval_policy = "never"
sandbox_mode = "danger-full-access"
service_tier = "fast"
```

Then run:

```bash
export CODEX_HOME=/private/tmp/codex-review-home.<ephemeral>
export SSL_CERT_FILE="$(python3 - <<'PY'
import certifi
print(certifi.where())
PY
)"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
export NODE_EXTRA_CA_CERTS="$SSL_CERT_FILE"
codex review --uncommitted
```

Notes:

- `codex review --uncommitted` rejects an inline prompt, so the reusable invocation is promptless.
- `service_tier = flex` was rejected by this CLI at runtime; `fast` is the value that allowed the run to proceed.
- The outer checkout remained the live dirty tree throughout; the nested review was not pointed at a copy.

## Final Review Result

The completed review surfaced two actionable findings:

1. `[P1] Translate docker job cwd into the container namespace` in [runner/aether2/jobs.py](/Users/mohamud/Downloads/harnesseng/runner/aether2/jobs.py:74)
2. `[P2] Default detached jobs to the task workspace, not .aether2` in [runner/aether2/jobs.py](/Users/mohamud/Downloads/harnesseng/runner/aether2/jobs.py:62)

I did not modify the Aether implementation to address them, per scope. The review evidence is enough for the stabilization thread to act on.

## Cleanup / Security

- Ephemeral review homes under `/private/tmp` were removed after the run.
- No `.tmp_codex_home` was created in the repository.
- No auth/session/cache artifacts were written under the checkout.
- No credentials were printed or persisted in the repo.

## References

- Failure log reviewed: [codex_review_actual.txt](/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_build_orchestration/codex_review_actual.txt)
- Genericity gate inspected as part of proving the live-tree review surface: [tools/aether2_genericity_check.py](/Users/mohamud/Downloads/harnesseng/tools/aether2_genericity_check.py)
