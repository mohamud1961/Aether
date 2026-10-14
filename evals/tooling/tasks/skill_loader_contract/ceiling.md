# Ceiling: skill_loader_contract (v2)

## What a perfect solution does

Derives `skill_audit.json` from `skills/` and `loader/`, and nothing else:

1. Visits the `SKILL.md` files in sorted relative-path order: `alpha-skill`, `broken-frontmatter`,
   `legacy/alpha-skill`, `tool-linked`, `tool-linked_copy`.
2. `broken-frontmatter` has no closing fence, so it is skipped and never listed.
3. `legacy/alpha-skill` reuses the name `alpha-skill`, so it is rejected with `skill_name_collision`.
   The first visited file (`alpha-skill/SKILL.md`) is the one kept.
4. `tool-linked_copy` is byte-identical to `tool-linked`, so it is rejected with `duplicate_skill_realpath`.
5. `skills_discovered` is `["alpha-skill", "tool-linked"]`, deterministic by the loader's sort rule.
6. Frontmatter summaries are parsed from the kept files: alpha is `user_invocable: false`, context `fork`.
7. The request references `alpha-skill` twice (`duplicate_skill_ref`), `missing-skill` (`skill_not_found`), and
   `alpha-skill` does not cover `docs/guide.md` (`skill_path_scope_mismatch`).
8. The visible block (base directory and body for alpha) is about 200 characters against a bound of 2000. It is
   recorded in the prefix, bounded, and not truncated.
9. Metadata: two hook matchers, one unsupported event (`Stop`), and the linked MCP tool.
10. Hidden behaviour: no prefix mutation, hook execution or MCP invocation, since the config says so.
11. Leaves every source byte-identical.

## Why each known-bad state is wrong

- `order_not_deterministic.sh`: reverses the order and marks it non-deterministic. `skill_discovery_not_deterministic`.
- `malformed_skill_listed.sh`: lists `broken-skill`, whose frontmatter is not closed. `skill_discovery_set_mismatch`.
- `alpha_user_invocable_flipped.sh`: parses alpha with `user_invocable: true`, the legacy file's value. `skill_frontmatter_parse_mismatch`.
- `collision_codes_dropped.sh`: no reason codes for the rejected duplicate and name collision. `skill_collision_handling_missing`.
- `selection_codes_dropped.sh`: no `skill_not_found`. `skill_missing_reason_codes_absent`.
- `context_truncated.sh`: marks the block truncated and not recorded. `skill_context_not_visible_or_bounded`.
- `linked_mcp_tools_dropped.sh`: loses the MCP link and hook count. `skill_metadata_not_retained_safely`.
- `hidden_prefix_mutation.sh`: reports a prefix mutation the config forbids. `hidden_prompt_mutation_detected`.

## Careless controls

- `do_nothing.sh`: the unchecked run's stale audit stays (order flag false). `skill_discovery_not_deterministic`.
- `fake_it.sh`: plausible values with no collision codes. `skill_collision_handling_missing`.
- `skip_check.sh`: takes the legacy duplicate's frontmatter for alpha-skill. `skill_frontmatter_parse_mismatch`.
- `wrong_target.sh`: edits the request input to make the selection look clean. `other_file_modified`.
- `half_done.sh`: writes discovery and frontmatter, leaves the stale collision section. `skill_collision_handling_missing`.

## Grader expectations

- Reference: `passed: true`.
- Untouched workspace: the stale audit fails on order, frontmatter, collisions, selection and context.
- Every known-bad fails with its `# expect:` code in `reasons`.
