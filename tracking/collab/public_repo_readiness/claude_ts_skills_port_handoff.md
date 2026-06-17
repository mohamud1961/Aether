# Claude TS Skills Loader/Registry Port Handoff

- Status: `COMPLETE`
- Originating orchestrator thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-15`
- Orchestrator send target: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Orchestrator send result: `SENT via codex_app.send_message_to_thread to 019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`

## Objective And Completed Scope

Completed the bounded direct TS-to-Python skills slice requested by the
orchestrator:

- ported/adapted the Claude TS filesystem skill loader, bundled-skill registry
  concept, MCP builder bridge, and visible skill-context rendering into
  canonical Python modules under `harness/aether2/skills/`;
- kept UI/Ink, marketplace, auth/provider, telemetry, and Claude-branded
  bundled content excluded;
- integrated the slice narrowly with the existing Aether context surface via
  explicit `ContextManager.extra_prefix_messages`, so selected skill text is
  visible and auditable rather than hidden prompt mutation;
- added focused tests plus the requested deterministic
  `skill_loader_contract_smoke` eval pack, board, and example scoreboard;
- updated the direct port map with exact source coverage, exclusions, and
  simplifications.

## Exact TS Source Files Read

### Ported Now

- `research/sources/codebases/quarantine/claude-code_ts_release/README.md`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/skills/index.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/commands/skills/skills.tsx`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/loadSkillsDir.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/bundledSkills.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/mcpSkillBuilders.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/hooks/registerFrontmatterHooks.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/types/command.ts`

### Inspected And Explicitly Excluded Or Deferred

- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/bundled/index.ts`
- `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/bundled/verify.ts`
- inventory listing only for:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/skills/bundled/**`
- supporting neighboring context only:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/hooks/registerSkillHooks.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/tools/AgentTool/loadAgentsDir.ts`
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/utils/settings/types.ts`
- excluded from this slice:
  - `research/sources/codebases/quarantine/claude-code_ts_release/src/components/skills/**`
  - React/Ink command rendering in `src/commands/skills/skills.tsx`
  - shipped bundled skill bodies under `src/skills/bundled/**`
  - provider/auth/telemetry/browser/remote-agent specific bundled content

## Exact Python, Eval, Test, And Doc Files Changed

- `harness/aether2/skills/loader.py`
- `harness/aether2/skills/registry.py`
- `harness/aether2/skills/invocation.py`
- `harness/aether2/skills/__init__.py`
- `harness/aether2/skills/README.md`
- `harness/aether2/__init__.py`
- `runner/aether2/skills.py`
- `runner/aether2/__init__.py`
- `tests/test_aether2_skills.py`
- `tests/test_skill_loader_contract_smoke.py`
- `eval_suite/custom/skill_loader_contract_smoke/README.md`
- `eval_suite/custom/skill_loader_contract_smoke/grader.py`
- `eval_suite/custom/skill_loader_contract_smoke/task_pack.json`
- `eval_suite/custom/skill_loader_contract_smoke/fixture/reference/skill_audit.json`
- `eval_suite/custom/skill_loader_contract_smoke/fixture/workspace/skill_audit.json`
- `eval_suite/boards/skill_loader_contract_smoke_v1.json`
- `eval_suite/scoreboards/skill_loader_contract_smoke_v1.example.scoreboard.json`
- `tracking/collab/public_repo_readiness/claude_ts_direct_port_map.md`
- `tracking/collab/public_repo_readiness/claude_ts_skills_port_handoff.md`

## Behavior Ported

- Deterministic `SKILL.md` directory loading under an explicit skills root.
- Shared frontmatter parsing for descriptions, tool allowlists, argument hints,
  user-invocable state, fork context, agent refs, path scopes, and hook
  metadata.
- Stable same-file duplicate handling using canonical resolved file paths.
- Stable same-name collision handling via explicit source precedence and
  visible registry issues.
- Explicit skill selection by provided refs only; no task-name or
  eval-name auto-selection.
- Visible, bounded `[skills_context]` model-facing block built only through an
  explicit helper and recorded in the immutable prefix.
- Write-once MCP skill-builder registry mirroring the TS leaf bridge so future
  MCP skill discovery can reuse the same loader helpers.
- Retained hook metadata and MCP-linked tool metadata without automatic
  execution or hidden prompt mutation.
- Bundled skill registration/materialization concept with safe reference-file
  extraction and path-traversal blocking.

## Simplifications And Deferred Pieces

- No managed/user/project auto-discovery walk or bare-mode/settings-policy
  integration was ported.
- No legacy `/commands/`-as-skills loader was ported.
- No shell-command execution from skill markdown, argument substitution, or
  session-ID substitution was ported.
- No automatic frontmatter-hook registration/execution was ported; metadata is
  retained only.
- No live MCP skill discovery was ported; only the write-once builder bridge
  and linked-tool metadata retention exist.
- No bundled skill content from the quarantined TS tree was ported.
- No UI menus, marketplace flows, provider auth, telemetry, analytics, or
  Claude branding were ported.

## License / Provenance Status

- The quarantined `README.md` contains an MIT placeholder claim and requires
  inclusion of the original copyright and license notice; that claim is not
  authoritative.
- The local quarantined tree still does not surface the expected root
  `LICENSE`/notice text.
- Result:
  - local port/adaptation work proceeded;
  - public publication remains blocked on recovering/verifying the exact
    upstream notice text and copyright holder.
- Existing provenance draft still applies:
  - `tracking/collab/public_repo_readiness/claude_ts_provenance_notice_draft.md`

## Validation Commands And Results

- `python3 -m py_compile harness/aether2/skills/loader.py harness/aether2/skills/registry.py harness/aether2/skills/invocation.py harness/aether2/skills/__init__.py harness/aether2/__init__.py runner/aether2/skills.py runner/aether2/__init__.py tests/test_aether2_skills.py tests/test_skill_loader_contract_smoke.py eval_suite/custom/skill_loader_contract_smoke/grader.py`
  - Result: passed
- `python3 -m pytest tests/test_aether2_skills.py tests/test_skill_loader_contract_smoke.py -q -p no:cacheprovider`
  - Result: `11 passed in 0.18s`
- `python3 -m pytest tests/test_aether2_skills.py tests/test_skill_loader_contract_smoke.py tests/test_aether2_hooks.py tests/test_aether2_mcp_registry.py tests/test_aether2_tools.py tests/test_aether2_loop.py tests/test_aether2_context.py tests/test_aether2_prompts.py tests/test_aether2_runtime_identity.py tests/test_aether2_entrypoint_import_hygiene.py tests/test_runtime_policy_hook_smoke.py tests/test_mcp_registry_contract_smoke.py tests/test_public_manifest_repair_smoke.py -q -p no:cacheprovider`
  - Result: `104 passed in 63.77s (0:01:03)`
- `python3 tools/aether2_genericity_check.py`
  - Result: passed
- `git diff --check -- harness/aether2 runner/aether2 tests eval_suite tracking/collab/public_repo_readiness`
  - Result: passed
- broad Aether baseline:
  - Not run
  - Reason: no changes to loop execution, context-building semantics, prompt text, or tool dispatch behavior beyond new explicit skill helpers/public exports; no runtime loop/tool behavior changed in this slice.

## Review Findings And Dispositions

- Codex review helper status:
  - blocked
  - exact helper run:
    - `~/.codex/skills/codex-review/scripts/codex-review`
  - exact error preserved:
    - `review command: codex review --uncommitted`
    - `WARNING: proceeding, even though we could not update PATH: Operation not permitted (os error 1)`
    - `Error loading config.toml: unknown variant 'default', expected 'fast' or 'flex' in service_tier`
- Manual adversarial review scope covered:
  - direct-port fidelity for `SKILL.md` loading/frontmatter/collision behavior;
  - explicit-only skill selection and hidden-prompt-mutation risk;
  - path traversal in bundled reference-file extraction;
  - retained-but-inactive hook metadata safety;
  - MCP-linked metadata retention without live invocation;
  - public notice/provenance gaps;
  - genericity and eval contamination boundaries.
- Manual review disposition:
  - accepted findings:
    - the first render pass only bounded skill content plus payload overhead; fixed so the final serialized `[skills_context]` block is hard-bounded and reran the focused + broad validation suite.
  - rejected / bounded-by-scope concerns:
    - no auto-discovery walk across settings scopes: intentional slice simplification, documented and not hidden
    - no frontmatter hook execution: intentional safety bound for this slice; metadata retention is explicit and tested
    - no live MCP skill discovery: intentionally deferred; only the write-once builder bridge is ported now

## Exact Next Dependency-Ready Direct-Port Slice

- Recommended next slice: `explicit subagent / AgentTool loader + handoff`
- Reason:
  - hooks/permissions, MCP, and skills surfaces now exist as reusable
    substrate;
  - the next direct TS dependency is worker/subagent loading and handoff,
    which can now consume explicit skill refs and the already-ported hook/MCP
    metadata surfaces without pulling in excluded UI/auth code.

## Persisted RAW_LEDGER_UPDATE

- Recorder output:
  - `tracking/ledger/inbox/2026-06-15/214353_direct-claude-ts-to-python-port-worker-11_port-claude-ts-skills-loader-registry-surface-into-aether-harnesseng-python-with-deterministic-smoke-eval-coverage_b9f29fd5b1.md`

## External State Confirmation

- No branch/worktree/commit/push was created.
- No eval/full task run was started.
- No VM/container lifecycle action was started.
- No credential, auth, or live network-dependent proprietary surface was
  touched.
- No background process, server, or external job remains intentionally active.
