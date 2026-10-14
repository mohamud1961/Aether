# Task card: skill loader contract audit (v2)

Admission: **capability**. Controls test the v2 design. They do not establish parity with the original trace contract.

## Design (v2)

- Skill sources are in the workspace: frontmatter, a name collision (`legacy/alpha-skill`), a content duplicate (`tool-linked_copy`), and a malformed file (`broken-frontmatter`).
- Loader contract and config are in `loader/`; the request is `loader/request.json`.
- The audit is derived. The stale `skill_audit.json` is an unchecked earlier run.
- No `$TASK_ROOT` in the reference.
- Source files are sealed by hash.

## Controls

- Known-bad: 8 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| skill_discovery_not_deterministic | known_bad order_not_deterministic; careless do_nothing |
| skill_discovery_set_mismatch | known_bad malformed_skill_listed |
| skill_frontmatter_parse_mismatch | known_bad alpha_user_invocable_flipped; careless skip_check |
| skill_collision_handling_missing | known_bad collision_codes_dropped; careless fake_it, half_done |
| skill_missing_reason_codes_absent | known_bad selection_codes_dropped |
| skill_context_not_visible_or_bounded | known_bad context_truncated |
| skill_metadata_not_retained_safely | known_bad linked_mcp_tools_dropped |
| hidden_prompt_mutation_detected | known_bad hidden_prefix_mutation |
| other_file_modified | careless wrong_target |
