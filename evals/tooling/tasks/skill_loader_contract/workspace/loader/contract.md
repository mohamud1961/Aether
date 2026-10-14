# Skill loader contract (v2)

- Discovery walks `skills/` and reads each `SKILL.md`. Files are visited in sorted relative-path order.
- A file whose frontmatter has no closing `---` fence is skipped.
- Frontmatter values are JSON-compatible: lists and booleans are JSON, `context: null` means no context.
- Collisions: a file whose bytes match an earlier-visited skill file is rejected with `duplicate_skill_realpath`.
  A file whose `name` matches an earlier-visited skill is rejected with `skill_name_collision`.
  The first visited file wins. Rejected files are not in `skills_discovered`.
- Selection (from `loader/request.json`): a reference with no discovered skill gives `skill_not_found`.
  A reference that appears more than once gives `duplicate_skill_ref` (resolved once).
  A skill whose `paths` do not match every touched path gives `skill_path_scope_mismatch`.
- Visible context: for each resolved skill, a block of `Base directory: skills/<name>` then the body (text after the
  closing fence). Blocks are joined by a blank line. The block is recorded in the prompt prefix when
  `record_context_in_prefix` is true. It is bounded when `max_context_chars` is set. It is truncated when its length
  exceeds that bound.
- Metadata retention: every discovered skill keeps its hooks (event and matcher) and its linked MCP tools. Hook events
  not in `supported_hook_events` are reported as unsupported.
- Hidden behaviour is reported from config: prefix mutation, hook execution and MCP invocation are all `none`/`false`
  in this config, so none happen implicitly.

Comments inside `SKILL.md` files are prose for the agent, not loader rules.
