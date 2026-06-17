# Raw Ledger Update

- recorded_at_utc: 2026-06-17T12:20:45.982138+00:00
- source: agent_session
- cwd: /Users/mohamud/Downloads/harnesseng
- actor: Antigravity
- task: fix-public-readiness-gaps-and-code-relocation
- event_type: implementation
- raw_block_type: RAW_LEDGER_UPDATE
- sha256: 0d97c6d9912a5ba7d06939ae470b149274d02ca7b4a6974a32ffd807f3b89e2d
- commit_message: "chore: relocate codebase to harness/aether2, add license/claude docs, and harden grader with challenge validation"
- handoff_file: /Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/2026-06-17/122045_antigravity_fix-public-readiness-gaps-and-code-relocation_0d97c6d991.md

```text
RAW_LEDGER_UPDATE
- actor: Antigravity
- task: fix-public-readiness-gaps-and-code-relocation
- event_type: implementation
- summary: Relocated codebase from aether/ to canonical harness/aether2/ namespace, resolved missing CI/documentation/license entry files, and hardened the MCP smoke grader.
- observations: Obsolete aether/ folder caused navigation path mismatches and required complex import hacks. Lack of root LICENSE, CLAUDE.md, and skills README was highlighted as a legal/trust risk. The MCP smoke grader was gameable by copying static reference files.
- inference: Standard imports and package finding work out of the box when code lives directly under harness/aether2/. Adding standard open-source files restores legal and developer trust. A dynamic challenge verification prevents candidates from passing by simply copying static JSON answers.
- evidence_paths: harness/aether2/, pyproject.toml, LICENSE, CLAUDE.md, .github/workflows/ci.yml, eval_suite/families/tooling/mcp_registry_contract_smoke/, tests/test_mcp_registry_contract_smoke.py
- affected_components: packaging, documentation, CI, grader, test suite
- decision_change: Relocate codebase to canonical namespace; replace static grader checks with dynamic challenge-token verification.
- unresolved_questions: None
- confidence: high
- commit_message: "chore: relocate codebase to harness/aether2, add license/claude docs, and harden grader with challenge validation"
```
