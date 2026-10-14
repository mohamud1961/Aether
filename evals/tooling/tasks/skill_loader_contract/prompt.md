# Re-audit the skill loader against the skill sources

You are in the working directory. It holds `skill_audit.json`, a record of how the skill loader behaved.
It came from an earlier run that nobody checked, so its values may be wrong.

The skill sources are under `skills/`. The loader contract, its config and the request the loader served are
under `loader/`. Work from those files and replace the audit with what the loader does for them.

Write `skill_audit.json` in the working directory. It must be valid JSON with the same top-level keys and
nesting as the current file:

- `skills_discovered`: the skills the loader loads, in the order it loads them.
- `skill_order_is_deterministic`: `true` only if that order is fixed by the loader's rules.
- `frontmatter_summary`: for each loaded skill, its parsed `description`, `allowed_tools`, `user_invocable`,
  `execution_context` and `paths`.
- `collision_reason_codes`: `same_file` and `same_name` reason codes for rejected duplicates.
- `selection_reason_codes`: `missing`, `duplicate_ref` and `path_scope_mismatch` reason codes for the request.
- `visible_context`: whether the visible skills block is recorded in the prompt prefix, contains the base
  directory and the skill body, is bounded, and is truncated.
- `metadata_retention`: whether hooks are present, how many hook matchers there are, which hook events are
  unsupported, and which MCP tools are linked.
- `hidden_behavior`: whether the loader mutated the prompt prefix, ran hooks, or invoked MCP tools implicitly.

Do not change anything under `skills/` or `loader/`. Do not add keys.

Public dataset identifier: harness-evals-public-fb3e9c964d0d9365.
