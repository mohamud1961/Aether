# Raw Ledger Update

- recorded_at_utc: 2026-06-15T18:31:01.303418+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Public Repository Worker 6
- task: public Aether documentation and Python packaging curation
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: cdb79c616f240cfff491143c7a1f0c9e985f63efa63f9218b0daed772c9f92f4
- commit_message: Update public HarnessEng docs and package discovery
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-15/183101_public-repository-worker-6_public-aether-documentation-and-python-packaging-curation_cdb79c616f.md

```text
RAW_LEDGER_UPDATE
- actor: Public Repository Worker 6
- task: public Aether documentation and Python packaging curation
- event_type: implementation
- summary: Curated the public README/navigation surface to truthfully describe the canonical `harness.aether2` package, the `runner.aether2` compatibility boundary, and the public eval/workflow/docs layout. Added explicit setuptools package discovery for `harness*` and `runner*` so editable installs discover both namespaces.
- observations: Editable install previously failed in a foreign temp cwd because setuptools auto-discovery saw many unrelated top-level directories in the flat layout. After adding explicit package discovery, `python3 -m pip install -e /Users/mohamud/Downloads/harnesseng` succeeded in a temp venv and `import harness.aether2, runner.aether2` worked from a foreign cwd. The broad Aether compatibility pytest baseline passed (239 passed). `python3 tools/aether2_genericity_check.py` passed. `git diff --check` passed.
- inference: The public package surface is now installable-looking and honest about current implementation boundaries without changing behavior. Canonical ownership is clearly centered on `harness.aether2`, while `runner.aether2` remains compatibility-only.
- evidence_paths: /Users/mohamud/Downloads/harnesseng/README.md; /Users/mohamud/Downloads/harnesseng/pyproject.toml; /Users/mohamud/Downloads/harnesseng/docs/architecture/public-architecture.md; /Users/mohamud/Downloads/harnesseng/runner/README.md; /Users/mohamud/Downloads/harnesseng/harness/README.md; /Users/mohamud/Downloads/harnesseng/eval_suite/README.md; /Users/mohamud/Downloads/harnesseng/variants/README.md; /Users/mohamud/Downloads/harnesseng/workflows/README.md; /Users/mohamud/Downloads/harnesseng/tools/aether2_genericity_check.py
- affected_components: public README/navigation docs; public architecture map; setuptools package discovery for harness and runner namespaces; foreign-cwd editable-install import path
- decision_change: Added explicit setuptools package discovery include rules for `harness*` and `runner*`; replaced skeleton/placeholder public prose with truthful canonical/compatibility documentation; documented the broad local compatibility baseline and install smoke in the public README.
- unresolved_questions: Whether the repo should gain a dedicated automated editable-install smoke test later, or continue relying on the documented manual smoke plus existing import-identity tests.
- confidence: high
- commit_message: Update public HarnessEng docs and package discovery
```
